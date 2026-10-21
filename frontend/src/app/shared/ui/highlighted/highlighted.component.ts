/**
 * Text with highlighted parts, drawn from segments (`{text, hit}`) as `<mark>` elements. The text is always bound as
 * text, never as HTML: a title that contains markup stays text (M5 contract 6.1).
 */
import { ChangeDetectionStrategy, Component, input } from '@angular/core';

export interface TextSegment {
  text: string;
  hit: boolean;
}

@Component({
  selector: 'app-highlighted',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `@for (s of segments(); track $index) {@if (s.hit) {<mark>{{ s.text }}</mark>} @else {{{ s.text }}}}`,
  styles: `
    mark {
      padding: 0 0.1em;
      border-radius: var(--radius-sm);
      background: var(--color-primary-subtle, var(--color-selected));
      color: inherit;
      font-weight: var(--fw-semibold);
    }
  `,
})
export class HighlightedComponent {
  readonly segments = input.required<readonly TextSegment[]>();
}
