import { useState, useRef, useEffect } from 'react';
import { useSearch } from '../hooks/useMapData';

interface SearchBarProps {
  onSelectResult: (lng: number, lat: number, name: string) => void;
}

export function SearchBar({ onSelectResult }: SearchBarProps) {
  const [query, setQuery] = useState('');
  const [showResults, setShowResults] = useState(false);
  const { results, loading, search, clearResults } = useSearch();
  const inputRef = useRef<HTMLInputElement>(null!);
  const containerRef = useRef<HTMLDivElement>(null!);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowResults(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleInput = (value: string) => {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (value.trim().length < 2) {
      clearResults();
      setShowResults(false);
      return;
    }
    debounceRef.current = setTimeout(() => {
      search(value);
      setShowResults(true);
    }, 300);
  };

  const handleSelect = (result: { lat: string; lon: string; display_name: string }) => {
    onSelectResult(parseFloat(result.lon), parseFloat(result.lat), result.display_name);
    setQuery(result.display_name.split(',')[0]);
    setShowResults(false);
    clearResults();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setShowResults(false);
      inputRef.current?.blur();
    }
    if (e.key === 'Enter' && query.trim()) {
      search(query);
      setShowResults(true);
    }
  };

  return (
    <div className="search-bar" ref={containerRef}>
      <svg className="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => handleInput(e.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={() => results.length > 0 && setShowResults(true)}
        placeholder="Search Dublin... e.g. Stoneybatter, D7"
        className="search-input"
      />
      {loading && <span className="search-spinner" />}

      {showResults && results.length > 0 && (
        <ul className="search-results" onMouseDown={(e) => e.preventDefault()}>
          {results.slice(0, 6).map((r, i) => (
            <li key={i} className="search-result-item" onClick={() => handleSelect(r)}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                <circle cx="12" cy="10" r="3" />
              </svg>
              <span>{r.display_name}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
