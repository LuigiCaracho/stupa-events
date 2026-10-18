/** Turns a Problem+JSON failure into the German toast text of the pages. */
import type { Problem } from '@core/api/models';
import type { I18nService } from '@core/i18n/i18n.service';
import type { TranslationKey } from '@core/i18n/translations';
import { reasonText } from '@shared/ui/guard-list/reason-text';

const BY_CODE: Record<string, TranslationKey> = {
  not_found: 'problem.notFound',
  forbidden: 'problem.forbidden',
  conflict: 'problem.conflict',
  field_locked: 'problem.fieldLocked',
  invalid_transition: 'problem.invalidTransition',
  payload_too_large: 'problem.tooLarge',
  unsupported_media_type: 'problem.unsupportedMedia',
  rate_limited: 'problem.rateLimited',
  service_unavailable: 'problem.unavailable',
};

/**
 * Builds the message for a failed call.
 *
 * Args:
 *   i18n: Translation service.
 *   problem: The parsed Problem+JSON (`{ status: 0 }` when there was no body).
 *
 * Returns:
 *   A refused transition lists its blockers; known codes map to a fixed sentence; anything
 *   else gets the generic text with the trace id.
 */
export function problemMessage(i18n: I18nService, problem: Problem): string {
  if (problem.status === 0) return i18n.translate('problem.offline');
  const blockers = (problem.reasons ?? []).filter((r) => r.severity === 'blocker');
  if (blockers.length > 0) {
    const text = blockers.map((r) => reasonText(i18n, r)).join(' ');
    return i18n.translate('problem.refused', { reasons: text });
  }
  const known = problem.code ? BY_CODE[problem.code] : undefined;
  if (known) return i18n.translate(known);
  return problem.traceId
    ? i18n.translate('problem.generic', { traceId: problem.traceId })
    : i18n.translate('problem.genericNoId');
}
