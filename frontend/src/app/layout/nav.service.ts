/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/layout/nav.service.ts (rewritten) */
/**
 * Navigation model of the signed-in frame. Rewritten from the workflow tool: the workflow entries are gone. M3 has Aufgaben,
 * Pipeline, Dossiers, Verwaltung and Konto; M5 adds Kalender, Archiv, Formate and Bibliothek. On the phone the bar holds
 * four entries and a "Mehr" sheet holds the rest. The filter is UX only; route guards and the server stay authoritative.
 */
import { Injectable, computed, inject } from '@angular/core';
import { AuthService } from '@core/auth/auth.service';
import type { TranslationKey } from '@core/i18n/translations';
import type { IconName } from '@stupa-makers/ui-kit';

export type NavKey =
  | 'tasks'
  | 'pipeline'
  | 'dossiers'
  | 'calendar'
  | 'archive'
  | 'formats'
  | 'library'
  | 'admin'
  | 'account';

/** One entry of the navigation rail and of the phone bar. */
export interface NavItem {
  key: NavKey;
  path: string;
  labelKey: TranslationKey;
  icon: IconName;
  /** Visible when the principal has at least one of these permissions (empty = any session). */
  permissions: string[];
  /** `end` entries sit at the foot of the rail, after the spacer. */
  place: 'main' | 'end';
}

export const NAV_ITEMS: readonly NavItem[] = [
  {
    key: 'tasks',
    path: '/aufgaben',
    labelKey: 'nav.tasks',
    icon: 'tasks',
    permissions: [],
    place: 'main',
  },
  {
    key: 'pipeline',
    path: '/pipeline',
    labelKey: 'nav.pipeline',
    icon: 'kanban',
    permissions: [],
    place: 'main',
  },
  {
    key: 'dossiers',
    path: '/dossiers',
    labelKey: 'nav.dossiers',
    icon: 'list',
    permissions: [],
    place: 'main',
  },
  {
    key: 'calendar',
    path: '/kalender',
    labelKey: 'nav.calendar',
    icon: 'cal',
    permissions: [],
    place: 'main',
  },
  {
    key: 'archive',
    path: '/archiv',
    labelKey: 'nav.archive',
    icon: 'archive',
    permissions: [],
    place: 'main',
  },
  {
    key: 'formats',
    path: '/formate',
    labelKey: 'nav.formats',
    icon: 'form',
    permissions: [],
    place: 'main',
  },
  {
    key: 'library',
    path: '/bibliothek',
    labelKey: 'nav.library',
    icon: 'book',
    permissions: [],
    place: 'main',
  },
  {
    key: 'admin',
    path: '/verwaltung',
    labelKey: 'nav.admin',
    icon: 'gear',
    permissions: ['taxonomy.manage', 'venue.manage', 'admin.mappings'],
    place: 'main',
  },
  {
    key: 'account',
    path: '/konto',
    labelKey: 'nav.account',
    icon: 'user',
    permissions: [],
    place: 'end',
  },
];

/** The entries of the phone bar, in bar order; the others sit in the "Mehr" sheet. */
export const BOTTOM_BAR_KEYS: readonly NavKey[] = ['tasks', 'pipeline', 'calendar', 'archive'];

@Injectable({ providedIn: 'root' })
export class NavService {
  private readonly auth = inject(AuthService);

  readonly visible = computed<NavItem[]>(() =>
    this.auth.isAuthenticated()
      ? NAV_ITEMS.filter((item) => this.auth.canAny(...item.permissions))
      : [],
  );
}
