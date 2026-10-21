/**
 * The dossier page `/dossiers/:id` (M5b contract 10.1): one page from the head with its action bar over the poster slot
 * and the anchor navigation to the sections Eckdaten, Doku, Anhänge, Checkliste, Mails, Angebote, So lief es and Verlauf.
 * The server decides every action (`allowedActions`, `editableFields`); the page only runs them. Hints ("Fehlt noch")
 * never block. The form saves as a draft by itself; the conflict dialog and the leave question stay.
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
import { Router } from '@angular/router';
import { problemOf } from '@core/api/problem';
import { AuthService } from '@core/auth/auth.service';
import type { PendingChanges } from '@core/auth/pending-changes.guard';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { TranslationKey } from '@core/i18n/translations';
import type { PosterSubmission } from '@shared/ui/poster-upload/poster-upload.component';
import {
  FieldGroupComponent,
  FieldRowComponent,
} from '@shared/ui/field-group/field-group.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { ButtonComponent, ToastService } from '@stupa-makers/ui-kit';
import { catchError, forkJoin, map, of } from 'rxjs';
import { FieldQuestionsComponent } from '../activity/field-questions.component';
import { ActivityTabComponent } from '../activity/activity-tab.component';
import { AttachmentsApi } from '../api/attachments-api.service';
import { CommentsApi } from '../api/comments-api.service';
import { DossierCommands } from '../api/dossier-commands';
import { formatEventTime } from '../api/event-time';
import type { EventDto, EventFields, Hint } from '../api/event.models';
import { EventsApi } from '../api/events-api.service';
import { OutcomeApi } from '../api/outcome-api.service';
import { problemMessage } from '../api/problem-message';
import { AttachmentsTabComponent } from '../attachments/attachments-tab.component';
import { QuotesTabComponent } from '../attachments/quotes-tab.component';
import { AutosaveIndicatorComponent } from '../autosave/autosave-indicator.component';
import { DraftAutosave } from '../autosave/draft-autosave';
import type { CancelMode } from '../cancel/cancel-request';
import { CancelDialogComponent } from '../cancel/cancel-dialog.component';
import { ChecklistTabComponent } from '../checklist/checklist-tab.component';
import { ConflictDialogComponent } from '../conflict/conflict-dialog.component';
import { FactsFormComponent } from '../facts/facts-form.component';
import { OutcomeSectionComponent } from '../outcome/outcome-section.component';
import { EventFormComponent } from '../form/event-form.component';
import { FormatSaveDialogComponent } from '../format-save/format-save-dialog.component';
import { type HeadCommand, DossierHeadComponent } from '../head/dossier-head.component';
import { RevertDialogComponent } from '../history/revert-dialog.component';
import { HintListComponent } from '../hints/hint-list.component';
import { HowtoTabComponent } from '../howto/howto-tab.component';
import { LocationDialogComponent } from '../location/location-dialog.component';
import { MailsTabComponent } from '../mails/mails-tab.component';
import type { CommentThread } from '../model/comment.models';
import { LastTimeBlockComponent } from '../overview/last-time-block.component';
import { TemplatePanelComponent } from '../overview/template-panel.component';
import { PosterSlotComponent } from '../poster/poster-slot.component';
import { focusField } from './focus-field';
import { type LeaveChoice, LeaveDialogComponent } from './leave-dialog.component';
import { SectionNavComponent, type SectionLink } from './section-nav.component';

type DialogState =
  | null
  | { kind: 'lifecycle'; mode: CancelMode }
  | { kind: 'revert'; rev: number }
  | { kind: 'conflict'; current: EventDto; mine: EventFields; base: Record<string, unknown> | null }
  | { kind: 'leave'; resolve: (go: boolean) => void };

type LifecycleCall = 'publish' | 'unpublish' | 'archive' | 'restore';

const DONE: Record<LifecycleCall, TranslationKey> = {
  publish: 'detail.published',
  unpublish: 'detail.unpublished',
  archive: 'detail.archived',
  restore: 'detail.restored',
};

const POSTER_CODES: ReadonlySet<string> = new Set([
  'no_poster',
  'poster_alt_missing',
  'poster_credit_missing',
  'poster_consent_missing',
  'poster_not_ready',
]);

const FIELD_OF_CODE: Record<string, string> = {
  no_summary: 'summary',
  no_category: 'primaryCategoryId',
  no_venue: 'venueId',
};

@Component({
  selector: 'app-dossier-detail',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    ActivityTabComponent,
    AttachmentsTabComponent,
    AutosaveIndicatorComponent,
    ButtonComponent,
    CancelDialogComponent,
    ChecklistTabComponent,
    ConflictDialogComponent,
    DossierHeadComponent,
    EventFormComponent,
    FactsFormComponent,
    FieldGroupComponent,
    FieldQuestionsComponent,
    FieldRowComponent,
    FormatSaveDialogComponent,
    HintListComponent,
    HowtoTabComponent,
    LastTimeBlockComponent,
    LeaveDialogComponent,
    LocationDialogComponent,
    MailsTabComponent,
    NoteComponent,
    OutcomeSectionComponent,
    PosterSlotComponent,
    QuotesTabComponent,
    RevertDialogComponent,
    SectionNavComponent,
    SkeletonComponent,
    TemplatePanelComponent,
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
  private readonly outcomeApi = inject(OutcomeApi);
  private readonly auth = inject(AuthService);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly commands = inject(DossierCommands);
  private readonly router = inject(Router);

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
  protected readonly formatDialog = signal(false);
  protected readonly locationDialog = signal(false);
  protected readonly refreshTick = signal(0);
  protected readonly recomputed = signal(0);
  protected readonly busy = signal(false);
  protected readonly draft = signal<EventFields | null>(null);
  protected readonly restoredAt = signal<Date | null>(null);
  private readonly state = computed(() => this.event()?.state);
  protected readonly basicsOpen = linkedSignal({
    source: this.state,
    computation: (state) => state === 'draft',
  });

  protected readonly autosave = new DraftAutosave({
    api: this.api,
    event: this.event,
    sub: () => this.auth.userId(),
    onApplied: (updated) => this.event.set(updated),
    onConflict: (current) => this.openConflict(current),
    onOffline: () => this.toast.show(this.i18n.translate('autosave.offlineToast'), 'warning', 8000),
    onError: (err) => this.toast.error(problemMessage(this.i18n, problemOf(err))),
  });

  protected readonly editable = computed(() => (this.event()?.editableFields ?? []).length > 0);
  protected readonly canWrite = computed(() => this.editable() || this.auth.can('event.edit'));
  protected readonly canComment = computed(() => this.canWrite() || this.auth.can('comment.write'));
  protected readonly canRevert = computed(
    () => this.event()?.allowedActions.includes('revert-revision') ?? false,
  );

  protected readonly hints = rxResource({
    params: () => {
      const e = this.event();
      return e ? { id: e.id, rev: e.rev, tick: this.refreshTick() } : undefined;
    },
    stream: ({ params }) =>
      this.api.hints(params.id).pipe(
        map((out) => out.items),
        catchError(() => of([] as Hint[])),
      ),
  });
  protected readonly hintList = computed(() => (this.hints.hasValue() ? this.hints.value() : []));
  protected readonly posterMissingWarn = computed(
    () => this.event()?.state === 'published' && !this.event()?.poster,
  );

  protected readonly counts = rxResource({
    params: () => {
      const e = this.event();
      return e ? { id: e.id, tick: this.refreshTick() } : undefined;
    },
    stream: ({ params }) => this.attachmentsApi.counts(params.id).pipe(catchError(() => of(null))),
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

  protected readonly links = computed<SectionLink[]>(() => {
    const c = this.counts.hasValue() ? this.counts.value() : null;
    const link = (id: string, key: TranslationKey, count?: number): SectionLink => ({
      id,
      label: this.i18n.translate(key),
      ...(count ? { count } : {}),
    });
    return [
      link('eckdaten', 'detail.data'),
      link('doku', 'detail.tabHowto'),
      link('anhaenge', 'detail.tabAttachments', c?.attachments),
      link('checkliste', 'detail.tabChecklist', c?.openChecklist),
      link('mails', 'detail.tabMails', c?.mailTemplates),
      link('angebote', 'detail.tabQuotes', c?.quotes),
      link('so-lief-es', 'detail.tabOutcome'),
      link('verlauf', 'detail.tabHistory', c?.openComments),
    ];
  });

  protected readonly when = computed(() => {
    const e = this.event();
    return e
      ? `${formatEventTime(e.startsAt, e.tzid)} – ${formatEventTime(e.endsAt, e.tzid)}`
      : '';
  });

  constructor() {
    effect(() => {
      const e = this.loaded.hasValue() ? this.loaded.value() : null;
      if (e) untracked(() => this.begin(e));
    });
    effect(() => {
      const command = this.commands.pending();
      const e = this.event();
      if (!command || !e) return;
      untracked(() => {
        this.commands.clear();
        if (command.name === 'save-as-format' && e.allowedActions.includes('save-as-format'))
          this.formatDialog.set(true);
      });
    });
    effect(() => {
      const actions = this.event()?.allowedActions ?? [];
      untracked(() => this.commands.allowed.set(actions));
    });
    inject(DestroyRef).onDestroy(() => {
      this.autosave.destroy();
      this.commands.allowed.set([]);
    });
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
  }

  protected useBudget(cents: number): void {
    const e = this.event();
    if (!e) return;
    this.outcomeApi.putFacts(e.id, e.rev, { ...(e.facts ?? {}), budgetCents: cents }).subscribe({
      next: (updated) => {
        this.event.set(updated);
        this.toast.success(this.i18n.translate('facts.saved'));
      },
      error: (err: unknown) => this.failed(err),
    });
  }

  protected outcomeChanged(updated: EventDto | null): void {
    if (updated) this.event.set(updated);
    else this.api.get(this.id()).subscribe({ next: (e) => this.event.set(e), error: () => undefined });
    this.changedKnowledge();
  }

  protected reload(): void {
    this.loaded.reload();
  }

  protected command(c: HeadCommand): void {
    switch (c) {
      case 'publish':
      case 'unpublish':
      case 'archive':
      case 'restore':
        return this.lifecycle(c);
      case 'cancel':
      case 'postpone':
      case 'reinstate':
        return this.dialog.set({ kind: 'lifecycle', mode: c });
      case 'confirm-location':
        return this.locationDialog.set(true);
      case 'save-as-format':
        return this.formatDialog.set(true);
      case 'clone':
        void this.router.navigate(['/dossiers/neu'], { queryParams: { vorlage: this.id() } });
    }
  }

  private lifecycle(call: LifecycleCall): void {
    const run = (e: EventDto): void => {
      this.busy.set(true);
      this.api[call](e.id, e.rev).subscribe({
        next: (updated) => {
          this.busy.set(false);
          this.event.set(updated);
          this.toast.success(this.i18n.translate(DONE[call]));
        },
        error: (err: unknown) => this.failed(err, true),
      });
    };
    const e = this.event();
    if (!e || this.busy()) return;
    if (!this.autosave.dirty()) return run(e);
    this.autosave.save().subscribe({
      next: (updated) => {
        this.draft.set(null);
        this.event.set(updated);
        run(updated);
      },
      error: (err: unknown) => this.failed(err),
    });
  }

  protected fix(hint: Hint): void {
    if (POSTER_CODES.has(hint.code)) return this.focusHeading('#poster-heading');
    switch (hint.code) {
      case 'location_unconfirmed':
        return this.locationDialog.set(true);
      case 'facts_incomplete':
        this.basicsOpen.set(true);
        return this.afterRender(() => this.focusHeading('#facts-heading'));
      case 'no_organization':
        return this.goTo('eckdaten');
      case 'howto_missing':
        return this.goTo('doku');
      case 'outcome_open':
        return this.goTo('so-lief-es');
      default: {
        this.basicsOpen.set(true);
        const field = FIELD_OF_CODE[hint.code] ?? hint.field;
        this.afterRender(() => focusField(this.host.nativeElement, field));
      }
    }
  }

  protected goTo(id: string): void {
    const target = this.host.nativeElement.querySelector<HTMLElement>(`#${id}`);
    target?.scrollIntoView?.({ block: 'start' });
    target?.focus({ preventScroll: true });
  }

  private focusHeading(selector: string): void {
    const heading = this.host.nativeElement.querySelector<HTMLElement>(selector);
    heading?.scrollIntoView?.({ block: 'center' });
    heading?.focus({ preventScroll: true });
  }

  private afterRender(step: () => void): void {
    setTimeout(step);
  }

  protected locationConfirmed(updated: EventDto): void {
    this.locationDialog.set(false);
    this.event.set(updated);
  }

  protected formatSaved(): void {
    this.formatDialog.set(false);
    this.refresh();
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
        this.toast.success(this.i18n.translate('detail.posterUploaded'));
        this.refresh();
      },
      error: (err: unknown) => this.failed(err),
    });
  }

  protected removePoster(): void {
    const poster = this.event()?.poster;
    if (!poster || this.busy()) return;
    this.busy.set(true);
    this.attachmentsApi.retire(poster.id).subscribe({
      next: () => {
        this.busy.set(false);
        this.toast.success(this.i18n.translate('detail.posterRemoved'));
        this.refresh();
      },
      error: (err: unknown) => this.failed(err),
    });
  }

  protected revertTo(rev: number): void {
    this.dialog.set({ kind: 'revert', rev });
  }

  protected revert(note: string): void {
    const state = this.dialog();
    const e = this.event();
    if (state?.kind !== 'revert' || !e) return;
    this.busy.set(true);
    this.api.revert(e.id, e.rev, { rev: state.rev, ...(note && { note }) }).subscribe({
      next: (updated) => {
        this.busy.set(false);
        this.toast.success(this.i18n.translate('history.reverted'));
        this.applied(updated);
      },
      error: (err: unknown) => this.failed(err, true),
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

  private failed(err: unknown, report = false): void {
    this.busy.set(false);
    const problem = problemOf(err);
    if (problem.code === 'conflict' && !report) return;
    this.toast.error(problemMessage(this.i18n, problem));
    if (problem.status === 409 || problem.status === 412) this.refresh();
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

  protected restoredText(): string {
    const at = this.restoredAt();
    return this.i18n.translate('autosave.restored', {
      time: at ? at.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }) : '',
    });
  }
}
