/**
 * The internal calendar inside the event list (M5b contract 10.2): month or week as a grid, an agenda list on the
 * phone. The list page owns the filters and the Liste | Kalender switch; this view owns period and mode, asks the
 * endpoint for exactly the range the grid reports and opens a clicked dossier.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import {
  CALENDAR_NOW,
  CalendarGridComponent,
} from '@shared/ui/calendar-grid/calendar-grid.component';
import {
  type CalendarMode,
  type DayRange,
  periodTitle,
  shiftAnchor,
  todayKey,
} from '@shared/ui/calendar-grid/calendar-grid.util';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { ButtonComponent, SegmentedComponent, type SegmentedOption } from '@stupa-makers/ui-kit';
import { of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { type EventFilters, statesOf } from '../../dossiers/filters/event-filters';
import { CalendarApi } from '../api/calendar-api.service';
import { toGridEntry } from '../model/calendar-entries';
import type { CalendarOut } from '../model/calendar.models';

@Component({
  selector: 'app-calendar-view',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    ButtonComponent,
    CalendarGridComponent,
    NoteComponent,
    SegmentedComponent,
    SkeletonComponent,
  ],
  templateUrl: './calendar-view.component.html',
  styleUrl: './calendar-view.component.scss',
})
export class CalendarViewComponent {
  private readonly api = inject(CalendarApi);
  private readonly router = inject(Router);
  private readonly i18n = inject(I18nService);
  private readonly now = inject(CALENDAR_NOW);

  readonly filters = input.required<EventFilters>();

  protected readonly mode = signal<CalendarMode>('month');
  protected readonly anchor = signal(todayKey(this.now()));
  protected readonly range = signal<DayRange | null>(null);

  protected readonly data = rxResource<
    CalendarOut | null,
    { range: DayRange; filters: EventFilters } | undefined
  >({
    params: () => {
      const range = this.range();
      return range ? { range, filters: this.filters() } : undefined;
    },
    stream: ({ params }) => {
      const f = params.filters;
      const state = statesOf(f.state);
      return this.api
        .range({
          ...params.range,
          q: f.q || undefined,
          organization: f.organization || undefined,
          category: f.category || undefined,
          mine: f.mine || undefined,
          ...(state.length > 0 ? { state } : {}),
        })
        .pipe(catchError(() => of(null)));
    },
  });

  protected readonly entries = computed(() =>
    (this.data.value()?.entries ?? [])
      .filter((e) => this.filters().state !== 'cancelled' || e.publicStatus === 'cancelled')
      .map(toGridEntry),
  );
  protected readonly title = computed(() => periodTitle(this.mode(), this.anchor()));
  protected readonly failed = computed(() => this.data.hasValue() && this.data.value() === null);
  protected readonly modes = computed<SegmentedOption[]>(() =>
    (['month', 'week'] as const).map((value) => ({
      value,
      label: this.i18n.translate(`calendar.${value}`),
    })),
  );

  protected step(direction: -1 | 1): void {
    this.anchor.set(shiftAnchor(this.mode(), this.anchor(), direction));
  }

  protected today(): void {
    this.anchor.set(todayKey(this.now()));
  }

  protected setMode(value: string | null): void {
    this.mode.set(value === 'week' ? 'week' : 'month');
  }

  protected open(id: string): void {
    void this.router.navigate(['/dossiers', id]);
  }
}
