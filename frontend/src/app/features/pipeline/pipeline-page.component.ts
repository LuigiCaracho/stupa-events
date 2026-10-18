/**
 * I03: the pipeline board (`/pipeline`). Loads `GET /api/events?view=board` with the filters of the URL, shows
 * the columns, and turns a drop, a keyboard drop or a phone sheet choice into a transition: T01 fires at once, every
 * other transition opens the confirm dialog I13. The board refreshes on window focus and every 60 s unless a
 * card is held or a dialog is open. The server decides; a 422 or 409 sends the card back and says why.
 */
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  NgZone,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import type { ProblemReason } from '@core/api/models';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { mediaQuerySignal } from '../../layout/media-query';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { PageHeaderComponent } from '@shared/ui/page-header/page-header.component';
import {
  type BoardMove,
  PipelineBoardComponent,
} from '@shared/ui/pipeline-board/pipeline-board.component';
import { reasonText } from '@shared/ui/guard-list/reason-text';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { ButtonComponent, IconComponent, MEDIA, ToastService } from '@stupa-makers/ui-kit';
import { COLUMN_OF_STATE, type EventCard } from '../dossiers/api/board.models';
import type { EventDto, TransitionId } from '../dossiers/api/event.models';
import { EventsApi } from '../dossiers/api/events-api.service';
import { problemMessage } from '../dossiers/api/problem-message';
import { TransitionDialogComponent } from '../dossiers/transition/transition-dialog.component';
import { BoardCardComponent } from './board-card/board-card.component';
import { createFilterState } from './filters/filter-state';
import { PipelineFiltersComponent } from './filters/pipeline-filters.component';
import { activeFilterCount, filtersToQuery } from './filters/pipeline-filters';
import { MoveSheetComponent } from './move-sheet/move-sheet.component';

const REFRESH_MS = 60_000;
const COLUMN_LIMIT = 50;

interface PendingMove {
  card: EventCard;
  transition: TransitionId;
}

@Component({
  selector: 'app-pipeline-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    BoardCardComponent,
    ButtonComponent,
    EmptyStateComponent,
    IconComponent,
    MoveSheetComponent,
    NoteComponent,
    PageHeaderComponent,
    PipelineBoardComponent,
    PipelineFiltersComponent,
    SkeletonComponent,
    TransitionDialogComponent,
  ],
  host: { '(document:visibilitychange)': 'refreshIfIdle()' },
  templateUrl: './pipeline-page.component.html',
  styleUrl: './pipeline-page.component.scss',
})
export class PipelinePageComponent {
  private readonly api = inject(EventsApi);
  private readonly router = inject(Router);
  private readonly i18n = inject(I18nService);
  private readonly toast = inject(ToastService);

  protected readonly state = createFilterState();
  protected readonly phone = mediaQuerySignal(MEDIA.phone);
  protected readonly holding = signal(false);
  protected readonly pending = signal<PendingMove | null>(null);
  protected readonly sheet = signal<EventCard | null>(null);
  private readonly boardRef = viewChild(PipelineBoardComponent);

  protected readonly board = rxResource({
    params: () => this.state.applied(),
    stream: ({ params }) =>
      this.api.board({ ...filtersToQuery(params), columnLimit: COLUMN_LIMIT }),
  });

  protected readonly columns = computed(() =>
    this.board.hasValue() ? this.board.value().columns : [],
  );
  protected readonly total = computed(() => this.columns().reduce((sum, c) => sum + c.total, 0));
  protected readonly filtered = computed(
    () => activeFilterCount(this.state.applied()) > 0 || this.state.applied().view !== 'active',
  );

  constructor() {
    const zone = inject(NgZone);
    const timer = zone.runOutsideAngular(() =>
      setInterval(() => zone.run(() => this.refreshIfIdle()), REFRESH_MS),
    );
    inject(DestroyRef).onDestroy(() => clearInterval(timer));
  }

  protected refreshIfIdle(): void {
    const hidden = typeof document !== 'undefined' && document.visibilityState === 'hidden';
    if (hidden || this.holding() || this.pending() || this.sheet() || this.board.isLoading())
      return;
    this.board.reload();
  }

  protected open(card: EventCard): void {
    void this.router.navigate(['/dossiers', card.id]);
  }

  protected move(m: BoardMove): void {
    this.request(m.card, m.transition);
  }

  protected chosen(transition: TransitionId): void {
    const card = this.sheet();
    this.sheet.set(null);
    if (card) this.request(card, transition);
  }

  private request(card: EventCard, transition: TransitionId): void {
    if (transition === 'T01') this.fire(card);
    else this.pending.set({ card, transition });
  }

  private fire(card: EventCard): void {
    this.api.transition(card.id, 'T01', {}, card.rev).subscribe({
      next: (updated) => this.moved(updated),
      error: (err: unknown) => this.refused(err),
    });
  }

  protected moved(updated: EventDto): void {
    this.pending.set(null);
    this.boardRef()?.announce(
      this.i18n.translate('board.moved', {
        title: updated.title,
        column: this.i18n.translate(`board.col.${COLUMN_OF_STATE[updated.state]}`),
      }),
    );
    this.board.reload();
  }

  protected stale(): void {
    this.pending.set(null);
    this.toast.error(this.i18n.translate('board.stale'));
    this.board.reload();
  }

  private refused(err: unknown): void {
    const problem = problemOf(err);
    if (problem.status === 409) return this.stale();
    const blockers = (problem.reasons ?? []).filter((r: ProblemReason) => r.severity === 'blocker');
    this.toast.error(
      blockers.length
        ? this.i18n.translate('board.moveRefused', {
            reasons: blockers.map((r) => reasonText(this.i18n, r)).join(' '),
          })
        : problemMessage(this.i18n, problem),
    );
    this.board.reload();
  }

  protected fix(card: EventCard): void {
    this.pending.set(null);
    void this.router.navigate(['/dossiers', card.id]);
  }

  protected list(): void {
    void this.router.navigateByUrl('/dossiers');
  }

  protected newEvent(): void {
    void this.router.navigateByUrl('/dossiers/neu');
  }
}
