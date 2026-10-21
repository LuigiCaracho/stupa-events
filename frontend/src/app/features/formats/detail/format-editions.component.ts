/**
 * "Ausgaben" of a format (I18): date, state as text, attendance, actual costs and "Anleitung ungeprüft". Costs of
 * another organization's edition are not sent (`null`), the cell then shows a dash. A row opens the dossier, or the
 * archive page when the edition belongs to another organization.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { formatMoney } from '@shared/format.util';
import { eventStateStatus } from '@shared/status-kind.util';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { CellDirective, DataTableComponent, type ColumnDef } from '@stupa-makers/ui-kit';
import { formatEventDay } from '../../dossiers/api/event-time';
import type { FormatEdition } from '../model/format.models';

@Component({
  selector: 'app-format-editions',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, CellDirective, DataTableComponent, StatusTextComponent],
  templateUrl: './format-editions.component.html',
})
export class FormatEditionsComponent {
  private readonly i18n = inject(I18nService);

  readonly editions = input.required<readonly FormatEdition[]>();
  readonly loading = input(false);
  readonly open = output<FormatEdition>();

  protected readonly columns = computed<ColumnDef[]>(() => [
    { key: 'startsAt', label: this.i18n.translate('format.col.date'), card: 'title', initialSort: 'desc' },
    { key: 'state', label: this.i18n.translate('format.col.state') },
    { key: 'attendance', label: this.i18n.translate('outcome.attendance'), align: 'end' },
    { key: 'costsCents', label: this.i18n.translate('format.col.costs'), align: 'end' },
    { key: 'howtoUnverified', label: this.i18n.translate('format.col.howto') },
  ]);
  protected readonly rowKey = (row: unknown): unknown => (row as FormatEdition).id;

  protected day(e: FormatEdition): string {
    return formatEventDay(e.startsAt, 'Europe/Berlin');
  }

  protected state(e: FormatEdition) {
    return eventStateStatus(e.state);
  }

  protected money(e: FormatEdition): string {
    return e.costsCents === null ? '–' : formatMoney(this.i18n, e.costsCents, 'EUR');
  }
}
