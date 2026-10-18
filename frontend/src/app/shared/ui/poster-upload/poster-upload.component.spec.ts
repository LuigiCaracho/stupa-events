import { fireEvent, render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../testing/a11y';
import { PosterUploadComponent } from './poster-upload.component';

const png = new File(['png'], 'plakat.png', { type: 'image/png' });

describe('PosterUploadComponent', () => {
  async function setup() {
    const submitted = jest.fn();
    const view = await render(PosterUploadComponent, { on: { submitted } });
    const picker = view.container.querySelector('input[type="file"]') as HTMLInputElement;
    return { view, submitted, picker };
  }

  it('asks for file, alt text, credit and rights before it emits', async () => {
    const { submitted } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Poster hochladen' }));
    expect(submitted).not.toHaveBeenCalled();
    expect(screen.getByText('Bitte wähle eine Datei.')).toBeInTheDocument();
    expect(screen.getByText('Alt-Text fehlt.')).toBeInTheDocument();
    expect(screen.getByText('Credit fehlt.')).toBeInTheDocument();
    expect(screen.getByText('Bitte wähle eine Rechtegrundlage.')).toBeInTheDocument();
  });

  it('emits the file with the trimmed texts and the chosen rights basis', async () => {
    const { submitted, picker } = await setup();
    await userEvent.upload(picker, png);
    expect(screen.getByRole('status')).toHaveTextContent('Gewählt: plakat.png');
    await userEvent.type(screen.getByLabelText(/Alt-Text/), '  Plakat der Movienight ');
    await userEvent.type(screen.getByLabelText(/Credit/), 'Max Muster');
    await userEvent.click(screen.getByRole('combobox', { name: /Rechtegrundlage/ }));
    await userEvent.click(screen.getByRole('option', { name: 'Eigenes Werk' }));
    await userEvent.click(screen.getByRole('button', { name: 'Poster hochladen' }));
    expect(submitted).toHaveBeenCalledWith({
      file: png,
      altText: 'Plakat der Movienight',
      credit: 'Max Muster',
      rightsBasis: 'own_work',
      personsDepicted: false,
      consentNote: '',
    });
  });

  it('asks for the consent note when people are recognisable and sends it', async () => {
    const { submitted, picker } = await setup();
    await userEvent.upload(picker, png);
    await userEvent.type(screen.getByLabelText(/Alt-Text/), 'Plakat');
    await userEvent.type(screen.getByLabelText(/Credit/), 'Max');
    await userEvent.click(screen.getByRole('combobox', { name: /Rechtegrundlage/ }));
    await userEvent.click(screen.getByRole('option', { name: 'Eigenes Werk' }));
    expect(screen.queryByLabelText(/Einwilligung/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('checkbox', { name: 'Personen sind erkennbar' }));
    await userEvent.click(screen.getByRole('button', { name: 'Poster hochladen' }));
    expect(screen.getByText('Die Einwilligung fehlt.')).toBeInTheDocument();
    expect(submitted).not.toHaveBeenCalled();
    await userEvent.type(screen.getByLabelText(/Einwilligung/), ' schriftlich ');
    await userEvent.click(screen.getByRole('button', { name: 'Poster hochladen' }));
    expect(submitted).toHaveBeenCalledWith(
      expect.objectContaining({ personsDepicted: true, consentNote: 'schriftlich' }),
    );
  });

  it('rejects a file of the wrong type with an alert', async () => {
    const { view } = await setup();
    const zone = view.container.querySelector('.fdz') as HTMLElement;
    fireEvent.drop(zone, {
      dataTransfer: { files: [new File(['x'], 'a.pdf', { type: 'application/pdf' })] },
    });
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Dieses Format wird nicht angenommen',
    );
  });

  it('has no axe violations', async () => {
    const { view } = await setup();
    expect(await runAxe(view.container)).toHaveNoViolations();
  });
});
