/**
 * `app-map`: the one map component (PLAN 8.8). Three modes share the loader and the style switch: `events` clusters
 * the event points, `campus` fills the building polygons by their event count, `pick` holds one draggable pin. The
 * host element carries `data-map-state`, `data-feature-count`, `data-cluster-count` and `data-zoom` as a test seam.
 * Nothing leaves the origin: style, glyphs, sprites and tiles are same-origin files.
 */
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  effect,
  inject,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { ThemeService } from '@core/theme/theme.service';
import type { GeoJSONSource, Map as MlMap, MapGeoJSONFeature, Marker } from 'maplibre-gl';
import { collectionBounds } from './map-bounds';
import {
  CAMPUS_SOURCE,
  CLUSTER_MAX_ZOOM,
  EVENTS_SOURCE,
  ME_SOURCE,
  campusLayers,
  campusSource,
  eventsLayers,
  eventsSource,
  meLayer,
  meSource,
  selectionFilter,
} from './map-layers';
import { MapLoaderService, type MapLibre } from './map-loader.service';
import { STYLE_OPTIONS } from './map-style';
import { readMapColors } from './map-theme';
import {
  EMPTY_COLLECTION,
  type GeoCollection,
  type MapMode,
  type MapPin,
  type MapState,
  REUTLINGEN_CENTER,
  STYLE_BASE,
} from './map.models';

const OVERLAY_LAYERS = [
  'ev-clusters',
  'ev-cluster-count',
  'ev-points',
  'ev-selected',
  'ev-campus-fill',
  'ev-campus-outline',
  'ev-campus-label',
  'ev-me',
];
const OVERLAY_SOURCES = [EVENTS_SOURCE, CAMPUS_SOURCE, ME_SOURCE];

const pointCollection = (pin: MapPin | null): GeoCollection => ({
  type: 'FeatureCollection',
  features: pin
    ? [
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [pin.lon, pin.lat] },
          properties: {},
        },
      ]
    : [],
});

const round6 = (n: number): number => Math.round(n * 1e6) / 1e6;

@Component({
  selector: 'app-map',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe],
  host: {
    '[attr.data-map-state]': 'state()',
    '[attr.data-feature-count]': 'featureCount()',
    '[attr.data-cluster-count]': 'clusterCount()',
    '[attr.data-zoom]': 'zoom()',
  },
  templateUrl: './map.component.html',
  styleUrl: './map.component.scss',
})
export class MapComponent {
  private readonly loader = inject(MapLoaderService);
  private readonly theme = inject(ThemeService);
  private readonly i18n = inject(I18nService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly canvas = viewChild.required<ElementRef<HTMLElement>>('canvas');

  readonly mode = input<MapMode>('events');
  readonly collection = input<GeoCollection>(EMPTY_COLLECTION);
  readonly selected = input<string | null>(null);
  readonly pin = input<MapPin | null>(null);
  readonly userPosition = input<MapPin | null>(null);
  readonly ariaLabel = input<string | null>(null);
  readonly height = input('28rem');
  readonly skipTarget = input<string | null>(null);

  readonly featureSelect = output<string>();
  readonly featureOpen = output<string>();
  readonly clusterSelect = output<string[]>();
  readonly pinChange = output<MapPin>();
  readonly mapError = output<void>();

  protected readonly state = signal<MapState>('loading');
  protected readonly featureCount = signal(0);
  protected readonly clusterCount = signal(0);
  protected readonly zoom = signal(0);

  private lib: MapLibre | null = null;
  private map: MlMap | null = null;
  private marker: Marker | null = null;
  private fitted = false;
  private viewKept = false;
  private styleUrl = '';

  constructor() {
    afterNextRender(() => void this.start());
    this.destroyRef.onDestroy(() => this.map?.remove());
    effect(() => this.onTheme(this.theme.resolved()));
    effect(() => this.onData(this.collection()));
    effect(() => this.onSelected(this.selected()));
    effect(() => this.onUser(this.userPosition()));
    effect(() => this.onPin(this.pin()));
  }

  protected label(): string {
    const fallback = {
      events: 'map.label.events',
      campus: 'map.label.campus',
      pick: 'map.label.pick',
    } as const;
    return this.ariaLabel() ?? this.i18n.translate(fallback[this.mode()]);
  }

  private async start(): Promise<void> {
    try {
      this.lib = await this.loader.load();
      this.styleUrl = this.styleFor(this.theme.resolved());
      const map = new this.lib.Map({
        container: this.canvas().nativeElement,
        center: [...REUTLINGEN_CENTER],
        zoom: 11,
        maxZoom: 18,
        attributionControl: false,
        locale: this.controlLabels(),
        pitchWithRotate: false,
        dragRotate: false,
      });
      this.map = map;
      map.setStyle(this.styleUrl, STYLE_OPTIONS);
      this.addControls(map);
      map.on('style.load', () => this.onStyleLoad());
      map.on('movestart', (event: { originalEvent?: unknown }) => {
        if (event.originalEvent) this.viewKept = true;
      });
      map.on('idle', () => this.onIdle());
      map.on('error', () => this.state() === 'loading' && this.fail());
      if (this.mode() === 'pick') this.attachPick(map);
    } catch {
      this.fail();
    }
  }

  private fail(): void {
    this.state.set('error');
    this.mapError.emit();
  }

  private styleFor(theme: 'light' | 'dark'): string {
    return `${STYLE_BASE}/style-${theme}.json`;
  }

  private controlLabels(): Record<string, string> {
    const t = (key: Parameters<I18nService['translate']>[0]): string => this.i18n.translate(key);
    return {
      'NavigationControl.ZoomIn': t('map.zoomIn'),
      'NavigationControl.ZoomOut': t('map.zoomOut'),
      'NavigationControl.ResetBearing': t('map.resetBearing'),
      'AttributionControl.ToggleAttribution': t('map.attributionToggle'),
    };
  }

  private addControls(map: MlMap): void {
    const lib = this.lib as MapLibre;
    map.addControl(new lib.NavigationControl({ showCompass: false }), 'top-right');
    map.addControl(new lib.AttributionControl({ compact: true }), 'bottom-right');
  }

  private reducedMotion(): boolean {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  private onTheme(theme: 'light' | 'dark'): void {
    const url = this.styleFor(theme);
    if (!this.map || url === this.styleUrl) return;
    this.styleUrl = url;
    this.map.setStyle(url, STYLE_OPTIONS);
  }

  private onStyleLoad(): void {
    this.addOverlays();
    this.state.set('ready');
    if (!this.fitted) this.fitToData();
  }

  private addOverlays(): void {
    const map = this.map;
    if (!map) return;
    const colors = readMapColors(this.canvas().nativeElement);
    const mode = this.mode();
    OVERLAY_LAYERS.filter((id) => map.getLayer(id)).forEach((id) => map.removeLayer(id));
    OVERLAY_SOURCES.filter((id) => map.getSource(id)).forEach((id) => map.removeSource(id));
    if (mode === 'events') {
      map.addSource(EVENTS_SOURCE, eventsSource(this.collection()));
      eventsLayers(colors).forEach((layer) => map.addLayer(layer));
      map.addSource(ME_SOURCE, meSource(pointCollection(this.userPosition())));
      map.addLayer(meLayer(colors));
      this.bindEventClicks(map);
      map.setFilter('ev-selected', selectionFilter(this.selected()));
    } else if (mode === 'campus') {
      map.addSource(CAMPUS_SOURCE, campusSource(this.collection()));
      campusLayers(colors).forEach((layer) => map.addLayer(layer));
      this.bindCampusClicks(map);
      this.applySelectedCampus();
    }
  }

  private bindEventClicks(map: MlMap): void {
    if (this.clicksBound) return;
    this.clicksBound = true;
    map.on('click', 'ev-clusters', (e) => void this.onClusterClick(e.features?.[0]));
    map.on('click', 'ev-points', (e) => this.onPointClick(e.features?.[0]));
    for (const id of ['ev-clusters', 'ev-points']) {
      map.on('mouseenter', id, () => (map.getCanvas().style.cursor = 'pointer'));
      map.on('mouseleave', id, () => (map.getCanvas().style.cursor = ''));
    }
  }

  private clicksBound = false;

  private bindCampusClicks(map: MlMap): void {
    if (this.clicksBound) return;
    this.clicksBound = true;
    map.on('click', 'ev-campus-fill', (e) => {
      const no = e.features?.[0]?.properties?.['buildingNo'];
      if (typeof no === 'string') this.featureSelect.emit(no);
    });
    map.on('mouseenter', 'ev-campus-fill', () => (map.getCanvas().style.cursor = 'pointer'));
    map.on('mouseleave', 'ev-campus-fill', () => (map.getCanvas().style.cursor = ''));
  }

  private async onClusterClick(feature: MapGeoJSONFeature | undefined): Promise<void> {
    const map = this.map;
    const source = map?.getSource(EVENTS_SOURCE) as GeoJSONSource | undefined;
    const id = feature?.properties?.['cluster_id'];
    if (!map || !source || typeof id !== 'number' || feature?.geometry.type !== 'Point') return;
    const target = await source.getClusterExpansionZoom(id);
    if (target > CLUSTER_MAX_ZOOM) {
      const leaves = await source.getClusterLeaves(id, 1000, 0);
      const slugs = leaves.map((l) => l.properties?.['slug']).filter((s) => typeof s === 'string');
      this.clusterSelect.emit(slugs as string[]);
      return;
    }
    const [lon, lat] = feature.geometry.coordinates;
    map.easeTo({ center: [lon, lat], zoom: target, animate: !this.reducedMotion() });
  }

  private onPointClick(feature: MapGeoJSONFeature | undefined): void {
    const map = this.map;
    const lib = this.lib;
    const slug = feature?.properties?.['slug'];
    if (!map || !lib || typeof slug !== 'string' || feature?.geometry.type !== 'Point') return;
    this.featureSelect.emit(slug);
    const body = document.createElement('div');
    const title = document.createElement('strong');
    title.textContent = String(feature.properties['title'] ?? '');
    const link = document.createElement('a');
    link.href = `/e/${encodeURIComponent(slug)}`;
    link.textContent = this.i18n.translate('map.popupOpen');
    link.addEventListener('click', (event) => {
      event.preventDefault();
      this.featureOpen.emit(slug);
    });
    body.append(title, document.createElement('br'), link);
    const [lon, lat] = feature.geometry.coordinates;
    new lib.Popup({ offset: 14, closeButton: true })
      .setLngLat([lon, lat])
      .setDOMContent(body)
      .addTo(map);
  }

  private attachPick(map: MlMap): void {
    const lib = this.lib as MapLibre;
    map.on('click', (e) => this.place({ lat: e.lngLat.lat, lon: e.lngLat.lng }, true));
    this.marker = new lib.Marker({
      draggable: true,
      color: readMapColors(this.canvas().nativeElement).accent,
    });
    this.marker.on('dragend', () => {
      const at = (this.marker as Marker).getLngLat();
      this.pinChange.emit({ lat: round6(at.lat), lon: round6(at.lng) });
    });
    this.onPin(this.pin());
  }

  private place(pin: MapPin, emit: boolean): void {
    const map = this.map;
    const marker = this.marker;
    if (!map || !marker) return;
    marker.setLngLat([pin.lon, pin.lat]).addTo(map);
    if (emit) this.pinChange.emit({ lat: round6(pin.lat), lon: round6(pin.lon) });
  }

  private onPin(pin: MapPin | null): void {
    if (this.mode() !== 'pick' || !this.map || !this.marker) return;
    if (!pin) {
      this.marker.remove();
      return;
    }
    this.place(pin, false);
    this.map.easeTo({ center: [pin.lon, pin.lat], animate: !this.reducedMotion() });
  }

  private onData(data: GeoCollection): void {
    this.featureCount.set(data.features.length);
    const map = this.map;
    if (!map || this.state() !== 'ready') return;
    const id = this.mode() === 'campus' ? CAMPUS_SOURCE : EVENTS_SOURCE;
    (map.getSource(id) as GeoJSONSource | undefined)?.setData(data as never);
    this.fitToData();
  }

  private fitToData(): void {
    const map = this.map;
    const mode = this.mode();
    if (!map || mode === 'pick') return;
    const bounds = collectionBounds(this.collection());
    if (!bounds || (this.fitted && mode === 'campus') || this.viewKept) return;
    this.fitted = true;
    const [w, s, e, n] = bounds;
    const single = w === e && s === n;
    if (single) map.easeTo({ center: [w, s], zoom: 14, animate: false });
    else
      map.fitBounds(
        [
          [w, s],
          [e, n],
        ],
        { padding: 48, maxZoom: 15, animate: false },
      );
  }

  private onSelected(selected: string | null): void {
    const map = this.map;
    if (!map || this.state() !== 'ready') return;
    if (this.mode() === 'events' && map.getLayer('ev-selected')) {
      map.setFilter('ev-selected', selectionFilter(selected));
    } else if (this.mode() === 'campus') {
      this.applySelectedCampus();
    }
  }

  private selectedCampus: string | null = null;

  private applySelectedCampus(): void {
    const map = this.map;
    if (!map || !map.getSource(CAMPUS_SOURCE)) return;
    if (this.selectedCampus) {
      map.setFeatureState({ source: CAMPUS_SOURCE, id: this.selectedCampus }, { selected: false });
    }
    this.selectedCampus = this.selected();
    if (this.selectedCampus) {
      map.setFeatureState({ source: CAMPUS_SOURCE, id: this.selectedCampus }, { selected: true });
    }
  }

  private onUser(position: MapPin | null): void {
    const map = this.map;
    if (!map || this.state() !== 'ready' || this.mode() !== 'events') return;
    (map.getSource(ME_SOURCE) as GeoJSONSource | undefined)?.setData(
      pointCollection(position) as never,
    );
    if (position) {
      this.viewKept = true;
      map.flyTo({ center: [position.lon, position.lat], zoom: 13, animate: !this.reducedMotion() });
    }
  }

  private onIdle(): void {
    const map = this.map;
    if (!map) return;
    this.zoom.set(Math.round(map.getZoom() * 10) / 10);
    this.clusterCount.set(
      map.getLayer('ev-clusters')
        ? map.queryRenderedFeatures({ layers: ['ev-clusters'] }).length
        : 0,
    );
  }
}
