/** Pure helpers of the category table: depth-first order with indentation depth, and the descendants of a node. */
import type { AdminCategory } from '../../api/admin.models';

const byParent = (categories: readonly AdminCategory[], parentOf: (c: AdminCategory) => string) =>
  categories.reduce(
    (groups, c) => groups.set(parentOf(c), [...(groups.get(parentOf(c)) ?? []), c]),
    new Map<string, AdminCategory[]>(),
  );

export type CategoryRow = AdminCategory & { depth: number };

/**
 * Orders categories parent-first, children right after their parent.
 *
 * Args:
 *   categories: Flat list in server order (kind, sort, name).
 *
 * Returns:
 *   The same categories depth-first with `depth`; a category whose parent is missing
 *   counts as a root, so nothing disappears.
 */
export function categoryRows(categories: readonly AdminCategory[]): CategoryRow[] {
  const ids = new Set(categories.map((c) => c.id));
  const children = byParent(categories, (c) => (c.parentId && ids.has(c.parentId) ? c.parentId : ''));
  const walk = (parent: string, depth: number): CategoryRow[] =>
    (children.get(parent) ?? []).flatMap((c) => [{ ...c, depth }, ...walk(c.id, depth + 1)]);
  return walk('', 0);
}

/**
 * Collects a category and all its descendants.
 *
 * Args:
 *   categories: Flat list.
 *   rootId: Id of the category.
 *
 * Returns:
 *   Ids of `rootId` and everything below it; the parent select must not offer these.
 */
export function descendantIds(categories: readonly AdminCategory[], rootId: string): Set<string> {
  const children = byParent(categories, (c) => c.parentId ?? '');
  const collect = (id: string): string[] => [id, ...(children.get(id) ?? []).flatMap((c) => collect(c.id))];
  return new Set(collect(rootId));
}
