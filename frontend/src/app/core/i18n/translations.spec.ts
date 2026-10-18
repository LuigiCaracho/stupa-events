/** Catalog sanity checks. */
import { de } from './translations';

describe('translations', () => {
  it('has no empty string', () => {
    expect(Object.entries(de).filter(([, v]) => v.trim() === '')).toEqual([]);
  });

  it('uses the Du-form and no Sie-form in the shell strings', () => {
    expect(Object.values(de).filter((v) => /\bSie\b/.test(v))).toEqual([]);
  });

  // TODO Stufe B: en catalog and the parity spec (every de key exists in en).
  it.todo('has an en entry for every de key');
});
