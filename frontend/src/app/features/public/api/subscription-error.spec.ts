/** Spec for the subscription error mapping: Problem+JSON codes, the 429 wait and the 404 of an unusable token. */
import { HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import { subscriptionErrorOf } from './subscription-error';

const http = (status: number, body: object | null = null, headers: Record<string, string> = {}) =>
  new HttpErrorResponse({ status, error: body, headers: new HttpHeaders(headers) });

describe('subscriptionErrorOf', () => {
  it.each([
    ['altcha_invalid', 400, 'altchaInvalid'],
    ['consent_outdated', 409, 'consentOutdated'],
    ['unknown_interest', 422, 'unknownInterest'],
    ['no_interest', 422, 'noInterest'],
    ['invalid_token', 404, 'invalidToken'],
  ])('maps %s', (code, status, kind) => {
    expect(subscriptionErrorOf(http(status, { status, code })).kind).toBe(kind);
  });

  it('turns Retry-After seconds into whole minutes and defaults to 15', () => {
    expect(subscriptionErrorOf(http(429, null, { 'Retry-After': '601' }))).toEqual({
      kind: 'rateLimited',
      retryMinutes: 11,
    });
    expect(subscriptionErrorOf(http(429)).retryMinutes).toBe(15);
  });

  it('treats a bare 404 as an unusable token, another 422 as invalid input, the rest as failed', () => {
    expect(subscriptionErrorOf(http(404)).kind).toBe('invalidToken');
    expect(subscriptionErrorOf(http(422, { status: 422 })).kind).toBe('invalidInput');
    expect(subscriptionErrorOf(http(500)).kind).toBe('failed');
    expect(subscriptionErrorOf(new Error('x')).kind).toBe('failed');
  });
});
