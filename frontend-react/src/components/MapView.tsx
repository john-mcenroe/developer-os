import { useCallback, useEffect, useRef, useState } from 'react';
import MapGL, {
  Source,
  Layer,
  NavigationControl,
  type MapRef,
  type MapLayerMouseEvent,
  type ViewStateChangeEvent,
} from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';

import { useMapData, useEnrichedParcel } from '../hooks/useMapData';
import { useSiteSearch } from '../hooks/useSiteSearch';
import { DUBLIN_CENTER, DEFAULT_ZOOM } from '../config/layers';
import { LayerPanel } from './LayerPanel';
import { SearchBar } from './SearchBar';
import { DetailPanel } from './DetailPanel';
import { SiteSearch } from './SiteSearch';
import { ZoomIndicator } from './ZoomIndicator';
import { BasemapToggle } from './BasemapToggle';

import type { ViewState, SiteSearchResult, AreaFocus } from '../types';

const OSM_STYLE = {
  version: 8 as const,
  sources: {
    osm: {
      type: 'raster' as const,
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxzoom: 19,
    },
  },
  layers: [{ id: 'osm-tiles', type: 'raster' as const, source: 'osm' }],
};

const SATELLITE_STYLE = {
  version: 8 as const,
  sources: {
    satellite: {
      type: 'raster' as const,
      tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
      tileSize: 256,
      attribution: '&copy; Esri',
      maxzoom: 19,
    },
  },
  layers: [{ id: 'satellite-tiles', type: 'raster' as const, source: 'satellite' }],
};

const EMPTY_FC: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] };

export function MapView() {
  const mapRef = useRef<MapRef | null>(null);
  const [viewState, setViewState] = useState<ViewState>({
    longitude: DUBLIN_CENTER.longitude,
    latitude: DUBLIN_CENTER.latitude,
    zoom: DEFAULT_ZOOM,
  });
  const [basemap, setBasemap] = useState<'map' | 'satellite'>('map');
  const [visibleLayers, setVisibleLayers] = useState<Set<string>>(() => {
    const initial = new Set<string>();
    initial.add('cadastral_freehold');
    initial.add('cadastral_leasehold');
    initial.add('dlr_planning_polygons');
    initial.add('sold_properties');
    return initial;
  });

  // Detail panel state
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedProps, setSelectedProps] = useState<Record<string, unknown> | null>(null);
  const [selectedFeatureId, setSelectedFeatureId] = useState<number | null>(null);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const { data: enrichedData, loading: enrichedLoading, fetchEnriched, clear: clearEnriched } = useEnrichedParcel();

  // AI Site Search
  const siteSearch = useSiteSearch();
  const [searchSelectedIndex, setSearchSelectedIndex] = useState<number | null>(null);

  const TABLE_TO_DETAIL: Record<string, string> = {
    sold_properties: 'sold',
    cadastral_freehold: 'parcel',
    cadastral_leasehold: 'parcel',
    rzlt: 'rzlt',
    dlr_planning_polygons: 'planning',
    dlr_planning_points: 'planning',
    national_planning_polygons: 'planning',
    national_planning_points: 'planning',
    census_small_areas: 'census',
    side_sites: 'side_site',
  };

  const siteSearchFn = siteSearch.search;
  const handleSiteSearch = useCallback((query: string) => {
    const map = mapRef.current?.getMap();
    let viewport: { sw: [number, number]; ne: [number, number] } | undefined;
    if (map) {
      const bounds = map.getBounds();
      viewport = {
        sw: [bounds.getWest(), bounds.getSouth()],
        ne: [bounds.getEast(), bounds.getNorth()],
      };
    }
    setSearchSelectedIndex(null);
    siteSearchFn(query, viewport, viewState.zoom, Array.from(visibleLayers));
  }, [siteSearchFn, viewState.zoom, visibleLayers]);

  const handleSearchResultSelect = useCallback((result: SiteSearchResult, index: number) => {
    setSearchSelectedIndex(index);

    // Fly to result
    if (result.lng && result.lat) {
      mapRef.current?.flyTo({ center: [result.lng, result.lat], zoom: 16, duration: 1500 });
    }

    // Open detail panel
    const detailType = TABLE_TO_DETAIL[result._table] || 'generic';
    setSelectedType(detailType);
    setSelectedProps(result as unknown as Record<string, unknown>);
    setSelectedSourceId(null);
    setSelectedFeatureId(null);

    // If it's a parcel, fetch enriched data
    if ((detailType === 'parcel') && result.id) {
      const parcelType = result._table === 'cadastral_leasehold' ? 'leasehold' : 'freehold';
      fetchEnriched(Number(result.id), parcelType);
    } else {
      clearEnriched();
    }
  }, [fetchEnriched, clearEnriched]);

  const siteSearchClear = siteSearch.clear;
  const handleSearchClear = useCallback(() => {
    siteSearchClear();
    setSearchSelectedIndex(null);
  }, [siteSearchClear]);

  // Hypothesis colors for preview polygons
  const HYPOTHESIS_COLORS = ['#3b82f6', '#8b5cf6', '#f59e0b', '#22c55e', '#ef4444', '#06b6d4'];

  // Build GeoJSON for preview polygon regions (areas lighting up during search)
  const previewPolygonsGeoJSON: GeoJSON.FeatureCollection = {
    type: 'FeatureCollection',
    features: siteSearch.previewFeatures
      .filter(f => f.geometry.type === 'Polygon' || f.geometry.type === 'MultiPolygon')
      .map((f, i) => ({
        type: 'Feature' as const,
        geometry: f.geometry,
        properties: {
          idx: i,
          hypothesisIndex: f.hypothesisIndex,
          color: HYPOTHESIS_COLORS[f.hypothesisIndex % HYPOTHESIS_COLORS.length],
        },
      })),
  };

  // Preview point markers for Point-type results during search
  const previewPointsGeoJSON: GeoJSON.FeatureCollection = {
    type: 'FeatureCollection',
    features: siteSearch.previewFeatures
      .filter(f => f.geometry.type === 'Point')
      .map((f, i) => ({
        type: 'Feature' as const,
        geometry: f.geometry,
        properties: {
          idx: i,
          hypothesisIndex: f.hypothesisIndex,
          color: HYPOTHESIS_COLORS[f.hypothesisIndex % HYPOTHESIS_COLORS.length],
        },
      })),
  };

  // Fly to area when AI detects a named location
  const prevAreaRef = useRef<AreaFocus | null>(null);
  useEffect(() => {
    const focus = siteSearch.areaFocus;
    if (!focus || focus === prevAreaRef.current) return;
    prevAreaRef.current = focus;

    if (focus.bbox && focus.bbox.length === 4) {
      // Nominatim bbox is [south, north, west, east]
      const [south, north, west, east] = focus.bbox.map(Number);
      mapRef.current?.fitBounds(
        [[west, south], [east, north]],
        { padding: 60, duration: 2000, maxZoom: 15 },
      );
    } else {
      mapRef.current?.flyTo({
        center: [focus.lng, focus.lat],
        zoom: 14,
        duration: 2000,
      });
    }
  }, [siteSearch.areaFocus]);

  // Fit bounds to final results when search completes
  const prevResultCountRef = useRef(0);
  useEffect(() => {
    const results = siteSearch.results;
    if (results.length === 0 || results.length === prevResultCountRef.current) return;
    prevResultCountRef.current = results.length;

    if (results.length >= 2) {
      let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity;
      for (const r of results) {
        if (r.lng < minLng) minLng = r.lng;
        if (r.lng > maxLng) maxLng = r.lng;
        if (r.lat < minLat) minLat = r.lat;
        if (r.lat > maxLat) maxLat = r.lat;
      }
      // Only fit bounds if results span a meaningful area (not all same point)
      const lngSpan = maxLng - minLng;
      const latSpan = maxLat - minLat;
      if (lngSpan > 0.001 || latSpan > 0.001) {
        mapRef.current?.fitBounds(
          [[minLng, minLat], [maxLng, maxLat]],
          { padding: 80, duration: 1500, maxZoom: 16 },
        );
      }
    }
  }, [siteSearch.results]);

  // Clear ghost marker count on new search
  useEffect(() => {
    if (siteSearch.phase === 'idle') {
      prevResultCountRef.current = 0;
      prevAreaRef.current = null;
    }
  }, [siteSearch.phase]);

  // Build GeoJSON for search result markers (points for numbered pins)
  const searchResultsGeoJSON: GeoJSON.FeatureCollection = {
    type: 'FeatureCollection',
    features: siteSearch.results.map((r, i) => ({
      type: 'Feature' as const,
      geometry: { type: 'Point' as const, coordinates: [r.lng, r.lat] },
      properties: { rank: i + 1, score: r._score, selected: searchSelectedIndex === i ? 1 : 0 },
    })),
  };

  // Build GeoJSON for the SELECTED result's actual geometry (polygon highlight)
  const selectedResultGeoJSON: GeoJSON.FeatureCollection = {
    type: 'FeatureCollection',
    features: searchSelectedIndex != null && siteSearch.results[searchSelectedIndex]?.geometry
      ? [{
          type: 'Feature' as const,
          geometry: siteSearch.results[searchSelectedIndex].geometry!,
          properties: { rank: searchSelectedIndex + 1 },
        }]
      : [],
  };

  // Build GeoJSON for ALL results that have polygon geometries (always visible for browsing)
  const allResultPolygonsGeoJSON: GeoJSON.FeatureCollection = {
    type: 'FeatureCollection',
    features: siteSearch.results
      .map((r, i) => ({ r, i }))
      .filter(({ r }) => r.geometry && r.geometry.type !== 'Point')
      .map(({ r, i }) => ({
        type: 'Feature' as const,
        geometry: r.geometry!,
        properties: { rank: i + 1 },
      })),
  };

  const { scheduleLoad, loadAllLayers } = useMapData(mapRef, visibleLayers, viewState.zoom);

  // Load data on mount and when view/layers change
  const handleMoveEnd = useCallback(
    (e: ViewStateChangeEvent) => {
      setViewState(e.viewState);
      scheduleLoad();
    },
    [scheduleLoad]
  );

  const handleLoad = useCallback(() => {
    loadAllLayers();
  }, [loadAllLayers]);

  // Reload when visible layers change
  useEffect(() => {
    loadAllLayers();
  }, [visibleLayers, loadAllLayers]);

  const toggleLayer = useCallback((layerId: string) => {
    setVisibleLayers((prev) => {
      const next = new Set(prev);
      if (next.has(layerId)) {
        next.delete(layerId);
      } else {
        next.add(layerId);
      }
      return next;
    });
  }, []);

  const handleMapClick = useCallback(
    (e: MapLayerMouseEvent) => {
      const map = mapRef.current?.getMap();
      if (!map) return;

      // Query features at click point across all interactive layers
      const interactiveLayers = [
        'cadastral_freehold-fill',
        'cadastral_leasehold-fill',
        'dlr_planning_polygons-fill',
        'dlr_planning_points-fill',
        'national_planning_polygons-fill',
        'national_planning_points-fill',
        'sold_properties-fill',
        'census_small_areas-fill',
        'rzlt-fill',
        'side_sites-fill',
        'sd_lap_boundaries-fill',
        'sd_planning_register-fill',
        'osm_buildings-fill',
        'osm_amenities-fill',
        'osm_transport-fill',
        'flood_zones-fill',
        'niah_buildings-fill',
        'schools-fill',
        'landuse-fill',
        'zoning-fill',
      ].filter((id) => map.getLayer(id));

      const features = map.queryRenderedFeatures(e.point, { layers: interactiveLayers });
      if (!features || features.length === 0) {
        setSelectedType(null);
        setSelectedProps(null);
        setSelectedFeatureId(null);
        setSelectedSourceId(null);
        clearEnriched();
        return;
      }

      const feature = features[0];
      const layerId = feature.layer.id;
      const props = feature.properties || {};
      const fid = feature.id != null ? Number(feature.id) : null;

      // Track selection for highlight
      setSelectedFeatureId(fid);

      if (layerId.startsWith('cadastral_freehold')) {
        setSelectedType('parcel');
        setSelectedProps({ ...props, type: 'freehold' });
        setSelectedSourceId('cadastral-freehold');
        if (fid) fetchEnriched(fid, 'freehold');
      } else if (layerId.startsWith('cadastral_leasehold')) {
        setSelectedType('parcel');
        setSelectedProps({ ...props, type: 'leasehold' });
        setSelectedSourceId('cadastral-leasehold');
        if (fid) fetchEnriched(fid, 'leasehold');
      } else if (layerId.startsWith('dlr_planning_polygons') || layerId.startsWith('dlr_planning_points')) {
        setSelectedType('planning');
        setSelectedProps(props);
        setSelectedSourceId('dlr-planning-polygons');
      } else if (layerId.startsWith('national_planning_polygons')) {
        setSelectedType('planning');
        setSelectedProps(props);
        setSelectedSourceId('national-planning-polygons');
      } else if (layerId.startsWith('national_planning_points')) {
        setSelectedType('planning');
        setSelectedProps(props);
        setSelectedSourceId('national-planning-points');
      } else if (layerId.startsWith('sold_properties')) {
        setSelectedType('sold');
        setSelectedProps(props);
        setSelectedSourceId('sold-properties');
      } else if (layerId.startsWith('census_small_areas')) {
        setSelectedType('census');
        setSelectedProps(props);
        setSelectedSourceId('census-small-areas');
      } else if (layerId.startsWith('rzlt')) {
        setSelectedType('rzlt');
        setSelectedProps(props);
        setSelectedSourceId('rzlt');
      } else if (layerId.startsWith('side_sites')) {
        setSelectedType('side_site');
        setSelectedProps(props);
        setSelectedSourceId('side-sites');
      } else if (layerId.startsWith('sd_lap')) {
        setSelectedType('lap');
        setSelectedProps(props);
        setSelectedSourceId('sd-lap-boundaries');
      } else if (layerId.startsWith('sd_planning')) {
        setSelectedType('sd_planning');
        setSelectedProps(props);
        setSelectedSourceId('sd-planning-register');
      } else if (layerId.startsWith('osm_buildings')) {
        setSelectedType('osm_building');
        setSelectedProps(props);
        setSelectedSourceId('osm-buildings');
      } else if (layerId.startsWith('osm_amenities')) {
        setSelectedType('amenity');
        setSelectedProps(props);
        setSelectedSourceId('osm-amenities');
      } else if (layerId.startsWith('osm_transport')) {
        setSelectedType('transport');
        setSelectedProps(props);
        setSelectedSourceId('osm-transport');
      } else if (layerId.startsWith('flood_zones')) {
        setSelectedType('flood_zone');
        setSelectedProps(props);
        setSelectedSourceId('flood-zones');
      } else if (layerId.startsWith('niah_buildings')) {
        setSelectedType('niah');
        setSelectedProps(props);
        setSelectedSourceId('niah-buildings');
      } else if (layerId.startsWith('schools')) {
        setSelectedType('school');
        setSelectedProps(props);
        setSelectedSourceId('schools');
      } else if (layerId.startsWith('landuse')) {
        setSelectedType('landuse');
        setSelectedProps(props);
        setSelectedSourceId('landuse');
      } else if (layerId.startsWith('zoning')) {
        setSelectedType('zoning');
        setSelectedProps(props);
        setSelectedSourceId('zoning');
      } else if (layerId.startsWith('commercial_valuations')) {
        setSelectedType('commercial');
        setSelectedProps(props);
        setSelectedSourceId('commercial_valuations');
      } else {
        setSelectedType('generic');
        setSelectedProps(props);
        setSelectedSourceId(null);
      }
    },
    [fetchEnriched, clearEnriched]
  );

  const handleCursorChange = useCallback((e: MapLayerMouseEvent) => {
    const map = mapRef.current?.getMap();
    if (!map) return;
    const interactiveLayers = [
      'cadastral_freehold-fill', 'cadastral_leasehold-fill',
      'dlr_planning_polygons-fill', 'dlr_planning_points-fill',
      'national_planning_polygons-fill', 'national_planning_points-fill',
      'sold_properties-fill', 'census_small_areas-fill', 'rzlt-fill',
      'side_sites-fill', 'sd_lap_boundaries-fill', 'sd_planning_register-fill',
      'osm_buildings-fill', 'osm_amenities-fill', 'osm_transport-fill',
      'flood_zones-fill', 'niah_buildings-fill',
      'schools-fill', 'landuse-fill', 'zoning-fill', 'commercial_valuations-fill',
    ].filter((id) => map.getLayer(id));
    const features = map.queryRenderedFeatures(e.point, { layers: interactiveLayers });
    map.getCanvas().style.cursor = features.length > 0 ? 'pointer' : '';
  }, []);

  const handleSearchSelect = useCallback((lng: number, lat: number) => {
    mapRef.current?.flyTo({ center: [lng, lat], zoom: 15, duration: 1500 });
  }, []);

  const closeDetail = useCallback(() => {
    setSelectedType(null);
    setSelectedProps(null);
    setSelectedFeatureId(null);
    setSelectedSourceId(null);
    clearEnriched();
  }, [clearEnriched]);

  const mapStyle = basemap === 'map' ? OSM_STYLE : SATELLITE_STYLE;

  // Selection filter: show only the selected feature
  const selFilter = (sourceId: string): maplibregl.ExpressionSpecification =>
    selectedSourceId === sourceId && selectedFeatureId != null
      ? ['==', ['id'], selectedFeatureId]
      : ['==', ['id'], -1]; // match nothing

  return (
    <div className="map-container">
      <MapGL
        ref={mapRef}
        {...viewState}
        onMove={(e) => setViewState(e.viewState)}
        onMoveEnd={handleMoveEnd}
        onLoad={handleLoad}
        onClick={handleMapClick}
        onMouseMove={handleCursorChange}
        mapStyle={mapStyle as unknown as maplibregl.StyleSpecification}
        style={{ width: '100%', height: '100%' }}
        attributionControl={false}
      >
        <NavigationControl position="top-right" />

        {/* === Cadastral Freehold === */}
        <Source id="cadastral-freehold" type="geojson" data={EMPTY_FC}>
          <Layer
            id="cadastral_freehold-fill"
            type="fill"
            paint={{ 'fill-color': 'rgba(255, 165, 0, 0.15)', 'fill-outline-color': 'rgba(255, 140, 0, 0)' }}
          />
          <Layer
            id="cadastral_freehold-outline"
            type="line"
            paint={{ 'line-color': '#ff8c00', 'line-width': 1 }}
          />
          <Layer
            id="cadastral_freehold-selected"
            type="fill"
            filter={selFilter('cadastral-freehold')}
            paint={{ 'fill-color': 'rgba(255, 200, 0, 0.5)', 'fill-outline-color': '#ffc800' }}
          />
          <Layer
            id="cadastral_freehold-selected-outline"
            type="line"
            filter={selFilter('cadastral-freehold')}
            paint={{ 'line-color': '#ffffff', 'line-width': 4 }}
          />
          <Layer
            id="cadastral_freehold-selected-glow"
            type="line"
            filter={selFilter('cadastral-freehold')}
            paint={{ 'line-color': '#ffc800', 'line-width': 10, 'line-opacity': 0.25, 'line-blur': 6 }}
          />
        </Source>

        {/* === Cadastral Leasehold === */}
        <Source id="cadastral-leasehold" type="geojson" data={EMPTY_FC}>
          <Layer
            id="cadastral_leasehold-fill"
            type="fill"
            paint={{ 'fill-color': 'rgba(100, 149, 237, 0.15)', 'fill-outline-color': 'rgba(100, 149, 237, 0)' }}
          />
          <Layer
            id="cadastral_leasehold-outline"
            type="line"
            paint={{ 'line-color': '#6495ed', 'line-width': 1 }}
          />
          <Layer
            id="cadastral_leasehold-selected"
            type="fill"
            filter={selFilter('cadastral-leasehold')}
            paint={{ 'fill-color': 'rgba(100, 200, 255, 0.5)', 'fill-outline-color': '#64c8ff' }}
          />
          <Layer
            id="cadastral_leasehold-selected-outline"
            type="line"
            filter={selFilter('cadastral-leasehold')}
            paint={{ 'line-color': '#ffffff', 'line-width': 4 }}
          />
          <Layer
            id="cadastral_leasehold-selected-glow"
            type="line"
            filter={selFilter('cadastral-leasehold')}
            paint={{ 'line-color': '#64c8ff', 'line-width': 10, 'line-opacity': 0.25, 'line-blur': 6 }}
          />
        </Source>

        {/* === RZLT === */}
        <Source id="rzlt" type="geojson" data={EMPTY_FC}>
          <Layer
            id="rzlt-fill"
            type="fill"
            paint={{ 'fill-color': 'rgba(239, 68, 68, 0.2)', 'fill-outline-color': 'rgba(239, 68, 68, 0)' }}
          />
          <Layer
            id="rzlt-outline"
            type="line"
            paint={{ 'line-color': '#ef4444', 'line-width': 2 }}
          />
          <Layer
            id="rzlt-selected"
            type="line"
            filter={selFilter('rzlt')}
            paint={{ 'line-color': '#ffffff', 'line-width': 3 }}
          />
        </Source>

        {/* === DLR Planning Polygons === */}
        <Source id="dlr-planning-polygons" type="geojson" data={EMPTY_FC}>
          <Layer
            id="dlr_planning_polygons-fill"
            type="fill"
            paint={{ 'fill-color': 'rgba(46, 204, 113, 0.25)', 'fill-outline-color': 'rgba(46, 204, 113, 0)' }}
          />
          <Layer
            id="dlr_planning_polygons-outline"
            type="line"
            paint={{ 'line-color': '#2ecc71', 'line-width': 2 }}
          />
          <Layer
            id="dlr_planning_polygons-selected"
            type="fill"
            filter={selFilter('dlr-planning-polygons')}
            paint={{ 'fill-color': 'rgba(46, 204, 113, 0.5)', 'fill-outline-color': '#27ae60' }}
          />
          <Layer
            id="dlr_planning_polygons-selected-outline"
            type="line"
            filter={selFilter('dlr-planning-polygons')}
            paint={{ 'line-color': '#ffffff', 'line-width': 4 }}
          />
          <Layer
            id="dlr_planning_polygons-selected-glow"
            type="line"
            filter={selFilter('dlr-planning-polygons')}
            paint={{ 'line-color': '#2ecc71', 'line-width': 10, 'line-opacity': 0.25, 'line-blur': 6 }}
          />
        </Source>

        {/* === DLR Planning Points === */}
        <Source id="dlr-planning-points" type="geojson" data={EMPTY_FC}>
          <Layer
            id="dlr_planning_points-fill"
            type="circle"
            paint={{
              'circle-radius': ['interpolate', ['linear'], ['zoom'], 12, 2, 15, 3.5, 18, 5],
              'circle-color': '#27ae60',
              'circle-stroke-color': 'rgba(255,255,255,0.5)',
              'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 12, 0, 15, 0.5],
              'circle-opacity': ['interpolate', ['linear'], ['zoom'], 12, 0.5, 15, 0.7, 18, 0.85],
            }}
          />
        </Source>

        {/* === Sold Properties === */}
        <Source id="sold-properties" type="geojson" data={EMPTY_FC}>
          <Layer
            id="sold_properties-fill"
            type="circle"
            paint={{
              'circle-radius': ['interpolate', ['linear'], ['zoom'], 12, 2, 14, 3, 16, 4.5, 18, 6],
              'circle-color': [
                'interpolate', ['linear'], ['coalesce', ['get', 'sale_price'], 0],
                100000, '#f1c40f',
                300000, '#e67e22',
                500000, '#e74c3c',
                1000000, '#8e44ad',
                3000000, '#2c3e50',
              ],
              'circle-stroke-color': 'rgba(255,255,255,0.6)',
              'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 12, 0, 15, 0.5, 18, 1],
              'circle-opacity': ['interpolate', ['linear'], ['zoom'], 12, 0.5, 15, 0.65, 18, 0.8],
            }}
          />
        </Source>

        {/* === Census Small Areas === */}
        <Source id="census-small-areas" type="geojson" data={EMPTY_FC}>
          <Layer
            id="census_small_areas-fill"
            type="fill"
            paint={{
              'fill-color': [
                'interpolate', ['linear'], ['coalesce', ['get', 'population_density'], 0],
                0, 'rgba(0, 188, 212, 0.05)',
                2000, 'rgba(0, 188, 212, 0.15)',
                10000, 'rgba(0, 188, 212, 0.3)',
                30000, 'rgba(0, 150, 136, 0.45)',
                80000, 'rgba(0, 105, 92, 0.6)',
              ],
              'fill-outline-color': 'rgba(0, 188, 212, 0)',
            }}
          />
          <Layer
            id="census_small_areas-outline"
            type="line"
            paint={{ 'line-color': '#00bcd4', 'line-width': 0.5 }}
          />
          <Layer
            id="census_small_areas-selected"
            type="fill"
            filter={selFilter('census-small-areas')}
            paint={{ 'fill-color': 'rgba(0, 230, 255, 0.4)', 'fill-outline-color': '#00e5ff' }}
          />
          <Layer
            id="census_small_areas-selected-outline"
            type="line"
            filter={selFilter('census-small-areas')}
            paint={{ 'line-color': '#ffffff', 'line-width': 4 }}
          />
          <Layer
            id="census_small_areas-selected-glow"
            type="line"
            filter={selFilter('census-small-areas')}
            paint={{ 'line-color': '#00e5ff', 'line-width': 10, 'line-opacity': 0.25, 'line-blur': 6 }}
          />
        </Source>

        {/* === Urban Areas === */}
        <Source id="urban-areas" type="geojson" data={EMPTY_FC}>
          <Layer
            id="urban_areas-fill"
            type="fill"
            paint={{ 'fill-color': 'rgba(0, 150, 136, 0.1)', 'fill-outline-color': 'rgba(0, 150, 136, 0)' }}
          />
          <Layer
            id="urban_areas-outline"
            type="line"
            paint={{ 'line-color': '#009688', 'line-width': 2 }}
          />
        </Source>

        {/* === OSM Buildings === */}
        <Source id="osm-buildings" type="geojson" data={EMPTY_FC}>
          <Layer
            id="osm_buildings-fill"
            type="fill"
            paint={{ 'fill-color': 'rgba(141, 110, 99, 0.15)', 'fill-outline-color': 'rgba(141, 110, 99, 0)' }}
          />
          <Layer
            id="osm_buildings-outline"
            type="line"
            paint={{ 'line-color': '#8d6e63', 'line-width': 0.5 }}
          />
        </Source>

        {/* === SD LAP Boundaries === */}
        <Source id="sd-lap-boundaries" type="geojson" data={EMPTY_FC}>
          <Layer
            id="sd_lap_boundaries-fill"
            type="fill"
            paint={{ 'fill-color': 'rgba(155, 89, 182, 0.1)', 'fill-outline-color': 'rgba(155, 89, 182, 0)' }}
          />
          <Layer
            id="sd_lap_boundaries-outline"
            type="line"
            paint={{ 'line-color': '#9b59b6', 'line-width': 2.5, 'line-dasharray': [6, 3] }}
          />
        </Source>

        {/* === SD Planning Register === */}
        <Source id="sd-planning-register" type="geojson" data={EMPTY_FC}>
          <Layer
            id="sd_planning_register-fill"
            type="fill"
            paint={{
              'fill-color': [
                'match', ['coalesce', ['get', 'status'], ''],
                'Grant', '#2ecc71',
                'Refuse', '#e74c3c',
                '#e67e22',
              ],
              'fill-opacity': 0.25,
            }}
          />
          <Layer
            id="sd_planning_register-outline"
            type="line"
            paint={{
              'line-color': [
                'match', ['coalesce', ['get', 'status'], ''],
                'Grant', '#2ecc71',
                'Refuse', '#e74c3c',
                '#e67e22',
              ],
              'line-width': 2,
            }}
          />
        </Source>

        {/* === National Planning Polygons === */}
        <Source id="national-planning-polygons" type="geojson" data={EMPTY_FC}>
          <Layer
            id="national_planning_polygons-fill"
            type="fill"
            paint={{ 'fill-color': 'rgba(52, 152, 219, 0.2)', 'fill-outline-color': 'rgba(52, 152, 219, 0)' }}
          />
          <Layer
            id="national_planning_polygons-outline"
            type="line"
            paint={{ 'line-color': '#3498db', 'line-width': 2 }}
          />
          <Layer
            id="national_planning_polygons-selected"
            type="fill"
            filter={selFilter('national-planning-polygons')}
            paint={{ 'fill-color': 'rgba(52, 152, 219, 0.45)', 'fill-outline-color': '#2980b9' }}
          />
          <Layer
            id="national_planning_polygons-selected-outline"
            type="line"
            filter={selFilter('national-planning-polygons')}
            paint={{ 'line-color': '#ffffff', 'line-width': 4 }}
          />
          <Layer
            id="national_planning_polygons-selected-glow"
            type="line"
            filter={selFilter('national-planning-polygons')}
            paint={{ 'line-color': '#3498db', 'line-width': 10, 'line-opacity': 0.25, 'line-blur': 6 }}
          />
        </Source>

        {/* === National Planning Points === */}
        <Source id="national-planning-points" type="geojson" data={EMPTY_FC}>
          <Layer
            id="national_planning_points-fill"
            type="circle"
            paint={{
              'circle-radius': ['interpolate', ['linear'], ['zoom'], 12, 2, 15, 3.5, 18, 5],
              'circle-color': '#2980b9',
              'circle-stroke-color': 'rgba(255,255,255,0.5)',
              'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 12, 0, 15, 0.5],
              'circle-opacity': ['interpolate', ['linear'], ['zoom'], 12, 0.5, 15, 0.7, 18, 0.85],
            }}
          />
        </Source>

        {/* === Side Sites === */}
        <Source id="side-sites" type="geojson" data={EMPTY_FC}>
          <Layer
            id="side_sites-fill"
            type="fill"
            paint={{
              'fill-color': [
                'interpolate', ['linear'], ['coalesce', ['get', 'score'], 0],
                0.3, 'rgba(255, 235, 59, 0.25)',
                0.6, 'rgba(255, 193, 7, 0.4)',
                0.8, 'rgba(255, 152, 0, 0.55)',
              ],
              'fill-outline-color': 'rgba(255, 193, 7, 0)',
            }}
          />
          <Layer
            id="side_sites-outline"
            type="line"
            paint={{ 'line-color': '#f9a825', 'line-width': 2 }}
          />
          <Layer
            id="side_sites-selected"
            type="line"
            filter={selFilter('side-sites')}
            paint={{ 'line-color': '#ffffff', 'line-width': 3 }}
          />
        </Source>

        {/* === Zoning === */}
        <Source id="zoning" type="geojson" data={EMPTY_FC}>
          <Layer
            id="zoning-fill"
            type="fill"
            paint={{
              'fill-color': 'rgba(156, 39, 176, 0.15)',
              'fill-outline-color': 'rgba(156, 39, 176, 0)',
            }}
          />
          <Layer
            id="zoning-outline"
            type="line"
            paint={{ 'line-color': '#9c27b0', 'line-width': 1.5 }}
          />
        </Source>

        {/* === Commercial Valuations === */}
        <Source id="commercial_valuations" type="geojson" data={EMPTY_FC}>
          <Layer
            id="commercial_valuations-fill"
            type="circle"
            paint={{
              'circle-radius': 4,
              'circle-color': '#e91e63',
              'circle-opacity': 0.7,
              'circle-stroke-width': 1,
              'circle-stroke-color': '#fff',
            }}
          />
        </Source>

        {/* === Schools === */}
        <Source id="schools" type="geojson" data={EMPTY_FC}>
          <Layer
            id="schools-fill"
            type="circle"
            paint={{
              'circle-radius': 7,
              'circle-color': '#4caf50',
              'circle-opacity': 0.85,
              'circle-stroke-width': 1.5,
              'circle-stroke-color': '#ffffff',
            }}
          />
        </Source>

        {/* === Land Use === */}
        <Source id="landuse" type="geojson" data={EMPTY_FC}>
          <Layer
            id="landuse-fill"
            type="fill"
            paint={{
              'fill-color': [
                'match', ['get', 'landuse'],
                'residential', 'rgba(255, 193, 7, 0.2)',
                'industrial', 'rgba(158, 158, 158, 0.3)',
                'commercial', 'rgba(233, 30, 99, 0.2)',
                'retail', 'rgba(156, 39, 176, 0.2)',
                'farmland', 'rgba(139, 195, 74, 0.2)',
                'forest', 'rgba(56, 142, 60, 0.25)',
                'meadow', 'rgba(174, 213, 129, 0.2)',
                'park', 'rgba(76, 175, 80, 0.2)',
                'quarry', 'rgba(121, 85, 72, 0.3)',
                'rgba(139, 195, 74, 0.15)',
              ],
              'fill-outline-color': 'rgba(139, 195, 74, 0)',
            }}
          />
          <Layer
            id="landuse-outline"
            type="line"
            paint={{ 'line-color': '#8bc34a', 'line-width': 0.5, 'line-opacity': 0.5 }}
          />
        </Source>

        {/* === Flood Zones === */}
        <Source id="flood-zones" type="geojson" data={EMPTY_FC}>
          <Layer
            id="flood_zones-fill"
            type="fill"
            paint={{
              'fill-color': [
                'match', ['get', 'flood_zone'],
                'A', 'rgba(33, 150, 243, 0.35)',
                'B', 'rgba(33, 150, 243, 0.15)',
                'rgba(33, 150, 243, 0.2)',
              ],
              'fill-outline-color': 'rgba(33, 150, 243, 0)',
            }}
          />
          <Layer
            id="flood_zones-outline"
            type="line"
            paint={{
              'line-color': [
                'match', ['get', 'flood_zone'],
                'A', '#1565c0',
                'B', '#64b5f6',
                '#2196f3',
              ],
              'line-width': 1,
            }}
          />
        </Source>

        {/* === NIAH Protected Structures === */}
        <Source id="niah-buildings" type="geojson" data={EMPTY_FC}>
          <Layer
            id="niah_buildings-fill"
            type="circle"
            paint={{
              'circle-radius': 6,
              'circle-color': '#ff9800',
              'circle-opacity': 0.8,
              'circle-stroke-width': 1.5,
              'circle-stroke-color': '#ffffff',
            }}
          />
        </Source>

        {/* === OSM Amenities === */}
        <Source id="osm-amenities" type="geojson" data={EMPTY_FC}>
          <Layer
            id="osm_amenities-fill"
            type="circle"
            paint={{
              'circle-radius': 5,
              'circle-color': '#e91e63',
              'circle-opacity': 0.7,
              'circle-stroke-width': 1,
              'circle-stroke-color': '#ffffff',
            }}
          />
        </Source>

        {/* === OSM Transport === */}
        <Source id="osm-transport" type="geojson" data={EMPTY_FC}>
          <Layer
            id="osm_transport-fill"
            type="circle"
            paint={{
              'circle-radius': 6,
              'circle-color': '#1565c0',
              'circle-opacity': 0.8,
              'circle-stroke-width': 1.5,
              'circle-stroke-color': '#ffffff',
            }}
          />
        </Source>

        {/* === Preview Polygons (regions lighting up during search, colored by hypothesis) === */}
        <Source id="preview-polygons" type="geojson" data={previewPolygonsGeoJSON}>
          <Layer
            id="preview-polygons-fill"
            type="fill"
            paint={{
              'fill-color': ['get', 'color'],
              'fill-opacity': 0.2,
            }}
          />
          <Layer
            id="preview-polygons-outline"
            type="line"
            paint={{
              'line-color': ['get', 'color'],
              'line-width': 2,
              'line-opacity': 0.6,
            }}
          />
          <Layer
            id="preview-polygons-glow"
            type="line"
            paint={{
              'line-color': ['get', 'color'],
              'line-width': 8,
              'line-opacity': 0.1,
              'line-blur': 4,
            }}
          />
        </Source>

        {/* === Preview Points (point results during search) === */}
        <Source id="preview-points" type="geojson" data={previewPointsGeoJSON}>
          <Layer
            id="preview-points-circles"
            type="circle"
            paint={{
              'circle-radius': 7,
              'circle-color': ['get', 'color'],
              'circle-opacity': 0.5,
              'circle-stroke-width': 1.5,
              'circle-stroke-color': ['get', 'color'],
              'circle-stroke-opacity': 0.7,
            }}
          />
        </Source>

        {/* === AI Search Results: All result polygon fills (always visible for browsing) === */}
        <Source id="ai-results-unselected-polys" type="geojson" data={allResultPolygonsGeoJSON}>
          <Layer
            id="ai-unselected-fill"
            type="fill"
            paint={{
              'fill-color': '#3b82f6',
              'fill-opacity': 0.18,
            }}
          />
          <Layer
            id="ai-unselected-outline"
            type="line"
            paint={{
              'line-color': '#3b82f6',
              'line-width': 2,
              'line-opacity': 0.6,
            }}
          />
          <Layer
            id="ai-unselected-glow"
            type="line"
            paint={{
              'line-color': '#3b82f6',
              'line-width': 6,
              'line-opacity': 0.1,
              'line-blur': 4,
            }}
          />
        </Source>

        {/* === AI Search Results: SELECTED polygon highlight === */}
        <Source id="ai-results-selected-poly" type="geojson" data={selectedResultGeoJSON}>
          <Layer
            id="ai-selected-fill"
            type="fill"
            paint={{
              'fill-color': 'rgba(139, 92, 246, 0.25)',
            }}
          />
          <Layer
            id="ai-selected-outline"
            type="line"
            paint={{
              'line-color': '#a78bfa',
              'line-width': 4,
              'line-opacity': 1,
            }}
          />
          <Layer
            id="ai-selected-outline-glow"
            type="line"
            paint={{
              'line-color': '#8b5cf6',
              'line-width': 10,
              'line-opacity': 0.2,
              'line-blur': 6,
            }}
          />
        </Source>

        {/* === AI Search Results: Numbered point markers === */}
        <Source id="ai-search-results" type="geojson" data={searchResultsGeoJSON}>
          <Layer
            id="ai-results-circles"
            type="circle"
            paint={{
              'circle-radius': ['case', ['==', ['get', 'selected'], 1], 16, 10],
              'circle-color': ['case', ['==', ['get', 'selected'], 1], '#8b5cf6', '#3b82f6'],
              'circle-stroke-width': ['case', ['==', ['get', 'selected'], 1], 3, 2],
              'circle-stroke-color': '#ffffff',
              'circle-opacity': ['case', ['==', ['get', 'selected'], 1], 1, 0.85],
            }}
          />
          {/* Glow ring behind selected marker */}
          <Layer
            id="ai-results-selected-ring"
            type="circle"
            filter={['==', ['get', 'selected'], 1]}
            paint={{
              'circle-radius': 24,
              'circle-color': 'transparent',
              'circle-stroke-width': 3,
              'circle-stroke-color': '#8b5cf6',
              'circle-stroke-opacity': 0.4,
            }}
          />
          <Layer
            id="ai-results-labels"
            type="symbol"
            layout={{
              'text-field': ['to-string', ['get', 'rank']],
              'text-size': ['case', ['==', ['get', 'selected'], 1], 13, 11],
              'text-font': ['Open Sans Bold'],
              'text-allow-overlap': true,
              'text-ignore-placement': true,
            }}
            paint={{
              'text-color': '#ffffff',
            }}
          />
        </Source>
      </MapGL>

      {/* Overlay controls */}
      <div className="map-overlays">
        <SearchBar onSelectResult={handleSearchSelect} />
        <LayerPanel visibleLayers={visibleLayers} onToggleLayer={toggleLayer} zoom={viewState.zoom} />
        <BasemapToggle basemap={basemap} onToggle={() => setBasemap((b) => (b === 'map' ? 'satellite' : 'map'))} />
        <ZoomIndicator zoom={viewState.zoom} />
      </div>

      <SiteSearch
        results={siteSearch.results}
        title={siteSearch.title}
        summary={siteSearch.summary}
        followUps={siteSearch.followUps}
        isLoading={siteSearch.isLoading}
        phase={siteSearch.phase}
        phaseMessage={siteSearch.phaseMessage}
        error={siteSearch.error}
        hypothesesCount={siteSearch.hypothesesCount}
        hypothesesNames={siteSearch.hypothesesNames}
        queriesCompleted={siteSearch.queriesCompleted}
        previewPointCount={siteSearch.previewFeatures.length}
        areaFocus={siteSearch.areaFocus}
        selectedIndex={searchSelectedIndex}
        onSearch={handleSiteSearch}
        onClear={handleSearchClear}
        onSelectResult={handleSearchResultSelect}
      />

      <DetailPanel
        type={selectedType}
        properties={selectedProps}
        enrichedData={enrichedData}
        enrichedLoading={enrichedLoading}
        onClose={closeDetail}
      />
    </div>
  );
}
