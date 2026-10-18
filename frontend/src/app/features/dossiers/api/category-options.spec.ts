import { categoryOptions } from './category-options';
import type { CategoryRef } from './event.models';

const node = (id: string, children: CategoryRef[] = []): CategoryRef => ({
  id,
  slug: id,
  name: id.toUpperCase(),
  kind: 'fachschaft',
  children,
});

describe('categoryOptions', () => {
  it('lists parents before children and indents by depth', () => {
    const tree = [node('a', [node('b', [node('c')])]), node('d')];
    expect(categoryOptions(tree)).toEqual([
      { value: 'a', label: 'A' },
      { value: 'b', label: ' B' },
      { value: 'c', label: '  C' },
      { value: 'd', label: 'D' },
    ]);
  });

  it('keeps a flat list flat', () => {
    expect(categoryOptions([{ id: 'x', slug: 'x', name: 'X', kind: 'format' }])).toEqual([
      { value: 'x', label: 'X' },
    ]);
  });
});
