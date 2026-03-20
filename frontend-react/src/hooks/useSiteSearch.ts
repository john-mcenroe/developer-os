import { useCallback, useRef, useState } from 'react';
import { API_BASE } from '../config/layers';
import type { SiteSearchResult, SiteSearchResponse, SearchPhase, PreviewFeature, AreaFocus } from '../types';

export interface SiteSearchState {
  phase: SearchPhase;
  phaseMessage: string;
  results: SiteSearchResult[];
  title: string;
  summary: string;
  followUps: { label: string; prompt: string }[];
  error: string | null;
  hypothesesCount: number;
  hypothesesNames: string[];
  queriesCompleted: number;
  activeHypotheses: Set<number>;
  completedHypotheses: Set<number>;
  previewFeatures: PreviewFeature[];
  areaFocus: AreaFocus | null;
}

const INITIAL_STATE: SiteSearchState = {
  phase: 'idle',
  phaseMessage: '',
  results: [],
  title: '',
  summary: '',
  followUps: [],
  error: null,
  hypothesesCount: 0,
  hypothesesNames: [],
  queriesCompleted: 0,
  activeHypotheses: new Set(),
  completedHypotheses: new Set(),
  previewFeatures: [],
  areaFocus: null,
};

export function useSiteSearch() {
  const [state, setState] = useState<SiteSearchState>(INITIAL_STATE);
  const abortRef = useRef<AbortController | null>(null);

  const search = useCallback(async (
    query: string,
    viewport?: { sw: [number, number]; ne: [number, number] },
    zoom?: number,
    activeLayers?: string[],
  ) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState({
      ...INITIAL_STATE,
      phase: 'routing',
      phaseMessage: 'Analyzing your query...',
    });

    try {
      const body = {
        messages: [{ role: 'user', content: query }],
        map_context: viewport ? {
          viewport: { sw: viewport.sw, ne: viewport.ne },
          zoom: zoom ?? 13,
          active_layers: activeLayers ?? [],
        } : null,
      };

      const resp = await fetch(`${API_BASE}/api/ai/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!resp.ok) {
        const err = await resp.text();
        setState(s => ({ ...s, phase: 'error', error: `API error: ${err.slice(0, 200)}` }));
        return;
      }

      const reader = resp.body?.getReader();
      if (!reader) {
        setState(s => ({ ...s, phase: 'error', error: 'No response stream' }));
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      // SSE format: "event: <type>\ndata: <json>\n\n"
      // Events are separated by double newlines.
      // The data line for the result event can be very large (200KB+),
      // so we must accumulate the buffer until we see "\n\n".
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete events (delimited by \n\n)
        let boundary: number;
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
          const eventBlock = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);

          // Parse the event block
          let eventType = '';
          let dataStr = '';
          for (const line of eventBlock.split('\n')) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith('data: ')) {
              dataStr = line.slice(6);
            }
          }

          if (eventType && dataStr) {
            try {
              const data = JSON.parse(dataStr);
              processEvent(eventType, data, setState);
            } catch {
              // Skip malformed JSON — may happen on partial chunks
            }
          }
        }
      }

      // Process any remaining buffer
      if (buffer.trim()) {
        let eventType = '';
        let dataStr = '';
        for (const line of buffer.split('\n')) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            dataStr = line.slice(6);
          }
        }
        if (eventType && dataStr) {
          try {
            const data = JSON.parse(dataStr);
            processEvent(eventType, data, setState);
          } catch { /* skip */ }
        }
      }

    } catch (e) {
      if ((e as Error).name === 'AbortError') return;
      setState(s => ({
        ...s,
        phase: 'error',
        error: e instanceof Error ? e.message : 'Search failed',
      }));
    }
  }, []);

  const clear = useCallback(() => {
    abortRef.current?.abort();
    setState(INITIAL_STATE);
  }, []);

  return {
    ...state,
    isLoading: !['idle', 'done', 'error'].includes(state.phase),
    search,
    clear,
  };
}

function processEvent(
  event: string,
  data: Record<string, unknown>,
  setState: React.Dispatch<React.SetStateAction<SiteSearchState>>,
) {
  switch (event) {
    case 'status': {
      const phase = data.phase as string;
      setState(s => ({
        ...s,
        phase: (phase as SearchPhase) || s.phase,
        phaseMessage: (data.message as string) || s.phaseMessage,
      }));
      break;
    }

    case 'area_focus':
      setState(s => ({
        ...s,
        areaFocus: {
          area: data.area as string,
          lat: data.lat as number,
          lng: data.lng as number,
          bbox: data.bbox as [string, string, string, string] | undefined,
        },
        phaseMessage: `Focusing on ${data.area}...`,
      }));
      break;

    case 'hypotheses':
      setState(s => ({
        ...s,
        hypothesesCount: (data.count as number) || 0,
        hypothesesNames: (data.names as string[]) || [],
        phaseMessage: `${data.count} hypotheses — testing in parallel...`,
      }));
      break;

    case 'hypothesis_start': {
      const hIdx = data.hypothesis_index as number;
      setState(s => {
        const active = new Set(s.activeHypotheses);
        active.add(hIdx);
        return {
          ...s,
          activeHypotheses: active,
          phaseMessage: `Testing: ${data.hypothesis_name as string}...`,
        };
      });
      break;
    }

    case 'query_complete': {
      const rawFeatures = (data.preview_features as Array<GeoJSON.Geometry>) || [];
      const hypIdx = (data.hypothesis_index as number) ?? 0;
      const hypName = (data.hypothesis_name as string) || '';
      const rowCount = (data.row_count as number) || 0;

      // Tag each preview geometry with its hypothesis
      const taggedFeatures: PreviewFeature[] = rawFeatures
        .filter(g => g && g.type)
        .map(geom => ({
          geometry: geom,
          hypothesisIndex: hypIdx,
          hypothesisName: hypName,
        }));

      setState(s => {
        const completed = new Set(s.completedHypotheses);
        completed.add(hypIdx);
        const active = new Set(s.activeHypotheses);
        active.delete(hypIdx);
        return {
          ...s,
          queriesCompleted: completed.size,
          completedHypotheses: completed,
          activeHypotheses: active,
          previewFeatures: [...s.previewFeatures, ...taggedFeatures],
          phaseMessage: hypName
            ? `${hypName} — found ${rowCount} site${rowCount !== 1 ? 's' : ''}`
            : `${completed.size}/${s.hypothesesCount} strategies complete`,
        };
      });
      break;
    }

    case 'tool_action':
      setState(s => ({
        ...s,
        phaseMessage: (data.message as string)
          || `${data.action === 'sql_broaden' ? 'Broadening' : 'Refining'}: ${(data.hypothesis as string) || ''}`.slice(0, 80),
      }));
      break;

    case 'result': {
      const r = data as unknown as SiteSearchResponse;
      // Strip heavy geometry from results to keep state lean
      const results = (r.results || []).map(res => ({
        ...res,
        geometry: res.geometry ? simplifyGeometry(res.geometry) : undefined,
      }));
      setState(s => ({
        ...s,
        phase: 'done',
        phaseMessage: '',
        results,
        previewFeatures: [], // Clear ghost markers — real ones take over
        title: r.title || 'Results',
        summary: r.summary || '',
        followUps: r.follow_ups || [],
      }));
      break;
    }

    case 'error':
      setState(s => ({
        ...s,
        phase: 'error',
        error: (data.message as string) || 'Unknown error',
        phaseMessage: '',
        previewFeatures: [],
      }));
      break;

    case 'done':
      setState(s => {
        if (s.phase !== 'done' && s.phase !== 'error') {
          return { ...s, phase: s.results.length > 0 ? 'done' : 'error', error: s.results.length > 0 ? null : 'No results found — try a more specific query', previewFeatures: [] };
        }
        return s;
      });
      break;
  }
}

/**
 * Simplify polygon geometry to reduce state size.
 * Keep only the first ring and downsample coordinates.
 */
function simplifyGeometry(geom: GeoJSON.Geometry): GeoJSON.Geometry {
  if (geom.type === 'Polygon' && geom.coordinates?.[0]) {
    const ring = geom.coordinates[0];
    if (ring.length > 50) {
      // Downsample: keep every Nth point + last point
      const step = Math.ceil(ring.length / 50);
      const simplified = ring.filter((_, i) => i % step === 0 || i === ring.length - 1);
      return { type: 'Polygon', coordinates: [simplified] };
    }
  }
  if (geom.type === 'MultiPolygon') {
    return {
      type: 'MultiPolygon',
      coordinates: geom.coordinates.map(poly => {
        const ring = poly[0];
        if (ring && ring.length > 50) {
          const step = Math.ceil(ring.length / 50);
          return [ring.filter((_, i) => i % step === 0 || i === ring.length - 1)];
        }
        return poly;
      }),
    };
  }
  return geom;
}
