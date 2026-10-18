/** Specs for the shell pages: login, account, home, error pages, placeholder. */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { AuthService } from '@core/auth/auth.service';
import { runAxe } from '../../testing/a11y';
import { createLocationMock, provideLocationMock } from '../../testing/location-mock';
import { AccountComponent } from './account/account.component';
import { ForbiddenComponent } from './forbidden.component';
import { HomeComponent } from './home/home.component';
import { LoginComponent } from './login/login.component';
import { NotFoundComponent } from './not-found.component';
import { PlaceholderComponent } from './placeholder/placeholder.component';

function providers(location = createLocationMock()) {
  return [provideRouter([]), provideHttpClient(), provideHttpClientTesting(), provideLocationMock(location)];
}

describe('LoginComponent', () => {
  it('starts the login and returns to the task page', async () => {
    const location = createLocationMock();
    await render(LoginComponent, { providers: providers(location) });
    await userEvent.click(screen.getByRole('button', { name: 'Mit Hochschul-Login anmelden' }));
    expect(location.assign).toHaveBeenCalledWith('/api/auth/login?returnTo=%2Faufgaben');
  });

  it('links to the public page', async () => {
    await render(LoginComponent, { providers: providers() });
    expect(screen.getByRole('link', { name: 'Zur öffentlichen Seite' })).toHaveAttribute('href', '/');
  });

  it('has no axe violations', async () => {
    const { container } = await render(LoginComponent, { providers: providers() });
    expect(await runAxe(container)).toHaveNoViolations();
  });
});

describe('HomeComponent', () => {
  it('offers the login', async () => {
    const location = createLocationMock();
    await render(HomeComponent, { providers: providers(location) });
    await userEvent.click(screen.getByRole('button', { name: 'Mit Hochschul-Login anmelden' }));
    expect(location.assign).toHaveBeenCalled();
  });
});

describe('AccountComponent', () => {
  async function setup() {
    const location = createLocationMock();
    const view = await render(AccountComponent, { providers: providers(location) });
    const injector = view.fixture.debugElement.injector;
    injector.get(AuthService).ensureLoaded().subscribe();
    injector.get(HttpTestingController).expectOne('/api/auth/me').flush({
      sub: '1',
      email: 'mia@hs-reutlingen.de',
      displayName: 'Mia',
      roles: ['organizer'],
      permissions: [],
      groups: ['events-fsi-organizer'],
      organizations: [{ slug: 'fsi', role: 'organizer' }],
    });
    view.fixture.detectChanges();
    return { ...view, location, http: injector.get(HttpTestingController) };
  }

  it('shows name, email, roles and organizations', async () => {
    await setup();
    expect(screen.getByText('Mia')).toBeInTheDocument();
    expect(screen.getByText('mia@hs-reutlingen.de')).toBeInTheDocument();
    expect(screen.getByText('organizer')).toBeInTheDocument();
    expect(screen.getByText('fsi (organizer)')).toBeInTheDocument();
  });

  it('logs out and follows the IdP logout url', async () => {
    const { location, http } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Abmelden' }));
    http.expectOne('/api/auth/logout').flush({ logoutUrl: 'https://idp/out' });
    expect(location.assign).toHaveBeenCalledWith('https://idp/out');
  });
});

describe('error pages and placeholder', () => {
  it.each([
    [ForbiddenComponent, 'Kein Zugriff'],
    [NotFoundComponent, 'Seite nicht gefunden'],
    [PlaceholderComponent, 'Folgt in diesem Meilenstein'],
  ])('%p names itself', async (component, heading) => {
    const { container } = await render(component, { providers: providers() });
    expect(screen.getByText(heading)).toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
