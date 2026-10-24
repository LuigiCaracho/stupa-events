/**
 * Fixtures of the public E2E (B1): the events a visitor can see. `findFixtures` reads them from the public API; when one
 * is missing, `createFixtures` makes it through the dossier UI as organizer-fsi (one with poster and ticket, one
 * cancelled, one past with poster). Titles start with `E2E B1`, so a rerun finds what an earlier run left.
 */
import { type APIRequestContext, type Browser, type Page, expect, request } from '@playwright/test';
import { createDossier, runAction, setSummary, uploadPoster } from './dossier';
import { eventOf, login, patchEvent, waitForCleanPoster } from './session';

const BASE_URL = process.env['E2E_BASE_URL'] ?? 'http://localhost:8081';
const PREFIX = 'E2E B1';

export interface PublicFixtures {
  poster: string;
  posterTitle: string;
  cancelled: string;
  past: string | null;
  category: string;
}

interface Card {
  slug: string;
  title: string;
  status: string;
  image: unknown;
  categories: { slug: string }[];
}

async function list(api: APIRequestContext, query: string): Promise<Card[]> {
  const answer = await api.get(`/api/public/events?${query}`);
  return answer.ok() ? (await answer.json()).items : [];
}

export async function findFixtures(): Promise<Partial<PublicFixtures>> {
  const api = await request.newContext({ baseURL: BASE_URL });
  const mine = encodeURIComponent(PREFIX);
  const upcoming = [
    ...(await list(api, `q=${mine}&limit=50`)),
    ...(await list(api, 'limit=50')),
  ];
  const past = [
    ...(await list(api, `q=${mine}&past=1&limit=50`)),
    ...(await list(api, 'past=1&limit=50')),
  ];
  let poster: Card | undefined;
  for (const card of upcoming.filter((c) => c.image && c.status === 'scheduled')) {
    const detail = await (await api.get(`/api/public/events/${card.slug}`)).json();
    if (detail.ticketUrl) {
      poster = card;
      break;
    }
  }
  await api.dispose();
  const cancelled = upcoming.find((c) => c.status === 'cancelled');
  const old = past.find((c) => c.image);
  return {
    poster: poster?.slug,
    posterTitle: poster?.title,
    cancelled: cancelled?.slug,
    past: old?.slug,
    category: poster?.categories[0]?.slug,
  };
}

async function publishedDossier(page: Page, name: string): Promise<string> {
  const id = await createDossier(page, `${PREFIX} ${name} ${Date.now()}`);
  await setSummary(page, `Beispieltext für ${name}`);
  return id;
}

export async function createFixtures(
  browser: Browser,
  have: Partial<PublicFixtures>,
): Promise<void> {
  const context = await browser.newContext({ baseURL: BASE_URL, locale: 'de-DE' });
  const page = await context.newPage();
  await login(page, 'organizer-fsi');
  if (!have.poster) {
    const id = await publishedDossier(page, 'Mit Poster');
    await uploadPoster(page, { altText: 'Plakat der Fixture', credit: 'Fachschaft Informatik' });
    await waitForCleanPoster(page, id);
    const event = await eventOf(page, id);
    const patch = await patchEvent(page, id, event['rev'], {
      ticketUrl: 'https://tickets.example.org/e2e',
    });
    expect(patch.ok()).toBe(true);
    await page.reload();
    await runAction(page, 'Veröffentlichen', 'Veröffentlicht');
  }
  if (!have.cancelled) {
    await publishedDossier(page, 'Abgesagt');
    await runAction(page, 'Veröffentlichen', 'Veröffentlicht');
    await page
      .getByRole('group', { name: 'Aktionen' })
      .getByRole('button', { name: 'Absagen' })
      .click();
    await page.getByRole('dialog').getByRole('button', { name: 'Absagen' }).last().click();
    await expect(page.locator('app-dossier-head').getByText('Abgesagt').first()).toBeVisible();
  }
  await context.close();
}
