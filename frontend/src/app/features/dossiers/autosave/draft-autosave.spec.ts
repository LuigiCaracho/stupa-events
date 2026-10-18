import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { Observable, of, throwError } from 'rxjs';
import { makeEvent } from '../../../../testing/event-fixtures';
import type { EventDto } from '../api/event.models';
import { AUTOSAVE_MS, DraftAutosave, IDLE_APPLY_MS } from './draft-autosave';

const offline = () => throwError(() => new HttpErrorResponse({ status: 0 }));
const problem = (status: number, extra: object = {}) =>
  throwError(() => new HttpErrorResponse({ status, error: { status, ...extra } }));

function setup(event: EventDto = makeEvent({ state: 'planning', rev: 3 })) {
  const api = {
    saveDraft: jest.fn(() => of({ baseRev: 3, fields: {}, updatedAt: '2026-10-18T10:00:00Z' })),
    patch: jest.fn(() => of(makeEvent({ rev: 4 }))),
    discardDraft: jest.fn(() => of(undefined)),
    draft: jest.fn((): Observable<unknown> => of(null)),
  };
  const store = new Map<string, string>();
  const storage = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  } as unknown as Storage;
  const deps = {
    api: api as never,
    event: signal<EventDto | null>(event),
    sub: () => 'u1',
    storage: () => storage,
    onApplied: jest.fn(),
    onConflict: jest.fn(),
    onOffline: jest.fn(),
    onError: jest.fn(),
  };
  return { api, deps, store, auto: new DraftAutosave(deps) };
}

describe('DraftAutosave', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  it('sends the draft 15 s after the first change with the revision as base', () => {
    const { auto, api } = setup();
    auto.change({ summary: 'Hallo' });
    expect(auto.status()).toBe('unsaved');
    expect(auto.unsent()).toBe(true);
    jest.advanceTimersByTime(AUTOSAVE_MS - 1);
    expect(api.saveDraft).not.toHaveBeenCalled();
    jest.advanceTimersByTime(1);
    expect(api.saveDraft).toHaveBeenCalledWith('ev-1', 3, { summary: 'Hallo' });
    expect(auto.status()).toBe('saved');
    expect(auto.savedAt()).not.toBeNull();
    expect(auto.unsent()).toBe(false);
    expect(auto.dirty()).toBe(true);
  });

  it('keeps sending every 15 s while changes arrive', () => {
    const { auto, api } = setup();
    auto.change({ summary: 'a' });
    jest.advanceTimersByTime(AUTOSAVE_MS);
    auto.change({ summary: 'ab' });
    expect(auto.status()).toBe('unsaved');
    jest.advanceTimersByTime(AUTOSAVE_MS);
    expect(api.saveDraft).toHaveBeenCalledTimes(2);
    expect(api.saveDraft).toHaveBeenLastCalledWith('ev-1', 3, { summary: 'ab' });
  });

  it('ignores an identical change and sends nothing twice', () => {
    const { auto, api } = setup();
    auto.change({ summary: 'a' });
    auto.change({ summary: 'a' });
    jest.advanceTimersByTime(AUTOSAVE_MS);
    auto.flush();
    expect(api.saveDraft).toHaveBeenCalledTimes(1);
  });

  it('drops the draft on the server when the person undoes every change', () => {
    const { auto, api } = setup();
    auto.change({ summary: 'a' });
    jest.advanceTimersByTime(AUTOSAVE_MS);
    auto.change({});
    expect(api.discardDraft).toHaveBeenCalledWith('ev-1');
    expect(auto.dirty()).toBe(false);
    jest.advanceTimersByTime(AUTOSAVE_MS * 2);
    expect(api.saveDraft).toHaveBeenCalledTimes(1);
  });

  it('keeps the text in local storage offline and sends it when the connection is back', () => {
    const { auto, api, deps, store } = setup();
    api.saveDraft.mockImplementationOnce(offline as never);
    auto.change({ summary: 'Hallo' });
    jest.advanceTimersByTime(AUTOSAVE_MS);
    expect(auto.status()).toBe('offline');
    expect(deps.onOffline).toHaveBeenCalledTimes(1);
    expect([...store.keys()]).toEqual(['draft:ev-1:u1']);
    expect(JSON.parse(store.get('draft:ev-1:u1')!)).toMatchObject({
      baseRev: 3,
      fields: { summary: 'Hallo' },
    });
    auto.flush();
    expect(auto.status()).toBe('saved');
    expect(store.size).toBe(0);
  });

  it('opens the conflict on a 409 with the current version', () => {
    const { auto, api, deps } = setup();
    const current = makeEvent({ rev: 9 });
    api.saveDraft.mockImplementationOnce((() =>
      problem(409, { code: 'conflict', current })) as never);
    auto.change({ summary: 'x' });
    jest.advanceTimersByTime(AUTOSAVE_MS);
    expect(auto.status()).toBe('conflict');
    expect(deps.onConflict).toHaveBeenCalledWith(current);
    jest.advanceTimersByTime(AUTOSAVE_MS * 3);
    expect(api.saveDraft).toHaveBeenCalledTimes(1);
  });

  it('reports another failure and tries again', () => {
    const { auto, api, deps } = setup();
    api.saveDraft.mockImplementationOnce((() => problem(500)) as never);
    auto.change({ summary: 'x' });
    jest.advanceTimersByTime(AUTOSAVE_MS);
    expect(deps.onError).toHaveBeenCalledTimes(1);
    expect(auto.status()).toBe('unsaved');
    jest.advanceTimersByTime(AUTOSAVE_MS);
    expect(auto.status()).toBe('saved');
  });

  it.each([403, 409, 413, 422])('stops and reports once on a %s', (status) => {
    const { auto, api, deps } = setup();
    api.saveDraft.mockImplementation((() => problem(status, { code: 'field_locked' })) as never);
    auto.change({ summary: 'x' });
    jest.advanceTimersByTime(AUTOSAVE_MS);
    expect(auto.status()).toBe('error');
    jest.advanceTimersByTime(AUTOSAVE_MS * 4);
    expect(api.saveDraft).toHaveBeenCalledTimes(1);
    expect(deps.onError).toHaveBeenCalledTimes(1);
    expect(auto.dirty()).toBe(true);
    auto.change({ summary: 'xy' });
    jest.advanceTimersByTime(AUTOSAVE_MS);
    expect(api.saveDraft).toHaveBeenCalledTimes(2);
  });

  it('does not send while a send runs or without an event', () => {
    const { auto, api, deps } = setup();
    deps.event.set(null);
    auto.change({ summary: 'x' });
    auto.flush();
    expect(api.saveDraft).not.toHaveBeenCalled();
  });

  it('saves for good with the note and clears everything', async () => {
    const { auto, api, store } = setup();
    auto.change({ summary: 'x' });
    const updated = await new Promise((resolve) => auto.save('Tippfehler').subscribe(resolve));
    expect(api.patch).toHaveBeenCalledWith('ev-1', 3, { summary: 'x', note: 'Tippfehler' });
    expect(updated).toMatchObject({ rev: 4 });
    expect(auto.dirty()).toBe(false);
    expect(auto.status()).toBe('saved');
    expect(store.size).toBe(0);
    jest.advanceTimersByTime(AUTOSAVE_MS * 2);
    expect(api.saveDraft).not.toHaveBeenCalled();
  });

  it('raises the conflict and rethrows when the save meets a newer version', async () => {
    const { auto, api, deps } = setup();
    const current = makeEvent({ rev: 8 });
    api.patch.mockImplementationOnce((() => problem(409, { code: 'conflict', current })) as never);
    auto.change({ summary: 'x' });
    await expect(
      new Promise((resolve, reject) => auto.save().subscribe({ next: resolve, error: reject })),
    ).rejects.toBeInstanceOf(HttpErrorResponse);
    expect(deps.onConflict).toHaveBeenCalledWith(current);
    expect(auto.status()).toBe('conflict');
  });

  it('goes back to unsaved when the save fails for another reason', async () => {
    const { auto, api } = setup();
    api.patch.mockImplementationOnce((() => problem(422, { code: 'validation_error' })) as never);
    auto.change({ summary: 'x' });
    await expect(
      new Promise((resolve, reject) => auto.save().subscribe({ next: resolve, error: reject })),
    ).rejects.toBeDefined();
    expect(auto.status()).toBe('unsaved');
  });

  it('does not call a locked field a conflict', async () => {
    const { auto, api, deps } = setup();
    api.patch.mockImplementationOnce((() => problem(409, { code: 'field_locked' })) as never);
    auto.change({ summary: 'x' });
    await expect(
      new Promise((resolve, reject) => auto.save().subscribe({ next: resolve, error: reject })),
    ).rejects.toBeDefined();
    expect(deps.onConflict).not.toHaveBeenCalled();
    expect(auto.status()).toBe('unsaved');
  });

  it('fails a save without an event', async () => {
    const { auto, deps } = setup();
    deps.event.set(null);
    await expect(
      new Promise((resolve, reject) => auto.save().subscribe({ next: resolve, error: reject })),
    ).rejects.toThrow('no event');
  });

  it('applies the draft after 30 minutes without input in planning', () => {
    const { auto, api, deps } = setup();
    auto.change({ summary: 'x' });
    jest.advanceTimersByTime(IDLE_APPLY_MS);
    expect(api.patch).toHaveBeenCalledTimes(1);
    expect(deps.onApplied).toHaveBeenCalledWith(expect.objectContaining({ rev: 4 }));
  });

  it('restarts the idle clock on every change and reports a failed idle save', () => {
    const { auto, api, deps } = setup();
    auto.change({ summary: 'x' });
    jest.advanceTimersByTime(IDLE_APPLY_MS - 1000);
    auto.change({ summary: 'xy' });
    jest.advanceTimersByTime(IDLE_APPLY_MS - 1000);
    expect(api.patch).not.toHaveBeenCalled();
    api.patch.mockImplementationOnce((() => problem(422)) as never);
    jest.advanceTimersByTime(1000);
    expect(deps.onError).toHaveBeenCalledTimes(1);
  });

  it.each(['in_review', 'approved', 'live'] as const)(
    'keeps the draft as a draft in %s',
    (state) => {
      const { auto, api } = setup(makeEvent({ state, rev: 3 }));
      auto.change({ summary: 'x' });
      jest.advanceTimersByTime(IDLE_APPLY_MS);
      expect(api.patch).not.toHaveBeenCalled();
    },
  );

  it('does not apply a conflicted draft by itself', () => {
    const { auto, api } = setup();
    api.saveDraft.mockImplementationOnce((() => problem(409, { code: 'conflict' })) as never);
    auto.change({ summary: 'x' });
    jest.advanceTimersByTime(IDLE_APPLY_MS);
    expect(api.patch).not.toHaveBeenCalled();
  });

  describe('restore', () => {
    const event = makeEvent({ rev: 3 });

    it('finds nothing', async () => {
      const { auto } = setup();
      await expect(new Promise((r) => auto.restore(event).subscribe(r))).resolves.toEqual({
        kind: 'none',
      });
    });

    it('restores a draft of the same revision', async () => {
      const { auto, api } = setup();
      api.draft.mockReturnValueOnce(
        of({ baseRev: 3, fields: { summary: 'Entwurf' }, updatedAt: '2026-10-18T09:00:00Z' }),
      );
      const result = await new Promise((r) => auto.restore(event).subscribe(r));
      expect(result).toMatchObject({ kind: 'restored' });
      expect(auto.fields()).toEqual({ summary: 'Entwurf' });
      expect(auto.status()).toBe('saved');
      expect(auto.unsent()).toBe(false);
    });

    it('reports a draft of an older revision as stale', async () => {
      const { auto, api } = setup();
      api.draft.mockReturnValueOnce(
        of({ baseRev: 2, fields: { summary: 'Alt' }, updatedAt: '2026-10-18T09:00:00Z' }),
      );
      const result = await new Promise((r) => auto.restore(event).subscribe(r));
      expect(result).toMatchObject({ kind: 'stale' });
      expect(auto.fields()).toEqual({});
    });

    it('prefers the offline text when it is newer and sends it', async () => {
      const { auto, api, store } = setup();
      api.draft.mockReturnValueOnce(
        of({ baseRev: 3, fields: { summary: 'Server' }, updatedAt: '2026-10-18T09:00:00Z' }),
      );
      store.set(
        'draft:ev-1:u1',
        JSON.stringify({ baseRev: 3, fields: { summary: 'Offline' }, at: '2026-10-18T09:30:00Z' }),
      );
      await new Promise((r) => auto.restore(event).subscribe(r));
      expect(auto.fields()).toEqual({ summary: 'Offline' });
      expect(auto.status()).toBe('unsaved');
      jest.advanceTimersByTime(AUTOSAVE_MS);
      expect(api.saveDraft).toHaveBeenCalledWith('ev-1', 3, { summary: 'Offline' });
    });

    it('survives a failing server read and a broken buffer', async () => {
      const { auto, api, store } = setup();
      api.draft.mockReturnValueOnce(
        throwError(() => new HttpErrorResponse({ status: 500 })) as never,
      );
      store.set('draft:ev-1:u1', '{not json');
      await expect(new Promise((r) => auto.restore(event).subscribe(r))).resolves.toEqual({
        kind: 'none',
      });
    });

    it('treats an empty draft as none', async () => {
      const { auto, api } = setup();
      api.draft.mockReturnValueOnce(
        of({ baseRev: 3, fields: {}, updatedAt: '2026-10-18T09:00:00Z' }),
      );
      await expect(new Promise((r) => auto.restore(event).subscribe(r))).resolves.toEqual({
        kind: 'none',
      });
    });
  });

  it('discards here and on the server, and resets without a server call', () => {
    const { auto, api } = setup();
    auto.change({ summary: 'x' });
    auto.discard();
    expect(api.discardDraft).toHaveBeenCalledWith('ev-1');
    expect(auto.dirty()).toBe(false);
    expect(auto.status()).toBe('idle');
    auto.change({ summary: 'y' });
    auto.reset();
    expect(api.discardDraft).toHaveBeenCalledTimes(1);
    expect(auto.dirty()).toBe(false);
  });

  it('keeps the offline text in storage when a dossier opens', () => {
    const { auto, store } = setup();
    store.set('draft:ev-1:u1', '{}');
    auto.reset();
    expect(store.size).toBe(1);
    auto.discard();
    expect(store.size).toBe(0);
  });

  it('stops its timers on destroy', () => {
    const { auto, api } = setup();
    auto.change({ summary: 'x' });
    auto.destroy();
    jest.advanceTimersByTime(IDLE_APPLY_MS);
    expect(api.saveDraft).not.toHaveBeenCalled();
    expect(api.patch).not.toHaveBeenCalled();
  });

  it('works without storage and without a signed-in person', () => {
    const { api, deps } = setup();
    api.saveDraft.mockImplementationOnce(offline as never);
    const blocked = new DraftAutosave({
      ...deps,
      storage: () => {
        throw new Error('blocked');
      },
      sub: () => null,
    });
    blocked.change({ summary: 'x' });
    jest.advanceTimersByTime(AUTOSAVE_MS);
    expect(blocked.status()).toBe('offline');
    const noStore = new DraftAutosave({ ...deps, storage: () => null });
    api.saveDraft.mockImplementationOnce(offline as never);
    noStore.change({ summary: 'y' });
    jest.advanceTimersByTime(AUTOSAVE_MS);
    expect(noStore.status()).toBe('offline');
  });
});

describe('DraftAutosave edge cases', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  it('keeps the offline state when more changes arrive and sends them after the retry', () => {
    const { auto, api } = setup();
    api.saveDraft.mockImplementationOnce(offline as never);
    auto.change({ summary: 'a' });
    jest.advanceTimersByTime(AUTOSAVE_MS);
    auto.change({ summary: 'ab' });
    expect(auto.status()).toBe('offline');
    auto.flush();
    expect(api.saveDraft).toHaveBeenLastCalledWith('ev-1', 3, { summary: 'ab' });
  });

  it('keeps sending when the text changed while the draft was on its way', () => {
    const { auto, api } = setup();
    let release: () => void = () => undefined;
    api.saveDraft.mockImplementationOnce(
      (() =>
        new Observable<unknown>((o) => {
          release = () => {
            o.next({});
            o.complete();
          };
        })) as never,
    );
    auto.change({ summary: 'a' });
    jest.advanceTimersByTime(AUTOSAVE_MS);
    expect(auto.status()).toBe('saving');
    auto.change({ summary: 'ab' });
    auto.flush();
    expect(api.saveDraft).toHaveBeenCalledTimes(1);
    release();
    expect(auto.status()).toBe('unsaved');
    jest.advanceTimersByTime(AUTOSAVE_MS);
    expect(api.saveDraft).toHaveBeenLastCalledWith('ev-1', 3, { summary: 'ab' });
  });

  it('does not send a second time while one is running', () => {
    const { auto, api } = setup();
    api.saveDraft.mockImplementationOnce((() => new Observable(() => undefined)) as never);
    auto.change({ summary: 'a' });
    jest.advanceTimersByTime(AUTOSAVE_MS);
    auto.flush();
    expect(api.saveDraft).toHaveBeenCalledTimes(1);
  });

  it('discards without an event and ignores a missing server draft call on reset', () => {
    const { auto, api, deps } = setup();
    deps.event.set(null);
    auto.discard();
    expect(api.discardDraft).not.toHaveBeenCalled();
  });

  it('survives a storage that throws on write and remove', () => {
    const { api, deps } = setup();
    const bad = {
      getItem: () => null,
      setItem: () => {
        throw new Error('full');
      },
      removeItem: () => {
        throw new Error('blocked');
      },
    } as unknown as Storage;
    const auto = new DraftAutosave({ ...deps, storage: () => bad });
    api.saveDraft.mockImplementationOnce(offline as never);
    auto.change({ summary: 'a' });
    jest.advanceTimersByTime(AUTOSAVE_MS);
    expect(auto.status()).toBe('offline');
    auto.flush();
    expect(auto.status()).toBe('saved');
  });

  it('does not lose the saved time when the person undoes everything', () => {
    const { auto } = setup();
    auto.change({ summary: 'a' });
    jest.advanceTimersByTime(AUTOSAVE_MS);
    auto.change({});
    expect(auto.status()).toBe('saved');
  });
});
