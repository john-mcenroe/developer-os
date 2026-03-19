export interface LayerConfig {
  id: string;
  label: string;
  color: string;
  minZoom: number;
  defaultVisible: boolean;
  endpoint: string;
  sourceId: string;
  group: 'boundaries' | 'planning' | 'market' | 'demographics';
}

export interface ViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch?: number;
  bearing?: number;
}

export interface BBox {
  west: number;
  south: number;
  east: number;
  north: number;
}

export interface ParcelProperties {
  id: number;
  national_ref?: string;
  inspire_id?: string;
  area_sqm?: number;
  area_acres?: number;
  type: 'freehold' | 'leasehold';
}

export interface RzltProperties {
  id: number;
  zone_desc?: string;
  zone_gzt?: string;
  gzt_desc?: string;
  site_area?: number;
  local_authority?: string;
}

export interface PlanningProperties {
  id: number;
  plan_ref?: string;
  county?: string;
  plan_auth?: string;
  reg_date?: string;
  descrptn?: string;
  location?: string;
  stage?: string;
  decision?: string;
  app_dec?: string;
  dec_date?: string;
  more_info?: string;
}

export interface SoldPropertyProperties {
  id: number;
  address?: string;
  sale_price?: number;
  asking_price?: number;
  sale_date?: string;
  beds?: number;
  baths?: number;
  property_type?: string;
  ber_rating?: string;
  floor_area_sqm?: number;
  price_per_sqm?: number;
}

export interface CensusProperties {
  id: number;
  sa_code?: string;
  urban_area?: string;
  county?: string;
  total_population?: number;
  total_households?: number;
  avg_household_size?: number;
  apartment_pct?: number;
  owner_occupied_pct?: number;
  rented_pct?: number;
  vacancy_rate?: number;
  employment_rate?: number;
  third_level_pct?: number;
  wfh_pct?: number;
  population_density?: number;
  avg_rooms?: number;
  health_good_pct?: number;
  built_pre_1919?: number;
  built_2016_plus?: number;
  area_sqm?: number;
}

export interface SideSiteProperties {
  id: number;
  area_sqm?: number;
  area_acres?: number;
  score?: number;
  compactness?: number;
  neighbor_count?: number;
  has_planning?: boolean | string;
  on_rzlt?: boolean | string;
  owner_occupied_pct?: number;
  vacancy_rate?: number;
  national_ref?: string;
}

export interface EnrichedParcel {
  parcel: ParcelProperties;
  rzlt_overlap?: RzltProperties[];
  nearby_sales?: {
    count: number;
    avg_sale_price: number;
    median_sale_price: number;
    avg_price_per_sqm?: number;
    recent?: Array<{
      address: string;
      sale_price: number;
      sale_date?: string;
      property_type?: string | null;
      distance_m: number;
    }>;
  };
  nearby_planning?: Array<{
    plan_ref: string;
    description: string;
    decision: string;
    distance_m: number;
    reg_date?: string;
    dec_date?: string;
    location?: string;
  }>;
  census?: CensusProperties;
}

export interface FeatureClickEvent {
  layerId: string;
  feature: GeoJSON.Feature;
  lngLat: { lng: number; lat: number };
}

export interface SearchResult {
  display_name: string;
  lat: string;
  lon: string;
  boundingbox?: string[];
}

export type FeatureProperties =
  | ParcelProperties
  | RzltProperties
  | PlanningProperties
  | SoldPropertyProperties
  | CensusProperties
  | SideSiteProperties;

/* ── AI Site Search ────────────────────────────────────────────────────── */

export interface SiteSearchResult {
  lng: number;
  lat: number;
  _score: number;
  _rank: number;
  _table: string;
  opportunity_reason: string;
  geometry?: GeoJSON.Geometry;
  [key: string]: unknown;
}

export interface SiteSearchResponse {
  type: 'map_realization';
  object_type: string;
  title: string;
  summary: string;
  results: SiteSearchResult[];
  follow_ups: { label: string; prompt: string }[];
  query_stats: { total: number; successful: number };
  intent: string;
}

export type SearchPhase = 'idle' | 'routing' | 'hypotheses' | 'executing' | 'ranking' | 'done' | 'error';
