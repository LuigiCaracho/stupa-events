/** The tabs of the admin frame with the permission each one needs, and the guard that lands `/verwaltung` on the first allowed one. */
import { inject } from '@angular/core';
import { type CanActivateFn, Router } from '@angular/router';
import { AuthService } from '@core/auth/auth.service';
import type { TranslationKey } from '@core/i18n/translations';
import { map } from 'rxjs/operators';

export interface AdminTab {
  id: string;
  labelKey: TranslationKey;
  permission: string;
}

export const ADMIN_TABS: readonly AdminTab[] = [
  { id: 'kategorien', labelKey: 'admin.tab.categories', permission: 'taxonomy.manage' },
  { id: 'orte', labelKey: 'admin.tab.venues', permission: 'venue.manage' },
  { id: 'organisationen', labelKey: 'admin.tab.organizations', permission: 'taxonomy.manage' },
  { id: 'zuordnungen', labelKey: 'admin.tab.mappings', permission: 'admin.mappings' },
];

export const ADMIN_PERMISSIONS: readonly string[] = [
  ...new Set(ADMIN_TABS.map((t) => t.permission)),
];

/** Redirects `/verwaltung` to the first tab the principal may use, or to `/forbidden`. */
export const adminLandingGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth.ensureLoaded().pipe(
    map(() => {
      const first = ADMIN_TABS.find((t) => auth.can(t.permission));
      return router.createUrlTree(first ? ['/verwaltung', first.id] : ['/forbidden']);
    }),
  );
};
