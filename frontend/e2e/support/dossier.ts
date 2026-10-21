/**
 * E2E building blocks of the dossier UI (M5b): create a draft through the dialog, run a lifecycle action from the action
 * bar and wait for the new state, save the summary, put a poster into the slot (file pick or drop). The lifecycle needs no
 * dialog except cancel and postpone, so `runAction` is one click and one expectation.
 */
import { type Page, expect } from '@playwright/test';
import { makePng } from './png';
import { eventOf, inDays, postJson } from './session';

export interface NewDossier {
  organization?: string;
  category?: string;
  venue?: string;
  days?: number;
}

export async function createDossier(
  page: Page,
  title: string,
  options: NewDossier = {},
): Promise<string> {
  await page.goto('/dossiers');
  await page.getByRole('button', { name: 'Neues Event' }).first().click();
  const dialog = page.getByRole('dialog', { name: 'Neues Event' });
  await dialog.getByRole('textbox', { name: 'Titel', exact: true }).fill(title);
  if (options.organization) {
    await dialog.getByRole('combobox', { name: /Organisation/ }).click();
    await page.getByRole('option', { name: options.organization, exact: true }).click();
  }
  const days = options.days ?? 40;
  await dialog.getByRole('textbox', { name: 'Beginn, Datum' }).fill(inDays(days));
  await dialog.getByRole('textbox', { name: 'Beginn, Datum' }).blur();
  await dialog.getByRole('textbox', { name: 'Beginn, Uhrzeit' }).fill('19:30');
  await dialog.getByRole('textbox', { name: 'Beginn, Uhrzeit' }).blur();
  await dialog.getByRole('textbox', { name: 'Ende, Datum' }).fill(inDays(days));
  await dialog.getByRole('textbox', { name: 'Ende, Datum' }).blur();
  await dialog.getByRole('textbox', { name: 'Ende, Uhrzeit' }).fill('21:30');
  await dialog.getByRole('textbox', { name: 'Ende, Uhrzeit' }).blur();
  await dialog.getByRole('textbox', { name: 'Ort', exact: true }).fill(options.venue ?? 'Kinosaal 9-133');
  await dialog.getByRole('combobox', { name: /Format oder Kategorie/ }).click();
  await page.getByRole('option', { name: options.category ?? 'Kino', exact: true }).click();
  await dialog.getByRole('button', { name: 'Anlegen' }).click();
  await page.waitForURL(/\/dossiers\/[0-9a-f-]{36}$/);
  await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible();
  return page.url().split('/').pop() as string;
}

/** Clicks an action of the bar and waits until the head shows the state text that follows. */
export async function runAction(page: Page, action: string, stateText: string): Promise<void> {
  await page.getByRole('group', { name: 'Aktionen' }).getByRole('button', { name: action }).click();
  await expect(page.locator('app-dossier-head app-status-text', { hasText: stateText }).first()).toBeVisible();
}

/** Opens a section of the dossier page through its anchor link. */
export async function toSection(page: Page, name: string): Promise<void> {
  await page.getByRole('navigation', { name: 'Abschnitte des Dossiers' }).getByRole('link', { name: new RegExp(`^${name}`) }).click();
}

export async function setSummary(page: Page, summary: string): Promise<void> {
  const field = page.getByRole('textbox', { name: /Kurztext/ });
  await field.fill(summary);
  await page.getByRole('button', { name: 'Speichern', exact: true }).click();
  await expect(page.getByText('Gespeichert.')).toBeVisible();
  await expect(field).toHaveValue(summary);
}

export interface PosterOptions {
  altText?: string;
  credit?: string;
  viaDrop?: boolean;
}

const dataTransferOf = async (page: Page) =>
  page.evaluateHandle((bytes) => {
    const transfer = new DataTransfer();
    transfer.items.add(new File([new Uint8Array(bytes)], 'plakat.png', { type: 'image/png' }));
    return transfer;
  }, [...makePng()]);

/** Puts a poster into the slot: by file pick, or by dropping a file on the drop zone (`viaDrop`). */
export async function uploadPoster(page: Page, options: PosterOptions = {}): Promise<void> {
  const slot = page.locator('app-poster-slot');
  if (options.viaDrop) {
    const transfer = await dataTransferOf(page);
    await slot.locator('.fdz').dispatchEvent('drop', { dataTransfer: transfer });
  } else {
    await slot.locator('input[type="file"]').setInputFiles({
      name: 'plakat.png',
      mimeType: 'image/png',
      buffer: makePng(),
    });
  }
  if (options.altText) await slot.getByRole('textbox', { name: /Alt-Text/ }).fill(options.altText);
  if (options.credit) await slot.getByRole('textbox', { name: /Credit/ }).fill(options.credit);
  await slot.getByRole('button', { name: 'Bild hochladen' }).click();
  await expect(page.getByText('Bild hochgeladen.')).toBeVisible();
}

/** Confirms an unconfirmed free venue text over the API (it only matters for the feed, not for publishing). */
export async function confirmLocation(page: Page, id: string): Promise<void> {
  const event = await eventOf(page, id);
  if (event['venueId'] || !event['venueText'] || event['locationConfirmedAt']) return;
  const answer = await postJson(page, `/api/events/${id}/actions/confirm-location`, {
    precision: 'building',
  });
  expect(answer.status()).toBe(200);
  await page.reload();
}
