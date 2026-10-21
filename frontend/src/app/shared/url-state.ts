/**
 * State of a filter row that lives in the URL: the value as shown, the value applied to the data (typing in the search
 * text waits 250 ms), and the query string as the third copy so a reload and "back" keep the filters. The generic
 * sibling of `features/pipeline/filters/filter-state.ts`, for pages with their own filter shape.
 */
import { DestroyRef, type Signal, inject, signal } from '@angular/core';
import { ActivatedRoute, type ParamMap, type Params, Router } from '@angular/router';

export const TYPING_DELAY_MS = 250;

export interface UrlState<T> {
  value: Signal<T>;
  applied: Signal<T>;
  set(next: T): void;
}

export interface UrlStateCodec<T> {
  parse(params: ParamMap): T;
  serialize(value: T): Params;
  /** True when the change comes from typing, so the data waits for a pause. */
  typing(prev: T, next: T): boolean;
}

/** Creates the state in an injection context; the URL is read once and then followed. */
export function createUrlState<T>(codec: UrlStateCodec<T>): UrlState<T> {
  const route = inject(ActivatedRoute);
  const router = inject(Router);
  const initial = codec.parse(route.snapshot.queryParamMap);
  const value = signal<T>(initial);
  const applied = signal<T>(initial);
  let timer: ReturnType<typeof setTimeout> | undefined;
  const same = (a: T, b: T): boolean =>
    JSON.stringify(codec.serialize(a)) === JSON.stringify(codec.serialize(b));

  const apply = (next: T): void => {
    applied.set(next);
    void router.navigate([], {
      relativeTo: route,
      queryParams: codec.serialize(next),
      replaceUrl: true,
    });
  };

  const sub = route.queryParamMap.subscribe((params) => {
    const fromUrl = codec.parse(params);
    if (same(fromUrl, applied())) return;
    clearTimeout(timer);
    value.set(fromUrl);
    applied.set(fromUrl);
  });
  inject(DestroyRef).onDestroy(() => {
    clearTimeout(timer);
    sub.unsubscribe();
  });

  return {
    value: value.asReadonly(),
    applied: applied.asReadonly(),
    set(next) {
      const typing = codec.typing(value(), next);
      value.set(next);
      clearTimeout(timer);
      if (typing) timer = setTimeout(() => apply(next), TYPING_DELAY_MS);
      else apply(next);
    },
  };
}
