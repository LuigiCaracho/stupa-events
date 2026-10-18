/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/layout/shell.component.spec.ts (rewritten) */
/** Spec for the shell frames. */
import { Component } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Router, provideRouter, type Routes } from '@angular/router';
import { SwUpdate } from '@angular/service-worker';
import { render, screen } from '@testing-library/angular';
import { AuthService } from '@core/auth/auth.service';
import { createLocationMock, provideLocationMock } from '../../testing/location-mock';
import { ShellComponent } from './shell.component';

@Component({ standalone: true, template: '<h1>Seite</h1>' })
class StubPage {}

const ROUTES: Routes = [
  { path: 'aufgaben', component: StubPage, data: { footer: true } },
  { path: 'login', component: StubPage, data: { chrome: false } },
  { path: 'start', component: StubPage, data: { fab: true } },
];

const PRINCIPAL = { sub: '1', displayName: 'Mia', roles: [], permissions: [], groups: [], organizations: [] };

async function setup(signedIn: boolean | null, url = '/aufgaben') {
  const view = await render(ShellComponent, {
    providers: [
      provideRouter(ROUTES),
      provideHttpClient(),
      provideHttpClientTesting(),
      provideLocationMock(createLocationMock()),
      { provide: SwUpdate, useValue: { isEnabled: false } },
    ],
  });
  const injector = view.fixture.debugElement.injector;
  const auth = injector.get(AuthService);
  const http = injector.get(HttpTestingController);
  auth.ensureLoaded().subscribe();
  if (signedIn !== null) {
    const req = http.expectOne('/api/auth/me');
    if (signedIn) req.flush(PRINCIPAL);
    else req.flush(null, { status: 401, statusText: 'Unauthorized' });
  }
  await injector.get(Router).navigateByUrl(url);
  view.fixture.detectChanges();
  return { ...view, http };
}

describe('ShellComponent', () => {
  it('shows the rail frame with the page for a signed-in principal', async () => {
    const { container } = await setup(true);
    expect(container.querySelector('app-nav-rail')).not.toBeNull();
    expect(container.querySelector('app-public-header')).toBeNull();
    expect(screen.getByRole('heading', { name: 'Seite' })).toBeInTheDocument();
    expect(container.querySelector('app-site-footer')).not.toBeNull();
  });

  it('shows the public frame with header and footer when nobody is signed in', async () => {
    const { container } = await setup(false);
    expect(container.querySelector('app-public-header')).not.toBeNull();
    expect(container.querySelector('app-nav-rail')).toBeNull();
    expect(container.querySelector('app-site-footer')).not.toBeNull();
  });

  it('shows only the page while the session is not known yet (pending)', async () => {
    const { container, http } = await setup(null);
    expect(container.querySelector('app-nav-rail')).toBeNull();
    expect(container.querySelector('app-public-header')).toBeNull();
    http.expectOne('/api/auth/me').flush(PRINCIPAL);
  });

  it('shows only the page on a route with chrome: false (bare)', async () => {
    const { container } = await setup(true, '/login');
    expect(container.querySelector('app-nav-rail')).toBeNull();
    expect(container.querySelector('.frame--bare')).not.toBeNull();
    expect(container.querySelector('app-site-footer')).toBeNull();
  });

  it('leaves the footer out on a work page without footer: true', async () => {
    const { container } = await setup(true, '/start');
    expect(container.querySelector('app-site-footer')).toBeNull();
  });

  it('offers the skip link', async () => {
    await setup(true);
    expect(screen.getByRole('link', { name: 'Zum Inhalt springen' })).toHaveAttribute('href', '#main');
  });
});
