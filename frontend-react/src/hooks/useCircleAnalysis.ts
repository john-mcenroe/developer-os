import { useState, useCallback, useRef } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface AreaAnalysis {
  area_name: string;
  overview: string;
  market_summary: string;
  development_potential: string;
  risk_factors: string;
  key_opportunities: string[];
  follow_ups: { label: string; prompt: string }[];
}

export interface CircleAnalysisState {
  isAnalyzing: boolean;
  analysis: AreaAnalysis | null;
  context: string[];
  center: { lng: number; lat: number } | null;
  radius: number;
  phase: string;
  error: string | null;
}

export function useCircleAnalysis() {
  const [state, setState] = useState<CircleAnalysisState>({
    isAnalyzing: false,
    analysis: null,
    context: [],
    center: null,
    radius: 0,
    phase: '',
    error: null,
  });

  const abortRef = useRef<AbortController | null>(null);

  const analyze = useCallback(async (lng: number, lat: number, radius: number, query = '') => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState({
      isAnalyzing: true,
      analysis: null,
      context: [],
      center: { lng, lat },
      radius,
      phase: 'Gathering area data...',
      error: null,
    });

    try {
      const resp = await fetch(`${API_BASE}/api/ai/area_analysis`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lng, lat, radius, query }),
        signal: controller.signal,
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      if (!resp.body) throw new Error('No response body');

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let eventType = '';
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ') && eventType) {
            try {
              const data = JSON.parse(line.slice(6));
              if (eventType === 'status') {
                setState(s => ({ ...s, phase: data.message || '' }));
              } else if (eventType === 'area_analysis') {
                setState(s => ({
                  ...s,
                  analysis: data.analysis,
                  context: data.context || [],
                  center: data.center,
                  radius: data.radius,
                }));
              } else if (eventType === 'done') {
                setState(s => ({ ...s, isAnalyzing: false, phase: '' }));
              }
            } catch { /* skip malformed */ }
            eventType = '';
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setState(s => ({
          ...s,
          isAnalyzing: false,
          error: (err as Error).message,
          phase: '',
        }));
      }
    }
  }, []);

  const clear = useCallback(() => {
    abortRef.current?.abort();
    setState({
      isAnalyzing: false,
      analysis: null,
      context: [],
      center: null,
      radius: 0,
      phase: '',
      error: null,
    });
  }, []);

  return { ...state, analyze, clear };
}
