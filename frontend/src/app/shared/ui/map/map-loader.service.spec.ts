import { TestBed } from '@angular/core/testing';
import { MAP_MODULE_IMPORT, MapLoaderService } from './map-loader.service';

const fakeLib = () => ({ setWorkerUrl: jest.fn(), addProtocol: jest.fn() });

describe('MapLoaderService', () => {
  afterEach(() => document.head.querySelectorAll('link[data-map-css]').forEach((l) => l.remove()));

  const setup = (importer: jest.Mock) => {
    TestBed.configureTestingModule({
      providers: [{ provide: MAP_MODULE_IMPORT, useValue: importer }],
    });
    return TestBed.inject(MapLoaderService);
  };

  it('loads the library once and wires worker, protocol and stylesheet', async () => {
    const lib = fakeLib();
    const importer = jest.fn().mockResolvedValue(lib);
    const loader = setup(importer);
    const [a, b] = await Promise.all([loader.load(), loader.load()]);
    expect(a).toBe(b);
    expect(importer).toHaveBeenCalledTimes(1);
    expect(importer.mock.calls[0][0]).toBe('/map/maplibre-gl.mjs?v=6.13.0');
    expect(lib.setWorkerUrl).toHaveBeenCalledWith('/map/maplibre-gl-worker.mjs?v=6.13.0');
    expect(lib.addProtocol).toHaveBeenCalledWith('pmtiles', expect.any(Function));
    expect(document.querySelectorAll('link[data-map-css]')).toHaveLength(1);
  });

  it('can retry after a failed load', async () => {
    const importer = jest.fn().mockRejectedValueOnce(new Error('x')).mockResolvedValue(fakeLib());
    const loader = setup(importer);
    await expect(loader.load()).rejects.toThrow('x');
    await expect(loader.load()).resolves.toBeDefined();
  });
});
