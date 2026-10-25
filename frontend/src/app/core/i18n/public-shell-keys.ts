/**
 * The keys outside the public catalogs that the public site shows: the frame, the install and update prompts, the 404
 * page, the calendar grid and the status words. They have an English text (`translations.shell.en.ts`); every other
 * internal key stays German, and `translate` falls back to it.
 */
export const PUBLIC_SHELL_KEYS = [
  'app.title',
  'app.skipToContent',
  'common.loading',
  'common.back',
  'nav.main',
  'nav.footer',
  'footer.coBranding',
  'footer.language',
  'theme.toggle',
  'action.login',
  'notFound.heading',
  'notFound.body',
  'pwa.updateReady',
  'pwa.reload',
  'pwa.installLabel',
  'pwa.installHint',
  'pwa.installClose',
  'publicStatus.cancelled',
  'publicStatus.postponed',
  'calendar.title',
  'calendar.gridLabel',
  'calendar.agenda',
  'calendar.allDay',
  'calendar.continues',
  'calendar.today',
  'calendar.more',
  'calendar.empty',
  'calendar.prev',
  'calendar.next',
  'calendar.goToday',
  'calendar.mode',
  'calendar.month',
  'calendar.week',
  'calendar.list',
  'calendar.view',
  'calendar.loadFailed',
  'calendar.truncated',
  'calendar.rangeTooLarge',
] as const;

export type PublicShellKey = (typeof PUBLIC_SHELL_KEYS)[number];
