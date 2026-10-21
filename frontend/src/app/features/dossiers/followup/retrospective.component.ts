/**
 * "Rückblick" of the follow-up (M5 contract 3.4): the retrospective is a document of kind `retrospective`, org
 * visibility, never carried over. Without one the editor starts with a short scaffold and the document is created on the
 * first save; afterwards the plain document editor (server draft every 15 s, revisions) takes over.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { ButtonComponent, ToastService } from '@stupa-makers/ui-kit';
import { DocumentsApi } from '../api/documents-api.service';
import type { EventDto } from '../api/event.models';
import { problemMessage } from '../api/problem-message';
import { DocumentEditorComponent } from '../editor/document-editor.component';
import { DossierMarkdownEditorComponent } from '../editor/dossier-markdown-editor.component';
import { resourceValue } from '@core/api/resource-value';

export const RETROSPECTIVE_SCAFFOLD = `## Was lief gut?

## Was lief nicht so gut?

## Was machen wir nächstes Mal anders?
`;

@Component({
  selector: 'app-retrospective',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    ButtonComponent,
    DocumentEditorComponent,
    DossierMarkdownEditorComponent,
    NoteComponent,
    SkeletonComponent,
  ],
  templateUrl: './retrospective.component.html',
  styleUrl: './retrospective.component.scss',
})
export class RetrospectiveComponent {
  private readonly api = inject(DocumentsApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly event = input.required<EventDto>();
  readonly canEdit = input(false);
  readonly changed = output<void>();

  protected readonly list = rxResource({
    params: () => this.event().id,
    stream: ({ params }) => this.api.list(params, 'retrospective'),
  });
  protected readonly doc = computed(() => resourceValue(this.list, [])[0]);
  protected readonly text = signal(RETROSPECTIVE_SCAFFOLD);
  protected readonly saving = signal(false);

  protected create(): void {
    this.saving.set(true);
    this.api
      .create(this.event().id, {
        kind: 'retrospective',
        title: this.i18n.translate('retro.defaultTitle'),
        bodyMd: this.text(),
        visibility: 'org',
        carryOver: false,
      })
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.toast.success(this.i18n.translate('document.saved'));
          this.list.reload();
          this.changed.emit();
        },
        error: (err: unknown) => {
          this.saving.set(false);
          const problem = problemOf(err);
          if (problem.code === 'already_exists') this.list.reload();
          else this.toast.error(problemMessage(this.i18n, problem));
        },
      });
  }
}
