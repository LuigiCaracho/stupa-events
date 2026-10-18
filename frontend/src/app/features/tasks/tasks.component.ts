/**
 * I02: "Meine Aufgaben" (`/aufgaben`) from `GET /api/tasks`. Sections, each an `h2`: waiting for the principal's
 * approval (with the traffic light of the date and the four-eyes hint), returned to the principal with the question,
 * due checklist items (empty until M4), own dossiers by state, open follow-ups and dossiers changed after publishing
 * (reset or acknowledge). A fab (phone) starts I05.
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { EventState } from '@shared/status-kind.util';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { PageHeaderComponent } from '@shared/ui/page-header/page-header.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { ButtonComponent, IconComponent, ToastService } from '@stupa-makers/ui-kit';
import { formatEventDay } from '../dossiers/api/event-time';
import { EventsApi } from '../dossiers/api/events-api.service';
import { problemMessage } from '../dossiers/api/problem-message';
import type { ChangedCard, ReturnedCard } from '../dossiers/api/task.models';
import { ReasonDialogComponent } from '../dossiers/reason/reason-dialog.component';
import { TaskSectionComponent } from './task-section/task-section.component';

const OPEN_ORDER: readonly EventState[] = ['idea', 'planning', 'in_review', 'approved'];

@Component({
  selector: 'app-tasks',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    ButtonComponent,
    EmptyStateComponent,
    IconComponent,
    NoteComponent,
    PageHeaderComponent,
    ReasonDialogComponent,
    SkeletonComponent,
    TaskSectionComponent,
  ],
  templateUrl: './tasks.component.html',
  styleUrl: './tasks.component.scss',
})
export class TasksComponent {
  private readonly api = inject(EventsApi);
  private readonly i18n = inject(I18nService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastService);

  protected readonly tasks = rxResource({ stream: () => this.api.tasks() });
  protected readonly value = computed(() => (this.tasks.hasValue() ? this.tasks.value() : null));
  protected readonly reverting = signal<ChangedCard | null>(null);
  protected readonly busy = signal(false);

  protected readonly empty = computed(() => {
    const counts = this.value()?.counts;
    return !!counts && Object.values(counts).every((n) => n === 0);
  });

  protected readonly mineSorted = computed(() =>
    [...(this.value()?.mine ?? [])].sort(
      (a, b) => OPEN_ORDER.indexOf(a.state) - OPEN_ORDER.indexOf(b.state),
    ),
  );

  protected returnedLine(card: ReturnedCard): string {
    const who = card.returnedBy.displayName ?? '?';
    return this.i18n.translate('tasks.returnedLine', {
      who,
      day: formatEventDay(card.returnedAt, card.tzid),
      note: card.note,
    });
  }

  protected openNew(): void {
    void this.router.navigateByUrl('/dossiers/neu');
  }

  protected acknowledge(card: ChangedCard): void {
    this.run(this.api.action(card.id, 'acknowledge-changes', {}, card.rev), 'tasks.acknowledged');
  }

  protected revert(note: string): void {
    const card = this.reverting();
    if (!card) return;
    this.run(
      this.api.action(
        card.id,
        'revert-revision',
        { rev: card.baselineRev, ...(note && { note }) },
        card.rev,
      ),
      'tasks.reverted',
    );
  }

  private run(
    call: ReturnType<EventsApi['action']>,
    done: 'tasks.acknowledged' | 'tasks.reverted',
  ): void {
    this.busy.set(true);
    call.subscribe({
      next: () => {
        this.busy.set(false);
        this.reverting.set(null);
        this.toast.success(this.i18n.translate(done));
        this.tasks.reload();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.toast.error(problemMessage(this.i18n, problemOf(err)));
        this.tasks.reload();
      },
    });
  }
}
