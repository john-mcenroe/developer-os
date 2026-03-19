interface ZoomIndicatorProps {
  zoom: number;
}

export function ZoomIndicator({ zoom }: ZoomIndicatorProps) {
  const zoomLevel = Math.round(zoom * 10) / 10;
  const showHint = zoom < 15;

  return (
    <div className="zoom-indicator">
      <span className="zoom-level">z{zoomLevel}</span>
      {showHint && <span className="zoom-hint">Zoom in for parcels</span>}
    </div>
  );
}
