/**
 * Routes of the public site (B1 contract 3.1). Every route forces the `public` frame and shows the footer, so a signed-in
 * person who opens `/e/<slug>` from a mail sees the same page as everybody else. `app.routes.ts` mounts them before the
 * feature areas; the server renders the page head for `/`, `/suche`, `/kalender`, `/rueckblick`, `/e/*` and `/k/*`. The token pages
 * `/bestaetigen/:token` and `/abo/:token` are plain shells; the token-less twins catch a reload after the page removed the
 * token from the address bar and show the "link invalid" state.
 */
import type { Route, Routes } from '@angular/router';

export const PUBLIC_DATA = { frame: 'public', footer: true } as const;

/** The confirmation page is a bare page without the site chrome: one sentence and one button (P08). */
const CONFIRM_DATA = { chrome: false } as const;

const page = (
  path: string,
  title: string,
  load: Route['loadComponent'],
  data: object = {},
): Route => ({
  path,
  data: { ...PUBLIC_DATA, title, ...data },
  loadComponent: load,
});

export const PUBLIC_ROUTES: Routes = [
  {
    ...page('', 'public.today.title', () =>
      import('./pages/today/today.component').then((m) => m.TodayComponent),
    ),
    pathMatch: 'full',
  },
  page('suche', 'public.search.title', () =>
    import('./pages/search/search.component').then((m) => m.SearchComponent),
  ),
  page('kalender', 'public.calendar.title', () =>
    import('./pages/calendar/calendar.component').then((m) => m.CalendarPageComponent),
  ),
  page('e/:slug', 'public.event.title', () =>
    import('./pages/event/event.component').then((m) => m.EventPageComponent),
  ),
  page('k/:slug', 'public.category.title', () =>
    import('./pages/category/category.component').then((m) => m.CategoryPageComponent),
  ),
  page('rueckblick', 'public.review.title', () =>
    import('./pages/review/review.component').then((m) => m.ReviewPageComponent),
  ),
  page('abos', 'public.subscribe.title', () =>
    import('./pages/subscribe/subscribe.component').then((m) => m.SubscribePageComponent),
  ),
  page('start', 'public.start.title', () =>
    import('./pages/start/start.component').then((m) => m.StartPageComponent),
  ),
  page(
    'bestaetigen/:token',
    'public.confirm.title',
    () => import('./pages/confirm/confirm.component').then((m) => m.ConfirmPageComponent),
    CONFIRM_DATA,
  ),
  page(
    'bestaetigen',
    'public.confirm.title',
    () => import('./pages/confirm/confirm.component').then((m) => m.ConfirmPageComponent),
    CONFIRM_DATA,
  ),
  page('abo/:token', 'public.manage.title', () =>
    import('./pages/manage/manage.component').then((m) => m.ManagePageComponent),
  ),
  page('abo', 'public.manage.title', () =>
    import('./pages/manage/manage.component').then((m) => m.ManagePageComponent),
  ),
  page(
    'impressum',
    'public.legal.imprint',
    () => import('./pages/static/legal.component').then((m) => m.LegalPageComponent),
    { kind: 'imprint' },
  ),
  page(
    'datenschutz',
    'public.legal.privacy',
    () => import('./pages/static/legal.component').then((m) => m.LegalPageComponent),
    { kind: 'privacy' },
  ),
  page('offline', 'public.offline.title', () =>
    import('./pages/static/offline.component').then((m) => m.OfflinePageComponent),
  ),
];
