/**
 * Section "Verlauf": the revisions of the dossier, newest first, with the fields each one changed and, for those who may,
 * "Auf diesen Stand zurücksetzen".
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { fieldLabel } from '../hints/field-label';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import type { RevisionOut } from '../api/action.models';
import { EventsApi } from '../api/events-api.service';
import { isStateChange } from '../activity/timeline';

@Component({
  selector: 'app-dossier-history',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, ButtonComponent, NoteComponent, SkeletonComponent],
  templateUrl: './dossier-history.component.html',
  styleUrl: './dossier-history.component.scss',
})
export class DossierHistoryComponent {
  private readonly api = inject(EventsApi);
  private readonly i18n = inject(I18nService);

  readonly eventId = input.required<string>();
  /** The version the page shows; a new one reloads the list. */
  readonly rev = input.required<number>();
  readonly canRevert = input(false);

  readonly revert = output<number>();

  protected readonly revisions = rxResource({
    params: () => ({ id: this.eventId(), rev: this.rev() }),
    stream: ({ params }) => this.api.revisions(params.id),
  });
  protected readonly items = computed(() =>
    this.revisions.hasValue() ? this.revisions.value().items : [],
  );

  protected fields(revision: RevisionOut): string[] {
    return revision.changedFields.map((f) => fieldLabel(this.i18n, f));
  }

  protected isStateChange(revision: RevisionOut): boolean {
    return isStateChange(revision);
  }

  protected who(revision: RevisionOut): string {
    return revision.actorType === 'system'
      ? this.i18n.translate('history.system')
      : (revision.actor.displayName ?? '?');
  }

  protected when(revision: RevisionOut): string {
    return new Date(revision.at).toLocaleString('de-DE', {
      dateStyle: 'medium',
      timeStyle: 'short',
    });
  }
}
