/**
 * State of the filter row of one page: the value as typed, the value applied to the data (the search text
 * waits 250 ms), and the URL as the third copy so a reload and "back" keep the filters.
 */
import { DestroyRef, type Signal, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import {
  NO_FILTERS,
  type PipelineFilters,
  filtersFromParams,
  filtersToParams,
} from './pipeline-filters';

export const SEARCH_DELAY_MS = 250;

export interface FilterState {
  /** The value shown in the filter row. */
  filters: Signal<PipelineFilters>;
  /** The value the data loads with. */
  applied: Signal<PipelineFilters>;
  set(next: PipelineFilters): void;
}

/** Creates the filter state in an injection context; the URL is read once and then followed. */
export function createFilterState(): FilterState {
  const route = inject(ActivatedRoute);
  const router = inject(Router);
  const initial = filtersFromParams(route.snapshot.queryParamMap);
  const filters = signal<PipelineFilters>(initial);
  const applied = signal<PipelineFilters>(initial);
  let timer: ReturnType<typeof setTimeout> | undefined;

  const apply = (next: PipelineFilters): void => {
    applied.set(next);
    void router.navigate([], {
      relativeTo: route,
      queryParams: filtersToParams(next),
      replaceUrl: true,
    });
  };

  const sub = route.queryParamMap.subscribe((params) => {
    const fromUrl = filtersFromParams(params);
    if (JSON.stringify(filtersToParams(fromUrl)) === JSON.stringify(filtersToParams(applied())))
      return;
    clearTimeout(timer);
    filters.set(fromUrl);
    applied.set(fromUrl);
  });
  inject(DestroyRef).onDestroy(() => {
    clearTimeout(timer);
    sub.unsubscribe();
  });

  return {
    filters: filters.asReadonly(),
    applied: applied.asReadonly(),
    set(next) {
      const typing = next.q !== filters().q;
      filters.set(next);
      clearTimeout(timer);
      if (typing) timer = setTimeout(() => apply(next), SEARCH_DELAY_MS);
      else apply(next);
    },
  };
}

export { NO_FILTERS };
