import { render, screen, within } from '@testing-library/angular';
import { runAxe } from '../../../../testing/a11y';
import { makePreview } from '../../../../testing/m5-fixtures';
import type { CarryOverLine } from '../model/archive.models';
import { CarryOverListComponent } from './carry-over-list.component';

describe('CarryOverListComponent', () => {
  it('lists the four groups in order with parts and reasons from the table', async () => {
    const { container } = await render(CarryOverListComponent, {
      inputs: { report: makePreview().report },
    });
    const headings = Array.from(container.querySelectorAll('h4')).map((h) => h.textContent?.trim());
    expect(headings).toEqual([
      'Wird übernommen',
      'Wird übernommen und zurückgesetzt',
      'Wird teilweise übernommen',
      'Bleibt verlinkt',
      'Wird nicht übernommen',
    ]);
    expect(screen.getByText('Poster')).toBeInTheDocument();
    expect(screen.getByText('Poster: Datum im Bild, bitte neu gestalten')).toBeInTheDocument();
    expect(screen.getByText('Checkliste (6)')).toBeInTheDocument();
    expect(screen.getByText('Ortstext')).toBeInTheDocument();
    expect(screen.getByText('Der Ort muss neu bestätigt werden.')).toBeInTheDocument();
    expect(screen.getByText('Bleibt in der Vorlage und ist dort verlinkt.')).toBeInTheDocument();
  });

  it('leaves out an empty group', async () => {
    const report: CarryOverLine[] = [{ part: 'title', mode: 'copy', reason: 'clone.reason.title' }];
    const { container } = await render(CarryOverListComponent, { inputs: { report } });
    expect(container.querySelectorAll('section')).toHaveLength(1);
  });

  it('shows the raw name of a part and no reason for an unknown key', async () => {
    const { container } = await render(CarryOverListComponent, {
      inputs: { report: [{ part: 'new_thing', mode: 'never', reason: 'clone.reason.unknown_reason' }] },
    });
    const row = container.querySelector('.co__row') as HTMLElement;
    expect(within(row).getByText('new_thing')).toBeInTheDocument();
    expect(row.querySelector('.co__reason')).toBeNull();
  });

  it('has no axe violations', async () => {
    const { container } = await render(CarryOverListComponent, {
      inputs: { report: makePreview().report },
    });
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
