/**
 * axe in the browser (WCAG 2.1 AA, colour contrast included) for both themes. The theme is the `data-theme`
 * attribute of `<html>`, so one open page can be checked twice without a reload; a dialog stays open between the
 * two runs. Only `serious` and `critical` findings fail the test (M3 contract 9.4, scenario 8).
 */
import AxeBuilder from '@axe-core/playwright';
import { type Page, expect } from '@playwright/test';

export type Theme = 'light' | 'dark';
export const THEMES: readonly Theme[] = ['light', 'dark'];

const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

export async function useTheme(page: Page, theme: Theme): Promise<void> {
  await page.evaluate((t) => document.documentElement.setAttribute('data-theme', t), theme);
  // Colours transition for a moment after the switch; axe would measure the colours in between.
  await page.waitForTimeout(400);
}

async function violations(page: Page, scope?: string): Promise<string[]> {
  const builder = new AxeBuilder({ page }).withTags(TAGS);
  const result = await (scope ? builder.include(scope) : builder).analyze();
  return result.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`);
}

/** Checks the open page in light and dark and fails with the findings of both. */
export async function expectNoAxeViolations(
  page: Page,
  label: string,
  scope?: string,
): Promise<void> {
  for (const theme of THEMES) {
    await useTheme(page, theme);
    expect(await violations(page, scope), `${label} (${theme})`).toEqual([]);
  }
  await useTheme(page, 'light');
}
