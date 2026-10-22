/** Spec for the footer: co-branding line, legal and subscription links, internal login. */
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../testing/a11y';
import { createLocationMock, provideLocationMock } from '../../../testing/location-mock';
import { SiteFooterComponent } from './site-footer.component';

async function setup() {
  const location = createLocationMock();
  const view = await render(SiteFooterComponent, {
    providers: [
      provideRouter([]),
      provideHttpClient(),
      provideHttpClientTesting(),
      provideLocationMock(location),
    ],
  });
  return { ...view, location };
}

describe('SiteFooterComponent', () => {
  it('shows the co-branding line in a labelled footer', async () => {
    await setup();
    expect(screen.getByRole('contentinfo', { name: 'Fußzeile' })).toBeInTheDocument();
    expect(
      screen.getByText('STUPA Events, Studierendenparlament der Hochschule Reutlingen'),
    ).toBeInTheDocument();
  });

  it('links Impressum, Datenschutz and the subscriptions', async () => {
    await setup();
    expect(screen.getByRole('link', { name: 'Impressum' })).toHaveAttribute('href', '/impressum');
    expect(screen.getByRole('link', { name: 'Datenschutz' })).toHaveAttribute(
      'href',
      '/datenschutz',
    );
    expect(screen.getByRole('link', { name: 'Kalender abonnieren' })).toHaveAttribute(
      'href',
      '/abos',
    );
  });

  it('starts the internal login towards the dossier list', async () => {
    const { location } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Intern anmelden' }));
    expect(location.assign).toHaveBeenCalledWith('/api/auth/login?returnTo=%2Fdossiers');
  });

  it('has no axe violations', async () => {
    const { container } = await setup();
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
