import { provideRouter } from '@angular/router';
import { render, screen } from '@testing-library/angular';
import { runAxe } from '../../../../testing/a11y';
import { makeCard } from '../../../../testing/event-fixtures';
import { TaskSectionComponent } from './task-section.component';

describe('TaskSectionComponent', () => {
  it('shows an h2 with the count and one link per dossier', async () => {
    const { container } = await render(TaskSectionComponent, {
      inputs: {
        heading: 'tasks.mine',
        count: 7,
        cards: [
          makeCard({ id: 'a', title: 'A' }),
          makeCard({ id: 'b', title: 'B', organization: null }),
        ],
      },
      providers: [provideRouter([])],
    });
    expect(screen.getByRole('heading', { level: 2, name: 'Meine Dossiers' })).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'A' })).toHaveAttribute('href', '/dossiers/a');
    expect(screen.getByText(/Ohne Organisation/)).toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it('shows the state or the deadline next to the title on request', async () => {
    const { rerender } = await render(TaskSectionComponent, {
      inputs: {
        heading: 'tasks.mine',
        count: 1,
        cards: [makeCard({ state: 'idea' })],
        showState: true,
      },
      providers: [provideRouter([])],
    });
    expect(screen.getByText('Idee')).toBeInTheDocument();
    await rerender({
      partialUpdate: true,
      inputs: {
        showState: false,
        showDeadline: true,
        cards: [makeCard({ startsAt: '2020-01-01T10:00:00Z' })],
      },
    });
    expect(screen.getByText('läuft schon')).toBeInTheDocument();
  });
});
