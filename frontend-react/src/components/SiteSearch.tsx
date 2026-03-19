import { useCallback, useEffect, useRef, useState } from 'react';
import type { SiteSearchResult } from '../types';

const PLACEHOLDER_PROMPTS = [
  'Find large sites near DART stations with RZLT tax pressure...',
  'Undervalued areas with high vacancy rates in South Dublin...',
  'Sites over 1 acre with recent planning permissions granted...',
  'Areas where sale prices are below census median income...',
  'RZLT sites near schools with low development density...',
];

interface SiteSearchProps {
  results: SiteSearchResult[];
  title: string;
  summary: string;
  followUps: { label: string; prompt: string }[];
  isLoading: boolean;
  phase: string;
  phaseMessage: string;
  error: string | null;
  hypothesesCount: number;
  hypothesesNames: string[];
  queriesCompleted: number;
  selectedIndex: number | null;
  onSearch: (query: string) => void;
  onClear: () => void;
  onSelectResult: (result: SiteSearchResult, index: number) => void;
}

export function SiteSearch({
  results,
  title,
  summary,
  followUps,
  isLoading,
  phase,
  phaseMessage,
  error,
  hypothesesCount,
  hypothesesNames,
  queriesCompleted,
  selectedIndex,
  onSearch,
  onClear,
  onSelectResult,
}: SiteSearchProps) {
  const [query, setQuery] = useState('');
  const [placeholderIdx, setPlaceholderIdx] = useState(0);
  const [collapsed, setCollapsed] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Cycle placeholder text
  useEffect(() => {
    const interval = setInterval(() => {
      setPlaceholderIdx(i => (i + 1) % PLACEHOLDER_PROMPTS.length);
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  // Scroll selected card into view
  useEffect(() => {
    if (selectedIndex != null && scrollRef.current) {
      const cards = scrollRef.current.querySelectorAll('.result-card');
      cards[selectedIndex]?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
    }
  }, [selectedIndex]);

  // Keyboard nav
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (results.length === 0) return;
      if (e.key === 'ArrowLeft' && selectedIndex != null && selectedIndex > 0) {
        onSelectResult(results[selectedIndex - 1], selectedIndex - 1);
        e.preventDefault();
      } else if (e.key === 'ArrowRight' && selectedIndex != null && selectedIndex < results.length - 1) {
        onSelectResult(results[selectedIndex + 1], selectedIndex + 1);
        e.preventDefault();
      } else if (e.key === 'Escape') {
        if (results.length > 0) {
          setCollapsed(c => !c);
        } else {
          onClear();
        }
        e.preventDefault();
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [results, selectedIndex, onSelectResult, onClear]);

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isLoading) return;
    setCollapsed(false);
    onSearch(query.trim());
  }, [query, isLoading, onSearch]);

  const handleFollowUp = useCallback((prompt: string) => {
    setQuery(prompt);
    setCollapsed(false);
    onSearch(prompt);
  }, [onSearch]);

  const hasResults = results.length > 0;
  const showTray = (hasResults || isLoading) && !collapsed;

  return (
    <div className="site-search">
      {/* Results Tray */}
      {showTray && (
        <div className="results-tray">
          {/* Header */}
          {hasResults && (
            <div className="results-tray-header">
              <div className="results-tray-title-row">
                <h3 className="results-tray-title">{title}</h3>
                <span className="results-tray-count">{results.length} sites</span>
                <button className="results-tray-collapse" onClick={() => setCollapsed(true)} aria-label="Collapse results">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="6 15 12 9 18 15" />
                  </svg>
                </button>
              </div>
              {summary && <p className="results-tray-summary">{summary}</p>}
            </div>
          )}

          {/* Loading skeleton */}
          {isLoading && !hasResults && (
            <div className="results-tray-loading">
              <div className="search-phase-indicator">
                <span className="search-phase-dot" />
                <span className="search-phase-text">{phaseMessage}</span>
              </div>
              {/* Show hypothesis names as they arrive */}
              {hypothesesNames.length > 0 && (
                <div className="search-strategies">
                  {hypothesesNames.map((name, i) => (
                    <div key={i} className={`search-strategy ${i < queriesCompleted ? 'done' : i === queriesCompleted ? 'active' : ''}`}>
                      <span className="search-strategy-icon">
                        {i < queriesCompleted ? '✓' : i === queriesCompleted ? '⟳' : '○'}
                      </span>
                      <span className="search-strategy-name">{name}</span>
                    </div>
                  ))}
                </div>
              )}
              {hypothesesNames.length === 0 && (
                <div className="results-skeleton-row">
                  {[1, 2, 3, 4].map(i => (
                    <div key={i} className="result-card-skeleton">
                      <div className="skeleton-bar wide" />
                      <div className="skeleton-bar" />
                      <div className="skeleton-bar narrow" />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="results-tray-error">
              <span className="results-error-icon">!</span>
              {error}
            </div>
          )}

          {/* Cards */}
          {hasResults && (
            <div className="results-tray-scroll" ref={scrollRef}>
              {results.map((r, i) => (
                <ResultCard
                  key={`${r._rank}-${r.lng}-${r.lat}`}
                  result={r}
                  index={i}
                  isSelected={selectedIndex === i}
                  onClick={() => onSelectResult(r, i)}
                />
              ))}
            </div>
          )}

          {/* Follow-ups */}
          {hasResults && followUps.length > 0 && (
            <div className="results-follow-ups">
              {followUps.slice(0, 3).map((f, i) => (
                <button key={i} className="follow-up-chip" onClick={() => handleFollowUp(f.prompt)}>
                  {f.label}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Collapsed bar showing result count */}
      {hasResults && collapsed && (
        <button className="results-collapsed-bar" onClick={() => setCollapsed(false)}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="6 9 12 15 18 9" />
          </svg>
          <span>{results.length} results — {title}</span>
        </button>
      )}

      {/* Search Bar */}
      <form className="site-search-bar" onSubmit={handleSubmit}>
        <div className="site-search-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
        </div>
        <input
          ref={inputRef}
          type="text"
          className="site-search-input"
          placeholder={PLACEHOLDER_PROMPTS[placeholderIdx]}
          value={query}
          onChange={e => setQuery(e.target.value)}
          disabled={isLoading}
        />
        {isLoading && (
          <div className="site-search-loading">
            <span className="site-search-spinner" />
            <span className="site-search-phase-label">{phaseMessage}</span>
          </div>
        )}
        {!isLoading && query && (
          <button type="button" className="site-search-clear" onClick={() => { setQuery(''); onClear(); }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        )}
        <button
          type="submit"
          className="site-search-submit"
          disabled={isLoading || !query.trim()}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </form>
    </div>
  );
}

/* ── Result Card ───────────────────────────────────────────────────────── */

const TABLE_LABELS: Record<string, string> = {
  sold_properties: 'Sale',
  cadastral_freehold: 'Freehold',
  cadastral_leasehold: 'Leasehold',
  rzlt: 'RZLT',
  dlr_planning_polygons: 'Planning',
  dlr_planning_points: 'Planning',
  census_small_areas: 'Census',
  side_sites: 'Side Site',
};

const TABLE_COLORS: Record<string, string> = {
  sold_properties: '#e74c3c',
  cadastral_freehold: '#ff8c00',
  cadastral_leasehold: '#6495ed',
  rzlt: '#ef4444',
  dlr_planning_polygons: '#2ecc71',
  dlr_planning_points: '#2ecc71',
  census_small_areas: '#00bcd4',
  side_sites: '#f9a825',
};

function getResultTitle(r: SiteSearchResult): string {
  if (r.address) return String(r.address).split(',').slice(0, 2).join(', ');
  if (r.plan_ref) return String(r.plan_ref);
  if (r.zone_desc) return String(r.zone_desc);
  if (r.national_ref) return `Parcel ${r.national_ref}`;
  if (r.nationalcadastralreference) return `Parcel ${r.nationalcadastralreference}`;
  if (r.sa_code) return `Area ${r.sa_code}`;
  if (r.urban_area) return String(r.urban_area);
  if (r.county) return String(r.county);
  return `Site #${(r._rank ?? 0) + 1}`;
}

function formatArea(sqm: number): string {
  if (sqm >= 10000) return `${(sqm / 10000).toFixed(1)} ha`;
  return `${Math.round(sqm).toLocaleString()} m²`;
}

function getResultMetrics(r: SiteSearchResult): { label: string; value: string }[] {
  const metrics: { label: string; value: string }[] = [];
  if (r.sale_price) metrics.push({ label: 'Price', value: `€${Number(r.sale_price).toLocaleString()}` });
  if (r.area_sqm) metrics.push({ label: 'Area', value: formatArea(Number(r.area_sqm)) });
  if (r.site_area) metrics.push({ label: 'Area', value: formatArea(Number(r.site_area)) });
  if (r.area_acres) metrics.push({ label: 'Acres', value: `${r.area_acres} ac` });
  if (r.price_per_sqm) metrics.push({ label: '€/m²', value: `€${Number(r.price_per_sqm).toLocaleString()}` });
  if (r.total_population) metrics.push({ label: 'Pop', value: Number(r.total_population).toLocaleString() });
  if (r.vacancy_rate != null) metrics.push({ label: 'Vacancy', value: `${r.vacancy_rate}%` });
  if (r.descrptn && metrics.length === 0) metrics.push({ label: 'Type', value: String(r.descrptn).slice(0, 25) });
  return metrics.slice(0, 3);
}

function ResultCard({ result, index, isSelected, onClick }: {
  result: SiteSearchResult;
  index: number;
  isSelected: boolean;
  onClick: () => void;
}) {
  const rawScore = result._score || 0;
  const score = rawScore > 1 ? Math.round(rawScore) : Math.round(rawScore * 100);
  const scoreColor = score >= 70 ? '#22c55e' : score >= 50 ? '#f59e0b' : '#ef4444';
  const table = result._table || '';
  const tagLabel = TABLE_LABELS[table] || table;
  const tagColor = TABLE_COLORS[table] || '#6b7394';
  const title = getResultTitle(result);
  const metrics = getResultMetrics(result);

  return (
    <div
      className={`result-card ${isSelected ? 'selected' : ''}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && onClick()}
    >
      {/* Score bar */}
      <div className="result-card-score-bar">
        <div className="result-card-score-fill" style={{ width: `${score}%`, backgroundColor: scoreColor }} />
      </div>

      <div className="result-card-content">
        {/* Rank + Tag row */}
        <div className="result-card-top">
          <span className="result-card-rank" style={{ borderColor: scoreColor, color: scoreColor }}>
            {index + 1}
          </span>
          <span className="result-card-tag" style={{ color: tagColor, borderColor: tagColor }}>
            {tagLabel}
          </span>
          <span className="result-card-score" style={{ color: scoreColor }}>
            {score}
          </span>
        </div>

        {/* Title */}
        <div className="result-card-title">{title}</div>

        {/* Metrics */}
        {metrics.length > 0 && (
          <div className="result-card-metrics">
            {metrics.map((m, i) => (
              <div key={i} className="result-card-metric">
                <span className="result-card-metric-value">{m.value}</span>
                <span className="result-card-metric-label">{m.label}</span>
              </div>
            ))}
          </div>
        )}

        {/* Opportunity reason */}
        {result.opportunity_reason && (
          <div className="result-card-reason">{result.opportunity_reason}</div>
        )}
      </div>
    </div>
  );
}
