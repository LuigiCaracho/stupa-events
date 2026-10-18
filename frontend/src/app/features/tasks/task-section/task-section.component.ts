/**
 * One section of "Meine Aufgaben": a card with an `h2`, a count badge and a list of dossiers. Each row links to
 * the dossier; the page can project extra content per row (`#row` template) such as the question of a return or
 * the buttons of a changed dossier.
 */
import { NgTemplateOutlet } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  TemplateRef,
  contentChild,
  inject,
  input,
} from '@angular/core';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { TranslationKey } from '@core/i18n/translations';
import { eventStateStatus } from '@shared/status-kind.util';
import { ListItemComponent } from '@shared/ui/list-item/list-item.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { BadgeComponent, CardComponent } from '@stupa-makers/ui-kit';
import type { EventCard } from '../../dossiers/api/board.models';
import { formatEventDay } from '../../dossiers/api/event-time';
import { deadline } from '../task-deadline';

@Component({
  selector: 'app-task-section',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    NgTemplateOutlet,
    TranslatePipe,
    BadgeComponent,
    CardComponent,
    ListItemComponent,
    StatusTextComponent,
  ],
  templateUrl: './task-section.component.html',
  styleUrl: './task-section.component.scss',
})
export class TaskSectionComponent {
  private readonly i18n = inject(I18nService);

  readonly heading = input.required<TranslationKey>();
  readonly count = input.required<number>();
  readonly cards = input.required<readonly EventCard[]>();
  readonly showDeadline = input(false);
  readonly showState = input(false);

  protected readonly row = contentChild<TemplateRef<{ $implicit: EventCard }>>('row');

  protected sub(card: EventCard): string {
    const org = card.organization?.short ?? this.i18n.translate('dossiers.noOrg');
    return `${org} · ${formatEventDay(card.startsAt, card.tzid)}`;
  }

  protected state(card: EventCard) {
    return eventStateStatus(card.state);
  }

  protected due(card: EventCard) {
    return deadline(card.startsAt, new Date(), (key, params) => this.i18n.translate(key, params));
  }
}
