/**
 * A cursor-paged list for the public pages (search, category, review): the first page is a resource of the params, "Mehr
 * anzeigen" appends the next page. While new params load, the old rows stay (no flicker per keystroke); an answer that
 * arrives after the params changed again is dropped.
 */
import { DestroyRef, type Signal, computed, inject, linkedSignal, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { resourceValue } from '@core/api/resource-value';
import type { Observable } from 'rxjs';
import { type PublicErrorKind, publicErrorOf } from '../api/public-error';

export interface Page<T> {
  items: T[];
  nextCursor: string | null;
}

export interface PagedList<T, R extends Page<T>> {
  /** The first page; `facets`, `total` or `years` of a richer answer are read from here. */
  readonly first: Signal<R | undefined>;
  readonly items: Signal<T[]>;
  readonly hasMore: Signal<boolean>;
  readonly loading: Signal<boolean>;
  readonly loadingMore: Signal<boolean>;
  readonly error: Signal<PublicErrorKind | null>;
  readonly moreError: Signal<PublicErrorKind | null>;
  loadMore(): void;
  reload(): void;
}

export function pagedList<P, T, R extends Page<T>>(options: {
  params: () => P | undefined;
  fetch: (params: P, cursor: string | null) => Observable<R>;
}): PagedList<T, R> {
  const destroyed = inject(DestroyRef);
  const resource = rxResource<R, P | undefined>({
    params: options.params,
    stream: ({ params }) => options.fetch(params as P, null),
  });
  const value = computed(() => resourceValue(resource, undefined));
  const items = linkedSignal<R | undefined, T[]>({
    source: value,
    computation: (page, previous) => (page ? [...page.items] : (previous?.value ?? [])),
  });
  const cursor = linkedSignal(() => value()?.nextCursor ?? null);
  const loadingMore = signal(false);
  const moreError = signal<PublicErrorKind | null>(null);
  let alive = true;
  destroyed.onDestroy(() => (alive = false));

  const loadMore = (): void => {
    const params = options.params();
    const next = cursor();
    const page = value();
    if (params === undefined || next === null || loadingMore()) return;
    loadingMore.set(true);
    moreError.set(null);
    options.fetch(params, next).subscribe({
      next: (more) => {
        if (!alive || value() !== page) return;
        items.update((list) => [...list, ...more.items]);
        cursor.set(more.nextCursor);
        loadingMore.set(false);
      },
      error: (err: unknown) => {
        if (!alive) return;
        moreError.set(publicErrorOf(err));
        loadingMore.set(false);
      },
    });
  };

  return {
    first: value,
    items,
    hasMore: computed(() => cursor() !== null),
    loading: resource.isLoading,
    loadingMore,
    error: computed(() => (resource.error() ? publicErrorOf(resource.error()) : null)),
    moreError,
    loadMore,
    reload: () => void resource.reload(),
  };
}
