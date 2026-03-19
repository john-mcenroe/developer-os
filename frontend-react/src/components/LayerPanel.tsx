import { useState } from 'react';
import { LAYER_CONFIGS, LAYER_GROUPS } from '../config/layers';

interface LayerPanelProps {
  visibleLayers: Set<string>;
  onToggleLayer: (layerId: string) => void;
  zoom: number;
}

export function LayerPanel({ visibleLayers, onToggleLayer, zoom }: LayerPanelProps) {
  const [expanded, setExpanded] = useState(true);

  const groups = Object.entries(LAYER_GROUPS) as Array<
    [keyof typeof LAYER_GROUPS, (typeof LAYER_GROUPS)[keyof typeof LAYER_GROUPS]]
  >;

  return (
    <div className="layer-panel">
      <button className="layer-panel-toggle" onClick={() => setExpanded(!expanded)}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
          <rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" />
        </svg>
        <span>Layers</span>
        <svg
          width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          style={{ transform: expanded ? 'rotate(0)' : 'rotate(-90deg)', transition: 'transform 0.2s' }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {expanded && (
        <div className="layer-panel-content">
          {groups.map(([groupKey, group]) => {
            const groupLayers = LAYER_CONFIGS.filter((l) => l.group === groupKey);
            if (groupLayers.length === 0) return null;

            return (
              <div key={groupKey} className="layer-group">
                <div className="layer-group-header">
                  <span className="layer-group-icon">{group.icon}</span>
                  <span className="layer-group-label">{group.label}</span>
                </div>
                {groupLayers.map((layer) => {
                  const isVisible = visibleLayers.has(layer.id);
                  const belowMinZoom = zoom < layer.minZoom;

                  return (
                    <label
                      key={layer.id}
                      className={`layer-item ${belowMinZoom ? 'dimmed' : ''}`}
                      title={belowMinZoom ? `Zoom in to ${layer.minZoom}+ to see` : ''}
                    >
                      <input
                        type="checkbox"
                        checked={isVisible}
                        onChange={() => onToggleLayer(layer.id)}
                      />
                      <span className="layer-swatch" style={{ backgroundColor: layer.color }} />
                      <span className="layer-label">{layer.label}</span>
                      {belowMinZoom && isVisible && (
                        <span className="layer-zoom-badge">z{layer.minZoom}+</span>
                      )}
                    </label>
                  );
                })}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
