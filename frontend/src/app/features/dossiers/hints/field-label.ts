/** Label of a server field name (`startsAt` or `starts_at`), falling back to the raw name. */
import type { I18nService } from '@core/i18n/i18n.service';
import { de, type TranslationKey } from '@core/i18n/translations';

const known = (key: string): key is TranslationKey => key in de;

export function fieldLabel(i18n: I18nService, field: string | null): string {
  if (!field) return '';
  const camel = field.replace(/_([a-z])/g, (_m, c: string) => c.toUpperCase());
  const key = `field.${camel}`;
  return known(key) ? i18n.translate(key) : field;
}
