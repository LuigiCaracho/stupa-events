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
  reason_required: 'problem.reasonRequired',
  proposal_quota_exceeded: 'problem.proposalQuota',
  publish_at_in_past: 'problem.publishAtPast',
  publish_after_end: 'problem.publishAfterEnd',
  four_eyes: 'problem.fourEyes',
  revert_poster_replaced: 'problem.revertPosterReplaced',
  organization_already_set: 'problem.orgAlreadySet',
  unknown_venue: 'problem.unknownVenue',
  precondition_required: 'problem.preconditionRequired',
  start_in_past: 'problem.startInPast',
  validation_error: 'problem.validation',
  file_too_large: 'problem.fileTooLarge',
  archive_bomb: 'problem.activeContent',
  active_content: 'problem.activeContent',
  image_rejected: 'problem.imageRejected',
  image_too_small: 'problem.imageTooSmall',
  consent_missing: 'problem.consentMissing',
  visibility_not_allowed: 'problem.visibilityNotAllowed',
  social_post_needs_image: 'problem.socialPostNeedsImage',
  anchor_invalid: 'problem.anchorInvalid',
  template_invalid: 'problem.templateInvalid',
  subject_newline: 'problem.subjectNewline',
  diff_too_large: 'problem.diffTooLarge',
  waiver_reason_required: 'problem.waiverReasonRequired',
  assignee_not_member: 'problem.assigneeNotMember',
  kind_essential: 'problem.kindEssential',
  quarantined: 'problem.quarantined',
  poster_in_use: 'problem.posterInUse',
  dossier_closed: 'problem.dossierClosed',
  already_exists: 'problem.alreadyExists',
  template_item: 'problem.templateItem',
  item_waived: 'problem.itemWaived',
  not_a_root: 'problem.notARoot',
  quote_expired: 'problem.quoteExpired',
  attachment_infected: 'problem.attachmentInfected',
  slug_taken: 'problem.slugTaken',
  already_in_format: 'problem.alreadyInFormat',
  format_foreign: 'problem.formatForeign',
  not_a_template: 'problem.notATemplate',
  organization_required: 'problem.orgRequired',
  range_too_large: 'problem.rangeTooLarge',
  query_too_long: 'problem.queryTooLong',
  search_timeout: 'problem.searchTimeout',
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
  if (known === 'problem.fileTooLarge') {
    const limit = problem.limitBytes ? Math.round(problem.limitBytes / 1_048_576) : 25;
    return i18n.translate(known, { limit });
  }
  if (known) return i18n.translate(known);
  return problem.traceId
    ? i18n.translate('problem.generic', { traceId: problem.traceId })
    : i18n.translate('problem.genericNoId');
}
