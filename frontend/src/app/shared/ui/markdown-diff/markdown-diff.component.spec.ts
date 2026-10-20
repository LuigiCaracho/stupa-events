import { render, screen } from '@testing-library/angular';
import { runAxe } from '../../../../testing/a11y';
import type { DiffOut } from '../../../features/dossiers/model/document.models';
import { MarkdownDiffComponent } from './markdown-diff.component';

const diff: DiffOut = {
  from: 1,
  to: 2,
  added: 1,
  removed: 1,
  lines: [
    { op: 'equal', text: 'gleich', fromLine: 1, toLine: 1 },
    { op: 'remove', text: 'alt', fromLine: 2, toLine: null },
    { op: 'add', text: 'neu', fromLine: null, toLine: 2 },
  ],
};

describe('MarkdownDiffComponent', () => {
  it('shows a sign and a hidden word for every changed line, never colour alone', async () => {
    const { container } = await render(MarkdownDiffComponent, { inputs: { diff } });
    expect(screen.getByRole('status')).toHaveTextContent(
      'Fassung 1 zu 2: 1 Zeilen hinzugefügt, 1 entfernt.',
    );
    const rows = screen.getAllByRole('listitem');
    expect(rows).toHaveLength(3);
    expect(rows[1]).toHaveTextContent('Entfernt:');
    expect(rows[1]).toHaveTextContent('−');
    expect(rows[2]).toHaveTextContent('Hinzugefügt:');
    expect(rows[2]).toHaveTextContent('+');
    expect(rows[0]).not.toHaveTextContent('Unverändert:');
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
