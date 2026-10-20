import { DestroyRef } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { of, throwError } from 'rxjs';
import type { DocumentsApi } from '../api/documents-api.service';
import { DRAFT_INTERVAL_MS, DocumentDraft } from './document-draft';
import { readLocalCopy } from './local-copy';

function setup(putDraft = jest.fn(() => of({ bodyMd: '', baseRev: 1, updatedAt: '' }))) {
  const api = { putDraft, deleteDraft: jest.fn(() => of(undefined)) } as unknown as DocumentsApi;
  let destroy: () => void = () => undefined;
  const ref = { onDestroy: (fn: () => void) => (destroy = fn) } as unknown as DestroyRef;
  const draft = TestBed.runInInjectionContext(
    () =>
      new DocumentDraft(
        api,
        () => ({ documentId: 'd1', baseRev: 1 }),
        () => 'k',
        ref,
      ),
  );
  return { draft, api, putDraft, destroy: () => destroy() };
}

const fail = (status: number) =>
  jest.fn(() => throwError(() => new HttpErrorResponse({ status, error: { status } })));

describe('DocumentDraft', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => {
    jest.useRealTimers();
    localStorage.clear();
  });

  it('sends the changed text every 15 seconds and keeps a local copy', () => {
    const { draft, putDraft } = setup();
    draft.change('hello');
    expect(draft.status()).toBe('dirty');
    expect(readLocalCopy('k')).toBe('hello');
    jest.advanceTimersByTime(DRAFT_INTERVAL_MS);
    expect(putDraft).toHaveBeenCalledWith('d1', 1, 'hello');
    expect(draft.status()).toBe('saved');
    jest.advanceTimersByTime(DRAFT_INTERVAL_MS);
    expect(putDraft).toHaveBeenCalledTimes(1);
  });

  it('stays dirty after a network error and tries again', () => {
    const { draft, putDraft } = setup(fail(0));
    draft.change('x');
    draft.flush();
    expect(draft.status()).toBe('dirty');
    expect(draft.pending).toBe(true);
    putDraft.mockReturnValue(of({ bodyMd: '', baseRev: 1, updatedAt: '' }) as never);
    draft.flush();
    expect(draft.status()).toBe('saved');
  });

  it('stops after a 4xx answer until the text changes again', () => {
    const { draft, putDraft } = setup(fail(422));
    draft.change('x');
    draft.flush();
    expect(draft.status()).toBe('failed');
    draft.flush();
    expect(putDraft).toHaveBeenCalledTimes(1);
    draft.change('y');
    draft.flush();
    expect(putDraft).toHaveBeenCalledTimes(2);
  });

  it('retries after a 5xx and does nothing without a change or a target', () => {
    const { draft, putDraft } = setup(fail(503));
    draft.flush();
    expect(putDraft).not.toHaveBeenCalled();
    draft.change('x');
    draft.flush();
    expect(draft.status()).toBe('dirty');
  });

  it('keeps a newer edit that arrives while the request is out', () => {
    const { draft } = setup(
      jest.fn(() => {
        draft.change('newer');
        return of({ bodyMd: '', baseRev: 1, updatedAt: '' });
      }),
    );
    draft.change('old');
    draft.flush();
    expect(draft.status()).toBe('dirty');
    expect(draft.pending).toBe(true);
  });

  it('discards the server draft and the local copy', () => {
    const { draft, api } = setup();
    draft.change('x');
    draft.discard();
    expect(api.deleteDraft).toHaveBeenCalledWith('d1');
    expect(readLocalCopy('k')).toBeNull();
    expect(draft.status()).toBe('idle');
    draft.change('y');
    draft.settle();
    expect(draft.pending).toBe(false);
  });

  it('stops its timer when the owner is destroyed', () => {
    const { draft, putDraft, destroy } = setup();
    draft.change('x');
    destroy();
    jest.advanceTimersByTime(DRAFT_INTERVAL_MS * 2);
    expect(putDraft).not.toHaveBeenCalled();
  });
});
