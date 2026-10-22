/** Spec for the link that looks like a button. */
import { Component } from '@angular/core';
import { render, screen } from '@testing-library/angular';
import { LinkButtonComponent } from './link-button.component';

@Component({
  standalone: true,
  imports: [LinkButtonComponent],
  template: `<a appLinkButton="fill" size="lg" href="webcal://x/ics/all.ics">Öffnen</a>`,
})
class Host {}

describe('LinkButtonComponent', () => {
  it('stays a real link and carries its look as classes', async () => {
    await render(Host);
    const link = screen.getByRole('link', { name: 'Öffnen' });
    expect(link).toHaveAttribute('href', 'webcal://x/ics/all.ics');
    expect(link).toHaveClass('lb', 'lb--fill', 'lb--lg');
  });
});
