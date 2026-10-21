/** Groups the template hits by format for the list of I06: the client does this (M5 contract 13.1.8), the order of the server stays inside a group. */
import type { TemplateCard } from '../../archive/model/archive.models';

export interface TemplateGroup {
  key: string;
  title: string | null;
  items: TemplateCard[];
}

export function groupByFormat(cards: readonly TemplateCard[]): TemplateGroup[] {
  const groups = new Map<string, TemplateGroup>();
  for (const card of cards) {
    const key = card.format?.slug ?? '';
    const group = groups.get(key) ?? { key, title: card.format?.title ?? null, items: [] };
    group.items.push(card);
    groups.set(key, group);
  }
  const all = [...groups.values()];
  return [...all.filter((g) => g.key !== ''), ...all.filter((g) => g.key === '')];
}
