import type { TemplateCard } from '../../archive/model/archive.models';
import { groupByFormat } from './template-groups';

const card = (id: string, format: string | null): TemplateCard => ({
  id,
  title: id,
  startsAt: '2026-01-01T10:00:00Z',
  allDay: false,
  state: 'archived',
  organization: { slug: 'fsi', name: 'Fachschaft Informatik', short: 'FSI' },
  format: format ? { slug: format, title: format.toUpperCase() } : null,
  categories: [],
  attendance: null,
  howtoVerifiedAt: null,
  howtoUnverified: false,
  hasHowto: false,
  foreign: false,
  sharedDocuments: 0,
  checklistItems: 0,
});

describe('groupByFormat', () => {
  it('groups by format in the order of first appearance and puts "ohne Format" last', () => {
    const groups = groupByFormat([card('a', null), card('b', 'movie'), card('c', 'party'), card('d', 'movie')]);
    expect(groups.map((g) => [g.key, g.items.map((i) => i.id)])).toEqual([
      ['movie', ['b', 'd']],
      ['party', ['c']],
      ['', ['a']],
    ]);
    expect(groups[0].title).toBe('MOVIE');
    expect(groups[2].title).toBeNull();
  });

  it('gives no group for no cards', () => {
    expect(groupByFormat([])).toEqual([]);
  });
});
