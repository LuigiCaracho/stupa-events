/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/core/i18n/translations.ts (rewritten) */
/**
 * UI string catalog. Rewritten from the workflow tool: DE only in stage A (en parity follows with
 * stage B, see the TODO in `translations.spec.ts`). The shell strings live in
 * `translations.shell.de.ts`; the feature pages add theirs in `translations.events.de.ts`, the dossier page and its lifecycle in `translations.lifecycle.de.ts`, the admin area in `translations.admin.de.ts`, the M5 areas in `translations.{calendar,format,archive}.de.ts`, the public site in `translations.public.de.ts`.
 */
import { adminDe } from './translations.admin.de';
import { archiveDe } from './translations.archive.de';
import { calendarDe } from './translations.calendar.de';
import { dossierDe } from './translations.dossier.de';
import { eventsDe } from './translations.events.de';
import { formatDe } from './translations.format.de';
import { mapDe } from './translations.map.de';
import { lifecycleDe } from './translations.lifecycle.de';
import { publicDe } from './translations.public.de';
import { shellDe } from './translations.shell.de';
import { subscriptionsDe } from './translations.subscriptions.de';
import { sharedDe } from './translations.shared.de';

export type Locale = 'de' | 'en';

export const SUPPORTED_LOCALES: readonly Locale[] = ['de', 'en'] as const;
export const DEFAULT_LOCALE: Locale = 'de';

export const de = {
  ...shellDe,
  ...sharedDe,
  ...eventsDe,
  ...lifecycleDe,
  ...dossierDe,
  ...adminDe,
  ...calendarDe,
  ...formatDe,
  ...archiveDe,
  ...publicDe,
  ...subscriptionsDe,
  ...mapDe,
} as const;

export type TranslationKey = keyof typeof de;

/**
 * An English catalog covers the public site (public pages, subscriptions, shared blocks, maps and the public shell);
 * the internal catalogs stay German, and a missing key falls back to German. It loads on demand.
 */
export type PartialCatalog = Partial<Record<TranslationKey, string>>;

export const loadEnglish = (): Promise<PartialCatalog> =>
  import('./translations.en').then((m) => m.en);
