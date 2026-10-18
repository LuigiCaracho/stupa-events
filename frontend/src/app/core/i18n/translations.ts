/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/core/i18n/translations.ts (rewritten) */
/**
 * UI string catalog. Rewritten from the workflow tool: DE only in stage A (en parity follows with
 * stage B, see the TODO in `translations.spec.ts`). The shell strings live in
 * `translations.shell.de.ts`; the feature pages add theirs in `translations.events.de.ts`, the pipeline pages in `translations.pipeline.de.ts`, the admin area in `translations.admin.de.ts`.
 */
import { adminDe } from './translations.admin.de';
import { eventsDe } from './translations.events.de';
import { pipelineDe } from './translations.pipeline.de';
import { shellDe } from './translations.shell.de';
import { sharedDe } from './translations.shared.de';

export type Locale = 'de';

export const SUPPORTED_LOCALES: readonly Locale[] = ['de'] as const;
export const DEFAULT_LOCALE: Locale = 'de';

export const de = { ...shellDe, ...sharedDe, ...eventsDe, ...pipelineDe, ...adminDe } as const;

export type TranslationKey = keyof typeof de;

/** The catalog of every locale. */
export const CATALOG: Record<Locale, Record<TranslationKey, string>> = { de };
