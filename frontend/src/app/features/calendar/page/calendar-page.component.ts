/**
 * The internal calendar (`/kalender`, M5 contract 7): month or week as a grid, an agenda list on the phone. The page
 * owns period and mode, asks the endpoint for exactly the range the grid reports, takes the filters of the board
 * (the URL carries them, so the list/calendar switch of I04 keeps them) and opens a clicked dossier.
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
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
import { PageHeaderComponent } from '@shared/ui/page-header/page-header.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { StickyBarComponent } from '@shared/ui/sticky-bar/sticky-bar.component';
import { ButtonComponent, SegmentedComponent, type SegmentedOption } from '@stupa-makers/ui-kit';
import { of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { createFilterState } from '../../pipeline/filters/filter-state';
import { PipelineFiltersComponent } from '../../pipeline/filters/pipeline-filters.component';
import { CalendarApi } from '../api/calendar-api.service';
import { toGridEntry } from '../model/calendar-entries';
import type { CalendarOut } from '../model/calendar.models';

@Component({
  selector: 'app-calendar-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    ButtonComponent,
    CalendarGridComponent,
    NoteComponent,
    PageHeaderComponent,
    PipelineFiltersComponent,
    SegmentedComponent,
    SkeletonComponent,
    StickyBarComponent,
  ],
  templateUrl: './calendar-page.component.html',
  styleUrl: './calendar-page.component.scss',
})
export class CalendarPageComponent {
  private readonly api = inject(CalendarApi);
  private readonly router = inject(Router);
  private readonly i18n = inject(I18nService);
  private readonly now = inject(CALENDAR_NOW);

  protected readonly state = createFilterState();
  protected readonly mode = signal<CalendarMode>('month');
  protected readonly anchor = signal(todayKey(this.now()));
  protected readonly range = signal<DayRange | null>(null);

  protected readonly data = rxResource<CalendarOut | null, { range: DayRange } | undefined>({
    params: () => {
      const range = this.range();
      return range ? { range } : undefined;
    },
    stream: ({ params }) => {
      const f = this.state.applied();
      return this.api
        .range({
          ...params.range,
          q: f.q || undefined,
          organization: f.organization || undefined,
          category: f.category || undefined,
          mine: f.mine || undefined,
        })
        .pipe(catchError(() => of(null)));
    },
  });

  protected readonly entries = computed(() => (this.data.value()?.entries ?? []).map(toGridEntry));
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

  protected toList(): void {
    void this.router.navigate(['/dossiers'], { queryParamsHandling: 'preserve' });
  }
}
