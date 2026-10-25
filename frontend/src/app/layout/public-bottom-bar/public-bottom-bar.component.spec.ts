/** Spec for the phone bottom bar of the public frame. */
import { Router, provideRouter } from '@angular/router';
import { render, screen } from '@testing-library/angular';
import { runAxe } from '../../../testing/a11y';
import { PublicBottomBarComponent } from './public-bottom-bar.component';

async function setup(url: string) {
  const view = await render(PublicBottomBarComponent, {
    providers: [provideRouter([{ path: '**', children: [] }])],
  });
  await view.fixture.debugElement.injector.get(Router).navigateByUrl(url);
  view.fixture.detectChanges();
  return view;
}

describe('PublicBottomBarComponent', () => {
  it('has the four places (search is in the header pill) and links them', async () => {
    await setup('/');
    const links = screen.getAllByRole('link');
    expect(links.map((l) => l.textContent?.trim())).toEqual(['Heute', 'Kalender', 'Karte', 'Abos']);
    expect(links.map((l) => l.getAttribute('href'))).toEqual(['/', '/kalender', '/karte', '/abos']);
  });

  it('marks the open page with aria-current, and Heute only on the start page', async () => {
    await setup('/kalender?month=2026-11');
    expect(screen.getByRole('link', { name: 'Kalender' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'Heute' })).not.toHaveAttribute('aria-current');
  });

  it('is a labelled navigation without axe violations', async () => {
    const { container } = await setup('/abos');
    expect(screen.getByRole('navigation', { name: 'Hauptnavigation' })).toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
