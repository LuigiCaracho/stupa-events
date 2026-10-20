import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { MediaApiService } from '@shared/markdown/media-api.service';
import { of, throwError } from 'rxjs';
import { RichEditorComponent } from './rich-editor.component';

async function setup(value: string, uploadImage = jest.fn()) {
  const lossless = jest.fn();
  const view = await render(RichEditorComponent, {
    inputs: { value, docKey: 'k' },
    on: { lossless },
    providers: [{ provide: MediaApiService, useValue: { uploadImage } }],
  });
  view.fixture.detectChanges();
  return { ...view, lossless };
}

describe('RichEditorComponent', () => {
  it('reports that a text Tiptap writes back unchanged is lossless', async () => {
    const { lossless } = await setup('## Titel\n\nText');
    expect(lossless).toHaveBeenCalledWith(true);
    expect(screen.getByRole('toolbar', { name: 'Formatierung' })).toBeInTheDocument();
  });

  it('reports a text with a trailing newline as not lossless', async () => {
    expect((await setup('Text\n')).lossless).toHaveBeenCalledWith(false);
  });

  it('reports a task list as not lossless', async () => {
    expect((await setup('- [ ] Aufgabe')).lossless).toHaveBeenCalledWith(false);
  });

  it('toggles a format and shows it as pressed', async () => {
    const { fixture } = await setup('Text');
    const bold = screen.getByRole('button', { name: 'Fett' });
    expect(bold).toHaveAttribute('aria-pressed', 'false');
    await userEvent.click(bold);
    fixture.detectChanges();
    expect(screen.getByRole('button', { name: 'Fett' })).toBeInTheDocument();
  });

  it('uploads an image through the media service', async () => {
    const uploadImage = jest.fn(() =>
      of({
        id: 'i1',
        url: '/api/media/images/i1',
        mime: 'image/png',
        width: 1,
        height: 1,
        size: 1,
      }),
    );
    const { fixture } = await setup('Text', uploadImage);
    const upload = (
      fixture.componentInstance as unknown as { upload: (f: File) => Promise<unknown> }
    ).upload;
    await expect(upload(new File(['x'], 'bild.png', { type: 'image/png' }))).resolves.toEqual({
      src: '/api/media/images/i1',
      alt: 'bild.png',
    });
    uploadImage.mockReturnValueOnce(throwError(() => new Error('x')) as never);
    await expect(upload(new File(['x'], 'bild.png'))).rejects.toThrow('x');
  });
});
