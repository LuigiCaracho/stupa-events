/** Reads the Problem+JSON body of a failed HTTP call; anything else becomes a bare status. */
import { HttpErrorResponse } from '@angular/common/http';
import type { Problem } from './models';

/**
 * Extracts the problem detail of an HTTP error.
 *
 * Args:
 *   err: Anything an `HttpClient` call can reject with, or a resource error wrapping it as `cause`.
 *
 * Returns:
 *   The parsed problem, or `{ status }` when the body is not a problem object.
 */
export function problemOf(err: unknown): Problem {
  if (err instanceof Error && err.cause instanceof HttpErrorResponse) return problemOf(err.cause);
  if (!(err instanceof HttpErrorResponse)) return { status: 0 };
  const body: unknown = err.error;
  if (typeof body === 'object' && body !== null && 'status' in body) return body as Problem;
  return { status: err.status };
}
