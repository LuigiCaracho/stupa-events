/** The question on leaving the dossier page with changes that are not sent yet: save, discard or stay. */
import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { ButtonComponent, DialogComponent } from '@stupa-makers/ui-kit';

export type LeaveChoice = 'save' | 'discard' | 'stay';

@Component({
  selector: 'app-leave-dialog',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, ButtonComponent, DialogComponent],
  template: `
    <app-dialog
      [open]="true"
      [title]="'leave.title' | t"
      [subtitle]="subtitle()"
      [closeLabel]="'action.close' | t"
      (closed)="choice.emit('stay')"
    >
      <p>{{ 'leave.body' | t }}</p>
      <div dialog-footer class="ld">
        <app-button variant="text" (click)="choice.emit('stay')">{{ 'leave.stay' | t }}</app-button>
        <app-button variant="outlined" (click)="choice.emit('discard')">{{
          'leave.discard' | t
        }}</app-button>
        <app-button variant="fill" (click)="choice.emit('save')">{{ 'leave.save' | t }}</app-button>
      </div>
    </app-dialog>
  `,
  styles: `
    .ld {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: var(--space-2);
    }
  `,
})
export class LeaveDialogComponent {
  readonly subtitle = input('');
  readonly choice = output<LeaveChoice>();
}
