/** Texts of the guard reasons: the server sends an i18n key and a field name, the UI translates both. */
import type { ProblemReason } from '@core/api/models';
import type { I18nService } from '@core/i18n/i18n.service';
import { de, type TranslationKey } from '@core/i18n/translations';

const known = (key: string): key is TranslationKey => key in de;

/** Label of a server field name (`startsAt` or `starts_at`), falling back to the raw name. */
export function fieldLabel(i18n: I18nService, field: string | null): string {
  if (!field) return '';
  const camel = field.replace(/_([a-z])/g, (_m, c: string) => c.toUpperCase());
  const key = `field.${camel}`;
  return known(key) ? i18n.translate(key) : field;
}

/** The sentence of one reason; an unknown `messageKey` gives the generic sentence. */
export function reasonText(i18n: I18nService, reason: ProblemReason): string {
  const key = known(reason.messageKey) ? reason.messageKey : 'guards.unknown';
  return i18n.translate(key, { field: fieldLabel(i18n, reason.field) });
}

/** The fix buttons the app can act on in M3; the others (comments, duplicates, facts, checklists) come with M4 to M7. */
export const HANDLED_FIXES: ReadonlySet<string> = new Set([
  'fill_field',
  'change_date',
  'upload_poster',
  'pick_venue',
  'fill_rights',
  'mark_cancellation',
  'confirm_flyer',
  'set_end',
]);
