#!/usr/bin/env node
/**
 * Build check for the map (C contract 2.5 and 2.6): MapLibre and the PMTiles reader stay out of `index.html` and the
 * initial bundle (the files `index.html` loads), the library ships as a static file under `/map/`, and the one caller
 * of `navigator.geolocation` is the near-me chunk (the zone.js polyfill only wraps the API and may name it).
 * `MAP_LIB_VERSION` (the cache buster of the loader) must equal the installed maplibre-gl version.
 * Run after `npm run build`; exits 1 with the findings.
 */
const { readFileSync, readdirSync, existsSync } = require('node:fs');
const { join } = require('node:path');

const dist = process.argv[2] ?? join(__dirname, '..', 'dist', 'stupa-events', 'browser');
const html = readFileSync(join(dist, 'index.html'), 'utf8');
const initial = new Set(
  [...html.matchAll(/(?:src|href)="([^"]+\.js)"/g)].map((m) => m[1].replace(/^\//, '')),
);
const findings = [];

const pinned = /MAP_LIB_VERSION = '([^']+)'/.exec(
  readFileSync(join(__dirname, '..', 'src', 'app', 'shared', 'ui', 'map', 'map.models.ts'), 'utf8'),
)?.[1];
const installed = require('maplibre-gl/package.json').version;
if (pinned !== installed) {
  findings.push(`MAP_LIB_VERSION ${pinned} differs from the installed maplibre-gl ${installed}`);
}

for (const file of initial) {
  const code = readFileSync(join(dist, file), 'utf8');
  if (/maplibre|pmtiles/i.test(code)) findings.push(`${file} (initial) mentions maplibre or pmtiles`);
}
if (/maplibre/i.test(html)) findings.push('index.html mentions maplibre');

for (const file of ['maplibre-gl.mjs', 'maplibre-gl-worker.mjs', 'maplibre-gl.css']) {
  if (!existsSync(join(dist, 'map', file))) findings.push(`map/${file} is missing from the build`);
}

const chunks = readdirSync(dist).filter((f) => f.endsWith('.js'));
const geolocation = chunks.filter((f) => /geolocation/.test(readFileSync(join(dist, f), 'utf8')));
const allowed = (f) =>
  f.startsWith('polyfills') || /getCurrentPosition/.test(readFileSync(join(dist, f), 'utf8'));
for (const f of geolocation.filter((f) => !allowed(f))) findings.push(`${f} uses geolocation`);
if (geolocation.some((f) => initial.has(f) && !f.startsWith('polyfills'))) {
  findings.push('geolocation in the initial bundle');
}

if (findings.length) {
  console.error(findings.join('\n'));
  process.exit(1);
}
console.log('map isolation ok');
