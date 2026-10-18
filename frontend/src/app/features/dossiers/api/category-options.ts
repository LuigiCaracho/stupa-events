/** Select options of the category tree: depth-first, children indented by an em space per level. */
import type { SelectFieldOption } from '@shared/ui/select/select.component';
import type { CategoryRef } from './event.models';

const INDENT = ' ';

/**
 * Flattens a category tree (or a flat list) into select options.
 *
 * Args:
 *   nodes: Roots with optional `children`.
 *   depth: Current indentation level, for the recursion.
 *
 * Returns:
 *   One option per category, parents before their children, indented by depth.
 */
export function categoryOptions(nodes: readonly CategoryRef[], depth = 0): SelectFieldOption[] {
  return nodes.flatMap((c) => [
    { value: c.id, label: `${INDENT.repeat(depth)}${c.name}` },
    ...categoryOptions(c.children ?? [], depth + 1),
  ]);
}
