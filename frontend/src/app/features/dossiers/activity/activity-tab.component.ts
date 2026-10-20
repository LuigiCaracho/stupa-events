/**
 * I12 Verlauf und Kommentare: the question threads (open first) with anchors, resolve and reopen, the timeline of
 * revisions, transitions, howto revisions and comments, the comparison of two revisions and, for reviewers, the
 * older revision list with "Auf diesen Stand zurücksetzen". The guard sentence "Rückfrage am Poster blockiert die
 * Freigabe" shows while a thread on the poster is open.
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { problemOf } from '@core/api/problem';
import { AuthService } from '@core/auth/auth.service';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { ChatComponent, type ChatReply } from '@shared/ui/chat/chat.component';
import { fieldLabel } from '@shared/ui/guard-list/reason-text';
import { HistoryComponent } from '@shared/ui/history/history.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { ToastService } from '@stupa-makers/ui-kit';
import { catchError, forkJoin, of, switchMap, type Observable } from 'rxjs';
import { AttachmentsApi } from '../api/attachments-api.service';
import { CommentsApi } from '../api/comments-api.service';
import { DocumentsApi } from '../api/documents-api.service';
import type { EventDto } from '../api/event.models';
import { EventsApi } from '../api/events-api.service';
import { problemMessage } from '../api/problem-message';
import { DossierHistoryComponent } from '../history/dossier-history.component';
import type { CommentThread } from '../model/comment.models';
import type { DocumentRevisionOut } from '../model/document.models';
import { QuestionButtonComponent } from './question-button.component';
import { RevisionCompareComponent } from './revision-compare.component';
import { commentEntries, documentEntries, revisionEntries } from './timeline';

@Component({
  selector: 'app-activity-tab',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    ChatComponent,
    DossierHistoryComponent,
    HistoryComponent,
    NoteComponent,
    QuestionButtonComponent,
    RevisionCompareComponent,
    SkeletonComponent,
  ],
  templateUrl: './activity-tab.component.html',
  styleUrl: './activity-tab.component.scss',
})
export class ActivityTabComponent {
  private readonly comments = inject(CommentsApi);
  private readonly events = inject(EventsApi);
  private readonly documents = inject(DocumentsApi);
  private readonly attachments = inject(AttachmentsApi);
  private readonly auth = inject(AuthService);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly event = input.required<EventDto>();
  readonly threads = input<readonly CommentThread[]>([]);
  readonly canComment = input(false);
  readonly canRevert = input(false);

  readonly changed = output<void>();
  readonly revert = output<number>();

  protected readonly busy = signal(false);

  protected readonly revisions = rxResource({
    params: () => ({ id: this.event().id, rev: this.event().rev }),
    stream: ({ params }) => this.events.revisions(params.id, 100),
  });
  protected readonly extras = rxResource({
    params: () => this.event().id,
    stream: ({ params }) =>
      forkJoin({
        howto: this.documents.list(params, 'howto').pipe(
          switchMap((docs) => (docs[0] ? this.documents.revisions(docs[0].id) : of([]))),
          catchError(() => of([] as DocumentRevisionOut[])),
        ),
        files: this.attachments.list(params, true).pipe(catchError(() => of([]))),
      }),
  });

  protected readonly open = computed(() => this.threads().filter((t) => !t.resolvedAt));
  protected readonly done = computed(() => this.threads().filter((t) => !!t.resolvedAt));
  protected readonly posterBlocked = computed(() =>
    this.open().some(
      (t) =>
        t.anchor &&
        'field' in t.anchor &&
        (t.anchor.field === 'hero' || t.anchor.field === 'poster'),
    ),
  );

  protected readonly entries = computed(() => [
    ...revisionEntries(this.i18n, this.revisions.hasValue() ? this.revisions.value().items : []),
    ...documentEntries(this.i18n, this.extras.hasValue() ? this.extras.value().howto : []),
    ...commentEntries(this.i18n, this.threads()),
  ]);

  protected readonly anchorLabel = (t: CommentThread): string => {
    const a = t.anchor;
    if (!a) return this.i18n.translate('anchor.general');
    if ('field' in a) {
      return a.field === 'hero' || a.field === 'poster'
        ? this.i18n.translate('anchor.poster')
        : this.i18n.translate('anchor.field', { field: fieldLabel(this.i18n, a.field) });
    }
    if ('attachmentId' in a) {
      const files = this.extras.hasValue() ? this.extras.value().files : [];
      const name = files.find((f) => f.id === a.attachmentId)?.displayName ?? '';
      return this.i18n.translate('anchor.attachment', { name });
    }
    if ('checklistItemId' in a) return this.i18n.translate('anchor.checklist');
    return this.i18n.translate('anchor.howto');
  };

  protected readonly canResolve = (t: CommentThread): boolean =>
    this.canComment() &&
    (t.authorSub === this.auth.userId() ||
      this.auth.can('event.approve') ||
      this.auth.roles().includes('editor'));

  protected reply(r: ChatReply): void {
    this.run(this.comments.add(this.event().id, { bodyMd: r.bodyMd, parentId: r.parentId }));
  }

  protected resolve(id: string): void {
    this.run(this.comments.resolve(id));
  }

  protected reopen(id: string): void {
    this.run(this.comments.reopen(id));
  }

  protected refresh(): void {
    this.changed.emit();
  }

  private run(call: Observable<unknown>): void {
    this.busy.set(true);
    call.subscribe({
      next: () => {
        this.busy.set(false);
        this.changed.emit();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.toast.error(problemMessage(this.i18n, problemOf(err)));
      },
    });
  }
}
