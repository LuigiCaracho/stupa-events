/**
 * "Fehlt noch": the guard reasons of a transition, blockers first, each with the one-click
 * fix button its `fixAction` names (PLAN 4.4). The list only displays; the page reacts to `fix`.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import type { ProblemReason } from '@core/api/models';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { TranslationKey } from '@core/i18n/translations';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import { StatusTextComponent } from '../status-text/status-text.component';
import { reasonText } from './reason-text';

@Component({
  selector: 'app-guard-list',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, ButtonComponent, StatusTextComponent],
  templateUrl: './guard-list.component.html',
  styleUrl: './guard-list.component.scss',
})
export class GuardListComponent {
  private readonly i18n = inject(I18nService);

  readonly reasons = input.required<readonly ProblemReason[]>();
  readonly heading = input<TranslationKey>('guards.heading');
  readonly headingId = input('guard-list-heading');

  readonly fix = output<ProblemReason>();

  protected readonly sorted = computed(() => {
    const rank = (r: ProblemReason): number => (r.severity === 'blocker' ? 0 : 1);
    return [...this.reasons()].sort((a, b) => rank(a) - rank(b));
  });

  protected text(reason: ProblemReason): string {
    return reasonText(this.i18n, reason);
  }

  protected fixKey(reason: ProblemReason): TranslationKey | null {
    return reason.fixAction ? (`fix.${reason.fixAction}` as TranslationKey) : null;
  }
}
