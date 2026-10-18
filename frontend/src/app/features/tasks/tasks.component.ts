/**
 * I02 (light): "Meine Aufgaben" (`/aufgaben`). Dossiers that wait for the principal's approval
 * and the other open dossiers of the principal's organizations; a button (fab on phones) starts I05.
 */
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { ListItemComponent } from '@shared/ui/list-item/list-item.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { PageHeaderComponent } from '@shared/ui/page-header/page-header.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { type EventState, eventStateStatus } from '@shared/status-kind.util';
import { BadgeComponent, ButtonComponent, CardComponent, IconComponent } from '@stupa-makers/ui-kit';
import { formatEventTime } from '../dossiers/api/event-time';
import type { EventDto } from '../dossiers/api/event.models';
import { EventsApi } from '../dossiers/api/events-api.service';

const OPEN: readonly EventState[] = ['idea', 'planning', 'in_review', 'approved'];

@Component({
  selector: 'app-tasks',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    BadgeComponent,
    ButtonComponent,
    CardComponent,
    EmptyStateComponent,
    IconComponent,
    ListItemComponent,
    NoteComponent,
    PageHeaderComponent,
    SkeletonComponent,
    StatusTextComponent,
  ],
  templateUrl: './tasks.component.html',
  styleUrl: './tasks.component.scss',
})
export class TasksComponent {
  private readonly api = inject(EventsApi);
  private readonly i18n = inject(I18nService);
  private readonly router = inject(Router);

  protected readonly events = rxResource({ stream: () => this.api.list({ limit: 200 }) });

  private readonly open = computed(() =>
    (this.events.hasValue() ? this.events.value().items : []).filter((e) => OPEN.includes(e.state)),
  );
  protected readonly awaiting = computed(() =>
    this.open().filter((e) => e.state === 'in_review' && e.allowedTransitions.includes('T04')),
  );
  protected readonly mine = computed(() => this.open().filter((e) => !this.awaiting().includes(e)));

  protected status(event: EventDto) {
    return eventStateStatus(event.state);
  }

  protected sub(event: EventDto): string {
    const org = event.organization?.short ?? this.i18n.translate('dossiers.noOrg');
    return `${org} · ${formatEventTime(event.startsAt, event.tzid)}`;
  }

  protected openNew(): void {
    void this.router.navigateByUrl('/dossiers/neu');
  }
}
