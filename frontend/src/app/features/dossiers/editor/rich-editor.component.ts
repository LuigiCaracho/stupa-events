/**
 * The Tiptap editor of the ui-kit with a small toolbar. Only this file imports the kit's secondary entry; the shell
 * loads it with `@defer`, so Tiptap lands in a lazy chunk. After mounting it reports whether the text came back
 * unchanged (E20 per-document check), so the shell can fall back to the source mode.
 */
import {
  ChangeDetectionStrategy,
  Component,
  Injector,
  afterNextRender,
  inject,
  input,
  output,
  viewChild,
} from '@angular/core';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { roundtripsExactly } from '@shared/markdown/kit-roundtrip';
import { MediaApiService } from '@shared/markdown/media-api.service';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import {
  MarkdownEditorComponent,
  type MarkdownFormat,
  type MarkdownImageUploader,
} from '@stupa-makers/ui-kit/markdown-editor';

const FORMATS: readonly {
  format: MarkdownFormat;
  label: 'editor.bold' | 'editor.italic' | 'editor.heading' | 'editor.list';
}[] = [
  { format: 'heading', label: 'editor.heading' },
  { format: 'bold', label: 'editor.bold' },
  { format: 'italic', label: 'editor.italic' },
  { format: 'bulletList', label: 'editor.list' },
];

@Component({
  selector: 'app-rich-editor',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, ButtonComponent, MarkdownEditorComponent],
  templateUrl: './rich-editor.component.html',
  styleUrl: './rich-editor.component.scss',
})
export class RichEditorComponent {
  private readonly media = inject(MediaApiService);
  private readonly injector = inject(Injector);

  readonly value = input.required<string>();
  readonly docKey = input('');
  readonly disabled = input(false);
  readonly placeholder = input('');

  readonly valueChange = output<string>();
  readonly lossless = output<boolean>();

  protected readonly editor = viewChild.required(MarkdownEditorComponent);
  protected readonly formats = FORMATS;

  protected readonly upload: MarkdownImageUploader = (file) =>
    new Promise((resolve, reject) =>
      this.media.uploadImage(file).subscribe({
        next: (img) => resolve({ src: img.url, alt: file.name }),
        error: reject,
      }),
    );

  constructor() {
    afterNextRender(() => this.lossless.emit(roundtripsExactly(this.editor(), this.value())), {
      injector: this.injector,
    });
  }

  protected toggle(format: MarkdownFormat): void {
    this.editor().toggleFormat(format);
  }

  protected pressed(format: MarkdownFormat): boolean {
    return this.editor().activeFormats().has(format);
  }
}
