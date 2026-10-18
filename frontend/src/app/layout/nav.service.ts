/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/layout/nav.service.ts (rewritten) */
/**
 * Navigation model of the signed-in frame. Rewritten from the workflow tool: the workflow entries are gone, M1 has Aufgaben,
 * Dossiers and Konto. The filter is UX only; route guards and the server stay authoritative.
 */
import { Injectable, computed, inject } from '@angular/core';
import { AuthService } from '@core/auth/auth.service';
import type { TranslationKey } from '@core/i18n/translations';
import type { IconName } from '@stupa-makers/ui-kit';

export type NavKey = 'tasks' | 'dossiers' | 'account';

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
  { key: 'tasks', path: '/aufgaben', labelKey: 'nav.tasks', icon: 'tasks', permissions: [], place: 'main' },
  { key: 'dossiers', path: '/dossiers', labelKey: 'nav.dossiers', icon: 'kanban', permissions: [], place: 'main' },
  { key: 'account', path: '/konto', labelKey: 'nav.account', icon: 'user', permissions: [], place: 'end' },
];

/** The entries of the phone bar, in bar order. M1 has so few that all fit. */
export const BOTTOM_BAR_KEYS: readonly NavKey[] = ['tasks', 'dossiers', 'account'];

@Injectable({ providedIn: 'root' })
export class NavService {
  private readonly auth = inject(AuthService);

  readonly visible = computed<NavItem[]>(() =>
    this.auth.isAuthenticated()
      ? NAV_ITEMS.filter((item) => this.auth.canAny(...item.permissions))
      : [],
  );
}
