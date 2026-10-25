import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { MapComponent } from './map.component';
import { MapLoaderService } from './map-loader.service';
import type { GeoCollection, MapMode } from './map.models';

type Handler = (event?: unknown) => void;

class FakeMap {
  static last: FakeMap;
  handlers: Record<string, Handler[]> = {};
  layers = new Set<string>();
  sources = new Map<string, unknown>();
  styles: string[] = [];
  constructor(public options: object) {
    FakeMap.last = this;
  }
  on(name: string, a: string | Handler, b?: Handler): void {
    const key = typeof a === 'string' ? `${name}:${a}` : name;
    (this.handlers[key] ??= []).push((b ?? a) as Handler);
  }
  fire(name: string, event?: unknown): void {
    (this.handlers[name] ?? []).forEach((h) => h(event));
  }
  addControl = jest.fn();
  addSource = (id: string, spec: unknown) => this.sources.set(id, spec);
  addLayer = (layer: { id: string }) => this.layers.add(layer.id);
  getLayer = (id: string) => (this.layers.has(id) ? {} : undefined);
  getSource = (id: string) => (this.sources.has(id) ? { setData: jest.fn() } : undefined);
  removeLayer = (id: string) => this.layers.delete(id);
  removeSource = (id: string) => this.sources.delete(id);
  setFilter = jest.fn();
  setStyle = (url: string) => this.styles.push(url);
  setFeatureState = jest.fn();
  getCanvas = () => document.createElement('canvas');
  getZoom = () => 5.04;
  queryRenderedFeatures = () => [{}, {}];
  fitBounds = jest.fn();
  easeTo = jest.fn();
  flyTo = jest.fn();
  remove = jest.fn();
}

const fakeLib = {
  Map: FakeMap,
  NavigationControl: class {},
  AttributionControl: class {},
  Marker: class {
    on(): void {}
    setLngLat() {
      return this;
    }
    addTo() {
      return this;
    }
    remove(): void {}
  },
  Popup: class {},
};

@Component({
  standalone: true,
  imports: [MapComponent],
  template: `<app-map [mode]="mode()" [collection]="data()" (mapError)="errors = errors + 1" />`,
})
class Host {
  mode = signal<MapMode>('events');
  data = signal<GeoCollection>({
    type: 'FeatureCollection',
    features: [
      { type: 'Feature', geometry: { type: 'Point', coordinates: [9.2, 48.5] }, properties: {} },
    ],
  });
  errors = 0;
}

const flush = () => new Promise((r) => setTimeout(r));

async function mount(load: () => Promise<unknown>) {
  TestBed.configureTestingModule({
    imports: [Host],
    providers: [{ provide: MapLoaderService, useValue: { load } }],
  });
  const fixture = TestBed.createComponent(Host);
  fixture.detectChanges();
  await flush();
  fixture.detectChanges();
  return fixture;
}

describe('MapComponent', () => {
  it('reaches ready on style load and exposes the test seam', async () => {
    const fixture = await mount(() => Promise.resolve(fakeLib));
    const host = fixture.nativeElement.querySelector('app-map') as HTMLElement;
    expect(host.dataset['mapState']).toBe('loading');
    FakeMap.last.fire('style.load');
    FakeMap.last.fire('idle');
    fixture.detectChanges();
    expect(host.dataset['mapState']).toBe('ready');
    expect(host.dataset['featureCount']).toBe('1');
    expect(host.dataset['clusterCount']).toBe('2');
    expect(host.dataset['zoom']).toBe('5');
    expect(FakeMap.last.layers.has('ev-clusters')).toBe(true);
  });

  it('starts with the style of the resolved theme', async () => {
    await mount(() => Promise.resolve(fakeLib));
    expect(FakeMap.last.styles[0]).toMatch(/^\/map-style\/style-(light|dark)\.json$/);
  });

  it('flags an error when the library does not load', async () => {
    const fixture = await mount(() => Promise.reject(new Error('webgl')));
    const host = fixture.nativeElement.querySelector('app-map') as HTMLElement;
    expect(host.dataset['mapState']).toBe('error');
    expect(fixture.componentInstance.errors).toBe(1);
    expect(host.textContent).toContain('Die Karte konnte nicht geladen werden');
  });

  it('flags an error when the style cannot be fetched before it loaded', async () => {
    const fixture = await mount(() => Promise.resolve(fakeLib));
    FakeMap.last.fire('error');
    fixture.detectChanges();
    expect(
      (fixture.nativeElement.querySelector('app-map') as HTMLElement).dataset['mapState'],
    ).toBe('error');
  });

  it('ignores tile and glyph errors after the style loaded', async () => {
    const fixture = await mount(() => Promise.resolve(fakeLib));
    FakeMap.last.fire('style.load');
    FakeMap.last.fire('error');
    fixture.detectChanges();
    expect(
      (fixture.nativeElement.querySelector('app-map') as HTMLElement).dataset['mapState'],
    ).toBe('ready');
  });
});
