/**
 * Maps a Problem+JSON failure of an admin write to field messages and, if no field fits, a toast text.
 * Server `msg` texts are English and never shown; an unmapped field error becomes a generic German one.
 */
import type { Problem } from '@core/api/models';
import type { I18nService } from '@core/i18n/i18n.service';
import type { TranslationKey } from '@core/i18n/translations';
import { problemMessage } from '../dossiers/api/problem-message';

export interface AdminErrors {
  fields: Record<string, string>;
  message: string | null;
}

const BY_CODE: Record<string, { field: string; key: TranslationKey }> = {
  slug_taken: { field: 'slug', key: 'admin.err.slugTaken' },
  category_cycle: { field: 'parentId', key: 'admin.err.categoryCycle' },
  organization_cycle: { field: 'parentId', key: 'admin.err.organizationCycle' },
  reserved_group_prefix: { field: 'oidcGroup', key: 'admin.err.reservedGroupPrefix' },
  duplicate_group: { field: 'oidcGroup', key: 'admin.err.duplicateGroup' },
  organization_required: { field: 'organizationId', key: 'admin.err.organizationRequired' },
  organization_forbidden: { field: 'organizationId', key: 'admin.err.organizationForbidden' },
  approver_requires_trusted: { field: 'role', key: 'admin.err.approverRequiresTrusted' },
  implicit_role: { field: 'role', key: 'admin.err.implicitRole' },
  unknown_organization: { field: 'organizationId', key: 'admin.err.unknownOrganization' },
};

const MESSAGE_BY_CODE: Record<string, TranslationKey> = {
  last_admin_mapping: 'admin.err.lastAdminMapping',
  coordinates_incomplete: 'admin.err.coordinatesIncomplete',
};

/**
 * Turns a failed write into messages for the form.
 *
 * Args:
 *   i18n: Translation service.
 *   problem: The parsed Problem+JSON.
 *
 * Returns:
 *   `fields` keyed by wire field name for the inputs; `message` for a toast when no
 *   field carries the error.
 */
export function adminErrors(i18n: I18nService, problem: Problem): AdminErrors {
  const known = problem.code ? BY_CODE[problem.code] : undefined;
  if (known) return { fields: { [known.field]: i18n.translate(known.key) }, message: null };
  const messageKey = problem.code ? MESSAGE_BY_CODE[problem.code] : undefined;
  if (messageKey) return { fields: {}, message: i18n.translate(messageKey) };
  const invalid = i18n.translate('admin.err.invalidValue');
  const fields = Object.fromEntries((problem.errors ?? []).map((e) => [e.field, invalid]));
  if (Object.keys(fields).length > 0) return { fields, message: null };
  return { fields: {}, message: problemMessage(i18n, problem) };
}
