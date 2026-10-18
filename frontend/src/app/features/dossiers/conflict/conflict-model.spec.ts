import { makeEvent } from '../../../../testing/event-fixtures';
import { chosenFields, conflictRows, formatValue, serverDiff } from './conflict-model';

describe('conflict model', () => {
  const base = { title: 'Movienight', summary: 'Alt', startsAt: '2026-11-05T18:00:00Z' };
  const current = makeEvent({ summary: 'Neu von jemand', title: 'Movienight' });

  it('marks a field contested when both sides changed it differently', () => {
    const rows = conflictRows({ summary: 'Von mir', title: 'Filmabend' }, current, base);
    const summary = rows.find((r) => r.field === 'summary');
    const title = rows.find((r) => r.field === 'title');
    expect(summary).toMatchObject({
      base: 'Alt',
      mine: 'Von mir',
      theirs: 'Neu von jemand',
      contested: true,
    });
    expect(title?.contested).toBe(false);
  });

  it('also lists fields only the other side changed', () => {
    const rows = conflictRows({ title: 'Filmabend' }, current, base);
    expect(rows.map((r) => r.field).sort()).toEqual(['summary', 'title']);
    expect(serverDiff(rows).changed).toEqual([
      { key: 'summary', old: 'Alt', new: 'Neu von jemand' },
    ]);
  });

  it('works without a base: nothing is contested and no server diff exists', () => {
    const rows = conflictRows({ summary: 'Von mir' }, current, null);
    expect(rows).toHaveLength(1);
    expect(rows[0].contested).toBe(false);
    expect(serverDiff(rows).changed).toEqual([]);
  });

  it('keeps own values by default where nothing is contested and takes theirs where it is', () => {
    const mine = { summary: 'Von mir', title: 'Filmabend' };
    const rows = conflictRows(mine, current, base);
    expect(chosenFields(rows, {}, mine)).toEqual({ title: 'Filmabend' });
    expect(chosenFields(rows, { summary: 'mine' }, mine)).toEqual({
      summary: 'Von mir',
      title: 'Filmabend',
    });
  });

  it('does not resend a value that equals the current one', () => {
    const mine = { summary: 'Neu von jemand' };
    const rows = conflictRows(mine, current, base);
    expect(chosenFields(rows, { summary: 'mine' }, mine)).toEqual({});
  });

  it('formats times, ids and empty values for the dialog', () => {
    const look = {
      tzid: 'Europe/Berlin',
      venues: [{ id: 'v1', name: 'Kinosaal' }],
      categories: [{ id: 'c1', name: 'Kino' }],
      empty: '(leer)',
    };
    expect(formatValue('startsAt', '2026-11-05T18:00:00Z', look)).toContain('19:00');
    expect(formatValue('venueId', 'v1', look)).toBe('Kinosaal');
    expect(formatValue('venueId', 'zz', look)).toBe('zz');
    expect(formatValue('primaryCategoryId', 'c1', look)).toBe('Kino');
    expect(formatValue('summary', null, look)).toBe('(leer)');
    expect(formatValue('title', 'X', look)).toBe('X');
  });
});
