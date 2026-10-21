/**
 * Editor of one existing document by id (M5): the retrospective of a dossier and the master howto of a format. The
 * editor shell holds the text, a server draft is saved every 15 s, "Speichern" writes a new revision with an optional
 * change note (`PUT` with `If-Match`; a 409 asks to reload). The howto tab of M4 keeps its own variant with questions
 * and the revision list; this one is the plain form of it.
 */
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  untracked,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { TextareaComponent } from '@shared/ui/textarea/textarea.component';
import { ButtonComponent, ToastService } from '@stupa-makers/ui-kit';
import { catchError, of } from 'rxjs';
import { DocumentsApi } from '../api/documents-api.service';
import { problemMessage } from '../api/problem-message';
import type { DocumentOut } from '../model/document.models';
import { DocumentDraft } from './document-draft';
import { DossierMarkdownEditorComponent } from './dossier-markdown-editor.component';
import { readLocalCopy } from './local-copy';

const bodyOf = (d: DocumentOut | null): string => d?.bodyMd ?? '';

@Component({
  selector: 'app-document-editor',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    FormsModule,
    TranslatePipe,
    ButtonComponent,
    DossierMarkdownEditorComponent,
    NoteComponent,
    SkeletonComponent,
    TextareaComponent,
  ],
  templateUrl: './document-editor.component.html',
  styleUrl: './document-editor.component.scss',
})
export class DocumentEditorComponent {
  private readonly api = inject(DocumentsApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly documentId = input.required<string>();
  readonly canEdit = input(false);
  readonly label = input.required<string>();
  /** Part of the local copy key, so two editors of different kinds never share a draft. */
  readonly keyPrefix = input('document');

  readonly saved = output<DocumentOut>();

  protected readonly doc = signal<DocumentOut | null>(null);
  protected readonly text = signal('');
  protected readonly loadFailed = signal(false);
  protected readonly restored = signal(false);
  protected readonly saving = signal(false);
  protected readonly conflict = signal(false);
  protected readonly noting = signal(false);
  protected note = '';

  protected readonly docKey = computed(() => `${this.keyPrefix()}:${this.documentId()}`);
  protected readonly dirty = computed(() => this.text() !== bodyOf(this.doc()));
  protected readonly draft = new DocumentDraft(
    this.api,
    () => ({ documentId: this.documentId(), baseRev: (this.doc() as DocumentOut).rev }),
    () => this.docKey(),
    inject(DestroyRef),
  );

  constructor() {
    effect(() => {
      const id = this.documentId();
      untracked(() => this.open(id));
    });
  }

  protected edited(value: string): void {
    this.text.set(value);
    this.draft.change(value);
  }

  protected save(): void {
    const d = this.doc() as DocumentOut;
    this.saving.set(true);
    this.api
      .put(d.id, d.rev, { bodyMd: this.text(), changeNote: this.note.trim() || undefined })
      .subscribe({
        next: (saved) => {
          this.saving.set(false);
          this.noting.set(false);
          this.note = '';
          this.conflict.set(false);
          this.doc.set(saved);
          this.text.set(bodyOf(saved));
          this.draft.settle();
          this.toast.success(this.i18n.translate('document.saved'));
          this.saved.emit(saved);
        },
        error: (err: unknown) => this.fail(err),
      });
  }

  protected reload(): void {
    this.conflict.set(false);
    this.open(this.documentId());
  }

  protected discardDraft(): void {
    this.draft.discard();
    this.restored.set(false);
    this.text.set(bodyOf(this.doc()));
  }

  private open(id: string): void {
    this.loadFailed.set(false);
    this.api.get(id).subscribe({
      next: (d) => {
        this.doc.set(d);
        this.text.set(bodyOf(d));
        this.restoreDraft(d);
      },
      error: () => this.loadFailed.set(true),
    });
  }

  private restoreDraft(d: DocumentOut): void {
    this.restored.set(false);
    if (!this.canEdit()) return;
    this.api
      .getDraft(d.id)
      .pipe(catchError(() => of(null)))
      .subscribe((draft) => {
        const body = draft && draft.baseRev === d.rev ? draft.bodyMd : readLocalCopy(this.docKey());
        if (body !== null && body !== bodyOf(d)) {
          this.text.set(body);
          this.restored.set(true);
        }
      });
  }

  private fail(err: unknown): void {
    this.saving.set(false);
    const problem = problemOf(err);
    if (problem.code === 'conflict' || problem.status === 409) this.conflict.set(true);
    else this.toast.error(problemMessage(this.i18n, problem));
  }
}
