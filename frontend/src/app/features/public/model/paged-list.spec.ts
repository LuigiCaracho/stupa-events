/** Spec for the cursor-paged list helper. */
import { Component, signal } from '@angular/core';
import { type ComponentFixture, TestBed } from '@angular/core/testing';
import { Subject, throwError } from 'rxjs';
import { HttpErrorResponse } from '@angular/common/http';
import { type Page, pagedList } from './paged-list';

interface Row {
  id: number;
}

@Component({ standalone: true, template: '' })
class Host {
  readonly key = signal<string | undefined>('a');
  readonly calls: (string | null)[] = [];
  readonly pages = new Map<string | null, Subject<Page<Row>>>();
  readonly list = pagedList<string, Row, Page<Row>>({
    params: () => this.key(),
    fetch: (_key, cursor) => {
      this.calls.push(cursor);
      const subject = new Subject<Page<Row>>();
      this.pages.set(cursor, subject);
      return subject;
    },
  });
}

let fixture: ComponentFixture<unknown>;

function create<T>(type: new () => T): T {
  const f = TestBed.createComponent(type);
  fixture = f;
  return f.componentInstance;
}

async function settle(): Promise<void> {
  fixture.detectChanges();
  await new Promise((resolve) => setTimeout(resolve, 0));
  fixture.detectChanges();
}

describe('pagedList', () => {
  it('loads the first page, appends the next and stops without a cursor', async () => {
    const host = create(Host);
    await settle();
    host.pages.get(null)?.next({ items: [{ id: 1 }], nextCursor: 'c1' });
    await settle();
    expect(host.list.items()).toEqual([{ id: 1 }]);
    expect(host.list.hasMore()).toBe(true);

    host.list.loadMore();
    expect(host.list.loadingMore()).toBe(true);
    host.pages.get('c1')?.next({ items: [{ id: 2 }], nextCursor: null });
    await settle();
    expect(host.list.items()).toEqual([{ id: 1 }, { id: 2 }]);
    expect(host.list.hasMore()).toBe(false);
    expect(host.list.loadingMore()).toBe(false);
  });

  it('keeps the old rows while new params load and drops a late "more" answer', async () => {
    const host = create(Host);
    await settle();
    host.pages.get(null)?.next({ items: [{ id: 1 }], nextCursor: 'c1' });
    await settle();
    host.list.loadMore();

    expect(host.list.items()).toEqual([{ id: 1 }]);
    host.key.set('b');
    await settle();
    expect(host.list.items()).toEqual([{ id: 1 }]);
    host.pages.get('c1')?.next({ items: [{ id: 99 }], nextCursor: null });
    await settle();
    expect(host.list.items()).not.toContainEqual({ id: 99 });
  });

  it('reports a failed "more" without losing the rows', async () => {
    const host = create(Host);
    await settle();
    host.pages.get(null)?.next({ items: [{ id: 1 }], nextCursor: 'c1' });
    await settle();
    host.list.loadMore();
    host.pages.get('c1')?.error(new HttpErrorResponse({ status: 429, error: { status: 429 } }));
    await settle();
    expect(host.list.moreError()).toBe('rateLimited');
    expect(host.list.items()).toHaveLength(1);
  });
});

describe('pagedList errors', () => {
  it('maps a failed first page to an error kind', async () => {
    @Component({ standalone: true, template: '' })
    class Failing {
      readonly list = pagedList<string, Row, Page<Row>>({
        params: () => 'a',
        fetch: () =>
          throwError(
            () =>
              new HttpErrorResponse({
                status: 422,
                error: { status: 422, code: 'query_too_long' },
              }),
          ),
      });
    }
    const host = create(Failing);
    await settle();
    expect(host.list.error()).toBe('queryTooLong');
  });
});
