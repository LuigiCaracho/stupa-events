/** German labels of the admin enums (kinds, profiles, color tokens, precisions, roles) and the select options built from them. */
import type { I18nService } from '@core/i18n/i18n.service';
import type { TranslationKey } from '@core/i18n/translations';
import type { SelectFieldOption } from '@shared/ui/select/select.component';
import type {
  CategoryKind,
  ColorToken,
  MappingRole,
  OrganizationKind,
  PublicPrecision,
  RequiredProfile,
} from './api/admin.models';

export const KIND_KEYS: Record<CategoryKind | OrganizationKind, TranslationKey> = {
  format: 'admin.kind.format',
  fachschaft: 'admin.kind.fachschaft',
  partner: 'admin.kind.partner',
  stupa: 'admin.kind.stupa',
  referat: 'admin.kind.referat',
  hochschule: 'admin.kind.hochschule',
  redaktion: 'admin.kind.redaktion',
};

export const PROFILE_KEYS: Record<RequiredProfile, TranslationKey> = {
  generic: 'admin.profile.generic',
  party: 'admin.profile.party',
  meeting: 'admin.profile.meeting',
  trip: 'admin.profile.trip',
};

export const COLOR_KEYS: Record<ColorToken, TranslationKey> = {
  orange: 'admin.color.orange',
  blue: 'admin.color.blue',
  petrol: 'admin.color.petrol',
  navy: 'admin.color.navy',
  yellow: 'admin.color.yellow',
  red: 'admin.color.red',
};

export const PRECISION_KEYS: Record<PublicPrecision, TranslationKey> = {
  exact: 'admin.precision.exact',
  building: 'admin.precision.building',
  hidden: 'admin.precision.hidden',
};

export const ROLE_KEYS: Record<MappingRole, TranslationKey> = {
  admin: 'admin.role.admin',
  editor: 'admin.role.editor',
  stupa: 'admin.role.stupa',
  viewer: 'admin.role.viewer',
  submitter: 'admin.role.submitter',
  organizer: 'admin.role.organizer',
  approver: 'admin.role.approver',
};

/**
 * Builds select options for the given values, labelled through the key map.
 *
 * Args:
 *   i18n: Translation service.
 *   values: The enum values in display order.
 *   keys: Label keys per value.
 *
 * Returns:
 *   One option per value with the German label.
 */
export function optionsOf<T extends string>(
  i18n: I18nService,
  values: readonly T[],
  keys: Record<T, TranslationKey>,
): SelectFieldOption[] {
  return values.map((value) => ({ value, label: i18n.translate(keys[value]) }));
}

/**
 * Looks up the label key of a wire value; the template cannot index a typed record with an untyped row.
 *
 * Args:
 *   keys: Label keys per value.
 *   value: The wire value of the row.
 *
 * Returns:
 *   The translation key for the value.
 */
export const labelKey = <T extends string>(keys: Record<T, TranslationKey>, value: string): TranslationKey =>
  keys[value as T];
