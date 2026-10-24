/** Spec for the calendar address block: the webcal button, the read-only https field, copy with and without a clipboard. */
import { screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../../testing/a11y';
import { mountPublic, tick } from '../../../../../testing/public-harness';
import { Component } from '@angular/core';
import { ProfileLinksComponent } from './profile-links.component';

@Component({
  standalone: true,
  imports: [ProfileLinksComponent],
  template:
    '<app-profile-links icsUrl="https://x.test/ics/p/T.ics" webcalUrl="webcal://x.test/ics/p/T.ics" />',
})
class HostComponent {}

function setNavigator(value: Partial<Navigator>): void {
  Object.defineProperty(window, 'navigator', { value, configurable: true });
}

describe('ProfileLinksComponent', () => {
  const original = window.navigator;
  afterEach(() => setNavigator(original));

  it('opens the calendar app by webcal and shows the https address read-only', async () => {
    await mountPublic(HostComponent, 'x', '/x');
    expect(screen.getByRole('link', { name: 'In Kalender-App öffnen' })).toHaveAttribute(
      'href',
      'webcal://x.test/ics/p/T.ics',
    );
    const field = screen.getByLabelText('Dein Kalender-Link');
    expect(field).toHaveValue('https://x.test/ics/p/T.ics');
    expect(field).toHaveAttribute('readonly');
    expect(screen.getByText(/Änderungen kommen mit Verzögerung an/)).toBeInTheDocument();
  });

  it('copies the https address', async () => {
    const writeText = jest.fn().mockResolvedValue(undefined);
    setNavigator({ clipboard: { writeText } } as unknown as Navigator);
    await mountPublic(HostComponent, 'x', '/x');
    await userEvent.click(screen.getByRole('button', { name: 'Kopieren' }));
    expect(writeText).toHaveBeenCalledWith('https://x.test/ics/p/T.ics');
  });

  it('asks to mark the address by hand when copying fails', async () => {
    setNavigator({} as Navigator);
    const h = await mountPublic(HostComponent, 'x', '/x');
    await userEvent.click(screen.getByRole('button', { name: 'Kopieren' }));
    await tick(h);
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Link konnte nicht kopiert werden. Markier ihn bitte von Hand.',
    );
  });

  it('has no axe violations', async () => {
    const h = await mountPublic(HostComponent, 'x', '/x');
    expect(await runAxe(h.harness.routeNativeElement as HTMLElement)).toHaveNoViolations();
  });
});
