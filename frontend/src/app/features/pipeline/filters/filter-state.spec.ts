import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap } from '@angular/router';
import { BehaviorSubject } from 'rxjs';
import { NO_FILTERS } from './pipeline-filters';
import { SEARCH_DELAY_MS, createFilterState } from './filter-state';

function setup(initial: Record<string, string> = {}) {
  const params = new BehaviorSubject(convertToParamMap(initial));
  const navigate = jest.fn(() => Promise.resolve(true));
  TestBed.configureTestingModule({
    providers: [
      { provide: Router, useValue: { navigate } },
      {
        provide: ActivatedRoute,
        useValue: { snapshot: { queryParamMap: params.value }, queryParamMap: params },
      },
    ],
  });
  const state = TestBed.runInInjectionContext(() => createFilterState());
  return { state, navigate, params };
}

describe('createFilterState', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  it('starts with the filters of the URL', () => {
    const { state } = setup({ org: 'fsi', meine: '1' });
    expect(state.filters()).toMatchObject({ organization: 'fsi', mine: true });
    expect(state.applied()).toEqual(state.filters());
  });

  it('applies a chip at once and writes it into the URL without a new history entry', () => {
    const { state, navigate } = setup();
    state.set({ ...NO_FILTERS, category: 'film' });
    expect(state.applied().category).toBe('film');
    expect(navigate).toHaveBeenCalledWith(
      [],
      expect.objectContaining({
        replaceUrl: true,
        queryParams: expect.objectContaining({ kategorie: 'film' }),
      }),
    );
  });

  it('waits for the typing to rest before it applies the search', () => {
    const { state, navigate } = setup();
    state.set({ ...NO_FILTERS, q: 'k' });
    state.set({ ...NO_FILTERS, q: 'ki' });
    expect(state.filters().q).toBe('ki');
    expect(state.applied().q).toBe('');
    jest.advanceTimersByTime(SEARCH_DELAY_MS);
    expect(state.applied().q).toBe('ki');
    expect(navigate).toHaveBeenCalledTimes(1);
  });

  it('follows the URL when the person goes back', () => {
    const { state, params } = setup({ org: 'fsi' });
    params.next(convertToParamMap({ org: 'asta' }));
    expect(state.filters().organization).toBe('asta');
    expect(state.applied().organization).toBe('asta');
    params.next(convertToParamMap({ org: 'asta' }));
    expect(state.applied().organization).toBe('asta');
  });

  it('does not react to the echo of its own navigation', () => {
    const { state, params } = setup();
    state.set({ ...NO_FILTERS, mine: true });
    params.next(convertToParamMap({ meine: '1' }));
    expect(state.filters().mine).toBe(true);
  });
});
