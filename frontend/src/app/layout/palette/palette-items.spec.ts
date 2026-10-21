import { dossierIdOf, matches, toGroups, type PaletteItem } from './palette-items';

const item = (group: PaletteItem['group'], label: string): PaletteItem => ({
  id: `${group}:${label}`,
  group,
  label,
  run: () => undefined,
});

describe('palette items', () => {
  it('filters by a case-insensitive part of the label', () => {
    expect(matches(item('nav', 'Archiv'), 'ARCH')).toBe(true);
    expect(matches(item('nav', 'Archiv'), 'kal')).toBe(false);
    expect(matches(item('nav', 'Archiv'), '  ')).toBe(true);
  });

  it('orders the groups and drops the empty ones', () => {
    const groups = toGroups([item('nav', 'A'), item('events', 'B'), item('nav', 'C')]);
    expect(groups.map((g) => [g.key, g.items.length])).toEqual([
      ['events', 1],
      ['nav', 2],
    ]);
  });

  it('finds the dossier of a URL', () => {
    expect(dossierIdOf('/dossiers/abc-1')).toBe('abc-1');
    expect(dossierIdOf('/dossiers/abc-1/nachbereitung?x=1')).toBe('abc-1');
    expect(dossierIdOf('/dossiers/neu')).toBeNull();
    expect(dossierIdOf('/dossiers')).toBeNull();
    expect(dossierIdOf('/archiv/abc')).toBeNull();
  });
});
