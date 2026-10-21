/**
 * The section "Angebote" of the dossier page: the comparison quotes of the dossier (I08, contract 6.3). The API shows
 * quotes only to those who may see them; without that right the section says so. Every success tells the page.
 */
import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { ToastService } from '@stupa-makers/ui-kit';
import { type Observable, catchError, of } from 'rxjs';
import { AttachmentsApi } from '../api/attachments-api.service';
import type { EventDto } from '../api/event.models';
import { problemMessage } from '../api/problem-message';
import type { QuoteIn, QuotesOut } from '../model/attachment.models';
import { QuotesSectionComponent } from './quotes-section.component';

@Component({
  selector: 'app-quotes-tab',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, QuotesSectionComponent],
  template: `
    @if (quotes.value(); as q) {
      <app-quotes-section
        [quotes]="q"
        [canEdit]="canEdit()"
        [busy]="busy()"
        (add)="add($event)"
        (select)="choose($event)"
        (remove)="remove($event)"
        (budget)="budget.emit($event)"
      />
    } @else {
      <h2 class="sec" id="quotes-heading">{{ 'quote.title' | t }}</h2>
      <p>{{ 'quote.hidden' | t }}</p>
    }
  `,
})
export class QuotesTabComponent {
  private readonly api = inject(AttachmentsApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly event = input.required<EventDto>();
  readonly canEdit = input(false);

  readonly changed = output<void>();
  readonly budget = output<number>();

  protected readonly busy = signal(false);
  protected readonly quotes = rxResource<QuotesOut | null, string>({
    params: () => this.event().id,
    stream: ({ params }) => this.api.quotes(params).pipe(catchError(() => of(null))),
  });

  protected add(body: QuoteIn): void {
    this.run(this.api.addQuote(this.event().id, body));
  }

  protected choose(id: string): void {
    this.run(this.api.selectQuote(id));
  }

  protected remove(id: string): void {
    this.run(this.api.removeQuote(id));
  }

  private run(call: Observable<unknown>): void {
    this.busy.set(true);
    call.subscribe({
      next: () => {
        this.busy.set(false);
        this.quotes.reload();
        this.changed.emit();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.toast.error(problemMessage(this.i18n, problemOf(err)));
      },
    });
  }
}
