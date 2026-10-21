/**
 * M4 acceptance (PLAN 16.1, row M4) against the compose stack with the Keycloak dev IdP: a question on the poster blocks
 * the approval in the guard list until it is resolved, the checklist with its template, a mail template with a preview
 * and the sentence for an unknown placeholder, the comparison quotes of a foreign organization answering not found,
 * and axe in light and dark on the new tabs.
 */
import { type Browser, type Page, expect, test } from '@playwright/test';
import { expectNoAxeViolations } from './support/axe';
import {
  confirmLocation,
  confirmTransition,
  createDossier,
  setSummary,
  uploadPoster,
} from './support/dossier';
import { login, postJson, waitForCleanPoster } from './support/session';

const BASE_URL = process.env['E2E_BASE_URL'] ?? 'http://localhost:8081';
const STAMP = Date.now();
const title = (name: string): string => `E2E M4 ${name} ${STAMP}`;

test.use({ baseURL: BASE_URL });
test.describe.configure({ mode: 'serial' });

const ids: Record<string, string> = {};

async function fresh(browser: Browser): Promise<Page> {
  const context = await browser.newContext({ baseURL: BASE_URL, locale: 'de-DE' });
  return context.newPage();
}

async function tab(page: Page, name: string): Promise<void> {
  await page.getByRole('tab', { name: new RegExp(`^${name}`) }).click();
}

test('a question on the poster blocks the approval until it is resolved', async ({ browser }) => {
  const organizer = await fresh(browser);
  await login(organizer, 'organizer-fsi');
  ids['poster'] = await createDossier(organizer, title('Poster'));
  await confirmTransition(organizer, 'Planung starten', 'Planung');
  await setSummary(organizer, 'Kurztext Poster');
  await uploadPoster(organizer, 'Plakat der Veranstaltung', 'Fachschaft Informatik');
  await waitForCleanPoster(organizer, ids['poster']);
  await organizer.reload();
  await confirmTransition(organizer, 'Freigabe anfragen', 'Freigabe');
  await organizer.context().close();

  const editor = await fresh(browser);
  await login(editor, 'editor');
  await editor.goto(`/dossiers/${ids['poster']}`);
  await editor.getByRole('button', { name: 'Rückfrage zu Poster' }).click();
  await editor.getByLabel('Deine Rückfrage').fill('Ist das Bild für den Druck frei?');
  await editor.getByRole('button', { name: 'Rückfrage senden' }).click();
  await expect(editor.getByText('Rückfrage gesendet.')).toBeVisible();
  await expect(editor.getByText('Rückfrage offen').first()).toBeVisible();

  await editor.getByRole('button', { name: 'Freigeben' }).first().click();
  const dialog = editor.getByRole('dialog', { name: 'Freigeben' });
  await expect(
    dialog.getByText('Eine offene Rückfrage am Poster blockiert die Freigabe.'),
  ).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Bestätigen', exact: true })).toBeDisabled();
  await dialog.getByRole('button', { name: 'Abbrechen' }).click();

  await tab(editor, 'Verlauf');
  await expect(editor.getByRole('status').getByText(/blockiert die Freigabe/)).toBeVisible();
  await editor.getByRole('button', { name: 'Erledigt' }).click();
  await expect(editor.getByText('Offen', { exact: true })).toHaveCount(0);
  await expectNoAxeViolations(editor, 'Verlauf with questions');

  await tab(editor, 'Übersicht');
  await confirmLocation(editor, ids['poster']);
  await editor.getByRole('button', { name: 'Freigeben' }).first().click();
  await expect(
    editor
      .getByRole('dialog', { name: 'Freigeben' })
      .getByRole('button', { name: 'Bestätigen', exact: true }),
  ).toBeEnabled();
  await editor.context().close();
});

test('checklist: apply the template, add an own required point, tick one', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  ids['checklist'] = await createDossier(page, title('Checkliste'));
  await tab(page, 'Checkliste');
  await page.getByRole('button', { name: 'Vorlage anwenden' }).click();
  await expect(page.getByText(/Punkte aus der Vorlage hinzugefügt/)).toBeVisible();
  await expect(page.getByRole('heading', { name: /^Planung/ })).toBeVisible();
  await expect(page.getByText('Pflicht').first()).toBeVisible();

  await page.getByRole('button', { name: 'Punkt hinzufügen' }).click();
  await page.getByRole('textbox', { name: /^Punkt/ }).fill('Schlüssel beim Hausmeister holen');
  await page.getByRole('checkbox', { name: 'Pflichtpunkt' }).check();
  await page.getByRole('button', { name: 'Punkt anlegen' }).click();
  const own = page.getByRole('checkbox', { name: /Schlüssel beim Hausmeister holen/ });
  await expect(own).toBeVisible();
  await own.check();
  await expect(own).toBeChecked();
  await expectNoAxeViolations(page, 'Checkliste');
  await page.context().close();
});

test('mail template: placeholder chip, live preview and the sentence for an unknown placeholder', async ({
  browser,
}) => {
  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  ids['mail'] = await createDossier(page, title('Mail'));
  await tab(page, 'Mails');
  await page.getByRole('button', { name: 'Neue Vorlage' }).click();
  await expect(page.getByRole('radio', { name: 'Quelltext' })).toHaveAttribute(
    'aria-checked',
    'true',
  );
  await page.getByRole('textbox', { name: 'Betreff' }).fill('Einladung');
  await page.getByRole('textbox', { name: 'Text' }).fill('Hallo, ');
  await page.getByRole('button', { name: '{{ event.title }}' }).click();
  await expect(page.getByText(`Hallo, ${title('Mail')}`)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Als Mail öffnen' })).toBeVisible();

  await page.getByRole('textbox', { name: 'Text' }).fill('Raum {{ event.raum }}');
  await expect(page.getByRole('alert')).toContainText('Unbekannter Platzhalter {{ event.raum }}');
  await expect(page.getByRole('alert')).toContainText('{{ event.title }}');
  await expectNoAxeViolations(page, 'Mails');

  await page.getByRole('textbox', { name: 'Text' }).fill('Hallo {{ org.name }}');
  await page.getByRole('button', { name: 'Vorlage speichern' }).click();
  await expect(page.getByText('Vorlage gespeichert.')).toBeVisible();
  await page.context().close();
});

test('a foreign organization sees neither quotes nor attachments of the dossier', async ({
  browser,
}) => {
  const makers = await fresh(browser);
  await login(makers, 'organizer-makers');
  for (const path of ['quotes', 'attachments', 'checklist', 'comments', 'mail-templates']) {
    expect((await makers.request.get(`/api/events/${ids['checklist']}/${path}`)).status()).toBe(
      404,
    );
  }
  const quote = await postJson(makers, `/api/events/${ids['checklist']}/quotes`, {
    grp: 'Technik',
    vendor: 'Licht GmbH',
    amountCents: 10000,
  });
  expect(quote.status()).toBe(404);
  await makers.goto(`/dossiers/${ids['checklist']}`);
  await expect(makers.getByRole('alert')).toContainText(
    'Diese Seite gibt es nicht oder du hast keinen Zugriff.',
  );
  await makers.context().close();
});

test('attachments and howto render for the organizer and pass axe', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  await page.goto(`/dossiers/${ids['checklist']}`);
  await tab(page, 'Anhänge');
  await expect(page.getByRole('heading', { name: 'Anhänge' })).toBeVisible();
  await page.getByRole('button', { name: 'Anhang hinzufügen' }).click();
  await expect(page.getByRole('button', { name: 'Datei wählen' })).toBeVisible();
  await expectNoAxeViolations(page, 'Anhänge');
  await tab(page, 'Anleitung');
  await page.getByRole('button', { name: 'Vorlage einfügen' }).click();
  await expect(page.getByRole('textbox', { name: 'Diese Ausgabe' })).toHaveValue(
    /## Worum geht es\?/,
  );
  await expect(page.getByText('Bitte keine privaten Telefonnummern')).toBeVisible();
  await expectNoAxeViolations(page, 'Anleitung');
  await page.context().close();
});

async function expectNoSideScroll(page: Page, label: string): Promise<void> {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow, `${label}: horizontal overflow in px`).toBeLessThanOrEqual(0);
}

test('phone at 360 px: the new tabs, account and inbox without side scroll, axe, keyboard path', async ({
  browser,
}) => {
  test.setTimeout(180_000);
  const context = await browser.newContext({
    baseURL: BASE_URL,
    locale: 'de-DE',
    viewport: { width: 360, height: 740 },
  });
  const page = await context.newPage();
  await login(page, 'organizer-fsi');
  await page.goto(`/dossiers/${ids['checklist']}`);
  const headings: Record<string, string> = {
    Anhänge: 'Anhänge',
    Anleitung: 'Anleitung',
    Checkliste: 'Checkliste',
    Mails: 'Mails',
    Verlauf: 'Rückfragen',
  };
  for (const [name, heading] of Object.entries(headings)) {
    await tab(page, name);
    await expect(
      page.getByRole('heading', { name: new RegExp(`^${heading}`) }).first(),
    ).toBeVisible();
    await expectNoSideScroll(page, name);
    await expectNoAxeViolations(page, `${name} (360 px)`);
  }

  await tab(page, 'Checkliste');
  const box = page.getByRole('checkbox', { name: /Raum bestätigt/ });
  await box.focus();
  await page.keyboard.press('Space');
  await expect(box).toBeChecked();

  await tab(page, 'Anhänge');
  await page.getByRole('button', { name: 'Anhang hinzufügen' }).focus();
  await page.keyboard.press('Enter');
  const chooser = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: 'Datei wählen' }).focus();
  await page.keyboard.press('Enter');
  await (
    await chooser
  ).setFiles({
    name: 'tastatur.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('Per Tastatur hochgeladen.\n'),
  });
  await page.getByRole('button', { name: 'Hochladen' }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByText('tastatur.txt')).toBeVisible();
  await expectNoSideScroll(page, 'Anhänge nach Upload');

  await page.goto('/konto');
  await expect(page.getByRole('heading', { name: /Benachrichtigungen/ }).first()).toBeVisible();
  await expectNoSideScroll(page, 'Konto');
  await expectNoAxeViolations(page, 'Konto (360 px)');
  await page.getByRole('button', { name: /^Benachrichtigungen, \d+ ungelesen/ }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expectNoSideScroll(page, 'Inbox');
  await expectNoAxeViolations(page, 'Inbox (360 px)');
  await context.close();
});
