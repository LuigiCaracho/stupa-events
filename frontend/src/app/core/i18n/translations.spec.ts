/** Catalog sanity checks. */
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { NOTIFICATION_KINDS } from '../../features/dossiers/model/notification.models';
import { de } from './translations';
import { PUBLIC_SHELL_KEYS } from './public-shell-keys';
import { adminDe } from './translations.admin.de';
import { archiveDe } from './translations.archive.de';
import { dossierDe } from './translations.dossier.de';
import { en } from './translations.en';
import { eventsDe } from './translations.events.de';
import { formatDe } from './translations.format.de';
import { lifecycleDe } from './translations.lifecycle.de';
import { mapDe } from './translations.map.de';
import { publicDe } from './translations.public.de';
import { sharedDe } from './translations.shared.de';
import { subscriptionsDe } from './translations.subscriptions.de';

const APP = join(__dirname, '..', '..');

function sources(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return sources(path);
    const code = /\.(ts|html)$/.test(entry.name) && !/\.spec\.ts$/.test(entry.name);
    return code && !/^translations\..*\.de\.ts$/.test(entry.name)
      ? [readFileSync(path, 'utf8')]
      : [];
  });
}

describe('translations', () => {
  it('has no empty string', () => {
    expect(Object.entries(de).filter(([, v]) => v.trim() === '')).toEqual([]);
  });

  it('uses the Du-form and no Sie-form in the shell strings', () => {
    expect(Object.values(de).filter((v) => /\bSie\b/.test(v))).toEqual([]);
  });

  it('gendered with the colon or neutral, never with star, underscore, slash or capital I', () => {
    const forms = /\*in|_in|\/in\b|[a-zäöüß]In(nen)?\b|\*innen|\(in\)/;
    expect(Object.entries(de).filter(([, v]) => forms.test(v))).toEqual([]);
  });

  it('translates every hint code the backend can send', () => {
    const codes = [
      'no_poster',
      'poster_alt_missing',
      'poster_credit_missing',
      'poster_consent_missing',
      'poster_not_ready',
      'no_organization',
      'no_summary',
      'no_category',
      'no_venue',
      'location_unconfirmed',
      'facts_incomplete',
      'howto_missing',
      'outcome_open',
    ];
    expect(codes.map((c) => `hints.${c}`).filter((k) => !(k in de))).toEqual([]);
  });

  it('translates every notification kind', () => {
    expect(
      NOTIFICATION_KINDS.map((k) => `notification.kind.${k}`).filter((k) => !(k in de)),
    ).toEqual([]);
  });

  it('translates every reason of the clone report', () => {
    const reasons = [
      'title',
      'text',
      'reference',
      'location',
      'facts',
      'factsForeign',
      'documents',
      'howto',
      'checklist',
      'poster',
      'files',
      'social',
      'links',
      'history',
      'shared',
    ];
    expect(reasons.map((r) => `clone.reason.${r}`).filter((k) => !(k in de))).toEqual([]);
  });

  it('has no key that no code uses: a dead string is deleted, not kept', () => {
    const code = sources(APP).join('\n');
    const dynamic = [...code.matchAll(/`([\w.]+\.)\$\{/g)].map((m) => m[1]);
    const clone = [...code.matchAll(/dynamicKey\('([\w.]+)'/g)].map((m) => `${m[1]}.`);
    const prefixes = [...dynamic, ...clone];
    const used = (key: string): boolean =>
      code.includes(`'${key}'`) ||
      code.includes(`"${key}"`) ||
      prefixes.some((p) => key.startsWith(p));
    expect(Object.keys(de).filter((k) => !used(k))).toEqual([]);
  });

  it('keeps no key of the removed pipeline', () => {
    const dead = /^(guards|fix|transition|board|tasks|exception|assign|followup|home)\./;
    expect(Object.keys(de).filter((k) => dead.test(k))).toEqual([]);
  });
});

describe('English parity (B4)', () => {
  const covered = {
    ...Object.fromEntries(Object.keys(publicDe).map((k) => [k, k])),
    ...Object.fromEntries(Object.keys(subscriptionsDe).map((k) => [k, k])),
    ...Object.fromEntries(Object.keys(sharedDe).map((k) => [k, k])),
    ...Object.fromEntries(Object.keys(mapDe).map((k) => [k, k])),
    ...Object.fromEntries(PUBLIC_SHELL_KEYS.map((k) => [k, k])),
  };
  const keys = Object.keys(covered);
  const english = en as Record<string, string>;
  const german = de as Record<string, string>;
  const placeholders = (text: string): string[] =>
    [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
  /** Names and loan words that read the same in both languages. */
  const SAME = new Set([
    'STUPA Events',
    'Get started',
    'Thunderbird',
    'Offline',
    'Organisation',
    'Ticket',
    'Campus',
    'Events',
    '+{count}',
  ]);

  it('has an English text for every public German key', () => {
    expect(keys.filter((k) => !(k in english))).toEqual([]);
  });

  it('has no English key without a German counterpart', () => {
    expect(Object.keys(english).filter((k) => !(k in german))).toEqual([]);
    expect(Object.keys(english).filter((k) => !(k in covered))).toEqual([]);
  });

  it('keeps the same {placeholders} in both languages', () => {
    const bad = keys.filter(
      (k) => placeholders(german[k]).join() !== placeholders(english[k] ?? '').join(),
    );
    expect(bad).toEqual([]);
  });

  it('has no empty English text', () => {
    expect(Object.entries(english).filter(([, v]) => v.trim() === '')).toEqual([]);
  });

  it('has no English text that is the German one, except names', () => {
    expect(keys.filter((k) => english[k] === german[k] && !SAME.has(german[k]))).toEqual([]);
  });

  it('leaves the internal catalogs German: no English key outside the public ones', () => {
    const internal = Object.keys({
      ...adminDe,
      ...dossierDe,
      ...lifecycleDe,
      ...archiveDe,
      ...formatDe,
      ...eventsDe,
    });
    expect(internal.filter((k) => k in english && !(k in covered))).toEqual([]);
  });

  it('uses no German article or ending in an English text of the public shell', () => {
    expect(Object.values(english).filter((v) => /\b(und|der|die|das|nicht|ist)\b/.test(v))).toEqual(
      [],
    );
  });
});
