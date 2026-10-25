/** Spec for the public top bar: brand, navigation with the open page, login or "Zum Dossier", appearance toggle. */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Router, provideRouter } from '@angular/router';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { AuthService } from '@core/auth/auth.service';
import { ThemeService } from '@core/theme/theme.service';
import { runAxe } from '../../../testing/a11y';
import { createLocationMock, provideLocationMock } from '../../../testing/location-mock';
import { PublicHeaderComponent } from './public-header.component';

async function setup(url = '/') {
  const location = createLocationMock();
  const view = await render(PublicHeaderComponent, {
    providers: [
      provideRouter([{ path: '**', children: [] }]),
      provideHttpClient(),
      provideHttpClientTesting(),
      provideLocationMock(location),
    ],
  });
  const injector = view.fixture.debugElement.injector;
  await injector.get(Router).navigateByUrl(url);
  view.fixture.detectChanges();
  return {
    ...view,
    location,
    auth: injector.get(AuthService),
    http: injector.get(HttpTestingController),
    theme: injector.get(ThemeService),
  };
}

describe('PublicHeaderComponent', () => {
  it('links the brand to the public start page and shows the site title', async () => {
    const { container } = await setup();
    const brand = container.querySelector('a.pub__brand') as HTMLAnchorElement;
    expect(brand).toHaveAttribute('href', '/');
    expect(brand).toHaveAttribute('aria-label', 'STUPA Events');
    expect(container.querySelector('.pub__title')).toHaveTextContent('STUPA Events');
  });

  it('lists Heute, Suche, Kalender, Karte and Abos and marks the open page', async () => {
    await setup('/suche?q=kino');
    const nav = screen.getByRole('navigation', { name: 'Hauptnavigation' });
    expect(nav.querySelectorAll('a')).toHaveLength(5);
    expect(screen.getByRole('link', { name: 'Suche' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'Heute' })).not.toHaveAttribute('aria-current');
  });

  it('marks Heute only on the start page', async () => {
    await setup('/');
    expect(screen.getByRole('link', { name: 'Heute' })).toHaveAttribute('aria-current', 'page');
  });

  it('starts the sign-in and returns to the dossier list', async () => {
    const { location } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Anmelden' }));
    expect(location.assign).toHaveBeenCalledWith('/api/auth/login?returnTo=%2Fdossiers');
  });

  it('offers "Zum Dossier" instead of the sign-in for a signed-in person', async () => {
    const { auth, http, fixture } = await setup();
    auth.ensureLoaded().subscribe();
    http
      .expectOne('/api/auth/me')
      .flush({ sub: '1', roles: [], permissions: [], groups: [], organizations: [] });
    fixture.detectChanges();
    expect(screen.queryByRole('button', { name: 'Anmelden' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Zum Dossier' })).toHaveAttribute('href', '/dossiers');
  });

  it('toggles the appearance and says which state it is in', async () => {
    const { fixture, theme } = await setup();
    theme.setPreference('light');
    fixture.detectChanges();
    const toggle = screen.getByRole('button', { name: 'Hell oder dunkel umschalten' });
    expect(toggle).toHaveAttribute('aria-pressed', 'false');
    await userEvent.click(toggle);
    expect(theme.resolved()).toBe('dark');
    expect(toggle).toHaveAttribute('aria-pressed', 'true');
  });

  it('opens the search from the pill', async () => {
    const { fixture } = await setup();
    const router = fixture.debugElement.injector.get(Router);
    await userEvent.click(screen.getByRole('button', { name: 'Events suchen' }));
    await fixture.whenStable();
    expect(router.url).toBe('/suche');
  });

  it('has no axe violations', async () => {
    const { container } = await setup();
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
