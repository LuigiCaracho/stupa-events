/** A date and a time of day side by side (ui-kit datepicker and time input) with one label and one error. */
import { ChangeDetectionStrategy, Component, input, model } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatepickerComponent, TimeInputComponent } from '@stupa-makers/ui-kit';

@Component({
  selector: 'app-datetime-field',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, DatepickerComponent, TimeInputComponent],
  templateUrl: './datetime-field.component.html',
  styleUrl: './datetime-field.component.scss',
})
export class DatetimeFieldComponent {
  readonly dateLabel = input.required<string>();
  readonly timeLabel = input.required<string>();
  readonly required = input(false);
  readonly disabled = input(false);
  readonly error = input('');
  readonly hint = input('');

  readonly date = model('');
  readonly time = model('');
}
