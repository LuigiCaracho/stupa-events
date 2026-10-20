/**
 * Comparison quotes of a dossier (I08, contract 6.3): one table per group, a form for a new quote, the sum of the
 * chosen ones and "Als Budget übernehmen", which only hands the suggestion to the page. Shown only when the API
 * lets the person see quotes; the amounts appear nowhere else.
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { formatMoney } from '@shared/format.util';
import { QuoteTableComponent } from '@shared/ui/quote-table/quote-table.component';
import { ButtonComponent, CurrencyInputComponent, InputComponent } from '@stupa-makers/ui-kit';
import type { QuoteIn, QuotesOut } from '../model/attachment.models';

@Component({
  selector: 'app-quotes-section',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslatePipe,
    ButtonComponent,
    CurrencyInputComponent,
    InputComponent,
    QuoteTableComponent,
  ],
  templateUrl: './quotes-section.component.html',
  styleUrl: './quotes-section.component.scss',
})
export class QuotesSectionComponent {
  private readonly i18n = inject(I18nService);

  readonly quotes = input.required<QuotesOut>();
  readonly canEdit = input(false);
  readonly busy = input(false);

  readonly add = output<QuoteIn>();
  readonly select = output<string>();
  readonly remove = output<string>();
  readonly budget = output<number>();

  protected readonly open = signal(false);
  protected readonly attempted = signal(false);
  protected readonly form = inject(FormBuilder).nonNullable.group({
    grp: ['', [Validators.required, Validators.maxLength(80)]],
    vendor: ['', [Validators.required, Validators.maxLength(120)]],
    amount: ['', [Validators.required]],
    validUntil: [''],
  });

  protected readonly hasSum = computed(() => this.quotes().groups.some((g) => g.selectedId));

  protected total(): string {
    const q = this.quotes();
    return formatMoney(this.i18n, q.selectedTotalCents, q.selectedTotalCurrency);
  }

  protected submit(): void {
    this.attempted.set(true);
    const v = this.form.getRawValue();
    const amountCents = Math.round(Number(v.amount) * 100);
    if (this.form.invalid || !(amountCents > 0)) return;
    this.add.emit({
      grp: v.grp.trim(),
      vendor: v.vendor.trim(),
      amountCents,
      ...(v.validUntil && { validUntil: v.validUntil }),
    });
    this.form.reset();
    this.attempted.set(false);
    this.open.set(false);
  }

  protected bad(name: 'grp' | 'vendor' | 'amount'): boolean {
    return this.attempted() && this.form.controls[name].invalid;
  }
}
