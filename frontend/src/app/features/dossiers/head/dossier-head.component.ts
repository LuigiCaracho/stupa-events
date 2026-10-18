/**
 * Head of the dossier page (I07): title, state, public status with its public reason as text, organization and
 * time, the primary button of the state (`idea: T01, planning: T02, in_review: T04, approved: T05, followup: T09`, only when
 * the server allows it) and the menu "Mehr" with the other transitions and the actions. The page runs the commands.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { type EventState, eventStateStatus } from '@shared/status-kind.util';
import {
  RowMenuComponent,
  type RowMenuItem,
  type RowMenuSection,
} from '@shared/ui/row-menu/row-menu.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import { formatEventTime } from '../api/event-time';
import type { EventDto, TransitionId } from '../api/event.models';
import { TRANSITION_LABEL } from '../api/transition-label';
import { PRIMARY_TRANSITION, menuTransitions } from '../api/transitions';

const PATH: readonly EventState[] = [
  'idea',
  'planning',
  'in_review',
  'approved',
  'live',
  'followup',
];

export type HeadAction = 'cancel' | 'reinstate' | 'exception' | 'assign' | 'confirm-flyer';

export type HeadCommand =
  { kind: 'transition'; id: TransitionId } | { kind: 'action'; name: HeadAction };

const ACTION_OF: Record<string, HeadAction> = {
  cancel: 'cancel',
  postpone: 'cancel',
  reinstate: 'reinstate',
  'image-exception': 'exception',
  'assign-organization': 'assign',
  'confirm-flyer': 'confirm-flyer',
};

@Component({
  selector: 'app-dossier-head',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, ButtonComponent, RowMenuComponent, StatusTextComponent],
  templateUrl: './dossier-head.component.html',
  styleUrl: './dossier-head.component.scss',
})
export class DossierHeadComponent {
  private readonly i18n = inject(I18nService);

  readonly event = input.required<EventDto>();
  /** The action names the page offers (`allowedActions` of the server). */
  readonly actions = input<readonly string[]>([]);

  readonly command = output<HeadCommand>();

  protected readonly state = computed(() => eventStateStatus(this.event().state));
  protected readonly when = computed(
    () =>
      `${formatEventTime(this.event().startsAt, this.event().tzid)} – ${formatEventTime(this.event().endsAt, this.event().tzid)}`,
  );
  /** The states of the main path with the position of the current one; archived and withdrawn show no bar. */
  protected readonly steps = computed(() => {
    const at = PATH.indexOf(this.event().state);
    if (at < 0) return [];
    return PATH.map((state, i) => ({
      key: eventStateStatus(state).key,
      current: i === at,
      done: i < at,
    }));
  });
  protected readonly primary = computed<TransitionId | null>(() => {
    const e = this.event();
    const t = PRIMARY_TRANSITION[e.state];
    return t && e.allowedTransitions.includes(t) ? t : null;
  });
  protected readonly label = TRANSITION_LABEL;

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

  protected readonly sections = computed<RowMenuSection[]>(() => {
    const e = this.event();
    const t = this.i18n.translate.bind(this.i18n);
    const transitions: RowMenuItem[] = menuTransitions(e.state, e.allowedTransitions).map((id) => ({
      id: `T:${id}`,
      label: t(TRANSITION_LABEL[id]),
      danger: id === 'T11',
    }));
    const names = new Set(
      this.actions()
        .map((a) => ACTION_OF[a])
        .filter(Boolean),
    );
    const actions: RowMenuItem[] = [];
    if (names.has('cancel')) actions.push({ id: 'A:cancel', label: t('head.cancel') });
    if (names.has('reinstate') && e.publicStatus !== 'scheduled')
      actions.push({ id: 'A:reinstate', label: t('head.reinstate') });
    if (names.has('confirm-flyer'))
      actions.push({ id: 'A:confirm-flyer', label: t('head.confirmFlyer') });
    if (names.has('exception')) actions.push({ id: 'A:exception', label: t('detail.exception') });
    if (names.has('assign')) actions.push({ id: 'A:assign', label: t('head.assign') });
    return [{ items: actions }, { items: transitions }].filter((s) => s.items.length > 0);
  });

  protected selected(item: RowMenuItem): void {
    const [kind, value] = item.id.split(':');
    this.command.emit(
      kind === 'T'
        ? { kind: 'transition', id: value as TransitionId }
        : { kind: 'action', name: value as HeadAction },
    );
  }
}
