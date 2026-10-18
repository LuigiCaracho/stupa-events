/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/core/auth/auth.guard.ts */
import { inject } from '@angular/core';
import { type CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs/operators';
import { ToastService } from '@stupa-makers/ui-kit';
import { I18nService } from '@core/i18n/i18n.service';
import { AuthService } from './auth.service';

/**
 * Protects OIDC routes. The guard loads the principal once through `ensureLoaded`, then
 * decides synchronously.
 *
 * No session: start the OIDC login with a full redirect and cancel the navigation. The
 * login returns to the URL of that navigation. A login that just came back without a
 * session goes home with an error toast instead, so a failing `/auth/me` cannot loop.
 *
 * With `route.data.permission` set and no matching permission, the guard sends the user
 * to `/forbidden`. RBAC here is only UX. The server stays authoritative.
 */
export const authGuard: CanActivateFn = (route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const toast = inject(ToastService);
  const i18n = inject(I18nService);

  return auth.ensureLoaded().pipe(
    map((principal) => {
      if (!principal) {
        if (auth.loginJustFailed()) {
          toast.error(i18n.translate('auth.loginFailed'));
          return router.createUrlTree(['/login']);
        }
        auth.login(state?.url);
        return false;
      }
      const permission = route.data['permission'] as string | string[] | undefined;
      const required = permission === undefined ? [] : ([] as string[]).concat(permission);
      if (required.length > 0 && !auth.canAny(...required)) {
        toast.error(i18n.translate('rbac.forbidden'));
        return router.createUrlTree(['/forbidden']);
      }
      return true;
    }),
  );
};
