import type { CircleAnalysisState } from '../hooks/useCircleAnalysis';

interface AreaAnalysisPanelProps {
  state: CircleAnalysisState;
  onFollowUp: (query: string) => void;
  onClose: () => void;
}

export function AreaAnalysisPanel({ state, onFollowUp, onClose }: AreaAnalysisPanelProps) {
  const { isAnalyzing, analysis, phase, error } = state;

  if (!isAnalyzing && !analysis && !error) return null;

  return (
    <div className="area-analysis-panel">
      {/* Header */}
      <div className="aap-header">
        <div className="aap-title-row">
          <span className="aap-icon">◎</span>
          <h3 className="aap-title">
            {analysis?.area_name || 'Area Analysis'}
          </h3>
          <span className="aap-radius">
            {state.radius ? `${Math.round(state.radius)}m radius` : ''}
          </span>
          <button className="aap-close" onClick={onClose} aria-label="Close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      </div>

      {/* Loading */}
      {isAnalyzing && (
        <div className="aap-loading">
          <span className="aap-spinner" />
          <span>{phase}</span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="aap-error">Error: {error}</div>
      )}

      {/* Analysis content */}
      {analysis && (
        <div className="aap-body">
          {/* Overview */}
          <div className="aap-section">
            <div className="aap-section-title">Overview</div>
            <p className="aap-text">{analysis.overview}</p>
          </div>

          {/* Market */}
          <div className="aap-section">
            <div className="aap-section-title">Market Summary</div>
            <p className="aap-text">{analysis.market_summary}</p>
          </div>

          {/* Development */}
          <div className="aap-section">
            <div className="aap-section-title">Development Potential</div>
            <p className="aap-text">{analysis.development_potential}</p>
          </div>

          {/* Risks */}
          <div className="aap-section">
            <div className="aap-section-title">Risk Factors</div>
            <p className="aap-text">{analysis.risk_factors}</p>
          </div>

          {/* Opportunities */}
          {analysis.key_opportunities && analysis.key_opportunities.length > 0 && (
            <div className="aap-section">
              <div className="aap-section-title">Key Opportunities</div>
              <ul className="aap-opportunities">
                {analysis.key_opportunities.map((opp, i) => (
                  <li key={i}>{opp}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Follow-ups */}
          {analysis.follow_ups && analysis.follow_ups.length > 0 && (
            <div className="aap-follow-ups">
              {analysis.follow_ups.map((f, i) => (
                <button
                  key={i}
                  className="aap-follow-up-chip"
                  onClick={() => onFollowUp(f.prompt)}
                >
                  {f.label}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
