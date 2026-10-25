/**
 * Loads MapLibre once, on first use. The library is a static asset under `/map/` (copied by `angular.json`), not an
 * Angular chunk, so the service worker's `app` group does not prefetch its 1 MB for every first visit. The worker
 * file is same-origin, which MapLibre starts as a module worker without a `blob:` URL (CSP `worker-src 'self'`).
 * The PMTiles protocol runs on the main thread and sends `ngsw-bypass`, so the service worker never touches a tile.
 */
import { Injectable, InjectionToken, inject } from '@angular/core';
import { FetchSource, PMTiles, Protocol } from 'pmtiles';
import { MAP_ASSET_BASE, MAP_LIB_VERSION, TILE_BASE } from './map.models';

export type MapLibre = typeof import('maplibre-gl');

export const TILE_ARCHIVES = ['world', 'reutlingen'] as const;

export const MAP_MODULE_IMPORT = new InjectionToken<(url: string) => Promise<MapLibre>>(
  'MAP_MODULE_IMPORT',
  { factory: () => (url) => import(/* @vite-ignore */ url) as Promise<MapLibre> },
);

const asset = (file: string): string => `${MAP_ASSET_BASE}/${file}?v=${MAP_LIB_VERSION}`;

@Injectable({ providedIn: 'root' })
export class MapLoaderService {
  private readonly importer = inject(MAP_MODULE_IMPORT);
  private loading: Promise<MapLibre> | null = null;

  /** Resolves with the library; every caller shares the one load. A failed load can be retried. */
  load(): Promise<MapLibre> {
    this.loading ??= this.boot().catch((error: unknown) => {
      this.loading = null;
      throw error;
    });
    return this.loading;
  }

  private async boot(): Promise<MapLibre> {
    this.ensureStylesheet();
    const lib = await this.importer(asset('maplibre-gl.mjs'));
    lib.setWorkerUrl(asset('maplibre-gl-worker.mjs'));
    lib.addProtocol('pmtiles', this.protocol().tile);
    return lib;
  }

  private protocol(): Protocol {
    const protocol = new Protocol();
    const headers = new Headers({ 'ngsw-bypass': 'true' });
    for (const name of TILE_ARCHIVES) {
      protocol.add(new PMTiles(new FetchSource(`${TILE_BASE}/${name}.pmtiles`, headers)));
    }
    return protocol;
  }

  private ensureStylesheet(): void {
    if (document.querySelector('link[data-map-css]')) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = `${MAP_ASSET_BASE}/maplibre-gl.css?v=${MAP_LIB_VERSION}`;
    link.dataset['mapCss'] = '';
    document.head.appendChild(link);
  }
}
