/**
 * The dialogs of the dossier page in one place: I13 transition, I14 cancel or postpone, I15 image exception, assign
 * organization, "Absage zurücknehmen", "Auf Stand zurücksetzen", the edit conflict and the question on leaving. Exactly one is
 * open (`DialogState`); the page reacts to the outputs.
 */
import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';
import type { ProblemReason } from '@core/api/models';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { ButtonComponent, DialogComponent, ToastService } from '@stupa-makers/ui-kit';
import type { Observable } from 'rxjs';
import type {
  CategoryRef,
  EventDto,
  EventFields,
  TransitionId,
  VenueRef,
} from '../api/event.models';
import { EventsApi } from '../api/events-api.service';
import { problemMessage } from '../api/problem-message';
import { AssignOrgDialogComponent } from '../assign/assign-org-dialog.component';
import { CancelDialogComponent } from '../cancel/cancel-dialog.component';
import { ConflictDialogComponent } from '../conflict/conflict-dialog.component';
import { ImageExceptionDialogComponent } from '../exception/image-exception-dialog.component';
import { ReasonDialogComponent } from '../reason/reason-dialog.component';
import { TransitionDialogComponent } from '../transition/transition-dialog.component';

export type DialogState =
  | null
  | { kind: 'transition'; id: TransitionId }
  | { kind: 'cancel' }
  | { kind: 'reinstate' }
  | { kind: 'exception' }
  | { kind: 'assign' }
  | { kind: 'revert'; rev: number }
  | { kind: 'conflict'; current: EventDto; mine: EventFields; base: Record<string, unknown> | null }
  | { kind: 'leave'; resolve: (go: boolean) => void };

export type LeaveChoice = 'save' | 'discard' | 'stay';

@Component({
  selector: 'app-detail-dialogs',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    AssignOrgDialogComponent,
    ButtonComponent,
    CancelDialogComponent,
    ConflictDialogComponent,
    DialogComponent,
    ImageExceptionDialogComponent,
    ReasonDialogComponent,
    TransitionDialogComponent,
  ],
  templateUrl: './detail-dialogs.component.html',
  styleUrl: './detail-dialogs.component.scss',
})
export class DetailDialogsComponent {
  private readonly api = inject(EventsApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly event = input.required<EventDto>();
  readonly state = input<DialogState>(null);
  readonly venues = input<readonly VenueRef[]>([]);
  readonly categories = input<readonly CategoryRef[]>([]);
  readonly busy = input(false);

  readonly applied = output<EventDto>();
  readonly partial = output<EventDto>();
  readonly stale = output<void>();
  readonly fix = output<ProblemReason>();
  readonly closed = output<void>();
  readonly keep = output<EventFields>();
  readonly theirs = output<void>();
  readonly leave = output<LeaveChoice>();

  protected readonly working = signal(false);

  protected reinstate(reason: string): void {
    const e = this.event();
    this.run(this.api.action(e.id, 'reinstate', { reason }, e.rev), 'head.reinstated');
  }

  protected revert(rev: number, note: string): void {
    const e = this.event();
    this.run(
      this.api.action(e.id, 'revert-revision', { rev, ...(note && { note }) }, e.rev),
      'tasks.reverted',
    );
  }

  private run(call: Observable<EventDto>, done: 'head.reinstated' | 'tasks.reverted'): void {
    this.working.set(true);
    call.subscribe({
      next: (updated) => {
        this.working.set(false);
        this.toast.success(this.i18n.translate(done));
        this.applied.emit(updated);
      },
      error: (err: unknown) => {
        this.working.set(false);
        const problem = problemOf(err);
        this.toast.error(problemMessage(this.i18n, problem));
        if (problem.status === 409) this.stale.emit();
      },
    });
  }
}
