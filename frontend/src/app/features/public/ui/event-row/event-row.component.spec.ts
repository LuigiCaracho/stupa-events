/** Spec for the event row: link, time and place, state as text, category tag, thumbnail only on request. */
import { provideRouter } from '@angular/router';
import { render, screen } from '@testing-library/angular';
import { runAxe } from '../../../../../testing/a11y';
import { card } from '../../../../../testing/public-fixtures';
import { EventRowComponent } from './event-row.component';

const setup = (inputs: Record<string, unknown>) =>
  render(EventRowComponent, { inputs, providers: [provideRouter([])] });

describe('EventRowComponent', () => {
  it('links the title to the event and shows time and place in Berlin time', async () => {
    await setup({ card: card() });
    expect(screen.getByRole('link', { name: 'Movienight: Arrival' })).toHaveAttribute(
      'href',
      '/e/movienight',
    );
    expect(screen.getByText(/20:00 · Kinosaal/)).toBeInTheDocument();
  });

  it('says "ganztägig" for an all-day event', async () => {
    await setup({ card: card({ allDay: true }) });
    expect(screen.getByText(/ganztägig · Kinosaal/)).toBeInTheDocument();
  });

  it('shows cancelled and postponed as text', async () => {
    const view = await setup({ card: card({ status: 'cancelled' }) });
    expect(screen.getByText('Abgesagt')).toBeInTheDocument();
    view.fixture.componentRef.setInput('card', card({ status: 'postponed' }));
    view.fixture.detectChanges();
    expect(screen.getByText('Verschoben')).toBeInTheDocument();
  });

  it('shows no thumbnail by default', async () => {
    const without = await setup({ card: card() });
    expect(without.container.querySelector('img')).toBeNull();
  });

  it('shows a thumbnail with its size with `thumb`', async () => {
    const withThumb = await setup({ card: card(), thumb: true });
    const img = withThumb.container.querySelector('img') as HTMLImageElement;
    expect(img).toHaveAttribute('width', '400');
    expect(img).toHaveAttribute('height', '210');
  });

  it('has no axe violations', async () => {
    const { container } = await setup({ card: card({ status: 'cancelled' }), thumb: true });
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
