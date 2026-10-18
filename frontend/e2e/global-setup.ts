/** Playwright global setup: waits until the compose stack answers `/api/health` before the first test. */
import type { FullConfig } from '@playwright/test';

const WAIT_MS = 180_000;
const STEP_MS = 2_000;

async function healthy(url: string): Promise<boolean> {
  try {
    return (await fetch(url)).ok;
  } catch {
    return false;
  }
}

export default async function globalSetup(config: FullConfig): Promise<void> {
  const base = process.env['E2E_BASE_URL'] ?? config.projects[0]?.use.baseURL ?? 'http://localhost:8081';
  const url = new URL('/api/health', base).toString();
  const deadline = Date.now() + WAIT_MS;
  while (Date.now() < deadline) {
    if (await healthy(url)) return;
    await new Promise((resolve) => setTimeout(resolve, STEP_MS));
  }
  throw new Error(`Stack not healthy after ${WAIT_MS / 1000} s: ${url}. Start it with deploy/docker-compose.yml.`);
}
