/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/core/i18n/i18n.service.ts (rewritten) */
/**
 * UI i18n. Rewritten from the workflow tool:
 * DE only in stage A, no lazy catalogs. The `Intl` tag is the single mapping point for
 * date and number formatting: never hand a bare UI locale to `Intl`.
 */
import { Injectable, computed, signal } from '@angular/core';
import {
  CATALOG,
  DEFAULT_LOCALE,
  type Locale,
  SUPPORTED_LOCALES,
  type TranslationKey,
} from './translations';

const FORMAT_LOCALES: Record<Locale, string> = { de: 'de-DE' };

/** Maps a UI locale to its `Intl` tag. */
export function toFormatLocale(locale: string): string {
  return FORMAT_LOCALES[locale as Locale] ?? FORMAT_LOCALES[DEFAULT_LOCALE];
}

@Injectable({ providedIn: 'root' })
export class I18nService {
  private readonly _locale = signal<Locale>(DEFAULT_LOCALE);

  readonly locale = this._locale.asReadonly();
  readonly locales = SUPPORTED_LOCALES;
  readonly formatLocale = computed(() => toFormatLocale(this._locale()));
  readonly dictionary = computed(() => CATALOG[this._locale()]);

  constructor() {
    if (typeof document !== 'undefined') document.documentElement.lang = this._locale();
  }

  /** Resolves when the catalog of the active locale is usable (always, DE is bundled). */
  ready(): Promise<void> {
    return Promise.resolve();
  }

  /** Translates a key; a missing key falls back to the key itself. */
  translate(key: TranslationKey, params?: Record<string, string | number>): string {
    const raw = CATALOG[this._locale()][key] ?? key;
    return params ? this.interpolate(raw, params) : raw;
  }

  private interpolate(text: string, params: Record<string, string | number>): string {
    return text.replace(/\{(\w+)\}/g, (match, name: string) =>
      name in params ? String(params[name]) : match,
    );
  }
}
