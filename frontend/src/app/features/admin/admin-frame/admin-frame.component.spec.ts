import { Component } from '@angular/core';
import { Router, provideRouter } from '@angular/router';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { AuthService } from '@core/auth/auth.service';
import { runAxe } from '../../../../testing/a11y';
import { AdminFrameComponent } from './admin-frame.component';

@Component({ standalone: true, template: 'Seite' })
class StubPage {}

async function setup(permissions: string[], url = '/verwaltung/kategorien') {
  const stub = (path: string) => ({ path, component: StubPage });
  const view = await render(AdminFrameComponent, {
    providers: [
      provideRouter([
        {
          path: 'verwaltung',
          children: [stub('kategorien'), stub('orte'), stub('organisationen'), stub('zuordnungen')],
        },
      ]),
      { provide: AuthService, useValue: { can: (p: string) => permissions.includes(p) } },
    ],
  });
  const router = view.fixture.debugElement.injector.get(Router);
  await router.navigateByUrl(url);
  view.fixture.detectChanges();
  return { ...view, router };
}

describe('AdminFrameComponent', () => {
  it('shows one tab per permitted page, in order', async () => {
    await setup(['taxonomy.manage', 'venue.manage']);
    expect(screen.getAllByRole('tab').map((t) => t.textContent?.trim())).toEqual([
      'Kategorien',
      'Orte',
      'Organisationen',
    ]);
  });

  it('adds the mappings tab for admin.mappings and marks the open tab', async () => {
    await setup(['taxonomy.manage', 'venue.manage', 'admin.mappings'], '/verwaltung/zuordnungen');
    expect(screen.getByRole('tab', { name: 'Zuordnungen' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
  });

  it('navigates on a tab click', async () => {
    const { router } = await setup(['taxonomy.manage', 'venue.manage']);
    await userEvent.click(screen.getByRole('tab', { name: 'Orte' }));
    expect(router.url).toBe('/verwaltung/orte');
  });

  it('has no axe violations', async () => {
    const { container } = await setup(['taxonomy.manage']);
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
