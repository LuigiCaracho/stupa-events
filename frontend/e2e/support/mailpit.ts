/**
 * Mailpit client for the E2E (B3 contract 6.7): the dev stack catches every mail of the API worker and of Listmonk in
 * Mailpit (`SMTP_HOST=localhost SMTP_PORT=1025`). `waitForMail` polls the message list until a mail to the address (and
 * with a part of the subject) arrives and returns its text with the first token link (`/bestaetigen/<token>` or
 * `/abo/<token>`); `deleteAll` empties the box between the tests.
 */
import { expect } from '@playwright/test';

const MAILPIT = process.env['MAILPIT_URL'] ?? 'http://127.0.0.1:8025';
const TOKEN_LINK = /https?:\/\/[^\s"'<>]+\/(?:bestaetigen|abo)\/[A-Za-z0-9_-]{43}/;

interface Summary {
  ID: string;
  Subject: string;
  To: { Address: string }[];
}

export interface CapturedMail {
  subject: string;
  text: string;
  link: string | null;
  path: string | null;
}

async function listMessages(): Promise<Summary[]> {
  const answer = await fetch(`${MAILPIT}/api/v1/messages?limit=100`);
  expect(answer.ok, 'Mailpit reachable').toBe(true);
  return ((await answer.json()) as { messages: Summary[] }).messages ?? [];
}

export async function deleteAll(): Promise<void> {
  const answer = await fetch(`${MAILPIT}/api/v1/messages`, { method: 'DELETE' });
  expect(answer.ok, 'Mailpit emptied').toBe(true);
}

export async function waitForMail(
  to: string,
  subjectPart = '',
  timeoutMs = 90_000,
): Promise<CapturedMail> {
  let found: Summary | undefined;
  await expect
    .poll(
      async () => {
        found = (await listMessages()).find(
          (m) =>
            m.To.some((t) => t.Address.toLowerCase() === to.toLowerCase()) &&
            m.Subject.toLowerCase().includes(subjectPart.toLowerCase()),
        );
        return Boolean(found);
      },
      { timeout: timeoutMs, intervals: [1_000], message: `mail to ${to}` },
    )
    .toBe(true);
  const message = (await (await fetch(`${MAILPIT}/api/v1/message/${found?.ID}`)).json()) as {
    Text: string;
    HTML: string;
  };
  const text = message.Text || message.HTML;
  const link = TOKEN_LINK.exec(message.Text)?.[0] ?? TOKEN_LINK.exec(message.HTML)?.[0] ?? null;
  return { subject: found?.Subject ?? '', text, link, path: link ? new URL(link).pathname : null };
}

export async function countMailsTo(to: string): Promise<number> {
  return (await listMessages()).filter((m) =>
    m.To.some((t) => t.Address.toLowerCase() === to.toLowerCase()),
  ).length;
}
