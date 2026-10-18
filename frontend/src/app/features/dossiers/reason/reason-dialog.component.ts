/**
 * A small dialog with one text field: the reason of "Absage zurücknehmen", the optional note of "Auf diesen Stand
 * zurücksetzen". The parent runs the action and reports `busy` and `error`; the text is trimmed and, when
 * `required`, never empty.
 */
import { ChangeDetectionStrategy, Component, computed, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { TranslationKey } from '@core/i18n/translations';
import { ButtonComponent, DialogComponent, InputComponent } from '@stupa-makers/ui-kit';

const MAX = 500;

@Component({
  selector: 'app-reason-dialog',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, TranslatePipe, ButtonComponent, DialogComponent, InputComponent],
  templateUrl: './reason-dialog.component.html',
  styleUrl: './reason-dialog.component.scss',
})
export class ReasonDialogComponent {
  readonly heading = input.required<TranslationKey>();
  readonly subtitle = input('');
  readonly label = input.required<TranslationKey>();
  readonly confirm = input.required<TranslationKey>();
  readonly required = input(true);
  readonly busy = input(false);

  readonly submitted = output<string>();
  readonly closed = output<void>();

  protected readonly text = signal('');
  protected readonly attempted = signal(false);
  protected readonly invalid = computed(
    () => (this.required() && this.text().trim() === '') || this.text().trim().length > MAX,
  );

  protected submit(): void {
    this.attempted.set(true);
    if (this.invalid() || this.busy()) return;
    this.submitted.emit(this.text().trim());
  }
}
