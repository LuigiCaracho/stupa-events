/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/layout/nav-rail/nav-rail.component.spec.ts (rewritten) */
/** Spec for the M1 navigation rail. */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { render, screen } from '@testing-library/angular';
import { AuthService } from '@core/auth/auth.service';
import { runAxe } from '../../../testing/a11y';
import { createLocationMock, provideLocationMock } from '../../../testing/location-mock';
import { NavRailComponent } from './nav-rail.component';

async function setup() {
  const view = await render(NavRailComponent, {
    providers: [
      provideRouter([]),
      provideHttpClient(),
      provideHttpClientTesting(),
      provideLocationMock(createLocationMock()),
    ],
  });
  const injector = view.fixture.debugElement.injector;
  injector.get(AuthService).ensureLoaded().subscribe();
  injector
    .get(HttpTestingController)
    .expectOne('/api/auth/me')
    .flush({ sub: '1', roles: [], permissions: [], groups: [], organizations: [] });
  view.fixture.detectChanges();
  return view;
}

describe('NavRailComponent', () => {
  it('names the brand mark after the app and links it to the task page', async () => {
    await setup();
    expect(screen.getByRole('link', { name: 'STUPA Events, Start' })).toHaveAttribute('href', '/aufgaben');
  });

  it('lists the areas in rail order with Konto at the foot', async () => {
    const { container } = await setup();
    const labels = Array.from(container.querySelectorAll('.rail__label')).map((l) => l.textContent?.trim());
    expect(labels).toEqual(['Aufgaben', 'Dossiers', 'Konto']);
    expect(container.querySelector('.rail__spacer + a')).toHaveTextContent('Konto');
  });

  it('has no axe violations', async () => {
    const { container } = await setup();
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
