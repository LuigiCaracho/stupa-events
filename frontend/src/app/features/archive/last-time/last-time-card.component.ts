/**
 * "Letztes Mal" (M5 contract 4.3): attendance, costs and revenue of the earlier edition and its retrospective. Of another
 * organization only the attendance and a shared retrospective arrive (`restricted`), and the card says where the rest
 * stays. Used in the clone dialog (I06) and on the dossier overview (I07).
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { I18nService } from '@core/i18n/i18n.service';
import { LocalizedDatePipe } from '@core/i18n/localized-date.pipe';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { formatMoney } from '@shared/format.util';
import { MarkdownViewComponent } from '@shared/markdown/markdown-view.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import type { LastTime } from '../model/archive.models';

@Component({
  selector: 'app-last-time-card',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, LocalizedDatePipe, TranslatePipe, MarkdownViewComponent, NoteComponent],
  templateUrl: './last-time-card.component.html',
  styleUrl: './last-time-card.component.scss',
})
export class LastTimeCardComponent {
  private readonly i18n = inject(I18nService);

  readonly lastTime = input.required<LastTime>();
  /** The card links to the earlier edition (it is a dossier or an archive page). */
  readonly linked = input(true);

  protected readonly link = computed(() => {
    const s = this.lastTime().source;
    return s.own ? ['/dossiers', s.id] : ['/archiv', s.id];
  });

  protected money(cents: number): string {
    return formatMoney(this.i18n, cents, 'EUR');
  }
}
