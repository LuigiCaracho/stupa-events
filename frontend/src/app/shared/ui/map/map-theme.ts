/** Reads the map colours from the ui-kit design tokens, so pins, clusters and polygons follow the theme. */
import type { MapColors } from './map.models';

const token = (style: CSSStyleDeclaration, name: string, fallback: string): string =>
  style.getPropertyValue(name).trim() || fallback;

/** Colours for the overlays of the current theme; the hex fallbacks apply when a token is missing (tests, SSR). */
export function readMapColors(el: Element): MapColors {
  const style = getComputedStyle(el);
  const accent = token(style, '--color-primary', '#3c6a4d');
  return {
    accent,
    onAccent: token(style, '--color-on-primary', '#ffffff'),
    text: token(style, '--color-text', '#191c1a'),
    surface: token(style, '--color-surface', '#ffffff'),
    border: token(style, '--color-border-strong', '#9aa09b'),
    neutral: token(style, '--color-surface-sunken', '#e9ece8'),
    levels: [
      token(style, '--color-accent-container', '#cfe5d6'),
      token(style, '--color-accent', '#6aa583'),
      accent,
    ],
  };
}
