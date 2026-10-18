/**
 * I13: confirm a transition. Shows the guard list the server computes before the click ("Fehlt noch": blockers
 * first, warnings need a tick), the required note of T03/T06/T07/T10/T11, the release time of T04 with the switch
 * "Sofort veröffentlichen" (a second call, T05, follows T04) and the four-eyes hint. The button stays off while
 * a blocker is open and says why.
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
import { FormsModule } from '@angular/forms';
import type { ProblemReason } from '@core/api/models';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { eventStateStatus } from '@shared/status-kind.util';
import { DatetimeFieldComponent } from '@shared/ui/datetime-field/datetime-field.component';
import { GuardListComponent } from '@shared/ui/guard-list/guard-list.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import {
  ButtonComponent,
  CheckboxComponent,
  DialogComponent,
  InputComponent,
  SwitchComponent,
  ToastService,
} from '@stupa-makers/ui-kit';
import type { EventDto, TransitionId } from '../api/event.models';
import { EventsApi } from '../api/events-api.service';
import { problemMessage } from '../api/problem-message';
import { NOTE_LABEL } from '../api/transitions';
import { TRANSITION_LABEL } from '../api/transition-label';
import { type FormError, formError, transitionBody } from './transition-request';

/** What the dialog needs of a dossier: a board card or a full event both fit. */
export interface TransitionTarget {
  id: string;
  title: string;
  rev: number;
}

@Component({
  selector: 'app-transition-dialog',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    FormsModule,
    TranslatePipe,
    ButtonComponent,
    CheckboxComponent,
    DatetimeFieldComponent,
    DialogComponent,
    GuardListComponent,
    InputComponent,
    NoteComponent,
    SkeletonComponent,
    SwitchComponent,
  ],
  templateUrl: './transition-dialog.component.html',
  styleUrl: './transition-dialog.component.scss',
})
export class TransitionDialogComponent {
  private readonly api = inject(EventsApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  protected readonly label = TRANSITION_LABEL;

  readonly target = input.required<TransitionTarget>();
  readonly transition = input.required<TransitionId>();

  readonly done = output<EventDto>();
  /** T04 went through but the follow-up T05 did not: the page shows the new state, the dialog stays. */
  readonly partial = output<EventDto>();
  readonly stale = output<EventDto | null>();
  readonly fix = output<ProblemReason>();
  readonly closed = output<void>();

  protected readonly note = signal('');
  protected readonly acknowledged = signal(false);
  protected readonly busy = signal(false);
  protected readonly attempted = signal(false);
  protected readonly immediate = signal(true);
  protected readonly publishDate = signal('');
  protected readonly publishTime = signal('');
  protected readonly followUpFailed = signal('');

  protected readonly guards = rxResource({
    params: () => ({ id: this.target().id, transition: this.transition(), rev: this.target().rev }),
    stream: ({ params }) => this.api.guards(params.id, params.transition),
  });

  protected readonly reasons = computed(() =>
    this.guards.hasValue() ? this.guards.value().reasons : [],
  );
  protected readonly allowed = computed(
    () => this.guards.hasValue() && this.guards.value().allowed,
  );
  protected readonly blocked = computed(
    () =>
      this.guards.hasValue() &&
      (!this.allowed() || this.reasons().some((r) => r.severity === 'blocker')),
  );
  protected readonly fourEyes = computed(() => this.reasons().some((r) => r.code === 'four_eyes'));
  protected readonly needsAck = computed(() =>
    this.reasons().some((r) => r.severity === 'warning'),
  );
  protected readonly noteLabel = computed(() => NOTE_LABEL[this.transition()] ?? 'transition.note');
  protected readonly noteRequired = computed(() => NOTE_LABEL[this.transition()] !== undefined);
  protected readonly isPublish = computed(() => this.transition() === 'T04');
  protected readonly error = computed<FormError>(() =>
    formError({
      transition: this.transition(),
      note: this.note(),
      immediate: this.immediate(),
      publishDate: this.publishDate(),
      publishTime: this.publishTime(),
    }),
  );
  protected readonly canConfirm = computed(
    () => this.allowed() && !this.blocked() && (!this.needsAck() || this.acknowledged()),
  );
  protected readonly loadError = computed(() =>
    this.guards.error() ? problemMessage(this.i18n, problemOf(this.guards.error())) : '',
  );
  protected readonly blockedReason = computed(() =>
    this.fourEyes() ? 'transition.fourEyes' : 'transition.blocked',
  );

  protected retry(): void {
    this.guards.reload();
  }

  protected confirm(): void {
    this.attempted.set(true);
    if (!this.canConfirm() || this.error() || this.busy()) return;
    this.busy.set(true);
    const body = transitionBody({
      transition: this.transition(),
      note: this.note(),
      immediate: this.immediate(),
      publishDate: this.publishDate(),
      publishTime: this.publishTime(),
    });
    const { id, rev } = this.target();
    this.api.transition(id, this.transition(), body, rev).subscribe({
      next: (updated) => this.succeeded(updated),
      error: (err: unknown) => this.failed(err),
    });
  }

  private succeeded(updated: EventDto): void {
    if (this.isPublish() && this.immediate()) return this.publishNow(updated);
    this.finish(updated);
  }

  private publishNow(approved: EventDto): void {
    this.api.transition(approved.id, 'T05', {}, approved.rev).subscribe({
      next: (live) => this.finish(live),
      error: (err: unknown) => {
        this.busy.set(false);
        this.followUpFailed.set(problemMessage(this.i18n, problemOf(err)));
        this.partial.emit(approved);
      },
    });
  }

  private finish(updated: EventDto): void {
    this.busy.set(false);
    this.toast.success(
      this.i18n.translate('transition.done', {
        state: this.i18n.translate(eventStateStatus(updated.state).key),
      }),
    );
    this.done.emit(updated);
  }

  private failed(err: unknown): void {
    this.busy.set(false);
    const problem = problemOf(err);
    if (problem.status === 409) {
      const current = problem.current as EventDto | undefined;
      const state = current ? this.i18n.translate(eventStateStatus(current.state).key) : '';
      this.toast.error(
        this.i18n.translate(current ? 'transition.stale' : 'problem.conflict', { state }),
      );
      this.stale.emit(current ?? null);
      return;
    }
    this.toast.error(problemMessage(this.i18n, problem));
    this.guards.reload();
  }
}
