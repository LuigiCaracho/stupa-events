/** The dialog "Auf diesen Stand zurücksetzen" of the history: an optional note (at most 500 characters). */
import { ChangeDetectionStrategy, Component, computed, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { ButtonComponent, DialogComponent, InputComponent } from '@stupa-makers/ui-kit';

const MAX = 500;

@Component({
  selector: 'app-revert-dialog',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, TranslatePipe, ButtonComponent, DialogComponent, InputComponent],
  templateUrl: './revert-dialog.component.html',
  styleUrl: './revert-dialog.component.scss',
})
export class RevertDialogComponent {
  readonly subtitle = input('');
  readonly busy = input(false);

  readonly submitted = output<string>();
  readonly closed = output<void>();

  protected readonly note = signal('');
  protected readonly tooLong = computed(() => this.note().trim().length > MAX);

  protected submit(): void {
    if (this.tooLong() || this.busy()) return;
    this.submitted.emit(this.note().trim());
  }
}
