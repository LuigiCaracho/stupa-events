/** Pure builders for the overlay sources and layers of `app-map`; the component only adds them to the map. */
import type { FilterSpecification, LayerSpecification, SourceSpecification } from 'maplibre-gl';
import type { GeoCollection, MapColors } from './map.models';

export const EVENTS_SOURCE = 'ev-events';
export const CAMPUS_SOURCE = 'ev-campus';
export const ME_SOURCE = 'ev-me';
export const CLUSTER_MAX_ZOOM = 14;
export const CLUSTER_RADIUS = 50;
export const GLYPH_FONT = 'Noto Sans Medium';
export const CAMPUS_STEPS = [1, 3, 6] as const;

export const eventsSource = (data: GeoCollection): SourceSpecification => ({
  type: 'geojson',
  data: data as never,
  cluster: true,
  clusterRadius: CLUSTER_RADIUS,
  clusterMaxZoom: CLUSTER_MAX_ZOOM,
});

export const campusSource = (data: GeoCollection): SourceSpecification => ({
  type: 'geojson',
  data: data as never,
  promoteId: 'buildingNo',
});

export const meSource = (data: GeoCollection): SourceSpecification => ({
  type: 'geojson',
  data: data as never,
});

export const NO_SELECTION: FilterSpecification = ['==', ['get', 'slug'], ''];

export const selectionFilter = (slug: string | null): FilterSpecification =>
  slug ? ['==', ['get', 'slug'], slug] : NO_SELECTION;

export function eventsLayers(c: MapColors): LayerSpecification[] {
  return [
    {
      id: 'ev-clusters',
      type: 'circle',
      source: EVENTS_SOURCE,
      filter: ['has', 'point_count'],
      paint: {
        'circle-color': c.accent,
        'circle-stroke-color': c.surface,
        'circle-stroke-width': 2,
        'circle-radius': ['step', ['get', 'point_count'], 16, 5, 20, 20, 26],
      },
    },
    {
      id: 'ev-cluster-count',
      type: 'symbol',
      source: EVENTS_SOURCE,
      filter: ['has', 'point_count'],
      layout: {
        'text-field': ['get', 'point_count_abbreviated'],
        'text-font': [GLYPH_FONT],
        'text-size': 13,
        'text-allow-overlap': true,
      },
      paint: { 'text-color': c.onAccent },
    },
    {
      id: 'ev-points',
      type: 'circle',
      source: EVENTS_SOURCE,
      filter: ['!', ['has', 'point_count']],
      paint: {
        'circle-color': ['case', ['==', ['get', 'status'], 'cancelled'], c.border, c.accent],
        'circle-radius': 8,
        'circle-stroke-color': c.surface,
        'circle-stroke-width': 2,
      },
    },
    {
      id: 'ev-selected',
      type: 'circle',
      source: EVENTS_SOURCE,
      filter: NO_SELECTION,
      paint: {
        'circle-color': 'rgba(0,0,0,0)',
        'circle-radius': 13,
        'circle-stroke-color': c.text,
        'circle-stroke-width': 3,
      },
    },
  ];
}

export function meLayer(c: MapColors): LayerSpecification {
  return {
    id: 'ev-me',
    type: 'circle',
    source: ME_SOURCE,
    paint: {
      'circle-color': c.text,
      'circle-radius': 7,
      'circle-stroke-color': c.surface,
      'circle-stroke-width': 3,
    },
  };
}

export function campusLayers(c: MapColors): LayerSpecification[] {
  const [a, b, d] = CAMPUS_STEPS;
  return [
    {
      id: 'ev-campus-fill',
      type: 'fill',
      source: CAMPUS_SOURCE,
      paint: {
        'fill-color': [
          'step',
          ['get', 'count'],
          c.neutral,
          a,
          c.levels[0],
          b,
          c.levels[1],
          d,
          c.levels[2],
        ],
        'fill-opacity': 0.8,
      },
    },
    {
      id: 'ev-campus-outline',
      type: 'line',
      source: CAMPUS_SOURCE,
      paint: {
        'line-color': ['case', ['boolean', ['feature-state', 'selected'], false], c.text, c.border],
        'line-width': ['case', ['boolean', ['feature-state', 'selected'], false], 3, 1.5],
        'line-dasharray': [1, 0],
      },
    },
    {
      id: 'ev-campus-label',
      type: 'symbol',
      source: CAMPUS_SOURCE,
      layout: {
        'text-field': [
          'concat',
          ['get', 'buildingNo'],
          [
            'case',
            ['>', ['get', 'count'], 0],
            ['concat', ': ', ['to-string', ['get', 'count']]],
            '',
          ],
        ],
        'text-font': [GLYPH_FONT],
        'text-size': 13,
        'text-allow-overlap': true,
      },
      paint: { 'text-color': c.text, 'text-halo-color': c.surface, 'text-halo-width': 1.5 },
    },
  ];
}

/** Legend stops for the campus fill: lower bound of each of the four non-neutral levels. */
export const campusLegend = (): readonly { from: number; to: number | null }[] => [
  { from: CAMPUS_STEPS[0], to: CAMPUS_STEPS[1] - 1 },
  { from: CAMPUS_STEPS[1], to: CAMPUS_STEPS[2] - 1 },
  { from: CAMPUS_STEPS[2], to: null },
];
