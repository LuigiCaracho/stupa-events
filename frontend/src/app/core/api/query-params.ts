/** Builds `HttpParams` from a flat query object: empty values are dropped, arrays repeat the key. */
import { HttpParams } from '@angular/common/http';

export type QueryValue = string | number | boolean | readonly (string | number)[] | null | undefined;

export function toParams(query: object): HttpParams {
  let params = new HttpParams();
  for (const [key, value] of Object.entries(query as Record<string, QueryValue>)) {
    if (value === undefined || value === null || value === '' || value === false) continue;
    if (Array.isArray(value)) value.forEach((v) => (params = params.append(key, String(v))));
    else params = params.set(key, value === true ? '1' : String(value));
  }
  return params;
}
