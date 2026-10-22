/** Spec for P05 Kategorie: description, subscription link, upcoming list, review, empty and 404. */
import { HttpTestingController } from '@angular/common/http/testing';
import { screen } from '@testing-library/angular';
import { runAxe } from '../../../../../testing/a11y';
import { CATEGORIES, card, search } from '../../../../../testing/public-fixtures';
import { mountPublic, tick } from '../../../../../testing/public-harness';
import { CategoryPageComponent } from './category.component';

async function open(
  slug: string,
  upcoming = search([card()]),
  past = search([]),
  categories: object = CATEGORIES,
) {
  const h = await mountPublic(CategoryPageComponent, 'k/:slug', `/k/${slug}`);
  h.harness.detectChanges();
  h.http.expectOne('/api/public/categories').flush(categories);
  const calls = (http: HttpTestingController) => http.match((r) => r.url === '/api/public/events');
  for (const r of calls(h.http)) r.flush(r.request.params.get('past') === '1' ? past : upcoming);
  await tick(h);
  await tick(h);
  return h;
}

describe('CategoryPageComponent', () => {
  it('shows name, description, the subscription link and the upcoming events', async () => {
    await open('kultur');
    expect(screen.getByRole('heading', { level: 1, name: 'Kultur' })).toBeInTheDocument();
    expect(screen.getByText('Kino und mehr.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Kalender abonnieren' })).toHaveAttribute(
      'href',
      '/abos#k=kultur',
    );
    expect(screen.getByRole('link', { name: 'Movienight: Arrival' })).toBeInTheDocument();
  });

  it('asks for the category and, separately, the six latest past events', async () => {
    const h = await mountPublic(CategoryPageComponent, 'k/:slug', '/k/kultur');
    h.harness.detectChanges();
    h.http.expectOne('/api/public/categories').flush(CATEGORIES);
    const reqs = h.http.match((r) => r.url === '/api/public/events');
    expect(reqs.map((r) => r.request.params.get('category'))).toEqual(['kultur', 'kultur']);
    const review = reqs.find((r) => r.request.params.get('past') === '1')!;
    expect(review.request.params.get('limit')).toBe('6');
    reqs.forEach((r) => r.flush(search([])));
  });

  it('shows the review below when there are past events', async () => {
    await open(
      'kultur',
      search([card()]),
      search([card({ slug: 'alt', title: 'Altes Event', path: '/e/alt' })]),
    );
    expect(screen.getByRole('heading', { name: 'Rückblick' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Altes Event' })).toBeInTheDocument();
  });

  it('invites to subscribe when nothing is planned', async () => {
    await open('kultur', search([]));
    expect(
      screen.getByText(
        'Gerade nichts geplant in Kultur. Abonniere, dann siehst du neue Termine im Kalender.',
      ),
    ).toBeInTheDocument();
  });

  it('answers an unknown category with 404 text', async () => {
    await open('gibtsnicht');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Diese Kategorie gibt es nicht.',
    );
  });

  it('has no axe violations', async () => {
    const h = await open('kultur');
    expect(await runAxe(h.harness.routeNativeElement as HTMLElement)).toHaveNoViolations();
  });
});
