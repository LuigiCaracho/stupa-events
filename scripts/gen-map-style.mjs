/**
 * Writes the committed base styles frontend/public/map-style/style-{light,dark}.json from
 * @protomaps/basemaps (BSD-3-Clause, frontend devDependency). Two PMTiles sources: `world` (zoom 0-5,
 * overzoomed above) and `region` (Reutlingen, zoom 0-15). World labels stop at zoom 7, region layers
 * start there, so no label is drawn twice. Pins, clusters and building fills are added by app-map at
 * runtime because they read the design tokens. Usage: node scripts/gen-map-style.mjs
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const outDir = join(root, 'frontend/public/map-style');
const { layers, namedFlavor } = await import(
  pathToFileURL(join(root, 'frontend/node_modules/@protomaps/basemaps/dist/esm/index.js')).href
);

const HANDOFF_ZOOM = 7;
const ATTRIBUTION = '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap</a>';

const vectorSource = (file, maxzoom) => ({
  type: 'vector',
  url: `pmtiles:///tiles/${file}.pmtiles`,
  maxzoom,
  attribution: ATTRIBUTION,
});

const worldLayers = (flavor) =>
  layers('world', flavor, { lang: 'de' }).map((layer) =>
    layer.type === 'symbol' ? { ...layer, maxzoom: Math.min(layer.maxzoom ?? HANDOFF_ZOOM, HANDOFF_ZOOM) } : layer,
  );

const regionLayers = (flavor) =>
  layers('region', flavor, { lang: 'de' })
    .filter((layer) => layer.type !== 'background')
    .map((layer) => ({
      ...layer,
      id: `region_${layer.id}`,
      minzoom: Math.max(layer.minzoom ?? 0, HANDOFF_ZOOM),
    }));

const style = (theme) => {
  const flavor = namedFlavor(theme);
  return {
    version: 8,
    name: `stupa-events-${theme}`,
    glyphs: '/map-style/fonts/{fontstack}/{range}.pbf',
    sprite: `/map-style/sprites/v4/${theme}`,
    sources: { world: vectorSource('world', 5), region: vectorSource('reutlingen', 15) },
    layers: [...worldLayers(flavor), ...regionLayers(flavor)],
  };
};

mkdirSync(outDir, { recursive: true });
for (const theme of ['light', 'dark']) {
  writeFileSync(join(outDir, `style-${theme}.json`), `${JSON.stringify(style(theme), null, 1)}\n`);
}
