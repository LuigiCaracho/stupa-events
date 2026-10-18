/**
 * I04: dossier list (`/dossiers`, `/dossiers/neu`). Live search and a state filter over
 * `GET /api/events`, one row per dossier; on `/dossiers/neu` the dialog I05 opens over the list.
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { ListItemComponent } from '@shared/ui/list-item/list-item.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { PageHeaderComponent } from '@shared/ui/page-header/page-header.component';
import { SelectFieldComponent, type SelectFieldOption } from '@shared/ui/select/select.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { type EventState, eventStateStatus } from '@shared/status-kind.util';
import { ButtonComponent, InputComponent } from '@stupa-makers/ui-kit';
import { formatEventTime } from '../api/event-time';
import type { EventDto } from '../api/event.models';
import { EventsApi } from '../api/events-api.service';
import { NewEventDialogComponent } from '../new-event/new-event-dialog.component';

const STATES: readonly EventState[] = [
  'idea',
  'planning',
  'in_review',
  'approved',
  'live',
  'followup',
  'archived',
  'withdrawn',
];
const SEARCH_DELAY_MS = 250;

@Component({
  selector: 'app-dossier-list',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    FormsModule,
    TranslatePipe,
    ButtonComponent,
    EmptyStateComponent,
    InputComponent,
    ListItemComponent,
    NewEventDialogComponent,
    NoteComponent,
    PageHeaderComponent,
    SelectFieldComponent,
    SkeletonComponent,
    StatusTextComponent,
  ],
  templateUrl: './dossier-list.component.html',
  styleUrl: './dossier-list.component.scss',
})
export class DossierListComponent {
  private readonly api = inject(EventsApi);
  private readonly i18n = inject(I18nService);
  private readonly router = inject(Router);

  protected readonly newOpen = inject(ActivatedRoute).snapshot.data['newEvent'] === true;
  protected readonly search = signal('');
  protected readonly state = signal('');
  private timer: ReturnType<typeof setTimeout> | undefined;
  private readonly query = signal('');

  protected readonly events = rxResource({
    params: () => ({ q: this.query(), state: this.state() as EventState | '' }),
    stream: ({ params }) =>
      this.api.list({ q: params.q, state: params.state || undefined, limit: 200 }),
  });

  protected readonly stateOptions = computed<SelectFieldOption[]>(() =>
    STATES.map((s) => ({ value: s, label: this.i18n.translate(eventStateStatus(s).key) })),
  );

  protected readonly rows = computed(() => this.events.hasValue() ? this.events.value().items : []);
  protected readonly meta = computed(() => {
    return this.events.hasValue()
      ? this.i18n.translate('dossiers.count', { count: this.events.value().total })
      : null;
  });
  protected readonly filtered = computed(() => this.query() !== '' || this.state() !== '');

  protected onSearch(value: string): void {
    this.search.set(value);
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.query.set(value.trim()), SEARCH_DELAY_MS);
  }

  protected reset(): void {
    clearTimeout(this.timer);
    this.search.set('');
    this.query.set('');
    this.state.set('');
  }

  protected when(event: EventDto): string {
    return formatEventTime(event.startsAt, event.tzid);
  }

  protected sub(event: EventDto): string {
    const parts = [event.organization?.short ?? this.i18n.translate('dossiers.noOrg'), event.venueText];
    return parts.filter(Boolean).join(' · ');
  }

  protected status(event: EventDto) {
    return eventStateStatus(event.state);
  }

  protected openNew(): void {
    void this.router.navigateByUrl('/dossiers/neu');
  }

  protected closeNew(): void {
    void this.router.navigateByUrl('/dossiers');
  }

  protected opened(event: EventDto): void {
    void this.router.navigate(['/dossiers', event.id]);
  }
}
