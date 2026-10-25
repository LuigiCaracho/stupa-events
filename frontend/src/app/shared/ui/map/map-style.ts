/**
 * Options for loading the static style files: MapLibre rejects a relative `sprite`, and the files do not know the
 * origin, so the sprite URL is made absolute against the page origin when the style arrives.
 */
import type { StyleSpecification } from 'maplibre-gl';

export const absoluteSprite = (
  _previous: StyleSpecification | undefined,
  next: StyleSpecification,
): StyleSpecification =>
  typeof next.sprite === 'string'
    ? { ...next, sprite: new URL(next.sprite, window.location.origin).href }
    : next;

export const STYLE_OPTIONS = { diff: false, transformStyle: absoluteSprite } as const;
