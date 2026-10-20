import { fireEvent, render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../testing/a11y';
import { AttachmentUploadComponent } from './attachment-upload.component';

async function setup(inputs: Record<string, unknown> = {}) {
  const submitted = jest.fn();
  const cancelled = jest.fn();
  const view = await render(AttachmentUploadComponent, { inputs, on: { submitted, cancelled } });
  const drop = (file: File) =>
    userEvent.upload(view.container.querySelector('input[type="file"]') as HTMLInputElement, file);
  return { ...view, submitted, cancelled, drop };
}

const png = new File(['x'], 'bild.png', { type: 'image/png' });
const pdf = new File(['x'], 'plan.pdf', { type: 'application/pdf' });

describe('AttachmentUploadComponent', () => {
  it('asks for the file first', async () => {
    const { submitted } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Hochladen' }));
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(submitted).not.toHaveBeenCalled();
  });

  it('sends a document without the rights block', async () => {
    const { submitted, drop, container } = await setup();
    await drop(pdf);
    expect(screen.getByRole('status')).toHaveTextContent('plan.pdf');
    expect(screen.queryByLabelText(/Alt-Text|Beschreibung des Bildes/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Hochladen' }));
    expect(submitted).toHaveBeenCalledWith(
      expect.objectContaining({ file: pdf, kind: 'other', visibility: 'org' }),
    );
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it('requires alt text, credit, rights basis and the consent note for an image', async () => {
    const { submitted, drop } = await setup({ fixedKind: 'social_post' });
    await drop(png);
    await userEvent.click(screen.getByRole('button', { name: 'Hochladen' }));
    expect(submitted).not.toHaveBeenCalled();
    expect(screen.getAllByRole('alert').length).toBeGreaterThan(0);
  });

  it('sends the rights of an image with people and a date', async () => {
    const { submitted, drop } = await setup({ fixedKind: 'social_post' });
    await drop(png);
    const textboxes = screen.getAllByRole('textbox');
    await userEvent.type(textboxes[0], 'Plakat');
    await userEvent.type(textboxes[1], 'Anna');
    await userEvent.click(screen.getAllByRole('combobox')[1]);
    await userEvent.click(await screen.findByRole('option', { name: /Eigenes Werk/ }));
    await userEvent.click(screen.getByRole('checkbox', { name: /Personen/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Hochladen' }));
    expect(submitted).not.toHaveBeenCalled();
    await userEvent.type(screen.getAllByRole('textbox')[2], 'Einwilligung liegt vor');
    await userEvent.click(screen.getByRole('checkbox', { name: /Datum/ }));
    await userEvent.type(screen.getByRole('spinbutton'), '2025');
    await userEvent.click(screen.getByRole('button', { name: 'Hochladen' }));
    expect(submitted).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: 'social_post',
        altText: 'Plakat',
        credit: 'Anna',
        rightsBasis: 'own_work',
        personsDepicted: true,
        consentNote: 'Einwilligung liegt vor',
        containsDate: true,
        datedFor: 2025,
      }),
    );
  });

  it('hides "Alle Mitglieder" for a business plan and can cancel', async () => {
    const { cancelled } = await setup({ fixedKind: 'business_plan' });
    await userEvent.click(screen.getAllByRole('combobox')[0]);
    expect(await screen.findByRole('option', { name: 'Team' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Alle Mitglieder' })).not.toBeInTheDocument();
    await userEvent.keyboard('{Escape}');
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
    expect(cancelled).toHaveBeenCalled();
  });

  it('says so when a dropped file is not allowed', async () => {
    const { container } = await setup();
    const exe = new File(['x'], 'a.exe', { type: 'application/x-msdownload' });
    fireEvent.drop(container.querySelector('.fdz') as HTMLElement, {
      dataTransfer: { files: [exe] },
    });
    expect(await screen.findByText('Dieser Dateityp ist nicht erlaubt.')).toBeInTheDocument();
  });
});
