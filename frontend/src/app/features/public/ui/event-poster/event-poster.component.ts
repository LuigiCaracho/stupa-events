/**
 * The poster of an event in a box of fixed aspect ratio (1200:630 unless `--poster-ratio` says otherwise), so the page
 * does not jump while the image loads. `width` and `height` come from the API. Without an image, or when it fails to
 * load, a calm placeholder with an icon takes its place and says nothing to the visitor about a missing image.
 */
import { ChangeDetectionStrategy, Component, input, signal } from '@angular/core';
import { IconComponent } from '@stupa-makers/ui-kit';

export interface PosterSource {
  url: string;
  width: number;
  height: number;
}

@Component({
  selector: 'app-event-poster',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [IconComponent],
  templateUrl: './event-poster.component.html',
  styleUrl: './event-poster.component.scss',
})
export class EventPosterComponent {
  readonly image = input<PosterSource | null>(null);
  /** Empty means decorative. */
  readonly alt = input('');
  /** The image above the fold: loaded at once and with high priority, not lazily. */
  readonly eager = input(false);
  protected readonly failed = signal(false);
}
