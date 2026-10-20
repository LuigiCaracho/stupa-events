/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/layout/bottom-bar/bottom-bar.component.spec.ts (rewritten) */
/** Spec for the M1 bottom bar. */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { render, screen, within } from '@testing-library/angular';
import { AuthService } from '@core/auth/auth.service';
import { runAxe } from '../../../testing/a11y';
import { createLocationMock, provideLocationMock } from '../../../testing/location-mock';
import { BottomBarComponent } from './bottom-bar.component';

async function setup(signedIn = true) {
  const view = await render(BottomBarComponent, {
    providers: [
      provideRouter([]),
      provideHttpClient(),
      provideHttpClientTesting(),
      provideLocationMock(createLocationMock()),
    ],
  });
  const injector = view.fixture.debugElement.injector;
  injector.get(AuthService).ensureLoaded().subscribe();
  const req = injector.get(HttpTestingController).expectOne('/api/auth/me');
  if (signedIn) req.flush({ sub: '1', roles: [], permissions: [], groups: [], organizations: [] });
  else req.flush(null, { status: 401, statusText: 'Unauthorized' });
  view.fixture.detectChanges();
  return view;
}

describe('BottomBarComponent', () => {
  it('shows Aufgaben, Pipeline, Dossiers and Konto with their paths', async () => {
    await setup();
    const bar = screen.getByRole('navigation', { name: 'Hauptnavigation' });
    const labels = Array.from(bar.querySelectorAll('.bb__label')).map((l) => l.textContent?.trim());
    expect(labels).toEqual(['Aufgaben', 'Pipeline', 'Dossiers', 'Konto', 'Meldungen']);
    expect(within(bar).getByRole('link', { name: 'Aufgaben' })).toHaveAttribute(
      'href',
      '/aufgaben',
    );
    expect(within(bar).getByRole('link', { name: 'Konto' })).toHaveAttribute('href', '/konto');
  });

  it('shows no entry without a session', async () => {
    const { container } = await setup(false);
    expect(container.querySelectorAll('.bb__item')).toHaveLength(0);
  });

  it('has no axe violations', async () => {
    const { container } = await setup();
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
