/** The items of the palette and the pure functions that build and filter them (M5 contract 6.3). */
import type { TranslationKey } from '@core/i18n/translations';

export type PaletteGroupKey = 'events' | 'formats' | 'actions' | 'nav';

export interface PaletteItem {
  id: string;
  group: PaletteGroupKey;
  label: string;
  hint?: string;
  run: () => void;
}

export interface PaletteGroup {
  key: PaletteGroupKey;
  heading: TranslationKey;
  items: PaletteItem[];
}

export const GROUP_HEADING: Record<PaletteGroupKey, TranslationKey> = {
  events: 'palette.group.events',
  formats: 'palette.group.formats',
  actions: 'palette.group.actions',
  nav: 'palette.group.nav',
};

const ORDER: readonly PaletteGroupKey[] = ['events', 'formats', 'actions', 'nav'];

/** Case-insensitive substring filter of a local item; an empty query keeps everything. */
export function matches(item: PaletteItem, query: string): boolean {
  const q = query.trim().toLowerCase();
  return q === '' || item.label.toLowerCase().includes(q);
}

/** The non-empty groups in their fixed order. */
export function toGroups(items: readonly PaletteItem[]): PaletteGroup[] {
  return ORDER.map((key) => ({
    key,
    heading: GROUP_HEADING[key],
    items: items.filter((i) => i.group === key),
  })).filter((g) => g.items.length > 0);
}

/** The dossier id of a URL such as `/dossiers/<id>/nachbereitung`, or `null` outside a dossier. */
export function dossierIdOf(url: string): string | null {
  const m = /^\/dossiers\/([^/?#]+)/.exec(url);
  return m && m[1] !== 'neu' ? m[1] : null;
}
