/**
 * I13: confirm a transition (T01, T02, T04, T05). Shows the guard list computed by the server
 * before the click; the confirm button stays off while a blocker is open, warnings need a tick.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import type { ProblemReason } from '@core/api/models';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { GuardListComponent } from '@shared/ui/guard-list/guard-list.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { ButtonComponent, CheckboxComponent, DialogComponent, InputComponent, ToastService } from '@stupa-makers/ui-kit';
import type { EventDto, TransitionId } from '../api/event.models';
import { EventsApi } from '../api/events-api.service';
import { problemMessage } from '../api/problem-message';
import { TRANSITION_LABEL } from '../api/transition-label';
import { eventStateStatus } from '@shared/status-kind.util';

@Component({
  selector: 'app-transition-dialog',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    FormsModule,
    TranslatePipe,
    ButtonComponent,
    CheckboxComponent,
    DialogComponent,
    GuardListComponent,
    InputComponent,
    NoteComponent,
    SkeletonComponent,
  ],
  templateUrl: './transition-dialog.component.html',
  styleUrl: './transition-dialog.component.scss',
})
export class TransitionDialogComponent {
  private readonly api = inject(EventsApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  protected readonly label = TRANSITION_LABEL;

  readonly event = input.required<EventDto>();
  readonly transition = input.required<TransitionId>();

  readonly done = output<EventDto>();
  readonly stale = output<void>();
  readonly fix = output<ProblemReason>();
  readonly closed = output<void>();

  protected readonly note = signal('');
  protected readonly acknowledged = signal(false);
  protected readonly busy = signal(false);

  protected readonly guards = rxResource({
    params: () => ({ id: this.event().id, transition: this.transition(), rev: this.event().rev }),
    stream: ({ params }) => this.api.guards(params.id, params.transition),
  });

  protected readonly reasons = computed(() => this.guards.hasValue() ? this.guards.value().reasons : []);
  protected readonly allowed = computed(() => this.guards.hasValue() && this.guards.value().allowed);
  protected readonly blocked = computed(
    () => this.guards.hasValue() && (!this.allowed() || this.reasons().some((r) => r.severity === 'blocker')),
  );
  protected readonly needsAck = computed(() => this.reasons().some((r) => r.severity === 'warning'));
  protected readonly canConfirm = computed(
    () => this.allowed() && !this.blocked() && (!this.needsAck() || this.acknowledged()),
  );
  protected readonly loadError = computed(() =>
    this.guards.error() ? problemMessage(this.i18n, problemOf(this.guards.error())) : '',
  );
  protected readonly noteTooLong = computed(() => this.note().length > 500);

  protected retry(): void {
    this.guards.reload();
  }

  protected confirm(): void {
    if (!this.canConfirm() || this.noteTooLong() || this.busy()) return;
    this.busy.set(true);
    this.api.transition(this.event().id, this.transition(), this.note().trim() || undefined).subscribe({
      next: (updated) => {
        this.busy.set(false);
        this.toast.success(
          this.i18n.translate('transition.done', { state: this.i18n.translate(eventStateStatus(updated.state).key) }),
        );
        this.done.emit(updated);
      },
      error: (err: unknown) => {
        this.busy.set(false);
        const problem = problemOf(err);
        this.toast.error(problemMessage(this.i18n, problem));
        if (problem.status === 409) this.stale.emit();
        else this.guards.reload();
      },
    });
  }
}
