import { absoluteSprite } from './map-style';
import type { StyleSpecification } from 'maplibre-gl';

const style = (sprite?: string): StyleSpecification =>
  ({ version: 8, sources: {}, layers: [], ...(sprite ? { sprite } : {}) }) as StyleSpecification;

describe('absoluteSprite', () => {
  it('turns the relative sprite path into an absolute URL of the page origin', () => {
    const out = absoluteSprite(undefined, style('/map-style/sprites/v4/light'));
    expect(out.sprite).toBe(`${window.location.origin}/map-style/sprites/v4/light`);
  });

  it('leaves a style without sprite alone', () => {
    const input = style();
    expect(absoluteSprite(undefined, input)).toBe(input);
  });
});
