/**
 * B4 acceptance, English (C contract 6.4): the footer switch, `lang="en"`, the public pages without German leftovers
 * in the frame and the labels, the English date format, the choice surviving a reload and axe in English. Event titles
 * come from the data and stay as written.
 */
import { expect, test } from '@playwright/test';
import { expectNoAxeViolations } from './support/axe';

const BASE_URL = process.env['E2E_BASE_URL'] ?? 'http://127.0.0.1:8081';

test.use({ baseURL: BASE_URL, locale: 'de-DE' });

const GERMAN =
  /\b(Heute|Suche|Kalender|Abos|Karte|Impressum|Datenschutz|abonnieren|Veranstaltungen|Weiter|Zurück)\b/;

test('the footer switch turns the public site English and remembers it', async ({
  page,
  request,
}) => {
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('lang', 'de');
  await page.getByRole('button', { name: 'English' }).click();
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');

  const nav = page.getByRole('navigation', { name: 'Main navigation' });
  await expect(nav.getByRole('link')).toHaveText([
    'Today',
    'Search',
    'Calendar',
    'Map',
    'Subscribe',
  ]);
  await expect(page.getByRole('heading', { name: 'Today on campus' }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Legal notice' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Deutsch' })).toHaveAttribute('lang', 'de');

  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page.getByRole('link', { name: 'Privacy' })).toBeVisible();

  for (const [path, heading] of [
    ['/suche', 'Search'],
    ['/kalender', 'Calendar'],
    ['/abos', 'Subscribe'],
    ['/start', 'Get started'],
    ['/karte', 'World map'],
    ['/campus', 'Campus map'],
  ] as const) {
    await page.goto(path);
    await expect(page.getByRole('heading', { name: heading, exact: true }).first()).toBeVisible();
    const frame = await page.locator('header, footer, nav').allInnerTexts();
    expect(frame.join('\n'), `${path} frame`).not.toMatch(GERMAN);
  }

  const first = (
    (await (await request.get('/api/public/events?limit=1')).json()).items as { slug: string }[]
  )[0];
  await page.goto(`/e/${first.slug}`);
  await expect(page.getByText('When', { exact: true })).toBeVisible();
  await expect(page.getByRole('main')).toContainText(
    /(Mon|Tue|Wed|Thu|Fri|Sat|Sun), \d{1,2} [A-Z][a-z]{2} 20\d\d, \d\d:\d\d to \d\d:\d\d/,
  );
  await expect(page.getByRole('main')).not.toContainText(/\bUhr\b/);

  await page.goto('/');
  await expectNoAxeViolations(page, 'Heute (en)');
  await page.getByRole('button', { name: 'Deutsch' }).click();
  await expect(page.locator('html')).toHaveAttribute('lang', 'de');
  await expect(page.getByRole('link', { name: 'Impressum' })).toBeVisible();
});

test('an English browser gets English on the first visit', async ({ browser }) => {
  const context = await browser.newContext({ baseURL: BASE_URL, locale: 'en-GB' });
  const page = await context.newPage();
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page.getByRole('heading', { name: 'Today on campus' }).first()).toBeVisible();
  await context.close();
});
