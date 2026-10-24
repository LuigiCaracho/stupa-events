/**
 * A group of toggle chips (44 px, check mark when chosen) for the interests and the faculty of Get started and of the
 * manage page. Each chip is a button with `aria-pressed`; the page owns the selection and reacts to `chosen`.
 */
import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import type { QuestionOption } from '../../model/subscriptions.models';

@Component({
  selector: 'app-chip-group',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="chips" role="group" [attr.aria-label]="label()">
      @for (option of options(); track option.value) {
        <button
          type="button"
          class="chip"
          [attr.aria-pressed]="selected().includes(option.value)"
          (click)="chosen.emit(option.value)"
        >
          {{ option.label }}
        </button>
      }
    </div>
  `,
  styleUrl: './chip-group.component.scss',
})
export class ChipGroupComponent {
  readonly options = input<readonly QuestionOption[]>([]);
  readonly selected = input<readonly string[]>([]);
  readonly label = input('');
  readonly chosen = output<string>();
}
