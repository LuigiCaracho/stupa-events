/**
 * Read access to the dev Listmonk for the E2E: is there a subscriber with this address? It needs the API user of the
 * dev stack (`LISTMONK_API_USER`, `LISTMONK_API_TOKEN`); without them `hasSubscriber` answers `null` and the test skips
 * that assertion instead of guessing.
 */
const LISTMONK = process.env['LISTMONK_URL'] ?? 'http://127.0.0.1:9002';
const USER = process.env['LISTMONK_API_USER'];
const TOKEN = process.env['LISTMONK_API_TOKEN'];

export const listmonkConfigured = (): boolean => Boolean(USER && TOKEN);

export async function hasSubscriber(email: string): Promise<boolean | null> {
  if (!USER || !TOKEN) return null;
  const query = encodeURIComponent(`subscribers.email = '${email.replace(/'/g, "''")}'`);
  const answer = await fetch(`${LISTMONK}/api/subscribers?query=${query}&per_page=1`, {
    headers: { Authorization: `token ${USER}:${TOKEN}` },
  });
  if (!answer.ok) throw new Error(`Listmonk answered ${answer.status}`);
  const body = (await answer.json()) as { data: { total: number } };
  return body.data.total > 0;
}
