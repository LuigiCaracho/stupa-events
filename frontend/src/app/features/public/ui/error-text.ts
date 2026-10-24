/** The sentence for a failed subscription call: the translation key and its parameters. */
import type { TranslationKey } from '@core/i18n/translations';
import type { SubscriptionError, SubscriptionErrorKind } from '../api/subscription-error';

const KEYS: Record<Exclude<SubscriptionErrorKind, 'rateLimited'>, TranslationKey> = {
  altchaInvalid: 'public.sub.error.altchaInvalid',
  consentOutdated: 'public.sub.error.consentOutdated',
  invalidToken: 'public.sub.error.invalidToken',
  unknownInterest: 'public.sub.error.unknownInterest',
  noInterest: 'public.sub.error.noInterest',
  invalidInput: 'public.sub.error.invalidInput',
  failed: 'public.sub.error.failed',
};

export function errorText(error: SubscriptionError): {
  key: TranslationKey;
  params?: Record<string, number>;
} {
  if (error.kind !== 'rateLimited') return { key: KEYS[error.kind] };
  const minutes = error.retryMinutes ?? 15;
  return minutes === 1
    ? { key: 'public.sub.error.rateLimitedOne' }
    : { key: 'public.sub.error.rateLimited', params: { minutes } };
}
