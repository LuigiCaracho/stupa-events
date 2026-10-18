/** The phone sheet "Verschieben": the transitions a card may take, opened by a long press (the phone has no drag). */
import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { SideSheetComponent } from '@shared/ui/side-sheet/side-sheet.component';
import type { EventCard } from '../../dossiers/api/board.models';
import type { TransitionId } from '../../dossiers/api/event.models';
import { TRANSITION_LABEL } from '../../dossiers/api/transition-label';
import { SYSTEM_ONLY } from '../../dossiers/api/transitions';

@Component({
  selector: 'app-move-sheet',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, SideSheetComponent],
  templateUrl: './move-sheet.component.html',
  styleUrl: './move-sheet.component.scss',
})
export class MoveSheetComponent {
  readonly card = input.required<EventCard>();
  readonly chosen = output<TransitionId>();
  readonly closed = output<void>();

  protected readonly label = TRANSITION_LABEL;
  protected readonly options = computed(() =>
    this.card().allowedTransitions.filter((t) => !SYSTEM_ONLY.has(t)),
  );
}
