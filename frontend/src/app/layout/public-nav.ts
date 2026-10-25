/** The places of the public site, shared by the header navigation and the phone bottom bar (B1 contract 3.2, C contract 5.5). */
import type { IconName } from '@stupa-makers/ui-kit';
import type { TranslationKey } from '@core/i18n/translations';

export interface PublicNavItem {
  key: string;
  path: string;
  icon: IconName;
  labelKey: TranslationKey;
  /** `/` must match exactly, or it would be active everywhere. */
  exact: boolean;
  /** Whether the phone bottom bar shows it; the search lives in the header pill there. */
  phone: boolean;
}

export const PUBLIC_NAV: readonly PublicNavItem[] = [
  { key: 'today', path: '/', icon: 'home', labelKey: 'public.nav.today', exact: true, phone: true },
  {
    key: 'search',
    path: '/suche',
    icon: 'search',
    labelKey: 'public.nav.search',
    exact: false,
    phone: false,
  },
  {
    key: 'calendar',
    path: '/kalender',
    icon: 'cal',
    labelKey: 'public.nav.calendar',
    exact: false,
    phone: true,
  },
  {
    key: 'map',
    path: '/karte',
    icon: 'pin',
    labelKey: 'public.nav.map',
    exact: false,
    phone: true,
  },
  {
    key: 'subscribe',
    path: '/abos',
    icon: 'bell',
    labelKey: 'public.nav.subscribe',
    exact: false,
    phone: true,
  },
];
