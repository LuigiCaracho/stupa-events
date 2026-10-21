import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { makeFormat } from '../../../../testing/m5-fixtures';
import { FormatEditionsComponent } from './format-editions.component';

describe('FormatEditionsComponent', () => {
  it('lists date, state as text, attendance, actual costs and the howto warning', async () => {
    const editions = makeFormat().editions;
    await render(FormatEditionsComponent, { inputs: { editions } });
    expect(screen.getAllByText('Archiv').length).toBeGreaterThan(0);
    expect(screen.getByText('87')).toBeInTheDocument();
    expect(screen.getByText(/245,00/)).toBeInTheDocument();
    expect(screen.getAllByText('Anleitung ungeprüft')).toHaveLength(1);
  });

  it('shows a dash for the costs of an edition of another organization', async () => {
    const editions = [{ ...makeFormat().editions[0], costsCents: null, foreign: true }];
    await render(FormatEditionsComponent, { inputs: { editions } });
    expect(screen.getAllByText('–').length).toBeGreaterThan(0);
    expect(screen.queryByText(/200,00/)).not.toBeInTheDocument();
  });

  it('emits the edition of a clicked row', async () => {
    const open = jest.fn();
    const editions = makeFormat().editions;
    await render(FormatEditionsComponent, { inputs: { editions }, on: { open } });
    await userEvent.click(screen.getByText('Movienight SoSe26', { exact: false }));
    expect(open).toHaveBeenCalledWith(expect.objectContaining({ id: 'ed-2' }));
  });
});
