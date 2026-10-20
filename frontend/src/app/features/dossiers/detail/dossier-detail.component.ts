/**
 * I07: the dossier page (`/dossiers/:id`): head with the state buttons, overview with "Fehlt noch", the form with its
 * locks and autosave, the poster block, the tab "Verlauf" and the dialogs I13 to I15, the conflict dialog and the
 * leave question. The server decides every action; `allowedTransitions`, `allowedActions` and `editableFields` only shape the UI.
 */
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  computed,
  effect,
  inject,
  input,
  linkedSignal,
  signal,
  untracked,
} from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import type { ProblemReason } from '@core/api/models';
import { problemOf } from '@core/api/problem';
import type { PendingChanges } from '@core/auth/pending-changes.guard';
import { AuthService } from '@core/auth/auth.service';
import { I18nService } from '@core/i18n/i18n.service';
import type { TranslationKey } from '@core/i18n/translations';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { ActivityTabComponent } from '../activity/activity-tab.component';
import { FieldQuestionsComponent } from '../activity/field-questions.component';
import { AttachmentsApi } from '../api/attachments-api.service';
import { CommentsApi } from '../api/comments-api.service';
import { AttachmentsTabComponent } from '../attachments/attachments-tab.component';
import { ChecklistTabComponent } from '../checklist/checklist-tab.component';
import { HowtoTabComponent } from '../howto/howto-tab.component';
import { MailsTabComponent } from '../mails/mails-tab.component';
import type { CommentThread } from '../model/comment.models';
import { ImageThumbComponent } from '@shared/ui/image-thumb/image-thumb.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import {
  PosterUploadComponent,
  type PosterSubmission,
} from '@shared/ui/poster-upload/poster-upload.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { ButtonComponent, TabsComponent, ToastService, type TabItem } from '@stupa-makers/ui-kit';
import { forkJoin, of, type Observable } from 'rxjs';
import { catchError } from 'rxjs/operators';
import type { RevisionOut } from '../api/action.models';
import type { EventDto, EventFields, TransitionId } from '../api/event.models';
import { EventsApi } from '../api/events-api.service';
import { problemMessage } from '../api/problem-message';
import { PRIMARY_TRANSITION } from '../api/transitions';
import { DraftAutosave } from '../autosave/draft-autosave';
import { AutosaveIndicatorComponent } from '../autosave/autosave-indicator.component';
import { EventFormComponent } from '../form/event-form.component';
import { type HeadCommand, DossierHeadComponent } from '../head/dossier-head.component';
import { DossierOverviewComponent } from '../overview/dossier-overview.component';
import {
  DetailDialogsComponent,
  type DialogState,
  type LeaveChoice,
} from './detail-dialogs.component';
import { focusField } from './focus-field';

type DetailTab = 'overview' | 'attachments' | 'howto' | 'checklist' | 'mails' | 'history';

const POSTER_STATES: readonly string[] = ['idea', 'planning', 'in_review'];
const SAVE_BEFORE_TRANSITION: readonly string[] = ['idea', 'planning'];

@Component({
  selector: 'app-dossier-detail',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    ActivityTabComponent,
    AttachmentsTabComponent,
    AutosaveIndicatorComponent,
    ChecklistTabComponent,
    FieldQuestionsComponent,
    HowtoTabComponent,
    MailsTabComponent,
    ButtonComponent,
    DetailDialogsComponent,
    DossierHeadComponent,
    DossierOverviewComponent,
    EventFormComponent,
    ImageThumbComponent,
    NoteComponent,
    PosterUploadComponent,
    SkeletonComponent,
    StatusTextComponent,
    TabsComponent,
  ],
  host: {
    '(window:online)': 'autosave.flush()',
    '(window:beforeunload)': 'warnUnload($event)',
  },
  templateUrl: './dossier-detail.component.html',
  styleUrl: './dossier-detail.component.scss',
})
export class DossierDetailComponent implements PendingChanges {
  private readonly api = inject(EventsApi);
  private readonly attachmentsApi = inject(AttachmentsApi);
  private readonly commentsApi = inject(CommentsApi);
  private readonly auth = inject(AuthService);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly id = input.required<string>();

  protected readonly loaded = rxResource({
    params: () => this.id(),
    stream: ({ params }) => this.api.get(params),
  });
  protected readonly event = linkedSignal<EventDto | null>(() =>
    this.loaded.hasValue() ? this.loaded.value() : null,
  );
  protected readonly lookups = rxResource({
    stream: () =>
      forkJoin({
        categories: this.api.categories().pipe(catchError(() => of([]))),
        venues: this.api.venues().pipe(catchError(() => of([]))),
      }),
  });

  protected readonly dialog = signal<DialogState>(null);
  protected readonly tab = signal<DetailTab>('overview');
  protected readonly refreshTick = signal(0);
  protected readonly recomputed = signal(0);
  protected readonly posterOpen = signal(false);
  protected readonly busy = signal(false);
  protected readonly draft = signal<EventFields | null>(null);
  protected readonly restoredAt = signal<Date | null>(null);

  protected readonly autosave = new DraftAutosave({
    api: this.api,
    event: this.event,
    sub: () => this.auth.userId(),
    onApplied: (updated) => this.event.set(updated),
    onConflict: (current) => this.openConflict(current),
    onOffline: () => this.toast.show(this.i18n.translate('autosave.offlineToast'), 'warning', 8000),
    onError: (err) => this.toast.error(problemMessage(this.i18n, problemOf(err))),
  });

  protected readonly next = computed<TransitionId | null>(() => {
    const e = this.event();
    const t = e ? PRIMARY_TRANSITION[e.state] : undefined;
    return e && t && e.allowedTransitions.includes(t) ? t : null;
  });
  protected readonly guards = rxResource({
    params: () => {
      const e = this.event();
      const t = this.next();
      return e && t ? { id: e.id, transition: t, rev: e.rev } : undefined;
    },
    stream: ({ params }) => this.api.guards(params.id, params.transition),
  });

  protected readonly actions = computed<string[]>(() => {
    const e = this.event();
    if (!e) return [];
    return (
      e.allowedActions ??
      (this.auth.can('event.image_exception') && !e.imageException ? ['image-exception'] : [])
    );
  });
  protected readonly editable = computed(
    () => (this.event()?.editableFields ?? ['title']).length > 0,
  );
  protected readonly canPoster = computed(() =>
    POSTER_STATES.includes(this.event()?.state ?? 'live'),
  );
  protected readonly showUpload = computed(
    () => this.canPoster() && (this.posterOpen() || !this.event()?.poster),
  );
  protected readonly canRevert = computed(() => this.actions().includes('revert-revision'));

  protected readonly counts = rxResource({
    params: () => {
      const e = this.event();
      return e ? { id: e.id, tick: this.refreshTick() } : undefined;
    },
    stream: ({ params }) =>
      this.attachmentsApi.counts(params.id).pipe(catchError(() => of(null))),
  });
  protected readonly threads = rxResource<CommentThread[], { id: string; tick: number } | undefined>({
    params: () => {
      const e = this.event();
      return e ? { id: e.id, tick: this.refreshTick() } : undefined;
    },
    stream: ({ params }) =>
      params ? this.commentsApi.list(params.id).pipe(catchError(() => of([]))) : of([]),
  });
  protected readonly threadList = computed(() => (this.threads.hasValue() ? this.threads.value() : []));
  protected readonly canComment = computed(() => this.editable() || this.auth.can('comment.write'));

  protected readonly tabs = computed<TabItem[]>(() => {
    const c = this.counts.hasValue() ? this.counts.value() : null;
    const tab = (id: DetailTab, key: TranslationKey, count?: number): TabItem => ({
      id,
      label: this.i18n.translate(key),
      ...(count ? { count } : {}),
    });
    return [
      tab('overview', 'detail.tabOverview'),
      tab('attachments', 'detail.tabAttachments', c?.attachments),
      tab('howto', 'detail.tabHowto', c?.howto),
      tab('checklist', 'detail.tabChecklist', c?.openChecklist),
      tab('mails', 'detail.tabMails', c?.mailTemplates),
      tab('history', 'detail.tabHistory', c?.openComments),
    ];
  });

  protected readonly changes = rxResource({
    params: () => {
      const e = this.event();
      return e?.state === 'live' && this.auth.can('event.edit_critical_live')
        ? { id: e.id, rev: e.rev, after: Math.max(e.publishedRev ?? 0, e.textReviewedRev ?? 0) }
        : undefined;
    },
    stream: ({ params }) =>
      this.api
        .revisions(params.id, 50, 0, { fieldClass: 'text', minRev: params.after })
        .pipe(catchError(() => of(null))),
  });
  protected readonly changedAfter = computed<RevisionOut[]>(() => {
    const e = this.event();
    const page = this.changes.hasValue() ? this.changes.value() : null;
    if (!e || !page) return [];
    return page.items.filter((r) => r.actor.sub !== this.auth.userId());
  });

  constructor() {
    effect(() => {
      const e = this.loaded.hasValue() ? this.loaded.value() : null;
      if (e) untracked(() => this.begin(e));
    });
    inject(DestroyRef).onDestroy(() => this.autosave.destroy());
  }

  private begin(e: EventDto): void {
    this.autosave.reset();
    this.draft.set(null);
    this.restoredAt.set(null);
    this.autosave.restore(e).subscribe((r) => {
      if (r.kind === 'restored') {
        this.draft.set(r.draft.fields);
        this.restoredAt.set(new Date(r.draft.updatedAt));
      } else if (r.kind === 'stale') {
        this.openConflict(e, r.draft.fields, r.draft.baseRev);
      }
    });
  }

  protected changedKnowledge(): void {
    this.refreshTick.update((n) => n + 1);
    this.guards.reload();
  }

  protected useBudget(cents: number): void {
    // TODO-M4: the event form has no budget field yet (`facts.budgetCents` comes with the facts block); show the suggestion only.
    this.toast.show(
      this.i18n.translate('quote.budgetSuggested', { amount: (cents / 100).toFixed(2).replace('.', ',') }),
      'info',
      8000,
    );
  }

  protected reload(): void {
    this.loaded.reload();
  }

  protected command(c: HeadCommand): void {
    if (c.kind === 'transition')
      return this.saveFirst(() => this.dialog.set({ kind: 'transition', id: c.id }));
    switch (c.name) {
      case 'cancel':
        return this.dialog.set({ kind: 'cancel' });
      case 'reinstate':
        return this.dialog.set({ kind: 'reinstate' });
      case 'exception':
        return this.dialog.set({ kind: 'exception' });
      case 'assign':
        return this.dialog.set({ kind: 'assign' });
      case 'confirm-flyer':
        return this.confirmFlyer();
    }
  }

  protected fix(reason: ProblemReason): void {
    this.dialog.set(null);
    const action = reason.fixAction;
    if (action === 'upload_poster' || action === 'fill_rights') {
      this.posterOpen.set(true);
      setTimeout(() =>
        this.host.nativeElement.querySelector('#poster-heading')?.scrollIntoView?.(),
      );
    } else if (action === 'confirm_flyer') {
      this.confirmFlyer();
    } else if (action === 'open_comment') {
      this.tab.set('history');
    } else if (action === 'open_checklist') {
      this.tab.set('checklist');
    } else if (action) {
      this.tab.set('overview');
      setTimeout(() => focusField(this.host.nativeElement, action, reason.field));
    }
  }

  protected applied(updated: EventDto): void {
    this.event.set(updated);
    this.dialog.set(null);
  }

  protected refresh(): void {
    this.dialog.set(null);
    this.api
      .get(this.id())
      .subscribe({ next: (e) => this.event.set(e), error: () => this.loaded.reload() });
  }

  protected formChanged(fields: EventFields): void {
    this.autosave.change(fields);
  }

  protected save(): void {
    if (this.busy()) return;
    this.busy.set(true);
    this.autosave.save().subscribe({
      next: (updated) => {
        this.busy.set(false);
        this.draft.set(null);
        this.restoredAt.set(null);
        this.toast.success(this.i18n.translate('detail.saved'));
        this.recomputed.set(updated.checklistRecomputed ?? 0);
        this.event.set(updated);
      },
      error: (err: unknown) => this.failed(err),
    });
  }

  protected discardDraft(): void {
    this.autosave.discard();
    this.draft.set(null);
    this.restoredAt.set(null);
  }

  protected upload(sub: PosterSubmission): void {
    const e = this.event();
    if (!e || this.busy()) return;
    this.busy.set(true);
    this.api.uploadPoster(e.id, sub.file, sub).subscribe({
      next: () => {
        this.busy.set(false);
        this.posterOpen.set(false);
        this.toast.success(this.i18n.translate('detail.posterUploaded'));
        this.refresh();
      },
      error: (err: unknown) => this.failed(err),
    });
  }

  private confirmFlyer(): void {
    const e = this.event();
    if (!e) return;
    this.act(this.api.action(e.id, 'confirm-flyer', {}, e.rev), 'detail.flyerConfirmed');
  }

  protected revertTo(rev: number): void {
    this.dialog.set({ kind: 'revert', rev });
  }

  protected acknowledge(): void {
    const e = this.event();
    if (e) this.act(this.api.action(e.id, 'acknowledge-changes', {}, e.rev), 'tasks.acknowledged');
  }

  protected revertBaseline(): void {
    const e = this.event();
    if (e)
      this.dialog.set({
        kind: 'revert',
        rev: Math.max(e.publishedRev ?? 0, e.textReviewedRev ?? 0),
      });
  }

  private act(
    call: Observable<EventDto>,
    done: 'detail.flyerConfirmed' | 'tasks.acknowledged',
  ): void {
    call.subscribe({
      next: (updated) => {
        this.event.set(updated);
        this.toast.success(this.i18n.translate(done));
      },
      error: (err: unknown) => this.failed(err),
    });
  }

  private saveFirst(next: () => void): void {
    if (!this.autosave.dirty() || !SAVE_BEFORE_TRANSITION.includes(this.event()?.state ?? ''))
      return next();
    this.autosave.save().subscribe({
      next: (updated) => {
        this.draft.set(null);
        this.event.set(updated);
        next();
      },
      error: (err: unknown) => this.failed(err),
    });
  }

  private openConflict(current: EventDto | null, mine?: EventFields, baseRev?: number): void {
    const e = this.event();
    const fields = mine ?? this.autosave.fields();
    const base = baseRev ?? e?.rev;
    this.toast.error(this.i18n.translate('conflict.toast'));
    forkJoin({
      current: current ? of(current) : this.api.get(this.id()),
      base:
        base === undefined
          ? of(null)
          : this.api.revision(this.id(), base).pipe(catchError(() => of(null))),
    }).subscribe(({ current: now, base: rev }) =>
      this.dialog.set({
        kind: 'conflict',
        current: now,
        mine: fields,
        base: rev?.snapshot ?? null,
      }),
    );
  }

  protected keepMine(fields: EventFields): void {
    const state = this.dialog();
    if (state?.kind !== 'conflict') return;
    this.busy.set(true);
    this.api.patch(state.current.id, state.current.rev, fields).subscribe({
      next: (updated) => {
        this.busy.set(false);
        this.autosave.discard();
        this.draft.set(null);
        this.dialog.set(null);
        this.event.set(updated);
      },
      error: (err: unknown) => this.failed(err),
    });
  }

  protected takeTheirs(): void {
    const state = this.dialog();
    this.autosave.discard();
    this.draft.set(null);
    this.dialog.set(null);
    if (state?.kind === 'conflict') this.event.set(state.current);
  }

  private failed(err: unknown): void {
    this.busy.set(false);
    const problem = problemOf(err);
    if (problem.code === 'conflict') return;
    this.toast.error(problemMessage(this.i18n, problem));
    if (problem.status === 409) this.refresh();
  }

  protected warnUnload(event: BeforeUnloadEvent): void {
    if (!this.autosave.unsent()) return;
    event.preventDefault();
    event.returnValue = '';
  }

  canLeave(): boolean | Promise<boolean> {
    if (!this.autosave.unsent()) return true;
    return new Promise<boolean>((resolve) => this.dialog.set({ kind: 'leave', resolve }));
  }

  protected leaveChoice(choice: LeaveChoice): void {
    const state = this.dialog();
    if (state?.kind !== 'leave') return;
    if (choice === 'save') {
      this.autosave.save().subscribe({
        next: () => this.finishLeave(state, true),
        error: (err: unknown) => {
          this.failed(err);
          this.finishLeave(state, false);
        },
      });
      return;
    }
    if (choice === 'discard') this.autosave.discard();
    this.finishLeave(state, choice === 'discard');
  }

  private finishLeave(state: { resolve: (go: boolean) => void }, go: boolean): void {
    this.dialog.set(null);
    state.resolve(go);
  }

  protected posterSrc(e: EventDto): string {
    return this.api.posterUrl(e.id, 'thumb400');
  }

  protected restoredText(): string {
    const at = this.restoredAt();
    return this.i18n.translate('autosave.restored', {
      time: at ? at.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }) : '',
    });
  }
}
