/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/layout/site-footer/site-footer.component.spec.ts (rewritten) */
/** Spec for the M1 footer. */
import { render, screen } from '@testing-library/angular';
import { runAxe } from '../../../testing/a11y';
import { SiteFooterComponent } from './site-footer.component';

describe('SiteFooterComponent', () => {
  it('shows the co-branding line in a labelled footer', async () => {
    await render(SiteFooterComponent);
    expect(screen.getByRole('contentinfo', { name: 'Fußzeile' })).toBeInTheDocument();
    expect(
      screen.getByText('STUPA Events, Studierendenparlament der Hochschule Reutlingen'),
    ).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const { container } = await render(SiteFooterComponent);
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
