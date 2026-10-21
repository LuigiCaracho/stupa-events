/**
 * "Fehlt noch" (M5b contract 3.2, 10.1): the hints of the dossier as a plain, collapsible list with their count. A
 * hint never blocks anything; each one can carry the person to the place where it is fixed. The text comes from the
 * catalog, `hints.<code>`; an unknown code shows the generic line.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { de, type TranslationKey } from '@core/i18n/translations';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import type { Hint } from '../api/event.models';

interface Line {
  hint: Hint;
  text: string;
}

@Component({
  selector: 'app-hint-list',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, ButtonComponent, StatusTextComponent],
  templateUrl: './hint-list.component.html',
  styleUrl: './hint-list.component.scss',
})
export class HintListComponent {
  private readonly i18n = inject(I18nService);

  readonly hints = input<readonly Hint[]>([]);
  readonly fix = output<Hint>();

  protected readonly lines = computed<Line[]>(() =>
    [...this.hints()]
      .sort((a, b) => Number(b.severity === 'warn') - Number(a.severity === 'warn'))
      .map((hint) => ({ hint, text: this.text(hint) })),
  );

  private text(hint: Hint): string {
    const key = `hints.${hint.code}`;
    return this.i18n.translate((key in de ? key : 'hints.unknown') as TranslationKey);
  }
}
