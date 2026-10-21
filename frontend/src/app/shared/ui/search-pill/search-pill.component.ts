/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/shared/ui/search-pill/search-pill.component.ts (rewritten) */
import { ChangeDetectionStrategy, Component, computed, input, model, output } from '@angular/core';
import { IconComponent } from '@stupa-makers/ui-kit';
import { TranslatePipe } from '@core/i18n/translate.pipe';

/** `button` opens something (the command palette); `input` filters in place. */
export type SearchPillMode = 'button' | 'input';

/**
 * The round search field.
 *
 * - `input` (default): a search input that searches while the user types. There is no
 *   "Suchen" button: `value` is two-way, and the page runs the search on each change
 *   (`liveSearch` in `@shared/live-search` for a request). Escape clears it, and so
 *   does the × button with `clearable`. Enter submits no form; it emits `commit`, so
 *   the page can search at once. `busy` swaps the magnifier for a small spinner of the same size (no layout jump).
 * - `button`: looks the same but is a button that emits `activate`, for example to open
 *   the command palette.
 *
 * The `[trail]` slot takes a control at the end of the pill, for example the filter
 * button of a list or the account button on a phone. It sits beside the field, never in
 * it, so the two stay separate controls.
 */
@Component({
  selector: 'app-search-pill',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [IconComponent, TranslatePipe],
  host: {
    '[class.sp--md]': "size() === 'md'",
  },
  templateUrl: './search-pill.component.html',
  styleUrl: './search-pill.component.scss',
})
export class SearchPillComponent {
  readonly mode = input<SearchPillMode>('input');
  /** The visible text in the empty field, for example "Anträge durchsuchen". */
  readonly placeholder = input.required<string>();
  /** The accessible name. Defaults to the placeholder. */
  readonly label = input<string | null>(null);
  /** `lg` is 52px high (the main search), `md` is 44px (a list filter). */
  readonly size = input<'lg' | 'md'>('lg');
  /** Show a × button that clears a filled field (input mode). */
  readonly clearable = input(false);
  /** Upper bound of the input length (the server limit of a query). */
  readonly maxlength = input<number | null>(null);
  /** A search runs (input mode): the magnifier becomes a spinner. */
  readonly busy = input(false);

  /** The search text (input mode). */
  readonly value = model('');
  /** The button was pressed (button mode). */
  readonly activate = output<void>();
  /** Enter in the field (input mode): search now, without the debounce. */
  readonly commit = output<void>();

  protected readonly name = computed(() => this.label() ?? this.placeholder());

  protected onInput(event: Event): void {
    this.value.set((event.target as HTMLInputElement).value);
  }

  protected onKey(event: KeyboardEvent): void {
    if (event.key === 'Escape' && this.value() !== '') {
      event.preventDefault();
      event.stopPropagation();
      this.value.set('');
      return;
    }
    if (event.key === 'Enter' && !event.isComposing) {
      // The field searches by itself. Enter must not submit a form around it (a dialog
      // would save), it only asks for the search now.
      event.preventDefault();
      this.commit.emit();
    }
  }

  protected clear(input: HTMLInputElement): void {
    this.value.set('');
    input.focus();
  }
}
