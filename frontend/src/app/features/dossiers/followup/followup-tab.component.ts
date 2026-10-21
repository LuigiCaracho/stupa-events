/**
 * The tab "Nachbereitung" (`/dossiers/:id/nachbereitung`, M5 contract 11.5): the list of what T09 still misses, the
 * retrospective, the result with its waiver, the tick "Anleitung geprüft" and the way to the checklist of the
 * phase `followup`. The page owns the dossier; this block reports a new version through `changed` and asks the page to
 * run a fix or the transition T09 (dialog I13). In `live` before the follow-up begins it only shows what can already be written.
 */
import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import type { ProblemReason } from '@core/api/models';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { GuardListComponent } from '@shared/ui/guard-list/guard-list.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import type { EventDto, GuardResult } from '../api/event.models';
import { HowtoCheckComponent } from './howto-check.component';
import { OutcomeFormComponent } from './outcome-form.component';
import { RetrospectiveComponent } from './retrospective.component';

@Component({
  selector: 'app-followup-tab',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    ButtonComponent,
    GuardListComponent,
    HowtoCheckComponent,
    NoteComponent,
    OutcomeFormComponent,
    RetrospectiveComponent,
  ],
  templateUrl: './followup-tab.component.html',
  styleUrl: './followup-tab.component.scss',
})
export class FollowupTabComponent {
  readonly event = input.required<EventDto>();
  readonly canEdit = input(false);
  /** The guards of T09, when the dossier is in `followup`. */
  readonly guards = input<GuardResult | null>(null);

  readonly changed = output<EventDto | null>();
  readonly fix = output<ProblemReason>();
  readonly finish = output<void>();
  readonly openChecklist = output<void>();

  protected readonly archived = computed(() => this.event().state === 'archived');
  protected readonly writable = computed(() => this.canEdit() && !this.archived());
  protected readonly canFinish = computed(() => this.event().allowedTransitions.includes('T09'));
  protected readonly canVerify = computed(() => {
    const actions = this.event().allowedActions;
    return this.canEdit() && (!actions || actions.includes('verify-howto'));
  });
}
