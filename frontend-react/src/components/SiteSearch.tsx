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
  const [expanded, setExpanded] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Cycle placeholder text
  useEffect(() => {
    const interval = setInterval(() => {
      setPlaceholderIdx(i => (i + 1) % PLACEHOLDER_PROMPTS.length);
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  // Auto-expand when results arrive
  useEffect(() => {
    if (results.length > 0) setExpanded(true);
  }, [results.length]);

  // Scroll selected item into view
  useEffect(() => {
    if (selectedIndex != null && listRef.current) {
      const items = listRef.current.querySelectorAll('.search-result-item');
      items[selectedIndex]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [selectedIndex]);

  // Keyboard nav
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (results.length === 0) return;
      if (e.key === 'ArrowUp' && selectedIndex != null && selectedIndex > 0) {
        onSelectResult(results[selectedIndex - 1], selectedIndex - 1);
        e.preventDefault();
      } else if (e.key === 'ArrowDown') {
        const next = selectedIndex == null ? 0 : Math.min(selectedIndex + 1, results.length - 1);
        onSelectResult(results[next], next);
        e.preventDefault();
      } else if (e.key === 'Escape') {
        if (expanded && results.length > 0) {
          setExpanded(false);
        } else {
          onClear();
        }
        e.preventDefault();
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [results, selectedIndex, expanded, onSelectResult, onClear]);

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isLoading) return;
    setExpanded(true);
    onSearch(query.trim());
  }, [query, isLoading, onSearch]);

  const handleFollowUp = useCallback((prompt: string) => {
    setQuery(prompt);
    setExpanded(true);
    onSearch(prompt);
  }, [onSearch]);

  const hasResults = results.length > 0;
  const showPanel = (hasResults || isLoading) && expanded;

  return (
    <div className="site-search">
      {/* Expandable Results Panel — grows upward */}
      {showPanel && (
        <div className="search-results-panel">
          {/* Header */}
          {hasResults && (
            <div className="search-results-header">
              <div className="search-results-title-row">
                <h3 className="search-results-title">{title}</h3>
                <span className="search-results-badge">{results.length} sites</span>
                <button
                  className="search-results-toggle"
                  onClick={() => setExpanded(false)}
                  aria-label="Collapse"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </button>
              </div>
              {summary && <p className="search-results-summary">{summary}</p>}
            </div>
          )}

          {/* Loading state */}
          {isLoading && !hasResults && (
            <div className="search-loading">
              <div className="search-loading-header">
                <span className="search-loading-dot" />
                <span className="search-loading-text">{phaseMessage}</span>
              </div>
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
                <div className="search-loading-skeleton">
                  {[1, 2, 3].map(i => (
                    <div key={i} className="skeleton-row">
                      <div className="skeleton-circle" />
                      <div className="skeleton-lines">
                        <div className="skeleton-bar wide" />
                        <div className="skeleton-bar" />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="search-results-error">
              <span className="search-error-badge">!</span>
              {error}
            </div>
          )}

          {/* Scrollable result list */}
          {hasResults && (
            <div className="search-results-list" ref={listRef}>
              {results.map((r, i) => (
                <SearchResultItem
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
            <div className="search-follow-ups">
              {followUps.slice(0, 3).map((f, i) => (
                <button key={i} className="follow-up-chip" onClick={() => handleFollowUp(f.prompt)}>
                  {f.label}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Collapsed mini-bar */}
      {hasResults && !expanded && (
        <button className="search-collapsed-bar" onClick={() => setExpanded(true)}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="6 15 12 9 18 15" />
          </svg>
          <span>{results.length} results — {title}</span>
        </button>
      )}

      {/* Search Bar (always at bottom) */}
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

/* ── Result Row Item ──────────────────────────────────────────────────── */

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

function getMetricChips(r: SiteSearchResult): { label: string; value: string }[] {
  const m: { label: string; value: string }[] = [];
  if (r.sale_price) m.push({ label: 'Price', value: `€${Number(r.sale_price).toLocaleString()}` });
  if (r.area_sqm) m.push({ label: 'Area', value: formatArea(Number(r.area_sqm)) });
  if (r.site_area) m.push({ label: 'Area', value: formatArea(Number(r.site_area)) });
  if (r.price_per_sqm) m.push({ label: '€/m²', value: `€${Number(r.price_per_sqm).toLocaleString()}` });
  if (r.total_population) m.push({ label: 'Pop', value: Number(r.total_population).toLocaleString() });
  if (r.vacancy_rate != null) m.push({ label: 'Vacancy', value: `${r.vacancy_rate}%` });
  return m.slice(0, 3);
}

function SearchResultItem({ result, index, isSelected, onClick }: {
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
  const metrics = getMetricChips(result);

  return (
    <div
      className={`search-result-item ${isSelected ? 'selected' : ''}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && onClick()}
    >
      {/* Rank circle */}
      <div className="sri-rank" style={{ borderColor: scoreColor, color: scoreColor }}>
        {index + 1}
      </div>

      {/* Main content */}
      <div className="sri-body">
        <div className="sri-top-row">
          <span className="sri-title">{title}</span>
          <span className="sri-tag" style={{ color: tagColor, borderColor: tagColor }}>{tagLabel}</span>
        </div>

        {/* Metrics row */}
        {metrics.length > 0 && (
          <div className="sri-metrics">
            {metrics.map((m, i) => (
              <span key={i} className="sri-metric">
                <strong>{m.value}</strong> {m.label}
              </span>
            ))}
          </div>
        )}

        {/* Reason */}
        {result.opportunity_reason && (
          <div className="sri-reason">{result.opportunity_reason}</div>
        )}
      </div>

      {/* Score */}
      <div className="sri-score" style={{ color: scoreColor }}>
        {score}
      </div>
    </div>
  );
}
