import { DeferBlockBehavior } from '@angular/core/testing';
import { render, screen, waitFor } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../testing/a11y';
import { MediaApiService } from '@shared/markdown/media-api.service';
import { DossierMarkdownEditorComponent } from './dossier-markdown-editor.component';

async function setup(inputs: Record<string, unknown> = {}) {
  const selected = jest.fn();
  const view = await render(DossierMarkdownEditorComponent, {
    inputs: { label: 'Anleitung', value: '# Hallo', ...inputs },
    on: { selected },
    deferBlockBehavior: DeferBlockBehavior.Playthrough,
    providers: [{ provide: MediaApiService, useValue: { uploadImage: jest.fn() } }],
  });
  return { ...view, value: () => view.fixture.componentInstance.value(), selected };
}

describe('DossierMarkdownEditorComponent', () => {
  it('starts in the source mode while the roundtrip gate is red, with a preview', async () => {
    const { container } = await setup();
    const area = screen.getByRole('textbox', { name: 'Anleitung' });
    expect(area).toHaveValue('# Hallo');
    expect(screen.getByText('Vorschau')).toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it('emits what is typed', async () => {
    const { value } = await setup({ value: '' });
    await userEvent.type(screen.getByRole('textbox', { name: 'Anleitung' }), 'abc');
    expect(value()).toBe('abc');
    expect(screen.queryByText('Vorschau')).toBeInTheDocument();
  });

  it('reports a selection of the source and clears it', async () => {
    const { selected } = await setup({ value: 'Hallo Welt' });
    const area = screen.getByRole('textbox', { name: 'Anleitung' }) as HTMLTextAreaElement;
    area.setSelectionRange(0, 5);
    area.dispatchEvent(new Event('select'));
    expect(selected).toHaveBeenLastCalledWith({ from: 0, to: 5 });
    area.setSelectionRange(2, 2);
    area.dispatchEvent(new Event('select'));
    expect(selected).toHaveBeenLastCalledWith(null);
  });

  it('inserts text at the cursor of the source', async () => {
    const { fixture, value } = await setup({ value: 'Hallo  Welt' });
    const area = screen.getByRole('textbox', { name: 'Anleitung' }) as HTMLTextAreaElement;
    area.setSelectionRange(6, 6);
    fixture.componentInstance.insertText('{{ org.name }}');
    expect(value()).toBe('Hallo {{ org.name }} Welt');
  });

  it('switches from the rich editor to the source to insert text', async () => {
    const { fixture, value } = await setup({ value: '' });
    await userEvent.click(screen.getByRole('radio', { name: 'Editor' }));
    await screen.findByRole('toolbar', { name: 'Formatierung' });
    fixture.componentInstance.insertText('{{ event.title }}');
    expect(value()).toBe('{{ event.title }}');
    expect(await screen.findByRole('textbox', { name: 'Anleitung' })).toBeInTheDocument();
  });

  it('ignores a selection event without a textarea', async () => {
    const { fixture, selected } = await setup({ value: '' });
    await userEvent.click(screen.getByRole('radio', { name: 'Editor' }));
    (fixture.componentInstance as unknown as { select(): void }).select();
    expect(selected).toHaveBeenLastCalledWith(null);
  });

  it('is read-only when disabled', async () => {
    await setup({ disabled: true });
    expect(screen.getByRole('textbox', { name: 'Anleitung' })).toBeDisabled();
  });

  it('switches to the rich editor and back', async () => {
    await setup({ value: '' });
    await userEvent.click(screen.getByRole('radio', { name: 'Editor' }));
    expect(await screen.findByRole('toolbar', { name: 'Formatierung' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('radio', { name: 'Quelltext' }));
    expect(screen.getByRole('textbox', { name: 'Anleitung' })).toBeInTheDocument();
  });

  it('falls back to the source with a note when Tiptap would change the text', async () => {
    await setup({ value: 'Zeile eins\nZeile zwei\n' });
    await userEvent.click(screen.getByRole('radio', { name: 'Editor' }));
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('nicht verlustfrei'));
    expect(screen.getByRole('textbox', { name: 'Anleitung' })).toHaveValue(
      'Zeile eins\nZeile zwei\n',
    );
  });
});
