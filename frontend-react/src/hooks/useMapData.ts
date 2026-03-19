import { useCallback, useRef, useState } from 'react';
import { API_BASE, LAYER_CONFIGS } from '../config/layers';
import type { BBox, EnrichedParcel, SearchResult } from '../types';
import type { MapRef } from 'react-map-gl/maplibre';

const EMPTY_FC: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] };

export function useMapData(
  mapRef: React.RefObject<MapRef | null>,
  visibleLayers: Set<string>,
  zoom: number
) {
  const loadTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const getBBox = useCallback((): BBox | null => {
    const map = mapRef.current?.getMap();
    if (!map) return null;
    const bounds = map.getBounds();
    if (!bounds) return null;
    return {
      west: bounds.getWest(),
      south: bounds.getSouth(),
      east: bounds.getEast(),
      north: bounds.getNorth(),
    };
  }, [mapRef]);

  const fetchLayer = useCallback(
    async (endpoint: string, bbox: BBox, signal: AbortSignal) => {
      const bboxStr = `${bbox.west.toFixed(6)},${bbox.south.toFixed(6)},${bbox.east.toFixed(6)},${bbox.north.toFixed(6)}`;
      const res = await fetch(`${API_BASE}${endpoint}?bbox=${bboxStr}`, { signal });
      if (!res.ok) throw new Error(`Failed to fetch ${endpoint}`);
      return res.json();
    },
    []
  );

  const loadAllLayers = useCallback(() => {
    const map = mapRef.current?.getMap();
    if (!map) return;

    const bbox = getBBox();
    if (!bbox) return;

    // Abort previous in-flight requests
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    for (const layer of LAYER_CONFIGS) {
      const source = map.getSource(layer.sourceId);
      if (!source) continue;

      const isVisible = visibleLayers.has(layer.id);
      if (!isVisible) {
        (source as maplibregl.GeoJSONSource).setData(EMPTY_FC);
        continue;
      }

      if (zoom < layer.minZoom) {
        (source as maplibregl.GeoJSONSource).setData(EMPTY_FC);
        continue;
      }

      fetchLayer(layer.endpoint, bbox, controller.signal)
        .then((geojson) => {
          const src = map.getSource(layer.sourceId) as maplibregl.GeoJSONSource | undefined;
          if (src) src.setData(geojson);
        })
        .catch((err) => {
          if (err.name !== 'AbortError') {
            console.error(`Failed to load ${layer.id}:`, err);
          }
        });
    }
  }, [mapRef, getBBox, fetchLayer, visibleLayers, zoom]);

  const scheduleLoad = useCallback(() => {
    if (loadTimerRef.current) clearTimeout(loadTimerRef.current);
    loadTimerRef.current = setTimeout(loadAllLayers, 200);
  }, [loadAllLayers]);

  return { loadAllLayers, scheduleLoad };
}

export function useEnrichedParcel() {
  const [data, setData] = useState<EnrichedParcel | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchEnriched = useCallback(async (parcelId: number, parcelType: string) => {
    setLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/parcel/${parcelId}/enriched?parcel_type=${parcelType}`
      );
      if (!res.ok) throw new Error('Failed to fetch enriched data');
      const json = await res.json();
      setData(json);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const clear = useCallback(() => setData(null), []);

  return { data, loading, fetchEnriched, clear };
}

export function useSearch() {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);

  const search = useCallback(async (query: string) => {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(query)}`);
      const json = await res.json();
      const raw = Array.isArray(json) ? json : json.results || [];
      // Normalize: API returns `lng`, search expects `lon`
      setResults(raw.map((r: Record<string, unknown>) => ({
        ...r,
        lon: r.lon ?? r.lng,
        lat: r.lat,
        display_name: r.display_name,
      })));
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const clearResults = useCallback(() => setResults([]), []);

  return { results, loading, search, clearResults };
}
