/** Reads `ngsw-config.json` and matches paths against its patterns the way the worker does; for the PWA specs only. */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

export interface NgswConfig {
  navigationUrls: string[];
  assetGroups: { name: string; resources: { files?: string[]; urls?: string[] } }[];
  dataGroups: {
    name: string;
    urls: string[];
    cacheConfig: { strategy: string; maxAge: string; maxSize: number; timeout?: string };
  }[];
}

export function ngswConfig(): NgswConfig {
  const path = join(__dirname, '..', '..', 'ngsw-config.json');
  return JSON.parse(readFileSync(path, 'utf8')) as NgswConfig;
}

/** A small glob match for the patterns of ngsw-config: `**`, `*` and `(a|b)`. */
export function matches(pattern: string, path: string): boolean {
  const source = pattern
    .replace(/[.+^${}[\]\\]/g, '\\$&')
    .replace(/\*\*\//g, 'GLOBSTAR')
    .replace(/\*\*/g, '.*')
    .replace(/\*/g, '[^/]*')
    .replace(/GLOBSTAR/g, '(?:.*/)?');
  return new RegExp(`^${source}$`).test(path);
}
