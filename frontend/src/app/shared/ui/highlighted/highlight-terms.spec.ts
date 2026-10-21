import { highlightTerms } from './highlight-terms';

describe('highlightTerms', () => {
  it('marks every word of the query, ignoring case', () => {
    expect(highlightTerms('Movienight: Whiplash', 'movie whip')).toEqual([
      { text: 'Movie', hit: true },
      { text: 'night: ', hit: false },
      { text: 'Whip', hit: true },
      { text: 'lash', hit: false },
    ]);
  });

  it('returns the text unmarked for an empty or one-letter query', () => {
    expect(highlightTerms('Kino', '')).toEqual([{ text: 'Kino', hit: false }]);
    expect(highlightTerms('Kino', 'k')).toEqual([{ text: 'Kino', hit: false }]);
  });

  it('treats regular-expression characters as text', () => {
    expect(highlightTerms('a (b) c', '(b)')).toEqual([
      { text: 'a ', hit: false },
      { text: '(b)', hit: true },
      { text: ' c', hit: false },
    ]);
  });

  it('strips quotes and a leading minus of the search syntax', () => {
    expect(highlightTerms('Kinoabend', '"kino"')).toEqual([
      { text: 'Kino', hit: true },
      { text: 'abend', hit: false },
    ]);
  });

  it('marks a title word that sits inside a compound of the query', () => {
    expect(highlightTerms('Sitzung FSI', 'Fachschaftssitzung')).toEqual([
      { text: 'Sitzung', hit: true },
      { text: ' FSI', hit: false },
    ]);
    expect(highlightTerms('Sommerfest der Fachschaft', 'Fachschaftssitzung')).toEqual([
      { text: 'Sommerfest der ', hit: false },
      { text: 'Fachschaft', hit: true },
    ]);
  });

  it('ignores short title words and folds accents when it looks for compounds', () => {
    expect(highlightTerms('Bar Präsidium', 'Barpraesidiumabend')).toEqual([
      { text: 'Bar Präsidium', hit: false },
    ]);
    expect(highlightTerms('Café Hütte', 'Huttenabend')).toEqual([
      { text: 'Café ', hit: false },
      { text: 'Hütte', hit: true },
    ]);
    expect(highlightTerms('Hüttencafé', 'grosshuttencafe')).toEqual([
      { text: 'Hüttencafé', hit: true },
    ]);
  });
});
