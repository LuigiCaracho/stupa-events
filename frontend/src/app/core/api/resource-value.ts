/** The value of a resource, or `fallback` while it has none (loading, error). Reading `value()` in an error state would throw. */
import type { Resource } from '@angular/core';

export function resourceValue<T>(resource: Resource<T | undefined>, fallback: T): T {
  return resource.hasValue() ? (resource.value() as T) : fallback;
}
