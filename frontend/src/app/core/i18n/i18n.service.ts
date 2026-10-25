/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/core/i18n/i18n.service.ts (rewritten) */
/**
 * UI i18n. German is bundled; the English catalog of the public site loads on demand. The first visit follows the
 * saved choice, else `navigator.language`; the choice is saved in `localStorage` as a convenience only. The `Intl`
 * tag is the single mapping point for date and number formatting: never hand a bare UI locale to `Intl`.
 */
import { DOCUMENT } from '@angular/common';
import { Injectable, computed, inject, signal } from '@angular/core';
import { setFormatLang } from './format-locale';
import {
  DEFAULT_LOCALE,
  type Locale,
  type PartialCatalog,
  SUPPORTED_LOCALES,
  type TranslationKey,
  de,
  loadEnglish,
} from './translations';

const STORAGE_KEY = 'ev.locale';

const FORMAT_LOCALES: Record<Locale, string> = { de: 'de-DE', en: 'en-GB' };

/** Maps a UI locale to its `Intl` tag. */
export function toFormatLocale(locale: string): string {
  return FORMAT_LOCALES[locale as Locale] ?? FORMAT_LOCALES[DEFAULT_LOCALE];
}

const isLocale = (value: unknown): value is Locale => SUPPORTED_LOCALES.includes(value as Locale);

@Injectable({ providedIn: 'root' })
export class I18nService {
  private readonly win = inject(DOCUMENT).defaultView;
  private readonly _locale = signal<Locale>(DEFAULT_LOCALE);
  private readonly english = signal<PartialCatalog | null>(null);
  private booted: Promise<void> | null = null;

  constructor() {
    if (this.win) this.win.document.documentElement.lang = DEFAULT_LOCALE;
  }

  readonly locale = this._locale.asReadonly();
  readonly locales = SUPPORTED_LOCALES;
  readonly formatLocale = computed(() => toFormatLocale(this._locale()));
  readonly dictionary = computed<Partial<Record<TranslationKey, string>>>(() =>
    this._locale() === 'en' ? { ...de, ...this.english() } : de,
  );

  /** Picks the first locale (saved choice, else the browser language) and resolves when its catalog is usable. */
  ready(): Promise<void> {
    this.booted ??= this.apply(this.detect());
    return this.booted;
  }

  /** Switches the locale, loading the English catalog first, and saves the choice. */
  async setLocale(locale: Locale): Promise<void> {
    await this.apply(locale);
    try {
      this.win?.localStorage.setItem(STORAGE_KEY, locale);
    } catch {
      // The choice only stays for this visit.
    }
  }

  /** Translates a key; a key without an English text shows the German one, a missing key shows itself. */
  translate(key: TranslationKey, params?: Record<string, string | number>): string {
    const raw = this.dictionary()[key] ?? key;
    return params ? this.interpolate(raw, params) : raw;
  }

  private detect(): Locale {
    try {
      const saved = this.win?.localStorage.getItem(STORAGE_KEY);
      if (isLocale(saved)) return saved;
    } catch {
      // Blocked storage: fall through to the browser language.
    }
    return this.win?.navigator.language?.toLowerCase().startsWith('en') ? 'en' : DEFAULT_LOCALE;
  }

  private async apply(locale: Locale): Promise<void> {
    if (locale === 'en' && !this.english()) this.english.set(await loadEnglish());
    this._locale.set(locale);
    setFormatLang(locale);
    if (this.win) this.win.document.documentElement.lang = locale;
  }

  private interpolate(text: string, params: Record<string, string | number>): string {
    return text.replace(/\{(\w+)\}/g, (match, name: string) =>
      name in params ? String(params[name]) : match,
    );
  }
}
