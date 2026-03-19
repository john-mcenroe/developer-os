import { useCallback, useRef, useState } from 'react';
import { API_BASE } from '../config/layers';
import type { SiteSearchResult, SiteSearchResponse, SearchPhase } from '../types';

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
      // More descriptive messages for the user
      const descriptions: Record<string, string> = {
        routing: 'Analyzing your query...',
        hypotheses: 'Generating search strategies...',
        executing: 'Querying spatial database...',
        ranking: 'Scoring & ranking results...',
        responding: 'Preparing response...',
        querying: 'Running analysis...',
      };
      setState(s => ({
        ...s,
        phase: (phase as SearchPhase) || s.phase,
        phaseMessage: descriptions[phase] || (data.message as string) || s.phaseMessage,
      }));
      break;
    }

    case 'hypotheses':
      setState(s => ({
        ...s,
        hypothesesCount: (data.count as number) || 0,
        hypothesesNames: (data.names as string[]) || [],
        phaseMessage: `Testing ${data.count} search strategies...`,
      }));
      break;

    case 'query_complete':
      setState(s => {
        const completed = s.queriesCompleted + 1;
        const total = s.hypothesesCount;
        return {
          ...s,
          queriesCompleted: completed,
          phaseMessage: `Querying database... (${completed}/${total} strategies tested)`,
        };
      });
      break;

    case 'tool_action':
      setState(s => ({
        ...s,
        phaseMessage: `${data.action === 'sql_broaden' ? 'Broadening' : 'Testing'}: ${(data.hypothesis as string) || ''}`.slice(0, 60),
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
      }));
      break;

    case 'done':
      setState(s => {
        if (s.phase !== 'done' && s.phase !== 'error') {
          // If we got done but never got result, that's fine for non-site_search intents
          return { ...s, phase: s.results.length > 0 ? 'done' : 'error', error: s.results.length > 0 ? null : 'No results found — try a more specific query' };
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
