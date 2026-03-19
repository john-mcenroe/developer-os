interface BasemapToggleProps {
  basemap: 'map' | 'satellite';
  onToggle: () => void;
}

export function BasemapToggle({ basemap, onToggle }: BasemapToggleProps) {
  return (
    <button className="basemap-toggle" onClick={onToggle} title="Switch basemap">
      {basemap === 'map' ? (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
        </svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
          <line x1="8" y1="2" x2="8" y2="18" /><line x1="16" y1="6" x2="16" y2="22" />
        </svg>
      )}
      <span>{basemap === 'map' ? 'Satellite' : 'Map'}</span>
    </button>
  );
}
