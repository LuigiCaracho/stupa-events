/**
 * Pattern from STUPA-Workflow@93c33d6 frontend/src/app/pages/todos/board-view/todo-board-view.component.ts
 * (rebuilt for the dossier pipeline). The columns of the pipeline board. Desktop: the columns side by side, each a
 * drop list of `@angular/cdk/drag-drop`; a column accepts a card only when `card.moves[column]` exists. The keyboard does
 * the same: Space lifts the focused card, the arrows choose the column, Space or Enter put it down, Escape puts it back.
 * Phone: tabs over a scroll-snap pager, no drag; a long press asks the page for the move sheet. The page renders the card
 * through the projected template and runs the transition; a live region names each step.
 */
import {
  CdkDrag,
  CdkDropList,
  CdkDropListGroup,
  type CdkDragDrop,
  type CdkDragMove,
} from '@angular/cdk/drag-drop';
import { NgTemplateOutlet } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  Injector,
  TemplateRef,
  afterNextRender,
  computed,
  contentChild,
  effect,
  inject,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import type { BoardColumn, ColumnKey } from '../../../features/dossiers/api/board.models';
import type { EventCard } from '../../../features/dossiers/api/board.models';
import type { TransitionId } from '../../../features/dossiers/api/event.models';
import { I18nService } from '@core/i18n/i18n.service';
import type { TranslationKey } from '@core/i18n/translations';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { LongPressDirective } from '../../long-press.directive';
import { TabsComponent, type TabItem } from '@stupa-makers/ui-kit';

/** The context of the card template: the card, whether the keyboard holds it, and its column. */
export interface BoardCardContext {
  $implicit: EventCard;
  lifted: boolean;
  column: ColumnKey;
}

/** A move that the board asks for: the card, the column it should go to and the transition. */
export interface BoardMove {
  card: EventCard;
  column: ColumnKey;
  transition: TransitionId;
}

/** A pager that sends no scroll event for this long has come to rest (browsers without `scrollend`). */
const PAGER_REST_MS = 120;

interface KeyDrag {
  card: EventCard;
  from: number;
  col: number;
}

const COLUMN_KEY = (key: ColumnKey): TranslationKey => `board.col.${key}`;

@Component({
  selector: 'app-pipeline-board',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    CdkDrag,
    CdkDropList,
    CdkDropListGroup,
    LongPressDirective,
    NgTemplateOutlet,
    TabsComponent,
    TranslatePipe,
  ],
  host: {
    '(document:focusin)': 'leaveDrag($event)',
    '(document:pointerdown)': 'leaveDrag($event)',
  },
  templateUrl: './pipeline-board.component.html',
  styleUrl: './pipeline-board.component.scss',
})
export class PipelineBoardComponent {
  private readonly i18n = inject(I18nService);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);

  readonly columns = input.required<readonly BoardColumn[]>();
  readonly phone = input(false);

  readonly moveCard = output<BoardMove>();
  readonly menu = output<EventCard>();
  readonly holding = output<boolean>();

  protected readonly cardTpl = contentChild.required<TemplateRef<BoardCardContext>>('card');
  private readonly pager = viewChild<ElementRef<HTMLElement>>('pager');

  protected readonly kb = signal<KeyDrag | null>(null);
  protected readonly ptr = signal<{ card: EventCard; from: ColumnKey } | null>(null);
  protected readonly hover = signal<ColumnKey | null>(null);
  protected readonly epoch = signal(0);
  protected readonly epochs = computed(() => [this.epoch()]);
  protected readonly announcement = signal('');
  protected readonly refusal = signal('');
  protected readonly phoneColumn = signal(0);
  protected readonly dragDelay = { touch: 400, mouse: 0 };
  protected readonly dropAllowed = (
    drag: CdkDrag<EventCard>,
    drop: CdkDropList<ColumnKey>,
  ): boolean => this.canMove(drag.data, drop.data);
  private spaceTaken = false;
  private target: number | null = null;
  private restTimer: ReturnType<typeof setTimeout> | undefined;

  protected readonly holdingNow = computed(() => this.kb() !== null || this.ptr() !== null);
  protected readonly tabs = computed<TabItem[]>(() =>
    this.columns().map((c) => ({ id: c.key, label: this.name(c.key), count: c.total })),
  );
  protected readonly phoneKey = computed(() => this.columns()[this.phoneColumn()]?.key ?? null);

  constructor() {
    effect(() => this.holding.emit(this.holdingNow()));
    inject(DestroyRef).onDestroy(() => clearTimeout(this.restTimer));
  }

  protected name(key: ColumnKey): string {
    return this.i18n.translate(COLUMN_KEY(key));
  }

  protected canMove(card: EventCard, column: ColumnKey): boolean {
    return card.moves[column] !== undefined;
  }

  protected denied(key: ColumnKey): boolean {
    const origin = this.ptr()?.from ?? (this.kb() ? this.columns()[this.kb()!.from]?.key : null);
    const card = this.ptr()?.card ?? this.kb()?.card;
    const over = this.hover() ?? (this.kb() ? this.columns()[this.kb()!.col]?.key : null);
    return !!card && over === key && key !== origin && !this.canMove(card, key);
  }

  protected isTarget(key: ColumnKey): boolean {
    const kb = this.kb();
    return !!kb && this.columns()[kb.col]?.key === key && kb.col !== kb.from;
  }

  protected ctx(card: EventCard, column: ColumnKey): BoardCardContext {
    return { $implicit: card, lifted: this.kb()?.card.id === card.id, column };
  }

  /** Lets the page announce a result to the polite live region; a refusal goes to the assertive one. */
  announce(text: string, refusal = false): void {
    if (refusal) this.refusal.set(text);
    else this.announcement.set(text);
  }

  protected dragStarted(card: EventCard, from: ColumnKey): void {
    this.cancelKeyDrag();
    this.ptr.set({ card, from });
  }

  protected dragMoved(event: CdkDragMove<EventCard>): void {
    const { x, y } = event.pointerPosition;
    const key = document.elementFromPoint(x, y)?.closest<HTMLElement>('[data-col]')?.dataset[
      'col'
    ] as ColumnKey | undefined;
    this.hover.set(key ?? null);
  }

  protected dragEnded(): void {
    this.ptr.set(null);
    this.hover.set(null);
  }

  protected dropped(event: CdkDragDrop<ColumnKey, ColumnKey, EventCard>): void {
    const to = event.container.data;
    this.epoch.update((n) => n + 1);
    if (to !== event.previousContainer.data) this.requestMove(event.item.data, to);
  }

  private requestMove(card: EventCard, column: ColumnKey): void {
    const transition = card.moves[column];
    if (transition) this.moveCard.emit({ card, column, transition });
  }

  protected onKeyUp(event: KeyboardEvent): void {
    if (event.key !== ' ' || (!this.spaceTaken && !this.kb())) return;
    this.spaceTaken = false;
    event.preventDefault();
  }

  protected onKey(event: KeyboardEvent, card: EventCard, colIndex: number): void {
    if (this.phone()) return;
    const kb = this.kb();
    if (!kb) {
      if (event.key !== ' ') return;
      event.preventDefault();
      this.spaceTaken = true;
      this.kb.set({ card, from: colIndex, col: colIndex });
      this.announce(
        this.i18n.translate('board.lifted', {
          title: card.title,
          column: this.name(this.columns()[colIndex].key),
        }),
      );
      return;
    }
    if (kb.card.id !== card.id) return;
    switch (event.key) {
      case 'ArrowLeft':
      case 'ArrowRight':
        event.preventDefault();
        this.step(kb, event.key === 'ArrowLeft' ? -1 : 1);
        return;
      case ' ':
      case 'Enter':
        event.preventDefault();
        this.spaceTaken = event.key === ' ';
        this.commit(kb);
        return;
      case 'Escape':
        event.preventDefault();
        this.cancelKeyDrag();
        this.refocus(card.id);
        return;
      case 'Tab':
        this.cancelKeyDrag();
        return;
    }
  }

  private step(kb: KeyDrag, by: number): void {
    const cols = this.columns();
    const col = Math.max(0, Math.min(cols.length - 1, kb.col + by));
    if (col === kb.col) return;
    this.kb.set({ ...kb, col });
    const key = cols[col].key;
    const ok = col === kb.from || this.canMove(kb.card, key);
    this.announce(
      this.i18n.translate(ok ? 'board.target' : 'board.targetDenied', { column: this.name(key) }),
      !ok,
    );
  }

  private commit(kb: KeyDrag): void {
    const key = this.columns()[kb.col].key;
    if (kb.col === kb.from) {
      this.cancelKeyDrag();
    } else if (!this.canMove(kb.card, key)) {
      this.announce(this.i18n.translate('board.targetDenied', { column: this.name(key) }), true);
      return;
    } else {
      this.kb.set(null);
      this.requestMove(kb.card, key);
    }
    this.refocus(kb.card.id);
  }

  private cancelKeyDrag(): void {
    const kb = this.kb();
    if (!kb) return;
    this.kb.set(null);
    this.announce(this.i18n.translate('board.cancelled', { title: kb.card.title }));
  }

  protected leaveDrag(event: Event): void {
    const kb = this.kb();
    if (!kb) return;
    const target = event.target instanceof Element ? event.target : null;
    if (target?.closest('.bv__item')?.querySelector(`[data-card-id="${kb.card.id}"]`)) return;
    this.cancelKeyDrag();
  }

  private refocus(id: string): void {
    afterNextRender(
      () => this.host.nativeElement.querySelector<HTMLElement>(`[data-card-id="${id}"]`)?.focus(),
      { injector: this.injector },
    );
  }

  protected selectColumn(id: string | null): void {
    const i = this.columns().findIndex((c) => c.key === id);
    const el = this.pager()?.nativeElement;
    if (i < 0) return;
    this.phoneColumn.set(i);
    if (!el?.clientWidth) return;
    this.target = i;
    const reduce =
      typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    el.scrollTo({ left: i * el.clientWidth, behavior: reduce ? 'auto' : 'smooth' });
  }

  protected onPagerScroll(): void {
    const el = this.pager()?.nativeElement;
    if (!el?.clientWidth) return;
    clearTimeout(this.restTimer);
    this.restTimer = setTimeout(() => this.onPagerRest(), PAGER_REST_MS);
    const pos = el.scrollLeft / el.clientWidth;
    if (this.target !== null) {
      if (Math.abs(pos - this.target) > 0.05) return;
      this.target = null;
    }
    this.showPage(pos);
  }

  /** The scroll came to rest (`scrollend`, or no scroll event for a moment): whatever page it rests on is the tab. */
  protected onPagerRest(): void {
    clearTimeout(this.restTimer);
    this.target = null;
    const el = this.pager()?.nativeElement;
    if (el?.clientWidth) this.showPage(el.scrollLeft / el.clientWidth);
  }

  private showPage(pos: number): void {
    this.phoneColumn.set(Math.max(0, Math.min(Math.round(pos), this.columns().length - 1)));
  }

  protected onPagerTouch(): void {
    this.target = null;
  }
}
