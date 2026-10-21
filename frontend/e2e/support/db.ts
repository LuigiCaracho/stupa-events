/**
 * Test-only door into the dev database: moves a dossier into the follow-up by SQL, because the step after the end of an event
 * (T08) belongs to the worker clock. It runs `psql` inside the Postgres container of the dev stack
 * (`E2E_PG_CONTAINER`, default `stupa-events-dev-postgres-1`). Never point it at a stack that holds real data.
 */
import { execFileSync } from 'node:child_process';

const CONTAINER = process.env['E2E_PG_CONTAINER'] ?? 'stupa-events-dev-postgres-1';

export function psql(sql: string): string {
  return execFileSync(
    'docker',
    ['exec', '-i', CONTAINER, 'psql', '-U', 'postgres', '-d', 'events', '-At', '-c', sql],
    { encoding: 'utf8', timeout: 20_000 },
  ).trim();
}

export function databaseReachable(): boolean {
  try {
    return psql('select 1') === '1';
  } catch {
    return false;
  }
}

/** The dossier ended three days ago and sits in `followup` (what T08 does after the end plus twelve hours). */
export function moveToFollowup(id: string): void {
  const uuid = /^[0-9a-f-]{36}$/.exec(id)?.[0];
  if (!uuid) throw new Error(`not a dossier id: ${id}`);
  psql(
    `update event set state = 'followup', starts_at = now() - interval '3 days 2 hours', ` +
      `ends_at = now() - interval '3 days', rev = rev + 1 where id = '${uuid}'`,
  );
}
