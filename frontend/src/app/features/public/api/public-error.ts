/** Maps a failed public call to the few cases the pages tell apart (B1 contract 3.4). */
import { problemOf } from '@core/api/problem';

export type PublicErrorKind =
  'notFound' | 'rateLimited' | 'queryTooLong' | 'invalidQuery' | 'failed';

/** 404, 429 and the 422 codes of the search have their own sentence; everything else is "failed". */
export function publicErrorOf(err: unknown): PublicErrorKind {
  const problem = problemOf(err);
  if (problem.status === 404) return 'notFound';
  if (problem.status === 429) return 'rateLimited';
  if (problem.status === 422) {
    if (problem.code === 'query_too_long') return 'queryTooLong';
    if (problem.code === 'invalid_query') return 'invalidQuery';
  }
  return 'failed';
}
