/** Number formatting through `Intl` in the active UI locale; Angular's locale-bound pipes would need `registerLocaleData`. */
import type { I18nService } from '@core/i18n/i18n.service';

export function formatMoney(i18n: I18nService, cents: number, currency: string): string {
  return new Intl.NumberFormat(i18n.formatLocale(), { style: 'currency', currency }).format(
    cents / 100,
  );
}

export function formatMegabytes(i18n: I18nService, bytes: number): string {
  return new Intl.NumberFormat(i18n.formatLocale(), {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(bytes / 1_048_576);
}
