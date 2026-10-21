/** Catalog sanity checks. */
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { de } from './translations';

const APP = join(__dirname, '..', '..');

function sources(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return sources(path);
    const code = /\.(ts|html)$/.test(entry.name) && !/\.spec\.ts$/.test(entry.name);
    return code && !/^translations\..*\.de\.ts$/.test(entry.name) ? [readFileSync(path, 'utf8')] : [];
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

  it('has no key that no code uses: a dead string is deleted, not kept', () => {
    const code = sources(APP).join('\n');
    const dynamic = [...code.matchAll(/`([\w.]+\.)\$\{/g)].map((m) => m[1]);
    const clone = [...code.matchAll(/dynamicKey\('([\w.]+)'/g)].map((m) => `${m[1]}.`);
    const prefixes = [...dynamic, ...clone];
    const used = (key: string): boolean =>
      code.includes(`'${key}'`) || code.includes(`"${key}"`) || prefixes.some((p) => key.startsWith(p));
    expect(Object.keys(de).filter((k) => !used(k))).toEqual([]);
  });

  it('keeps no key of the removed pipeline', () => {
    const dead = /^(guards|fix|transition|board|tasks|exception|assign|followup)\./;
    expect(Object.keys(de).filter((k) => dead.test(k))).toEqual([]);
  });

  // TODO Stufe B: en catalog and the parity spec (every de key exists in en).
  it.todo('has an en entry for every de key');
});
