import type { AdminCategory } from '../../api/admin.models';
import { categoryRows, descendantIds } from './category-tree';

const cat = (id: string, parentId: string | null = null): AdminCategory => ({
  id,
  slug: id,
  name: id,
  kind: 'fachschaft',
  parentId,
  short: null,
  colorToken: null,
  requiredProfile: 'generic',
  legacyWpId: null,
  sort: 0,
  active: true,
  createdAt: '',
  updatedAt: '',
});

describe('category tree', () => {
  const flat = [cat('a'), cat('b', 'a'), cat('c', 'b'), cat('d'), cat('e', 'a')];

  it('orders children right after their parent with the depth', () => {
    expect(categoryRows(flat).map((r) => [r.id, r.depth])).toEqual([
      ['a', 0],
      ['b', 1],
      ['c', 2],
      ['e', 1],
      ['d', 0],
    ]);
  });

  it('treats a category with an unknown parent as a root', () => {
    expect(categoryRows([cat('x', 'gone')]).map((r) => [r.id, r.depth])).toEqual([['x', 0]]);
  });

  it('collects a node with all descendants', () => {
    expect([...descendantIds(flat, 'b')].sort()).toEqual(['b', 'c']);
    expect([...descendantIds(flat, 'a')].sort()).toEqual(['a', 'b', 'c', 'e']);
  });
});
