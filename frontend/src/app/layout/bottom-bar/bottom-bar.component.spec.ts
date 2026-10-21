/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/layout/bottom-bar/bottom-bar.component.spec.ts (rewritten) */
/** Spec for the M1 bottom bar. */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { render, screen, within } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
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
  it('shows Events, Archiv, Formate and Bibliothek with their paths, then Mehr and the bell', async () => {
    await setup();
    const bar = screen.getByRole('navigation', { name: 'Hauptnavigation' });
    const labels = Array.from(bar.querySelectorAll('.bb__label')).map((l) => l.textContent?.trim());
    expect(labels).toEqual(['Events', 'Archiv', 'Formate', 'Bibliothek', 'Mehr', 'Meldungen']);
    expect(within(bar).getByRole('link', { name: 'Events' })).toHaveAttribute('href', '/dossiers');
    expect(within(bar).getByRole('link', { name: 'Formate' })).toHaveAttribute('href', '/formate');
    expect(within(bar).getByRole('link', { name: 'Archiv' })).toHaveAttribute('href', '/archiv');
  });

  it('opens a sheet with Konto behind "Mehr"', async () => {
    await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Mehr' }));
    const sheet = await screen.findByRole('dialog', { name: 'Mehr' });
    const links = within(sheet).getAllByRole('link');
    expect(links.map((l) => l.textContent?.trim())).toEqual(['Konto']);
    expect(links.map((l) => l.getAttribute('href'))).toEqual(['/konto']);
    await userEvent.click(within(sheet).getByRole('button', { name: 'Schließen' }));
    expect(screen.queryByRole('dialog', { name: 'Mehr' })).not.toBeInTheDocument();
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
