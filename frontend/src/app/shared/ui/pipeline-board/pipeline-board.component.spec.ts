import { Component, signal } from '@angular/core';
import { By } from '@angular/platform-browser';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../testing/a11y';
import { makeCard, makeColumn } from '../../../../testing/event-fixtures';
import type { BoardColumn, EventCard } from '../../../features/dossiers/api/board.models';
import { type BoardMove, PipelineBoardComponent } from './pipeline-board.component';

const idea = makeCard({
  id: 'c-idea',
  title: 'Idee A',
  state: 'idea',
  moves: { planning: 'T01' },
  allowedTransitions: ['T01'],
});
const planning = makeCard({ id: 'c-plan', title: 'Plan B', moves: { in_review: 'T02' } });
const stuck = makeCard({ id: 'c-stuck', title: 'Fest C', state: 'live', moves: {} });

function columns(): BoardColumn[] {
  return [
    makeColumn('idea', [idea]),
    makeColumn('planning', [planning, stuck]),
    makeColumn('in_review'),
    makeColumn('published', [], { truncated: true, total: 120 }),
    makeColumn('followup'),
  ];
}

@Component({
  standalone: true,
  imports: [PipelineBoardComponent],
  template: `
    <app-pipeline-board
      [columns]="columns()"
      [phone]="phone()"
      (moveCard)="moves.push($event)"
      (menu)="menus.push($event)"
      (holding)="holds.push($event)"
    >
      <ng-template #card let-card let-lifted="lifted">
        <button type="button" [attr.data-card-id]="card.id" [attr.aria-pressed]="lifted">
          {{ card.title }}
        </button>
      </ng-template>
    </app-pipeline-board>
  `,
})
class HostComponent {
  readonly columns = signal(columns());
  readonly phone = signal(false);
  readonly moves: BoardMove[] = [];
  readonly menus: EventCard[] = [];
  readonly holds: boolean[] = [];
}

async function setup(phone = false) {
  const view = await render(HostComponent);
  view.fixture.componentInstance.phone.set(phone);
  view.fixture.detectChanges();
  const instance = view.fixture.debugElement.query(By.directive(PipelineBoardComponent))
    .componentInstance as Record<string, (...args: unknown[]) => unknown>;
  const board = new Proxy(instance, {
    get: (target, name: string) =>
      typeof target[name] === 'function' ? target[name].bind(target) : target[name],
  });
  const live = () => {
    view.fixture.detectChanges();
    return view.container.querySelector('[aria-live="polite"]')?.textContent?.trim() ?? '';
  };
  const refusal = () => {
    view.fixture.detectChanges();
    return view.container.querySelector('[aria-live="assertive"]')?.textContent?.trim() ?? '';
  };
  return { view, host: view.fixture.componentInstance, board, live, refusal };
}

describe('PipelineBoardComponent', () => {
  it('shows the columns with their counts, an empty text and the cut-off note', async () => {
    const { view } = await setup();
    const heads = Array.from(view.container.querySelectorAll('.bv__name')).map((h) =>
      h.textContent?.replace(/\s+/g, ' ').trim(),
    );
    expect(heads).toEqual([
      'Idee 1',
      'Planung 2',
      'Freigabe 0',
      'Veröffentlicht 120',
      'Nachbereitung 0',
    ]);
    expect(screen.getByRole('button', { name: 'Plan B' })).toBeInTheDocument();
    expect(screen.getAllByText('Keine Events in dieser Phase.')).toHaveLength(3);
    expect(screen.getByText('0 von 120 angezeigt. Grenze die Filter ein.')).toBeInTheDocument();
  });

  it('accepts a card only into a column that its moves name', async () => {
    const { board } = await setup();
    const accept = board['dropAllowed'] as (drag: unknown, drop: unknown) => boolean;
    expect(accept({ data: idea }, { data: 'planning' })).toBe(true);
    expect(accept({ data: idea }, { data: 'in_review' })).toBe(false);
    expect(accept({ data: stuck }, { data: 'in_review' })).toBe(false);
  });

  it('asks for the move of a drop into another column and ignores a drop in place', async () => {
    const { board, host, view } = await setup();
    const dropped = board['dropped'] as (event: unknown) => void;
    dropped({
      item: { data: idea },
      container: { data: 'planning' },
      previousContainer: { data: 'idea' },
    });
    expect(host.moves).toEqual([{ card: idea, column: 'planning', transition: 'T01' }]);
    dropped({
      item: { data: idea },
      container: { data: 'idea' },
      previousContainer: { data: 'idea' },
    });
    expect(host.moves).toHaveLength(1);
    view.fixture.detectChanges();
    expect(screen.getByRole('button', { name: 'Idee A' })).toBeInTheDocument();
  });

  it('marks a column the dragged card cannot reach and says so', async () => {
    const { board, view } = await setup();
    (board['dragStarted'] as (c: unknown, k: string) => void)(planning, 'planning');
    const column = view.container.querySelector<HTMLElement>('[data-col="followup"]')!;
    const spy = jest.fn().mockReturnValue(column);
    document.elementFromPoint = spy;
    (board['dragMoved'] as (e: unknown) => void)({ pointerPosition: { x: 1, y: 1 } });
    view.fixture.detectChanges();
    expect(column).toHaveClass('bv__col--deny');
    expect(column).toHaveTextContent('Nicht möglich');
    spy.mockReturnValue(view.container.querySelector<HTMLElement>('[data-col="in_review"]'));
    (board['dragMoved'] as (e: unknown) => void)({ pointerPosition: { x: 1, y: 1 } });
    view.fixture.detectChanges();
    expect(column).not.toHaveClass('bv__col--deny');
    (board['dragEnded'] as () => void)();
    view.fixture.detectChanges();
    expect(view.container.querySelector('.bv__col--deny')).toBeNull();
    Reflect.deleteProperty(document, 'elementFromPoint');
  });

  describe('keyboard', () => {
    it('lifts with Space, moves with the arrows and puts down with Space', async () => {
      const { host, live, view } = await setup();
      const user = userEvent.setup();
      const button = screen.getByRole('button', { name: 'Idee A' });
      button.focus();
      await user.keyboard(' ');
      expect(button).toHaveAttribute('aria-pressed', 'true');
      expect(live()).toBe('„Idee A“ aufgenommen, Spalte Idee.');
      await user.keyboard('{ArrowRight}');
      expect(live()).toBe('Spalte Planung, Verschieben möglich.');
      expect(view.container.querySelector('[data-col="planning"]')).toHaveClass('bv__col--target');
      await user.keyboard(' ');
      expect(host.moves).toEqual([{ card: idea, column: 'planning', transition: 'T01' }]);
      expect(host.holds).toContain(true);
      expect(host.holds.at(-1)).toBe(false);
    });

    it('also puts down with Enter', async () => {
      const { host } = await setup();
      const user = userEvent.setup();
      screen.getByRole('button', { name: 'Idee A' }).focus();
      await user.keyboard(' {ArrowRight}{Enter}');
      expect(host.moves).toHaveLength(1);
    });

    it('says "nicht möglich" for a closed column and keeps the card lifted', async () => {
      const { host, refusal } = await setup();
      const user = userEvent.setup();
      const button = screen.getByRole('button', { name: 'Idee A' });
      button.focus();
      await user.keyboard(' {ArrowRight}{ArrowRight}');
      expect(refusal()).toBe('Spalte Freigabe, nicht möglich.');
      await user.keyboard(' ');
      expect(refusal()).toBe('Spalte Freigabe, nicht möglich.');
      expect(host.moves).toEqual([]);
      expect(button).toHaveAttribute('aria-pressed', 'true');
    });

    it('puts the card back with Escape or when it goes back to its own column', async () => {
      const { host, live } = await setup();
      const user = userEvent.setup();
      const button = screen.getByRole('button', { name: 'Idee A' });
      button.focus();
      await user.keyboard(' {ArrowRight}{Escape}');
      expect(live()).toBe('„Idee A“ zurückgelegt.');
      expect(button).toHaveAttribute('aria-pressed', 'false');
      await user.keyboard(' {ArrowRight}{ArrowLeft}{ArrowLeft} ');
      expect(host.moves).toEqual([]);
      expect(live()).toBe('„Idee A“ zurückgelegt.');
    });

    it('stays in the first and last column and ignores keys of other cards', async () => {
      const { live } = await setup();
      const user = userEvent.setup();
      screen.getByRole('button', { name: 'Idee A' }).focus();
      await user.keyboard(' {ArrowLeft}');
      expect(live()).toBe('„Idee A“ aufgenommen, Spalte Idee.');
      await user.keyboard('x');
      expect(live()).toBe('„Idee A“ aufgenommen, Spalte Idee.');
    });

    it('ends the drag when the focus leaves the held card or Tab is pressed', async () => {
      const { live } = await setup();
      const user = userEvent.setup();
      const button = screen.getByRole('button', { name: 'Idee A' });
      button.focus();
      await user.keyboard(' ');
      screen.getByRole('button', { name: 'Plan B' }).focus();
      expect(live()).toBe('„Idee A“ zurückgelegt.');
      button.focus();
      await user.keyboard(' {Tab}');
      expect(button).toHaveAttribute('aria-pressed', 'false');
    });

    it('lifts only with Space and leaves other keys to the card', async () => {
      const { host, live } = await setup();
      const user = userEvent.setup();
      screen.getByRole('button', { name: 'Idee A' }).focus();
      await user.keyboard('{ArrowRight}');
      expect(live()).toBe('');
      expect(host.moves).toEqual([]);
    });

    it('does nothing on the phone', async () => {
      const { host } = await setup(true);
      expect(host.moves).toEqual([]);
    });
  });

  describe('phone', () => {
    it('offers a visible menu button on every card', async () => {
      const { host } = await setup(true);
      const button = screen.getByRole('button', { name: /Verschieben und mehr für „Idee A“/ });
      await userEvent.setup().click(button);
      expect(host.menus.map((c) => c.id)).toEqual([idea.id]);
    });

    it('shows tabs with counts over one page per column', async () => {
      const { view } = await setup(true);
      const tabs = screen
        .getAllByRole('tab')
        .map((t) => t.textContent?.replace(/\s+/g, ' ').trim());
      expect(tabs).toEqual([
        'Idee1',
        'Planung2',
        'Freigabe0',
        'Veröffentlicht120',
        'Nachbereitung0',
      ]);
      expect(view.container.querySelectorAll('.bv__page')).toHaveLength(5);
    });

    it('scrolls the pager to a tapped tab and follows the swipe', async () => {
      const { view, board } = await setup(true);
      const pager = view.container.querySelector<HTMLElement>('.bv__pager')!;
      Object.defineProperty(pager, 'clientWidth', { value: 300, configurable: true });
      pager.scrollTo = jest.fn() as never;
      await userEvent.setup().click(screen.getByRole('tab', { name: /Freigabe/ }));
      expect(pager.scrollTo).toHaveBeenCalledWith({ left: 600, behavior: 'smooth' });
      pager.scrollLeft = 300;
      (board['onPagerScroll'] as () => void)();
      expect(screen.getByRole('tab', { name: /Freigabe/ })).toHaveAttribute(
        'aria-selected',
        'true',
      );
      pager.scrollLeft = 600;
      (board['onPagerScroll'] as () => void)();
      expect(screen.getByRole('tab', { name: /Freigabe/ })).toHaveAttribute(
        'aria-selected',
        'true',
      );
      (board['onPagerTouch'] as () => void)();
      pager.scrollLeft = 300;
      (board['onPagerScroll'] as () => void)();
      view.fixture.detectChanges();
      expect(screen.getByRole('tab', { name: /Planung/ })).toHaveAttribute('aria-selected', 'true');
    });

    it('lands on the page where the scroll comes to rest, even when a tapped tab was still on its way', async () => {
      jest.useFakeTimers();
      try {
        const { view, board } = await setup(true);
        const pager = view.container.querySelector<HTMLElement>('.bv__pager')!;
        Object.defineProperty(pager, 'clientWidth', { value: 300, configurable: true });
        pager.scrollTo = jest.fn() as never;
        await userEvent
          .setup({ advanceTimers: jest.advanceTimersByTime })
          .click(screen.getByRole('tab', { name: /Planung/ }));
        pager.scrollLeft = 600;
        (board['onPagerScroll'] as () => void)();
        jest.advanceTimersByTime(130);
        view.fixture.detectChanges();
        expect(screen.getByRole('tab', { name: /Freigabe/ })).toHaveAttribute(
          'aria-selected',
          'true',
        );
        pager.scrollLeft = 0;
        pager.dispatchEvent(new Event('scrollend'));
        view.fixture.detectChanges();
        expect(screen.getByRole('tab', { name: /Idee/ })).toHaveAttribute('aria-selected', 'true');
      } finally {
        jest.useRealTimers();
      }
    });

    it('ignores a tab that does not exist and a pager without width', async () => {
      const { board } = await setup(true);
      (board['selectColumn'] as (id: string) => void)('nope');
      (board['onPagerScroll'] as () => void)();
      expect(screen.getByRole('tab', { name: /Idee/ })).toHaveAttribute('aria-selected', 'true');
    });

    it('asks for the move sheet on a long press (context menu)', async () => {
      const { host, view } = await setup(true);
      const item = view.container.querySelector('.bv__page .bv__item')!;
      item.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true }));
      expect(host.menus).toEqual([idea]);
    });
  });

  it('lets the page announce a result', async () => {
    const { board, live, view } = await setup();
    (board['announce'] as (t: string) => void)('„Idee A“ nach Planung verschoben.');
    view.fixture.detectChanges();
    expect(live()).toBe('„Idee A“ nach Planung verschoben.');
  });

  it('has no axe violations on the desktop layout', async () => {
    const { view } = await setup();
    expect(await runAxe(view.container)).toHaveNoViolations();
  });

  it('has no axe violations on the phone layout', async () => {
    const { view } = await setup(true);
    expect(await runAxe(view.container)).toHaveNoViolations();
  });
});
