/**
 * The locale of dates and of the few words that date helpers put into a sentence. `I18nService` sets it when the UI
 * locale changes; pure helpers (`event-time`, `event-format`, the calendar grid) read it, so they need no injector.
 * Zones never change with the locale: events stay in their own zone, platform days in Europe/Berlin.
 */

export type FormatLang = 'de' | 'en';

const TAGS: Record<FormatLang, string> = { de: 'de-DE', en: 'en-GB' };

export interface DateWords {
  to: string;
  allDay: string;
  clock: (time: string) => string;
  winter: string;
  summer: string;
}

const WORDS: Record<FormatLang, DateWords> = {
  de: {
    to: 'bis',
    allDay: 'ganztägig',
    clock: (time) => `${time} Uhr`,
    winter: 'Wintersemester',
    summer: 'Sommersemester',
  },
  en: {
    to: 'to',
    allDay: 'all day',
    clock: (time) => time,
    winter: 'Winter semester',
    summer: 'Summer semester',
  },
};

let active: FormatLang = 'de';
const formatters = new Map<string, Intl.DateTimeFormat>();

export function setFormatLang(lang: FormatLang): void {
  active = lang;
}

export const formatTag = (): string => TAGS[active];

export const dateWords = (): DateWords => WORDS[active];

/** A cached `Intl.DateTimeFormat` for the active locale. */
export function dateFormat(options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const key = `${active}|${JSON.stringify(options)}`;
  let format = formatters.get(key);
  if (!format) {
    format = new Intl.DateTimeFormat(TAGS[active], options);
    formatters.set(key, format);
  }
  return format;
}
