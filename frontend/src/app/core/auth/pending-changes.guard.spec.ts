import type { ActivatedRouteSnapshot, RouterStateSnapshot } from '@angular/router';
import { pendingChangesGuard } from './pending-changes.guard';

const ask = (component: { canLeave?: () => boolean | Promise<boolean> }) =>
  pendingChangesGuard(
    component,
    {} as ActivatedRouteSnapshot,
    {} as RouterStateSnapshot,
    {} as RouterStateSnapshot,
  );

describe('pendingChangesGuard', () => {
  it('lets a page without the question go', () => {
    expect(ask({})).toBe(true);
  });

  it('hands the question to the page', async () => {
    expect(ask({ canLeave: () => false })).toBe(false);
    await expect(ask({ canLeave: () => Promise.resolve(true) })).resolves.toBe(true);
  });
});
