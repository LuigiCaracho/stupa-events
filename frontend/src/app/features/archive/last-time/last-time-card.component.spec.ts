import { provideRouter } from '@angular/router';
import { render, screen } from '@testing-library/angular';
import { runAxe } from '../../../../testing/a11y';
import { makeLastTime } from '../../../../testing/m5-fixtures';
import { LastTimeCardComponent } from './last-time-card.component';

describe('LastTimeCardComponent', () => {
  const providers = [provideRouter([])];

  it('shows attendance and costs of the earlier edition and links to the dossier', async () => {
    await render(LastTimeCardComponent, { inputs: { lastTime: makeLastTime() }, providers });
    expect(screen.getByText('87')).toBeInTheDocument();
    expect(screen.getByText(/245,00/)).toBeInTheDocument();
    expect(screen.getByText(/130,00/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Movienight SoSe26' })).toHaveAttribute('href', '/dossiers/tpl-1');
  });

  it('links an edition of another organization to the archive page and hides costs when restricted', async () => {
    const lastTime = makeLastTime({
      source: { ...makeLastTime().source, own: false },
      costsCents: null,
      revenueCents: null,
      restricted: true,
    });
    await render(LastTimeCardComponent, { inputs: { lastTime }, providers });
    expect(screen.getByRole('link', { name: 'Movienight SoSe26' })).toHaveAttribute('href', '/archiv/tpl-1');
    expect(screen.queryByText('Kosten (Ist)')).not.toBeInTheDocument();
    expect(
      screen.getByText('Angebote und Businesspläne bleiben bei der ursprünglichen Organisation.'),
    ).toBeInTheDocument();
  });

  it('offers the retrospective and the notes when they exist, and a dash without attendance', async () => {
    const lastTime = makeLastTime({
      attendance: null,
      notes: 'Popcorn knapp',
      retrospective: { id: 'r1', rev: 1, bodyMd: 'Gut gelaufen' },
    });
    await render(LastTimeCardComponent, { inputs: { lastTime, linked: false }, providers });
    expect(screen.getByText('Popcorn knapp')).toBeInTheDocument();
    expect(screen.getByText('Rückblick der letzten Ausgabe')).toBeInTheDocument();
    expect(screen.getByText('–')).toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const { container } = await render(LastTimeCardComponent, {
      inputs: { lastTime: makeLastTime() },
      providers,
    });
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
