/**
 * E2E building blocks of the dossier UI: create, move through transitions ("Freigeben" approves without publishing,
 * so the M1 flow keeps its second step), save the summary, upload the poster.
 */
import { type Page, expect } from '@playwright/test';
import { makePng } from './png';
import { inDays } from './session';

export async function createDossier(page: Page, title: string): Promise<string> {
  await page.goto('/aufgaben');
  await page.getByRole('button', { name: 'Neues Event' }).first().click();
  const dialog = page.getByRole('dialog', { name: 'Neues Event' });
  await dialog.getByRole('textbox', { name: 'Titel', exact: true }).fill(title);
  await dialog.getByRole('textbox', { name: 'Beginn, Datum' }).fill(inDays(40));
  await dialog.getByRole('textbox', { name: 'Beginn, Datum' }).blur();
  await dialog.getByRole('textbox', { name: 'Beginn, Uhrzeit' }).fill('19:30');
  await dialog.getByRole('textbox', { name: 'Beginn, Uhrzeit' }).blur();
  await dialog.getByRole('textbox', { name: 'Ende, Datum' }).fill(inDays(40));
  await dialog.getByRole('textbox', { name: 'Ende, Datum' }).blur();
  await dialog.getByRole('textbox', { name: 'Ende, Uhrzeit' }).fill('21:30');
  await dialog.getByRole('textbox', { name: 'Ende, Uhrzeit' }).blur();
  await dialog.getByRole('textbox', { name: 'Ort', exact: true }).fill('Kinosaal 9-133');
  await dialog.getByRole('combobox', { name: /Format oder Kategorie/ }).click();
  await page.getByRole('option', { name: 'Kino', exact: true }).click();
  await dialog.getByRole('button', { name: 'Anlegen' }).click();
  await page.waitForURL(/\/dossiers\/[0-9a-f-]{36}$/);
  await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible();
  return page.url().split('/').pop() as string;
}

export async function confirmTransition(
  page: Page,
  action: string,
  newState: string,
): Promise<void> {
  await page.getByRole('button', { name: action }).first().click();
  const dialog = page.getByRole('dialog', { name: action });
  await dialog.getByRole('heading', { name: 'Fehlt noch' }).waitFor();
  const notice = dialog.getByRole('checkbox', { name: 'Ich habe die Hinweise gelesen.' });
  if (await notice.count()) await notice.check();
  if (action === 'Freigeben')
    await dialog.getByRole('switch', { name: 'Sofort veröffentlichen' }).click();
  const confirm = dialog.getByRole('button', { name: 'Bestätigen' });
  await expect(confirm).toBeEnabled();
  await confirm.click();
  await expect(dialog).toBeHidden();
  await expect(page.locator('app-status-text', { hasText: newState }).first()).toBeVisible();
}

export async function setSummary(page: Page, summary: string): Promise<void> {
  const field = page.getByRole('textbox', { name: /Kurztext/ });
  await field.fill(summary);
  await page.getByRole('button', { name: 'Speichern' }).click();
  await expect(page.getByText('Gespeichert.')).toBeVisible();
  await expect(field).toHaveValue(summary);
}

export async function uploadPoster(page: Page, altText: string, credit: string): Promise<void> {
  const upload = page.locator('app-poster-upload');
  await upload.locator('input[type="file"]').setInputFiles({
    name: 'plakat.png',
    mimeType: 'image/png',
    buffer: makePng(),
  });
  await upload.getByRole('textbox', { name: /Alt-Text/ }).fill(altText);
  await upload.getByRole('textbox', { name: /Credit/ }).fill(credit);
  await upload.getByRole('combobox', { name: /Rechtegrundlage/ }).click();
  await page.getByRole('option', { name: 'Eigenes Werk' }).click();
  await upload.getByRole('button', { name: 'Poster hochladen' }).click();
  await expect(page.getByText('Poster hochgeladen.')).toBeVisible();
}
