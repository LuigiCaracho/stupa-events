/**
 * I09 Anleitung: the howto of this edition. One document per dossier, edited in the editor shell, autosaved as a
 * server draft every 15 s, saved as a new revision with a change note (`PUT` with `If-Match`). Revisions and their
 * diff sit below. A text selection in the source mode can become a question anchored to `{documentId, rev, from, to}`.
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
import { rxResource } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { LocalizedDatePipe } from '@core/i18n/localized-date.pipe';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { TextareaComponent } from '@shared/ui/textarea/textarea.component';
import { ButtonComponent, ToastService } from '@stupa-makers/ui-kit';
import { catchError, of } from 'rxjs';
import { QuestionButtonComponent } from '../activity/question-button.component';
import { DocumentsApi } from '../api/documents-api.service';
import type { EventDto } from '../api/event.models';
import { problemMessage } from '../api/problem-message';
import {
  DossierMarkdownEditorComponent,
  type SourceSelection,
} from '../editor/dossier-markdown-editor.component';
import { DocumentDraft } from '../editor/document-draft';
import { readLocalCopy } from '../editor/local-copy';
import type { DocumentOut } from '../model/document.models';
import { HOWTO_SCAFFOLD } from './howto-scaffold';
import { RevisionsPanelComponent } from './revisions-panel.component';

@Component({
  selector: 'app-howto-tab',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    FormsModule,
    LocalizedDatePipe,
    TranslatePipe,
    ButtonComponent,
    DossierMarkdownEditorComponent,
    EmptyStateComponent,
    NoteComponent,
    QuestionButtonComponent,
    RevisionsPanelComponent,
    SkeletonComponent,
    TextareaComponent,
  ],
  templateUrl: './howto-tab.component.html',
  styleUrl: './howto-tab.component.scss',
})
export class HowtoTabComponent {
  private readonly api = inject(DocumentsApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly event = input.required<EventDto>();
  readonly canEdit = input(false);

  readonly changed = output<void>();

  protected readonly list = rxResource({
    params: () => this.event().id,
    stream: ({ params }) => this.api.list(params, 'howto'),
  });
  protected readonly doc = signal<DocumentOut | null>(null);
  protected readonly text = signal('');
  protected readonly restored = signal(false);
  protected readonly saving = signal(false);
  protected readonly conflict = signal(false);
  protected readonly noting = signal(false);
  protected readonly selection = signal<SourceSelection | null>(null);
  protected note = '';

  protected readonly docKey = computed(() => `howto:${this.doc()?.id ?? this.event().id}`);
  protected readonly dirty = computed(() => this.text() !== (this.doc()?.bodyMd ?? ''));
  protected readonly draft = new DocumentDraft(
    this.api,
    () => {
      const d = this.doc();
      return d ? { documentId: d.id, baseRev: d.rev } : null;
    },
    () => this.docKey(),
    inject(DestroyRef),
  );
  protected readonly anchor = computed(() => {
    const d = this.doc();
    const s = this.selection();
    return d && s ? { documentId: d.id, rev: d.rev, ...s } : null;
  });

  constructor() {
    effect(() => {
      const first = this.list.hasValue() ? this.list.value()[0] : undefined;
      if (first) untracked(() => this.open(first.id));
      else untracked(() => this.doc.set(null));
    });
  }

  protected create(): void {
    this.saving.set(true);
    this.api
      .create(this.event().id, {
        kind: 'howto',
        title: this.i18n.translate('howto.defaultTitle'),
        bodyMd: HOWTO_SCAFFOLD,
      })
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.list.reload();
          this.changed.emit();
        },
        error: (err: unknown) => this.fail(err),
      });
  }

  protected edited(value: string): void {
    this.text.set(value);
    this.draft.change(value);
  }

  protected save(): void {
    const d = this.doc();
    if (!d) return;
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
          this.text.set(saved.bodyMd ?? this.text());
          this.draft.settle();
          this.toast.success(this.i18n.translate('howto.saved'));
          this.changed.emit();
        },
        error: (err: unknown) => this.fail(err),
      });
  }

  protected reload(): void {
    const d = this.doc();
    this.conflict.set(false);
    if (d) this.open(d.id);
  }

  protected discardDraft(): void {
    this.draft.discard();
    this.restored.set(false);
    this.text.set(this.doc()?.bodyMd ?? '');
  }

  private open(id: string): void {
    this.api.get(id).subscribe({
      next: (d) => {
        this.doc.set(d);
        this.text.set(d.bodyMd ?? '');
        this.restoreDraft(d);
      },
      error: (err: unknown) => this.toast.error(problemMessage(this.i18n, problemOf(err))),
    });
  }

  private restoreDraft(d: DocumentOut): void {
    this.restored.set(false);
    this.api
      .getDraft(d.id)
      .pipe(catchError(() => of(null)))
      .subscribe((draft) => {
        const body = draft && draft.baseRev === d.rev ? draft.bodyMd : readLocalCopy(this.docKey());
        if (body !== null && body !== (d.bodyMd ?? '')) {
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
