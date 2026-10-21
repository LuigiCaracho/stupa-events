import { SLUG_PATTERN, slugify } from './slug';

describe('slugify', () => {
  it('spells out umlauts and drops edition marks of punctuation', () => {
    expect(slugify('Hüttencafé Größe!')).toBe('huettencafe-groesse');
    expect(slugify('  STUPA Movienight: Whiplash (OmU) ')).toBe('stupa-movienight-whiplash-omu');
  });

  it('gives an empty slug for a title without letters or digits', () => {
    expect(slugify('***')).toBe('');
  });

  it('cuts at 60 characters', () => {
    expect(slugify('a'.repeat(80))).toHaveLength(60);
  });

  it('matches the slug pattern only for clean slugs', () => {
    expect(SLUG_PATTERN.test('movienight')).toBe(true);
    expect(SLUG_PATTERN.test('movie-night-2')).toBe(true);
    expect(SLUG_PATTERN.test('Movie Night')).toBe(false);
    expect(SLUG_PATTERN.test('-x')).toBe(false);
  });
});
