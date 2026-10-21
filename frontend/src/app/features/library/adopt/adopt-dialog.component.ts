/**
 * "In Dossier übernehmen" (I19): pick one of your own open dossiers; the server copies the text into it (a howto becomes a
 * note when the dossier has one already). Files are never copied, only linked from their source.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { SelectFieldComponent, type SelectFieldOption } from '@shared/ui/select/select.component';
import { ButtonComponent, DialogComponent, ToastService } from '@stupa-makers/ui-kit';
import { catchError, of } from 'rxjs';
import type { CardPage } from '../../dossiers/api/card.models';
import { EventsApi } from '../../dossiers/api/events-api.service';
import { problemMessage } from '../../dossiers/api/problem-message';
import { LibraryApi } from '../api/library-api.service';
import { resourceValue } from '@core/api/resource-value';

const EMPTY: CardPage = { items: [], total: 0, limit: 100, offset: 0 };

@Component({
  selector: 'app-adopt-dialog',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, ButtonComponent, DialogComponent, SelectFieldComponent],
  templateUrl: './adopt-dialog.component.html',
  styleUrl: './adopt-dialog.component.scss',
})
export class AdoptDialogComponent {
  private readonly library = inject(LibraryApi);
  private readonly events = inject(EventsApi);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly documentId = input.required<string>();
  readonly title = input.required<string>();
  readonly closed = output<void>();

  protected readonly eventId = signal('');
  protected readonly busy = signal(false);
  protected readonly dossiers = rxResource({
    stream: () =>
      this.events
        .listCards({ mine: true, state: ['draft', 'published'], limit: 100 })
        .pipe(catchError(() => of(EMPTY))),
  });
  protected readonly options = computed<SelectFieldOption[]>(() =>
    resourceValue(this.dossiers, EMPTY).items.map((c) => ({
      value: c.id,
      label: c.title,
    })),
  );

  protected submit(): void {
    if (this.busy()) return;
    this.busy.set(true);
    this.library.adopt(this.documentId(), this.eventId()).subscribe({
      next: () => {
        this.busy.set(false);
        this.toast.success(this.i18n.translate('library.adopted'));
        this.closed.emit();
        void this.router.navigate(['/dossiers', this.eventId()]);
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.toast.error(problemMessage(this.i18n, problemOf(err)));
      },
    });
  }
}
