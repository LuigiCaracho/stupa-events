/**
 * "Was wird übernommen" (I06): the lines of the carry-over table (`CARRY_OVER`, M5 contract 4.2) in four groups, each
 * with the reason in words, for example "Poster: Datum im Bild, bitte neu gestalten". The server sends the lines, the
 * preview and the clone report are the same list; this block only draws them. Unknown parts show their raw name.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { dynamicKey } from '@core/i18n/dynamic-key';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { TranslationKey } from '@core/i18n/translations';
import type { CarryMode, CarryOverLine } from '../model/archive.models';

const ORDER: readonly CarryMode[] = ['copy', 'reset', 'partial', 'link', 'never'];
const HEADING: Record<CarryMode, TranslationKey> = {
  copy: 'clone.group.carried',
  reset: 'clone.group.reset',
  partial: 'clone.group.partial',
  link: 'clone.group.linked',
  never: 'clone.group.never',
};
const REASON_PREFIX = 'clone.reason.';

interface Row {
  part: string;
  reason: string | null;
}

@Component({
  selector: 'app-carry-over-list',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe],
  templateUrl: './carry-over-list.component.html',
  styleUrl: './carry-over-list.component.scss',
})
export class CarryOverListComponent {
  private readonly i18n = inject(I18nService);

  readonly report = input.required<readonly CarryOverLine[]>();

  protected readonly groups = computed(() =>
    ORDER.map((mode) => ({
      mode,
      heading: HEADING[mode],
      rows: this.report()
        .filter((line) => line.mode === mode)
        .map<Row>((line) => this.row(line)),
    })).filter((group) => group.rows.length > 0),
  );

  private row(line: CarryOverLine): Row {
    const partKey = dynamicKey('clone.part', line.part);
    const reasonKey = dynamicKey('clone.reason', line.reason.replace(REASON_PREFIX, ''));
    const part = partKey ? this.i18n.translate(partKey) : line.part;
    const label = line.count ? `${part} (${line.count})` : part;
    return { part: label, reason: reasonKey ? this.i18n.translate(reasonKey) : null };
  }
}
