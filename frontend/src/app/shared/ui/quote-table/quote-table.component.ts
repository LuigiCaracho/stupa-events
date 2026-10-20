/**
 * Comparison quotes of one group (M4 contract 5.8): vendor, amount, valid-until and the choice. Pattern from the kit's
 * data table, built as a plain table that turns into cards below 768 px. The cheapest quote carries the word
 * "günstigstes", an expired one an error text; the choice is a radio, so one quote per group.
 */
import { ChangeDetectionStrategy, Component, inject, input, output } from '@angular/core';
import { I18nService } from '@core/i18n/i18n.service';
import { LocalizedDatePipe } from '@core/i18n/localized-date.pipe';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import type { QuoteGroup } from '../../../features/dossiers/model/attachment.models';
import { formatMoney } from '../../format.util';
import { StatusTextComponent } from '../status-text/status-text.component';

@Component({
  selector: 'app-quote-table',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LocalizedDatePipe, TranslatePipe, ButtonComponent, StatusTextComponent],
  templateUrl: './quote-table.component.html',
  styleUrl: './quote-table.component.scss',
})
export class QuoteTableComponent {
  private readonly i18n = inject(I18nService);

  readonly group = input.required<QuoteGroup>();
  readonly canEdit = input(false);

  readonly select = output<string>();
  readonly remove = output<string>();

  protected money(cents: number, currency: string): string {
    return formatMoney(this.i18n, cents, currency);
  }
}
