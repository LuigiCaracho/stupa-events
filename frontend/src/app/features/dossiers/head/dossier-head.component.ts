/**
 * Head of the dossier page (M5b contract 10.1): title, state as text (plus "Abgesagt"/"Verschoben" with its public
 * reason), time, organization, venue and category, and the action bar. The bar shows exactly the actions the server
 * lists in `allowedActions`; the page runs them. "Als Format speichern" and "Ort bestätigen" sit in the menu "Mehr".
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { RouterLink } from '@angular/router';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { TranslationKey } from '@core/i18n/translations';
import { eventStateStatus } from '@shared/status-kind.util';
import {
  RowMenuComponent,
  type RowMenuItem,
  type RowMenuSection,
} from '@shared/ui/row-menu/row-menu.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import { formatEventTime } from '@shared/event-time';
import type { EventAction, EventDto } from '../api/event.models';

export type HeadCommand = Exclude<EventAction, 'revert-revision' | 'verify-howto'>;

interface Bar {
  action: HeadCommand;
  label: TranslationKey;
  variant: 'fill' | 'tonal' | 'text';
}

const BAR: readonly Bar[] = [
  { action: 'publish', label: 'head.publish', variant: 'fill' },
  { action: 'restore', label: 'head.restore', variant: 'fill' },
  { action: 'unpublish', label: 'head.unpublish', variant: 'tonal' },
  { action: 'cancel', label: 'head.cancel', variant: 'tonal' },
  { action: 'postpone', label: 'head.postpone', variant: 'tonal' },
  { action: 'reinstate', label: 'head.reinstate', variant: 'tonal' },
  { action: 'archive', label: 'head.archive', variant: 'tonal' },
  { action: 'clone', label: 'head.clone', variant: 'text' },
];

const MENU: readonly { action: HeadCommand; label: TranslationKey }[] = [
  { action: 'confirm-location', label: 'head.confirmLocation' },
  { action: 'save-as-format', label: 'head.saveAsFormat' },
];

@Component({
  selector: 'app-dossier-head',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, TranslatePipe, ButtonComponent, RowMenuComponent, StatusTextComponent],
  templateUrl: './dossier-head.component.html',
  styleUrl: './dossier-head.component.scss',
})
export class DossierHeadComponent {
  private readonly i18n = inject(I18nService);

  readonly event = input.required<EventDto>();
  /** The archived dossier has a howto nobody checked (derived by the page, M5 contract 3.2). */
  readonly howtoUnverified = input(false);
  /** A call runs; the bar waits. */
  readonly busy = input(false);

  readonly command = output<HeadCommand>();

  protected readonly state = computed(() => eventStateStatus(this.event().state));
  protected readonly when = computed(
    () =>
      `${formatEventTime(this.event().startsAt, this.event().tzid)} – ${formatEventTime(this.event().endsAt, this.event().tzid)}`,
  );
  protected readonly where = computed(() => {
    const e = this.event();
    return e.venue?.name ?? e.venueText;
  });

  protected readonly publicLine = computed(() => {
    const e = this.event();
    if (e.publicStatus === 'scheduled') return null;
    const kind = e.publicStatus === 'cancelled' ? ('error' as const) : ('warn' as const);
    const status = this.i18n.translate(
      e.publicStatus === 'cancelled' ? 'publicStatus.cancelled' : 'publicStatus.postponed',
    );
    const code = e.publicReason?.code;
    const reason = code && code !== 'none' ? this.i18n.translate(`publicReason.${code}`) : '';
    return { kind, text: [status, reason, e.publicReason?.text].filter(Boolean).join(' · ') };
  });

  protected readonly bar = computed(() =>
    BAR.filter((b) => this.event().allowedActions.includes(b.action)),
  );

  protected readonly sections = computed<RowMenuSection[]>(() => {
    const allowed = this.event().allowedActions;
    const items: RowMenuItem[] = MENU.filter((m) => allowed.includes(m.action)).map((m) => ({
      id: m.action,
      label: this.i18n.translate(m.label),
    }));
    return items.length > 0 ? [{ items }] : [];
  });

  protected selected(item: RowMenuItem): void {
    this.command.emit(item.id as HeadCommand);
  }
}
