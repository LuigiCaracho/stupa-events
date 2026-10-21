import { HttpErrorResponse } from '@angular/common/http';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { makeFormat } from '../../../../testing/m5-fixtures';
import { FormatsApi } from '../../formats/api/formats-api.service';
import { FormatSaveDialogComponent } from './format-save-dialog.component';

async function setup(saveAsFormat = jest.fn(() => of(makeFormat()))) {
  const saved = jest.fn();
  const closed = jest.fn();
  const view = await render(FormatSaveDialogComponent, {
    inputs: { eventId: 'ev-1', suggestedTitle: 'Hüttencafé Größe' },
    providers: [{ provide: FormatsApi, useValue: { saveAsFormat } }],
    on: { saved, closed },
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { view, saveAsFormat, saved, closed };
}

describe('FormatSaveDialogComponent', () => {
  it('suggests the title and a slug that follows it', async () => {
    await setup();
    expect(await screen.findByDisplayValue('Hüttencafé Größe')).toBeInTheDocument();
    expect(screen.getByDisplayValue('huettencafe-groesse')).toBeInTheDocument();
  });

  it('saves with slug and title and reports the format', async () => {
    const { saveAsFormat, saved } = await setup();
    await screen.findByDisplayValue('Hüttencafé Größe');
    await userEvent.click(screen.getByRole('button', { name: 'Format anlegen' }));
    expect(saveAsFormat).toHaveBeenCalledWith('ev-1', { slug: 'huettencafe-groesse', title: 'Hüttencafé Größe' });
    expect(saved).toHaveBeenCalledWith(expect.objectContaining({ slug: 'movienight' }));
  });

  it('stops following the title once the slug was edited by hand', async () => {
    await setup();
    const slug = await screen.findByLabelText(/Kürzel/);
    await userEvent.clear(slug);
    await userEvent.type(slug, 'cafe');
    await userEvent.type(screen.getByLabelText(/Name des Formats/), ' 2');
    expect(slug).toHaveValue('cafe');
  });

  it('refuses a slug with capitals and spaces without a request', async () => {
    const { saveAsFormat } = await setup();
    const slug = await screen.findByLabelText(/Kürzel/);
    await userEvent.clear(slug);
    await userEvent.type(slug, 'Mein Format');
    await userEvent.click(screen.getByRole('button', { name: 'Format anlegen' }));
    expect(await screen.findByText(/darf nur Kleinbuchstaben/)).toBeInTheDocument();
    expect(saveAsFormat).not.toHaveBeenCalled();
  });

  it('says when the slug is taken', async () => {
    await setup(
      jest.fn(() => throwError(() => new HttpErrorResponse({ status: 409, error: { status: 409, code: 'slug_taken' } }))),
    );
    await screen.findByDisplayValue('Hüttencafé Größe');
    await userEvent.click(screen.getByRole('button', { name: 'Format anlegen' }));
    expect(await screen.findByText('Dieses Kürzel gibt es schon.')).toBeInTheDocument();
  });

  it('closes with Abbrechen', async () => {
    const { closed } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
    expect(closed).toHaveBeenCalled();
  });

  it('has no axe violations', async () => {
    const { view } = await setup();
    await screen.findByDisplayValue('Hüttencafé Größe');
    expect(await runAxe(view.container)).toHaveNoViolations();
  });

  it('shows the message of any other refusal and keeps the dialog', async () => {
    const { saved } = await setup(
      jest.fn(() => throwError(() => new HttpErrorResponse({ status: 403, error: { status: 403, code: 'forbidden' } }))),
    );
    await screen.findByDisplayValue('Hüttencafé Größe');
    await userEvent.click(screen.getByRole('button', { name: 'Format anlegen' }));
    expect(saved).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});
