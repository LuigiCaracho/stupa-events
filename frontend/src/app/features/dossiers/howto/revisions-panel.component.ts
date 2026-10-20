/**
 * Revisions of a document with a diff of two of them (I09): the list newest first, two selects and `app-markdown-diff`
 * with the server's line diff. The diff is only text; a 422 `diff_too_large` shows a sentence instead.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { LocalizedDatePipe } from '@core/i18n/localized-date.pipe';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { MarkdownDiffComponent } from '@shared/ui/markdown-diff/markdown-diff.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SelectFieldComponent, type SelectFieldOption } from '@shared/ui/select/select.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import { catchError, of } from 'rxjs';
import { DocumentsApi } from '../api/documents-api.service';
import { problemMessage } from '../api/problem-message';
import type { DiffOut } from '../model/document.models';

@Component({
  selector: 'app-revisions-panel',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    LocalizedDatePipe,
    TranslatePipe,
    ButtonComponent,
    MarkdownDiffComponent,
    NoteComponent,
    SelectFieldComponent,
    SkeletonComponent,
  ],
  templateUrl: './revisions-panel.component.html',
  styleUrl: './revisions-panel.component.scss',
})
export class RevisionsPanelComponent {
  private readonly api = inject(DocumentsApi);
  private readonly i18n = inject(I18nService);

  readonly documentId = input.required<string>();
  /** Changes with every saved revision, so the list reloads. */
  readonly rev = input.required<number>();

  protected readonly revisions = rxResource({
    params: () => ({ id: this.documentId(), rev: this.rev() }),
    stream: ({ params }) => this.api.revisions(params.id),
  });

  protected readonly from = signal('');
  protected readonly to = signal('');
  protected readonly diff = signal<DiffOut | null>(null);
  protected readonly error = signal('');
  protected readonly comparing = signal(false);

  protected readonly options = computed<SelectFieldOption[]>(() =>
    (this.revisions.hasValue() ? this.revisions.value() : []).map((r) => ({
      value: String(r.rev),
      label: this.i18n.translate('howto.revLabel', { rev: r.rev }),
    })),
  );

  protected compare(): void {
    const from = Number(this.from());
    const to = Number(this.to());
    if (!from || !to) return;
    this.comparing.set(true);
    this.error.set('');
    this.api
      .diff(this.documentId(), from, to)
      .pipe(
        catchError((err: unknown) => {
          this.error.set(problemMessage(this.i18n, problemOf(err)));
          return of(null);
        }),
      )
      .subscribe((diff) => {
        this.comparing.set(false);
        this.diff.set(diff);
      });
  }
}
