/**
 * The anchor navigation of the dossier page (M5b contract 10.1): one link per section, sticky below the header while
 * the page scrolls, reachable by keyboard. A link scrolls to the section and moves the focus to it; the link of the
 * section in view carries `aria-current`.
 */
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  inject,
  input,
  signal,
} from '@angular/core';

export interface SectionLink {
  id: string;
  label: string;
  count?: number;
}

@Component({
  selector: 'app-section-nav',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './section-nav.component.html',
  styleUrl: './section-nav.component.scss',
})
export class SectionNavComponent {
  private readonly page = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly links = input.required<readonly SectionLink[]>();
  readonly label = input.required<string>();

  protected readonly current = signal<string | null>(null);

  constructor() {
    const destroy = inject(DestroyRef);
    afterNextRender(() => {
      if (typeof IntersectionObserver === 'undefined') return;
      const seen = new Set<string>();
      const observer = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (entry.isIntersecting) seen.add(entry.target.id);
            else seen.delete(entry.target.id);
          }
          const first = this.links().find((l) => seen.has(l.id));
          if (first) this.current.set(first.id);
        },
        { rootMargin: '-20% 0px -60% 0px' },
      );
      for (const link of this.links()) {
        const target = this.target(link.id);
        if (target) observer.observe(target);
      }
      destroy.onDestroy(() => observer.disconnect());
    });
  }

  protected go(event: Event, id: string): void {
    event.preventDefault();
    const target = this.target(id);
    if (!target) return;
    this.current.set(id);
    target.scrollIntoView?.({ block: 'start' });
    target.focus({ preventScroll: true });
  }

  private target(id: string): HTMLElement | null {
    const root = this.page.nativeElement.closest('app-dossier-detail') ?? document;
    return root.querySelector<HTMLElement>(`#${id}`);
  }
}
