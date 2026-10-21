/**
 * The section "So lief es" of the dossier page (M5b contract 6): the retrospective, the result and the tick "Anleitung
 * geprüft". All of it is voluntary and stays writable after the event, in the archive too. The page owns the dossier;
 * this block reports a new version through `changed` (`null`: only the documents changed, reload).
 */
import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import type { EventDto } from '../api/event.models';
import { HowtoCheckComponent } from './howto-check.component';
import { OutcomeFormComponent } from './outcome-form.component';
import { RetrospectiveComponent } from './retrospective.component';

@Component({
  selector: 'app-outcome-section',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [HowtoCheckComponent, OutcomeFormComponent, RetrospectiveComponent],
  template: `
    <div class="os">
      <app-retrospective [event]="event()" [canEdit]="canEdit()" (changed)="changed.emit(null)" />
      <app-outcome-form [event]="event()" [canEdit]="canEdit()" (changed)="changed.emit($event)" />
      <app-howto-check [event]="event()" [canEdit]="canVerify()" (changed)="changed.emit($event)" />
    </div>
  `,
  styles: `
    .os {
      display: grid;
      gap: var(--space-6);
    }
  `,
})
export class OutcomeSectionComponent {
  readonly event = input.required<EventDto>();
  readonly canEdit = input(false);
  readonly changed = output<EventDto | null>();

  protected readonly canVerify = computed(
    () => this.canEdit() && this.event().allowedActions.includes('verify-howto'),
  );
}
