import type { LayerConfig } from '../types';

export const LAYER_CONFIGS: LayerConfig[] = [
  // Boundaries
  {
    id: 'cadastral_freehold',
    label: 'Freehold Parcels',
    color: '#ff8c00',
    minZoom: 15,
    defaultVisible: true,
    endpoint: '/api/parcels',
    sourceId: 'cadastral-freehold',
    group: 'boundaries',
  },
  {
    id: 'cadastral_leasehold',
    label: 'Leasehold Parcels',
    color: '#6495ed',
    minZoom: 15,
    defaultVisible: true,
    endpoint: '/api/parcels_leasehold',
    sourceId: 'cadastral-leasehold',
    group: 'boundaries',
  },
  {
    id: 'rzlt',
    label: 'RZLT Sites',
    color: '#ef4444',
    minZoom: 0,
    defaultVisible: false,
    endpoint: '/api/rzlt',
    sourceId: 'rzlt',
    group: 'boundaries',
  },
  {
    id: 'urban_areas',
    label: 'Urban Areas',
    color: '#009688',
    minZoom: 0,
    defaultVisible: false,
    endpoint: '/api/urban_areas',
    sourceId: 'urban-areas',
    group: 'boundaries',
  },
  {
    id: 'osm_buildings',
    label: 'OSM Buildings',
    color: '#8d6e63',
    minZoom: 14,
    defaultVisible: false,
    endpoint: '/api/osm_buildings',
    sourceId: 'osm-buildings',
    group: 'boundaries',
  },
  {
    id: 'sd_lap_boundaries',
    label: 'LAP Boundaries',
    color: '#9b59b6',
    minZoom: 0,
    defaultVisible: false,
    endpoint: '/api/lap_boundaries',
    sourceId: 'sd-lap-boundaries',
    group: 'boundaries',
  },

  // Planning
  {
    id: 'dlr_planning_polygons',
    label: 'Planning (Areas)',
    color: '#2ecc71',
    minZoom: 13,
    defaultVisible: true,
    endpoint: '/api/planning_apps',
    sourceId: 'dlr-planning-polygons',
    group: 'planning',
  },
  {
    id: 'dlr_planning_points',
    label: 'Planning (Points)',
    color: '#27ae60',
    minZoom: 12,
    defaultVisible: false,
    endpoint: '/api/planning_apps_points',
    sourceId: 'dlr-planning-points',
    group: 'planning',
  },
  {
    id: 'sd_planning_register',
    label: 'SD Planning Register',
    color: '#e67e22',
    minZoom: 13,
    defaultVisible: false,
    endpoint: '/api/sd_planning_register',
    sourceId: 'sd-planning-register',
    group: 'planning',
  },
  {
    id: 'national_planning_polygons',
    label: 'National Planning (Areas)',
    color: '#3498db',
    minZoom: 13,
    defaultVisible: false,
    endpoint: '/api/national_planning_polygons',
    sourceId: 'national-planning-polygons',
    group: 'planning',
  },
  {
    id: 'national_planning_points',
    label: 'National Planning (Points)',
    color: '#2980b9',
    minZoom: 12,
    defaultVisible: false,
    endpoint: '/api/national_planning_points',
    sourceId: 'national-planning-points',
    group: 'planning',
  },

  // Market
  {
    id: 'sold_properties',
    label: 'Sold Properties',
    color: '#e74c3c',
    minZoom: 13,
    defaultVisible: true,
    endpoint: '/api/sold_properties',
    sourceId: 'sold-properties',
    group: 'market',
  },
  {
    id: 'side_sites',
    label: 'Side Sites',
    color: '#f9a825',
    minZoom: 15,
    defaultVisible: false,
    endpoint: '/api/side_sites',
    sourceId: 'side-sites',
    group: 'market',
  },

  // Demographics
  {
    id: 'census_small_areas',
    label: 'Census Areas',
    color: '#00bcd4',
    minZoom: 12,
    defaultVisible: false,
    endpoint: '/api/census_small_areas',
    sourceId: 'census-small-areas',
    group: 'demographics',
  },
];

export const LAYER_GROUPS = {
  boundaries: { label: 'Boundaries', icon: '◻' },
  planning: { label: 'Planning', icon: '◈' },
  market: { label: 'Market', icon: '◉' },
  demographics: { label: 'Demographics', icon: '◎' },
};

export const API_BASE = import.meta.env.DEV ? '' : 'http://localhost:8000';

export const DUBLIN_CENTER = { longitude: -6.2603, latitude: 53.3498 };
export const DEFAULT_ZOOM = 12;
