/** The save state next to the dossier form ("Gespeichert 14:02", "Speichert …", "Nicht gespeichert"), in a live region. */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { I18nService } from '@core/i18n/i18n.service';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import type { StatusKind } from '@shared/status-kind.util';
import type { SaveStatus } from './draft-autosave';

@Component({
  selector: 'app-autosave-indicator',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [StatusTextComponent],
  templateUrl: './autosave-indicator.component.html',
  styleUrl: './autosave-indicator.component.scss',
})
export class AutosaveIndicatorComponent {
  private readonly i18n = inject(I18nService);

  readonly status = input.required<SaveStatus>();
  readonly savedAt = input<Date | null>(null);

  protected readonly kind = computed<StatusKind>(() => {
    switch (this.status()) {
      case 'saved':
        return 'accent';
      case 'offline':
      case 'conflict':
      case 'error':
        return 'error';
      case 'unsaved':
        return 'warn';
      default:
        return 'neutral';
    }
  });

  protected readonly text = computed(() => {
    const time =
      this.savedAt()?.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }) ?? '';
    switch (this.status()) {
      case 'saved':
        return this.i18n.translate('autosave.saved', { time });
      case 'saving':
        return this.i18n.translate('autosave.saving');
      case 'unsaved':
        return this.i18n.translate('autosave.unsaved');
      case 'offline':
        return this.i18n.translate('autosave.offline');
      case 'conflict':
        return this.i18n.translate('autosave.conflict');
      case 'error':
        return this.i18n.translate('autosave.error');
      default:
        return '';
    }
  });
}
