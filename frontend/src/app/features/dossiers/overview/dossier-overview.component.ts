/**
 * Overview block of the dossier page (I07): the banner "Seit der Veröffentlichung geändert" for reviewers, the lock
 * and exception notes, the "Fehlt noch" guard list of the next transition with its fix buttons and, when nothing
 * is editable, the core data as read-only rows.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import type { ProblemReason } from '@core/api/models';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { TranslationKey } from '@core/i18n/translations';
import {
  FieldGroupComponent,
  FieldRowComponent,
} from '@shared/ui/field-group/field-group.component';
import { GuardListComponent } from '@shared/ui/guard-list/guard-list.component';
import { fieldLabel } from '@shared/ui/guard-list/reason-text';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import type { RevisionOut } from '../api/action.models';
import { formatEventTime } from '../api/event-time';
import type { EventDto, GuardResult } from '../api/event.models';

@Component({
  selector: 'app-dossier-overview',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    ButtonComponent,
    FieldGroupComponent,
    FieldRowComponent,
    GuardListComponent,
    NoteComponent,
    SkeletonComponent,
  ],
  templateUrl: './dossier-overview.component.html',
  styleUrl: './dossier-overview.component.scss',
})
export class DossierOverviewComponent {
  private readonly i18n = inject(I18nService);

  readonly event = input.required<EventDto>();
  readonly guards = input<GuardResult | null>(null);
  readonly guardsLoading = input(false);
  readonly changes = input<readonly RevisionOut[]>([]);
  readonly readOnly = input(false);
  readonly busy = input(false);

  readonly fix = output<ProblemReason>();
  readonly revert = output<void>();
  readonly acknowledge = output<void>();

  protected readonly when = computed(
    () =>
      `${formatEventTime(this.event().startsAt, this.event().tzid)} – ${formatEventTime(this.event().endsAt, this.event().tzid)}`,
  );

  protected readonly lockKey = computed<TranslationKey | null>(() => {
    const reason = this.event().lockReason;
    return reason ? (`lock.${reason}` as TranslationKey) : null;
  });

  protected readonly changeLine = computed(() => {
    const list = this.changes();
    if (list.length === 0) return '';
    const fields = [...new Set(list.flatMap((r) => r.changedFields))]
      .map((f) => fieldLabel(this.i18n, f))
      .join(', ');
    const last = list[0];
    const time = new Date(last.at).toLocaleTimeString('de-DE', {
      hour: '2-digit',
      minute: '2-digit',
    });
    return this.i18n.translate('changes.line', {
      fields,
      who: last.actor.displayName ?? '?',
      time,
    });
  });
}
