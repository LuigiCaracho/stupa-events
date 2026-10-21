/**
 * The poster slot at the top of the dossier page (M5b contract 3.1): the picture large in the aspect ratio of
 * `card_1200`, or an empty area that says "Ohne Bild nicht bewerbbar" with the upload (drag and drop or file picker)
 * right in it. A picture can be replaced or removed while the dossier is editable. The page sends the requests.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output, signal } from '@angular/core';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import {
  PosterUploadComponent,
  type PosterSubmission,
} from '@shared/ui/poster-upload/poster-upload.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { ButtonComponent, IconComponent } from '@stupa-makers/ui-kit';
import type { EventDto } from '../api/event.models';
import { EventsApi } from '../api/events-api.service';

const FALLBACK_RATIO = '16 / 9';

@Component({
  selector: 'app-poster-slot',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, ButtonComponent, IconComponent, PosterUploadComponent, StatusTextComponent],
  templateUrl: './poster-slot.component.html',
  styleUrl: './poster-slot.component.scss',
})
export class PosterSlotComponent {
  private readonly api = inject(EventsApi);

  readonly event = input.required<EventDto>();
  readonly canEdit = input(false);
  readonly busy = input(false);

  readonly submitted = output<PosterSubmission>();
  readonly removed = output<void>();

  protected readonly replacing = signal(false);
  protected readonly failed = signal(false);

  protected readonly poster = computed(() => this.event().poster);
  protected readonly src = computed(() => this.api.posterUrl(this.event().id, 'card1200'));
  protected readonly ratio = computed(() => {
    const d = this.poster()?.derivatives?.card1200;
    return d ? `${d.width} / ${d.height}` : FALLBACK_RATIO;
  });
  protected readonly showUpload = computed(
    () => this.canEdit() && (this.replacing() || !this.poster()),
  );

  protected send(sub: PosterSubmission): void {
    this.replacing.set(false);
    this.failed.set(false);
    this.submitted.emit(sub);
  }
}
