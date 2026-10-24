/**
 * Read access to the dev Listmonk for the E2E: is there a subscriber with this address? It needs the API user of the
 * dev stack (`LISTMONK_API_USER`, `LISTMONK_API_TOKEN`); without them `hasSubscriber` answers `null` and the test skips
 * that assertion instead of guessing. The lookup uses `search` and an exact match: the SQL `query` parameter needs the
 * permission `subscribers:sql_query`, which the API user does not have.
 */
const LISTMONK = process.env['LISTMONK_URL'] ?? 'http://127.0.0.1:9002';
const USER = process.env['LISTMONK_API_USER'];
const TOKEN = process.env['LISTMONK_API_TOKEN'];

export const listmonkConfigured = (): boolean => Boolean(USER && TOKEN);

export async function hasSubscriber(email: string): Promise<boolean | null> {
  if (!USER || !TOKEN) return null;
  const search = encodeURIComponent(email);
  const answer = await fetch(`${LISTMONK}/api/subscribers?search=${search}&per_page=100`, {
    headers: { Authorization: `token ${USER}:${TOKEN}` },
  });
  if (!answer.ok) throw new Error(`Listmonk answered ${answer.status}`);
  const body = (await answer.json()) as { data: { results: { email: string }[] | null } };
  return (body.data.results ?? []).some((row) => row.email.toLowerCase() === email.toLowerCase());
}
