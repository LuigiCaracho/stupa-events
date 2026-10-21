import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { BehaviorSubject } from 'rxjs';
import { type UrlStateCodec, createUrlState } from './url-state';

interface Filters {
  q: string;
  kind: string;
}

const codec: UrlStateCodec<Filters> = {
  parse: (p) => ({ q: p.get('q') ?? '', kind: p.get('kind') ?? '' }),
  serialize: (f) => ({ q: f.q || null, kind: f.kind || null }),
  typing: (a, b) => a.q !== b.q,
};

@Component({ standalone: true, template: '' })
class Host {
  readonly state = createUrlState(codec);
}

function setup(query: Record<string, string> = {}) {
  const params = new BehaviorSubject(convertToParamMap(query));
  TestBed.configureTestingModule({
    providers: [
      provideRouter([]),
      { provide: ActivatedRoute, useValue: { snapshot: { queryParamMap: params.value }, queryParamMap: params } },
    ],
  });
  const navigate = jest.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
  const host = TestBed.createComponent(Host).componentInstance;
  return { host, params, navigate };
}

describe('createUrlState', () => {
  afterEach(() => jest.useRealTimers());

  it('starts from the URL', () => {
    const { host } = setup({ q: 'kino' });
    expect(host.state.value()).toEqual({ q: 'kino', kind: '' });
    expect(host.state.applied()).toEqual({ q: 'kino', kind: '' });
  });

  it('applies a change of another filter at once and writes it to the URL', () => {
    const { host, navigate } = setup();
    host.state.set({ q: '', kind: 'document' });
    expect(host.state.applied().kind).toBe('document');
    expect(navigate).toHaveBeenCalledWith([], expect.objectContaining({ queryParams: { q: null, kind: 'document' }, replaceUrl: true }));
  });

  it('waits 250 ms after typing and applies only the last text', () => {
    jest.useFakeTimers();
    const { host, navigate } = setup();
    host.state.set({ q: 'k', kind: '' });
    host.state.set({ q: 'ki', kind: '' });
    expect(host.state.value().q).toBe('ki');
    expect(host.state.applied().q).toBe('');
    jest.advanceTimersByTime(250);
    expect(host.state.applied().q).toBe('ki');
    expect(navigate).toHaveBeenCalledTimes(1);
  });

  it('follows a change of the URL (back button) and ignores the echo of its own change', () => {
    const { host, params, navigate } = setup();
    host.state.set({ q: '', kind: 'document' });
    navigate.mockClear();
    params.next(convertToParamMap({ kind: 'document' }));
    expect(navigate).not.toHaveBeenCalled();
    params.next(convertToParamMap({ q: 'zurück' }));
    expect(host.state.value()).toEqual({ q: 'zurück', kind: '' });
    expect(host.state.applied()).toEqual({ q: 'zurück', kind: '' });
  });
});
