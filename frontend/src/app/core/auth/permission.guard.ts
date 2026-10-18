/**
 * Route guard factory for permission-gated areas (`verwaltung/*`). Runs after `authGuard`
 * and sends a principal without any of the permissions to `/forbidden`. UX only: the
 * server answers 403 on every route anyway.
 */
import { inject } from '@angular/core';
import { type CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs/operators';
import { AuthService } from './auth.service';

/**
 * Builds a guard that lets a principal pass with at least one of the permissions.
 *
 * Args:
 *   permissions: Permission names; `admin` passes through `AuthService.can`.
 *
 * Returns:
 *   A `CanActivateFn` that redirects to `/forbidden` on refusal.
 */
export const permissionGuard =
  (...permissions: string[]): CanActivateFn =>
  () => {
    const auth = inject(AuthService);
    const router = inject(Router);
    return auth
      .ensureLoaded()
      .pipe(map(() => auth.canAny(...permissions) || router.createUrlTree(['/forbidden'])));
  };
