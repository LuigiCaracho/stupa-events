/**
 * The editor shell of the dossier (E20, contract 6.2): a switch "Editor | Quelltext" over one Markdown value. The mode
 * starts from the roundtrip gate (`roundtrip-gate.json`); an existing text that Tiptap would not write back unchanged
 * opens in the source mode with a note. Markdown is always what is stored. The source mode is a textarea with image
 * upload and a preview; the rich mode is lazy (`@defer`), so Tiptap stays out of the initial bundle.
 */
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  input,
  model,
  inject,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { MarkdownImageUploadDirective } from '@shared/markdown/markdown-image-upload.directive';
import { MarkdownViewComponent } from '@shared/markdown/markdown-view.component';
import { RICH_EDITOR_DEFAULT } from '@shared/markdown/roundtrip-gate';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SegmentedComponent } from '@stupa-makers/ui-kit';
import { RichEditorComponent } from './rich-editor.component';

export interface SourceSelection {
  from: number;
  to: number;
}

let nextId = 0;

type Mode = 'editor' | 'source';

@Component({
  selector: 'app-dossier-markdown-editor',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    MarkdownImageUploadDirective,
    MarkdownViewComponent,
    NoteComponent,
    RichEditorComponent,
    SegmentedComponent,
  ],
  templateUrl: './dossier-markdown-editor.component.html',
  styleUrl: './dossier-markdown-editor.component.scss',
})
export class DossierMarkdownEditorComponent {
  readonly value = model('');
  readonly docKey = input('');
  readonly label = input.required<string>();
  readonly disabled = input(false);
  readonly placeholder = input('');

  readonly selected = output<SourceSelection | null>();

  protected readonly labelId = `dme-label-${nextId++}`;
  protected readonly mode = signal<Mode>(
    RICH_EDITOR_DEFAULT && !this.value() ? 'editor' : 'source',
  );
  protected readonly lossy = signal(false);
  protected readonly area = viewChild<ElementRef<HTMLTextAreaElement>>('area');

  private readonly i18n = inject(I18nService);
  protected readonly options = computed(() => [
    { value: 'editor', label: this.i18n.translate('editor.modeEditor') },
    { value: 'source', label: this.i18n.translate('editor.modeSource') },
  ]);

  protected setMode(mode: string | null): void {
    this.lossy.set(false);
    this.mode.set(mode === 'editor' ? 'editor' : 'source');
  }

  protected onChecked(lossless: boolean): void {
    if (lossless || this.mode() !== 'editor') return;
    this.lossy.set(true);
    this.mode.set('source');
  }

  protected type(event: Event): void {
    this.value.set((event.target as HTMLTextAreaElement).value);
  }

  /** Puts `text` at the cursor of the source; the rich mode switches to the source first, as it cannot take a cursor insert. */
  insertText(text: string): void {
    if (this.mode() !== 'source') this.setMode('source');
    const el = this.area()?.nativeElement;
    const current = this.value();
    const at = el ? el.selectionStart : current.length;
    const end = el ? el.selectionEnd : current.length;
    this.value.set(current.slice(0, at) + text + current.slice(end));
  }

  protected select(): void {
    const el = this.area()?.nativeElement;
    this.selected.emit(
      el && el.selectionStart !== el.selectionEnd
        ? { from: el.selectionStart, to: el.selectionEnd }
        : null,
    );
  }
}
