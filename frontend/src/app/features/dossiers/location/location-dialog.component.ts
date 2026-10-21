/**
 * "Ort bestätigen" (M5 contract 3.6): the free place text of a dossier becomes public only after a person confirms how
 * exact it may be shown. The dialog says "Der Ort ist öffentlich. Keine Privatadresse." and offers the precision
 * "Gebäude" or "Genau" (never "versteckt"). The page receives the updated dossier.
 */
import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { ButtonComponent, DialogComponent, SegmentedComponent, ToastService } from '@stupa-makers/ui-kit';
import { OutcomeApi } from '../api/outcome-api.service';
import type { EventDto } from '../api/event.models';
import { problemMessage } from '../api/problem-message';

@Component({
  selector: 'app-location-dialog',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, ButtonComponent, DialogComponent, SegmentedComponent],
  templateUrl: './location-dialog.component.html',
  styleUrl: './location-dialog.component.scss',
})
export class LocationDialogComponent {
  private readonly api = inject(OutcomeApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly event = input.required<EventDto>();
  readonly confirmed = output<EventDto>();
  readonly closed = output<void>();

  protected readonly precision = signal<'building' | 'exact'>('building');
  protected readonly busy = signal(false);
  protected readonly options = [
    { value: 'building', label: this.i18n.translate('location.building') },
    { value: 'exact', label: this.i18n.translate('location.exact') },
  ];

  protected submit(): void {
    this.busy.set(true);
    this.api.confirmLocation(this.event().id, this.precision()).subscribe({
      next: (updated) => {
        this.busy.set(false);
        this.toast.success(this.i18n.translate('location.confirmed'));
        this.confirmed.emit(updated);
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.toast.error(problemMessage(this.i18n, problemOf(err)));
      },
    });
  }
}
