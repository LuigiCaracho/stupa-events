/** Maps a failed subscription call to the cases the pages word differently (B3 contract 6.5); the 429 carries the wait in minutes. */
import { HttpErrorResponse } from '@angular/common/http';
import { problemOf } from '@core/api/problem';

export type SubscriptionErrorKind =
  | 'altchaInvalid'
  | 'rateLimited'
  | 'consentOutdated'
  | 'invalidToken'
  | 'unknownInterest'
  | 'noInterest'
  | 'invalidInput'
  | 'failed';

export interface SubscriptionError {
  kind: SubscriptionErrorKind;
  retryMinutes: number | null;
}

const BY_CODE: Record<string, SubscriptionErrorKind> = {
  altcha_invalid: 'altchaInvalid',
  rate_limited: 'rateLimited',
  consent_outdated: 'consentOutdated',
  invalid_token: 'invalidToken',
  unknown_interest: 'unknownInterest',
  no_interest: 'noInterest',
};

const DEFAULT_WAIT_MINUTES = 15;

function retryMinutes(err: unknown): number {
  const cause = err instanceof Error && err.cause instanceof HttpErrorResponse ? err.cause : err;
  const seconds = Number(cause instanceof HttpErrorResponse ? cause.headers.get('Retry-After') : null);
  return Number.isFinite(seconds) && seconds > 0 ? Math.ceil(seconds / 60) : DEFAULT_WAIT_MINUTES;
}

export function subscriptionErrorOf(err: unknown): SubscriptionError {
  const problem = problemOf(err);
  const byCode = problem.code ? BY_CODE[problem.code] : undefined;
  if (problem.status === 429 || byCode === 'rateLimited') {
    return { kind: 'rateLimited', retryMinutes: retryMinutes(err) };
  }
  if (byCode) return { kind: byCode, retryMinutes: null };
  if (problem.status === 404) return { kind: 'invalidToken', retryMinutes: null };
  if (problem.status === 422) return { kind: 'invalidInput', retryMinutes: null };
  return { kind: 'failed', retryMinutes: null };
}
