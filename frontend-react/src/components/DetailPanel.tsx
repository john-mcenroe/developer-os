import { useCallback, useEffect, useState } from 'react';
import type {
  EnrichedParcel,
  PlanningProperties,
  SoldPropertyProperties,
  CensusProperties,
  RzltProperties,
  SideSiteProperties,
} from '../types';

interface DetailPanelProps {
  type: string | null;
  properties: Record<string, unknown> | null;
  enrichedData: EnrichedParcel | null;
  enrichedLoading: boolean;
  onClose: () => void;
}

export function DetailPanel({ type, properties, enrichedData, enrichedLoading, onClose }: DetailPanelProps) {
  const isOpen = type !== null;

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

  if (!isOpen || !properties) return null;

  const { title, icon, accent } = getMeta(type);

  return (
    <div className={`detail-panel ${isOpen ? 'open' : ''}`}>
      <div className="detail-panel-header">
        <div className="detail-panel-header-left">
          <span className="detail-panel-icon" style={{ color: accent }}>{icon}</span>
          <h3 className="detail-panel-title">{title}</h3>
        </div>
        <button className="detail-panel-close" onClick={onClose} aria-label="Close">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>
      <div className="detail-panel-body">
        {type === 'parcel' && enrichedData ? (
          <EnrichedParcelDetail data={enrichedData} />
        ) : type === 'parcel' && enrichedLoading ? (
          <LoadingSkeleton />
        ) : type === 'parcel' ? (
          <ParcelDetail props={properties as unknown as Record<string, unknown>} />
        ) : type === 'planning' ? (
          <PlanningDetail props={properties as unknown as PlanningProperties} />
        ) : type === 'sold' ? (
          <SoldDetail props={properties as unknown as SoldPropertyProperties} />
        ) : type === 'census' ? (
          <CensusDetail props={properties as unknown as CensusProperties} />
        ) : type === 'rzlt' ? (
          <RzltDetail props={properties as unknown as RzltProperties} />
        ) : type === 'side_site' ? (
          <SideSiteDetail props={properties as unknown as SideSiteProperties} />
        ) : (
          <GenericDetail props={properties} />
        )}
      </div>
    </div>
  );
}

function getMeta(type: string | null): { title: string; icon: string; accent: string } {
  switch (type) {
    case 'parcel': return { title: 'Site Intelligence', icon: '◬', accent: '#ff8c00' };
    case 'planning': return { title: 'Planning Application', icon: '◈', accent: '#2ecc71' };
    case 'sold': return { title: 'Property Sale', icon: '◉', accent: '#e74c3c' };
    case 'census': return { title: 'Census Area', icon: '◎', accent: '#00bcd4' };
    case 'rzlt': return { title: 'RZLT Site', icon: '◆', accent: '#ef4444' };
    case 'side_site': return { title: 'Side Site', icon: '◇', accent: '#f9a825' };
    case 'lap': return { title: 'LAP Boundary', icon: '▢', accent: '#9b59b6' };
    case 'sd_planning': return { title: 'SD Planning', icon: '◈', accent: '#e67e22' };
    case 'osm_building': return { title: 'Building Footprint', icon: '⌂', accent: '#8d6e63' };
    case 'amenity': return { title: 'Amenity', icon: '◇', accent: '#e91e63' };
    case 'transport': return { title: 'Transport Stop', icon: '●', accent: '#1565c0' };
    case 'flood_zone': return { title: 'Flood Zone', icon: '◬', accent: '#2196f3' };
    case 'niah': return { title: 'Protected Structure', icon: '◆', accent: '#ff9800' };
    case 'school': return { title: 'School', icon: '▣', accent: '#4caf50' };
    case 'landuse': return { title: 'Land Use', icon: '▢', accent: '#8bc34a' };
    case 'zoning': return { title: 'Zoning', icon: '▤', accent: '#9c27b0' };
    default: return { title: 'Detail', icon: '○', accent: '#3b82f6' };
  }
}

function LoadingSkeleton() {
  return (
    <div className="detail-skeleton">
      <div className="skeleton-block hero" />
      <div className="skeleton-block" />
      <div className="skeleton-block" />
      <div className="skeleton-block wide" />
    </div>
  );
}

/* ── Primitives ────────────────────────────────────────────────────────── */

function Card({ title, subtitle, accent, badge, children }: {
  title: string;
  subtitle?: string;
  accent?: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-header-left">
          {accent && <span className="card-accent" style={{ backgroundColor: accent }} />}
          <span className="card-title">{title}</span>
          {subtitle && <span className="card-subtitle">{subtitle}</span>}
        </div>
        {badge && <span className="card-badge">{badge}</span>}
      </div>
      <div className="card-body">{children}</div>
    </div>
  );
}

function ExpandableCard({ title, subtitle, accent, badge, previewCount, children, allChildren }: {
  title: string;
  subtitle?: string;
  accent?: string;
  badge?: React.ReactNode;
  previewCount: number;
  children: React.ReactNode;
  allChildren: React.ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-header-left">
          {accent && <span className="card-accent" style={{ backgroundColor: accent }} />}
          <span className="card-title">{title}</span>
          {subtitle && <span className="card-subtitle">{subtitle}</span>}
        </div>
        {badge && <span className="card-badge">{badge}</span>}
      </div>
      <div className="card-body">
        {expanded ? allChildren : children}
      </div>
      <button
        className="card-expand-btn"
        onClick={() => setExpanded(!expanded)}
      >
        <span>{expanded ? 'Show less' : `Show all ${previewCount}`}</span>
        <svg
          width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          style={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 0.2s' }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
    </div>
  );
}

function HeroStat({ value, label, color }: { value: string; label: string; color?: string }) {
  return (
    <div className="hero-stat">
      <div className="hero-stat-value" style={color ? { color } : undefined}>{value}</div>
      <div className="hero-stat-label">{label}</div>
    </div>
  );
}

function Row({ label, value, color, mono }: { label: string; value: React.ReactNode; color?: string; mono?: boolean }) {
  return (
    <div className="detail-row">
      <span className="detail-label">{label}</span>
      <span className={`detail-value ${mono ? 'mono' : ''}`} style={color ? { color } : undefined}>
        {value ?? '—'}
      </span>
    </div>
  );
}

function Tag({ text, color }: { text: string; color: string }) {
  return (
    <span className="detail-tag" style={{ color, borderColor: color, background: `${color}15` }}>
      {text}
    </span>
  );
}

/* ── Visualize Button (Imagen 3 Fast) ────────────────────────────────── */

function VisualizeButton({ description, location, decision, planRef }: {
  description: string;
  location?: string;
  decision?: string;
  planRef?: string;
}) {
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');
  const [imageData, setImageData] = useState<{ image: string; mime_type: string } | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  const generate = useCallback(async () => {
    setState('loading');
    setErrorMsg('');
    try {
      const resp = await fetch('/api/planning/visualize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description,
          location: location || '',
          decision: decision || '',
          plan_ref: planRef || '',
        }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(err.detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      setImageData(data);
      setState('done');
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'Failed to generate image');
      setState('error');
    }
  }, [description, location, decision, planRef]);

  if (state === 'done' && imageData) {
    return (
      <div className="visualize-result">
        <img
          src={`data:${imageData.mime_type};base64,${imageData.image}`}
          alt="Architectural visualization"
          className="visualize-image"
        />
        <button className="visualize-btn regenerate" onClick={generate}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
          </svg>
          Regenerate
        </button>
      </div>
    );
  }

  return (
    <div className="visualize-container">
      <button
        className={`visualize-btn ${state === 'loading' ? 'loading' : ''}`}
        onClick={generate}
        disabled={state === 'loading'}
      >
        {state === 'loading' ? (
          <>
            <span className="visualize-spinner" />
            Generating...
          </>
        ) : (
          <>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <polyline points="21 15 16 10 5 21" />
            </svg>
            Visualize Development
          </>
        )}
      </button>
      {state === 'error' && <div className="visualize-error">{errorMsg}</div>}
    </div>
  );
}

/* ── Expandable Sale Item ──────────────────────────────────────────────── */

function SaleItem({ sale, defaultExpanded }: {
  sale: { address: string; sale_price: number; sale_date?: string; property_type?: string | null; distance_m: number };
  defaultExpanded?: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded || false);

  return (
    <div className={`sale-item-expandable ${expanded ? 'expanded' : ''}`}>
      <div className="sale-item-row" onClick={() => setExpanded(!expanded)}>
        <span className="sale-price">€{sale.sale_price?.toLocaleString() || '—'}</span>
        <span className="sale-address">
          {sale.address ? (sale.address.length > 26 ? sale.address.substring(0, 26) + '...' : sale.address) : '—'}
        </span>
        <span className="sale-distance">{sale.distance_m != null ? `${sale.distance_m}m` : ''}</span>
        <svg
          className="sale-chevron"
          width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          style={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0)' }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>
      {expanded && (
        <div className="sale-item-detail">
          <Row label="Full Address" value={sale.address || '—'} />
          <Row label="Sale Date" value={sale.sale_date || '—'} />
          {sale.property_type && <Row label="Type" value={sale.property_type} />}
          <Row label="Distance" value={`${sale.distance_m}m from site`} />
        </div>
      )}
    </div>
  );
}

/* ── Expandable Planning Item ──────────────────────────────────────────── */

function PlanningItem({ pl, defaultExpanded }: {
  pl: { plan_ref: string; description: string; decision: string; distance_m: number; reg_date?: string; dec_date?: string; location?: string };
  defaultExpanded?: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded || false);
  const isGranted = pl.decision?.toUpperCase().includes('GRANT');
  const isRefused = pl.decision?.toUpperCase().includes('REFUS');
  const statusColor = isGranted ? '#2ecc71' : isRefused ? '#e74c3c' : '#f59e0b';
  const statusLabel = isGranted ? 'Granted' : isRefused ? 'Refused' : 'Pending';

  return (
    <div className={`planning-item-expandable ${expanded ? 'expanded' : ''}`}>
      <div className="planning-item-row" onClick={() => setExpanded(!expanded)}>
        <div className="planning-item-left">
          <span className="planning-ref">{pl.plan_ref || '—'}</span>
          <Tag text={statusLabel} color={statusColor} />
        </div>
        <svg
          className="planning-chevron"
          width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          style={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0)' }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>
      <div className="planning-item-preview">
        {pl.description ? (expanded ? '' : (pl.description.length > 55 ? pl.description.substring(0, 55) + '...' : pl.description)) : '—'}
      </div>
      {expanded && (
        <div className="planning-item-detail">
          <Row label="Description" value={pl.description || '—'} />
          <Row label="Decision" value={pl.decision || '—'} color={statusColor} />
          <Row label="Distance" value={`${pl.distance_m}m from site`} />
          {pl.location && <Row label="Location" value={pl.location} />}
        </div>
      )}
    </div>
  );
}

/* ── Enriched Parcel (Site Intelligence) ───────────────────────────────── */

function EnrichedParcelDetail({ data }: { data: EnrichedParcel }) {
  const p = data.parcel;
  const typeColor = p.type === 'leasehold' ? '#6495ed' : '#ff8c00';
  const typeLabel = (p.type || 'freehold').charAt(0).toUpperCase() + (p.type || 'freehold').slice(1);
  const hasRzlt = data.rzlt_overlap && data.rzlt_overlap.length > 0;
  const hasSales = data.nearby_sales && data.nearby_sales.count > 0;

  // Derive a display name from the nearest sale address or cadastral ref
  const nearestAddress = data.nearby_sales?.recent?.[0]?.address;
  const parcelName = nearestAddress
    ? nearestAddress.split(',').slice(0, 2).join(', ')
    : `Parcel ${p.national_ref || p.id}`;

  return (
    <div className="detail-cards">
      {/* Parcel Identity Header */}
      <div className="parcel-name-card">
        <div className="parcel-name">{parcelName}</div>
        <div className="parcel-ref">
          Ref {p.national_ref || '—'}
          <span className="parcel-ref-sep">·</span>
          {typeLabel}
          <span className="parcel-ref-sep">·</span>
          ID {p.id}
        </div>
      </div>

      {/* Hero: Key metrics */}
      <div className="hero-card">
        <div className="hero-grid">
          <HeroStat
            value={p.area_sqm ? `${p.area_sqm.toLocaleString()} m²` : '—'}
            label="Site Area"
          />
          <HeroStat
            value={hasSales ? `€${data.nearby_sales!.avg_sale_price.toLocaleString()}` : '—'}
            label="Avg Nearby Price"
            color={hasSales ? '#e74c3c' : undefined}
          />
          <HeroStat
            value={p.area_acres ? `${p.area_acres} ac` : '—'}
            label="Acres"
          />
          <HeroStat
            value={hasSales && data.nearby_sales!.avg_price_per_sqm ? `€${data.nearby_sales!.avg_price_per_sqm.toLocaleString()}` : '—'}
            label="Avg €/m²"
            color={hasSales ? '#e67e22' : undefined}
          />
        </div>
        <div className="hero-tags">
          <Tag text={typeLabel} color={typeColor} />
          {hasRzlt && <Tag text="RZLT Zone" color="#ef4444" />}
          {data.census?.vacancy_rate && data.census.vacancy_rate > 8 && (
            <Tag text={`${data.census.vacancy_rate}% Vacant`} color="#f59e0b" />
          )}
        </div>
      </div>

      {/* RZLT Alert */}
      {hasRzlt && (
        <div className="alert-card danger">
          <div className="alert-icon">!</div>
          <div className="alert-content">
            <div className="alert-title">RZLT Zone — 3% Annual Tax</div>
            <div className="alert-detail">
              {data.rzlt_overlap!.map((r, i) => (
                <span key={i}>{r.zone_desc || r.zone_gzt || 'Unknown zone'}</span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Comparable Sales — expandable */}
      {hasSales && (() => {
        const recent = data.nearby_sales!.recent || [];
        const totalCount = data.nearby_sales!.count;
        const previewItems = recent.slice(0, 3);
        const hasMore = recent.length > 3 || totalCount > 3;

        const statsBlock = (
          <div className="stat-row-group">
            <Row label="Average" value={`€${data.nearby_sales!.avg_sale_price.toLocaleString()}`} color="#e74c3c" />
            <Row label="Median" value={`€${data.nearby_sales!.median_sale_price.toLocaleString()}`} />
            {data.nearby_sales!.avg_price_per_sqm && (
              <Row label="Avg €/m²" value={`€${data.nearby_sales!.avg_price_per_sqm.toLocaleString()}`} />
            )}
          </div>
        );

        const previewContent = (
          <>
            {statsBlock}
            {previewItems.length > 0 && (
              <div className="expandable-list">
                {previewItems.map((s, i) => (
                  <SaleItem key={i} sale={s} />
                ))}
              </div>
            )}
          </>
        );

        const fullContent = (
          <>
            {statsBlock}
            {recent.length > 0 && (
              <div className="expandable-list">
                {recent.map((s, i) => (
                  <SaleItem key={i} sale={s} defaultExpanded={i === 0} />
                ))}
              </div>
            )}
          </>
        );

        if (hasMore) {
          return (
            <ExpandableCard
              title="Comparable Sales"
              subtitle={`${totalCount} within 500m`}
              accent="#e74c3c"
              previewCount={totalCount}
              children={previewContent}
              allChildren={fullContent}
            />
          );
        }

        return (
          <Card title="Comparable Sales" subtitle={`${totalCount} within 500m`} accent="#e74c3c">
            {previewContent}
          </Card>
        );
      })()}

      {/* Planning Activity — expandable */}
      {data.nearby_planning && data.nearby_planning.length > 0 && (() => {
        const planning = data.nearby_planning!;
        const previewItems = planning.slice(0, 3);
        const hasMore = planning.length > 3;

        const previewContent = (
          <div className="expandable-list">
            {previewItems.map((pl, i) => (
              <PlanningItem key={i} pl={pl} />
            ))}
          </div>
        );

        const fullContent = (
          <div className="expandable-list">
            {planning.map((pl, i) => (
              <PlanningItem key={i} pl={pl} defaultExpanded={i === 0} />
            ))}
          </div>
        );

        if (hasMore) {
          return (
            <ExpandableCard
              title="Planning"
              subtitle={`${planning.length} within 500m`}
              accent="#2ecc71"
              previewCount={planning.length}
              children={previewContent}
              allChildren={fullContent}
            />
          );
        }

        return (
          <Card title="Planning" subtitle={`${planning.length} within 500m`} accent="#2ecc71">
            {previewContent}
          </Card>
        );
      })()}

      {/* Demographics */}
      {data.census && (
        <Card title="Demographics" subtitle="Census 2022" accent="#00bcd4">
          <CensusCard census={data.census} />
        </Card>
      )}
    </div>
  );
}

function ParcelDetail({ props }: { props: Record<string, unknown> }) {
  const p = props;
  const typeLabel = String(p.type || 'freehold').charAt(0).toUpperCase() + String(p.type || 'freehold').slice(1);
  const typeColor = p.type === 'leasehold' ? '#6495ed' : '#ff8c00';
  return (
    <div className="detail-cards">
      <div className="parcel-name-card">
        <div className="parcel-name">Parcel {String(p.national_ref || p.id || '—')}</div>
        <div className="parcel-ref">{typeLabel}</div>
      </div>
      <div className="hero-card">
        <div className="hero-grid">
          <HeroStat value={p.area_sqm ? `${Number(p.area_sqm).toLocaleString()} m²` : '—'} label="Site Area" />
          <HeroStat value={p.area_acres ? `${p.area_acres} ac` : '—'} label="Acres" />
        </div>
        <div className="hero-tags">
          <Tag text={typeLabel} color={typeColor} />
        </div>
      </div>
      <Card title="Identity" accent={typeColor}>
        <Row label="Cadastral Ref" value={String(p.national_ref || '—')} mono />
        <Row label="INSPIRE ID" value={String(p.inspire_id || '—')} mono />
        <Row label="Internal ID" value={String(p.id || '—')} mono />
      </Card>
    </div>
  );
}

/* ── Demographics Components ───────────────────────────────────────────── */

function BenchmarkBar({ value, benchmark, label, countyLabel, suffix, color, invertColor }: {
  value: number | null | undefined;
  benchmark: number | null | undefined;
  label: string;
  countyLabel?: string;
  suffix?: string;
  color?: string;
  invertColor?: boolean;
}) {
  if (value == null) return null;
  const s = suffix || '%';
  const maxVal = Math.max(value, benchmark || 0, 1);
  const valuePct = Math.min((value / maxVal) * 100, 100);
  const benchPct = benchmark != null ? Math.min((benchmark / maxVal) * 100, 100) : null;
  const delta = benchmark != null ? value - benchmark : null;
  const deltaColor = delta != null
    ? (invertColor ? (delta > 0 ? '#ef4444' : '#22c55e') : (delta > 0 ? '#22c55e' : '#ef4444'))
    : undefined;
  const barColor = color || '#00bcd4';

  return (
    <div className="benchmark-row">
      <div className="benchmark-header">
        <span className="benchmark-label">{label}</span>
        <span className="benchmark-values">
          <span className="benchmark-value" style={{ color: barColor }}>{typeof value === 'number' && value % 1 !== 0 ? value.toFixed(1) : value}{s}</span>
          {delta != null && <span className="benchmark-delta" style={{ color: deltaColor }}>{delta > 0 ? '+' : ''}{delta.toFixed(1)}</span>}
        </span>
      </div>
      <div className="benchmark-track">
        <div className="benchmark-fill" style={{ width: `${valuePct}%`, background: barColor }} />
        {benchPct != null && (
          <div className="benchmark-marker" style={{ left: `${benchPct}%` }} title={`${countyLabel || 'County'} avg: ${typeof benchmark === 'number' && benchmark % 1 !== 0 ? benchmark.toFixed(1) : benchmark}${s}`} />
        )}
      </div>
    </div>
  );
}

function HorizontalBarChart({ items, color }: {
  items: { label: string; value: number }[];
  color?: string;
}) {
  const maxVal = Math.max(...items.map(i => i.value), 1);
  const total = items.reduce((a, b) => a + b.value, 0);

  return (
    <div className="hbar-chart">
      {items.map((item) => {
        const pct = total > 0 ? ((item.value / total) * 100).toFixed(0) : '0';
        return (
          <div key={item.label} className="hbar-row">
            <span className="hbar-label">{item.label}</span>
            <div className="hbar-track">
              <div
                className="hbar-fill"
                style={{ width: `${(item.value / maxVal) * 100}%`, background: color || '#00bcd4' }}
              />
            </div>
            <span className="hbar-value">{pct}%</span>
          </div>
        );
      })}
    </div>
  );
}

function DemographicsSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="demo-section">
      <div className="demo-section-title">{title}</div>
      {children}
    </div>
  );
}

function CensusCard({ census }: { census: CensusProperties }) {
  const c = census;
  const bench = c.county_benchmarks;
  const countyLabel = c.county || 'County';

  // Tenure
  const ownerPct = c.owner_occupied_pct || 0;
  const rentPct = c.rented_pct || 0;
  const otherPct = Math.max(0, 100 - ownerPct - rentPct);
  const vacColor = (c.vacancy_rate || 0) > 10 ? '#e74c3c' : (c.vacancy_rate || 0) > 5 ? '#f59e0b' : '#22c55e';

  // Age profile
  const hasAge = c.age_0_14 != null || c.age_25_44 != null;
  const ageItems = hasAge ? [
    { label: '0–14', value: c.age_0_14 || 0 },
    { label: '15–24', value: c.age_15_24 || 0 },
    { label: '25–44', value: c.age_25_44 || 0 },
    { label: '45–64', value: c.age_45_64 || 0 },
    { label: '65+', value: c.age_65_plus || 0 },
  ] : [];

  // Housing age
  const hasHousingAge = c.built_pre_1919 != null || c.built_1971_2000 != null;
  const housingAgeItems = hasHousingAge ? [
    { label: 'Pre-1919', value: c.built_pre_1919 || 0 },
    { label: '1919–45', value: c.built_1919_1945 || 0 },
    { label: '1946–70', value: c.built_1946_1970 || 0 },
    { label: '1971–00', value: c.built_1971_2000 || 0 },
    { label: '2001–15', value: c.built_2001_2015 || 0 },
    { label: '2016+', value: c.built_2016_plus || 0 },
  ] : [];

  return (
    <div className="demographics-card">
      {/* Hero stats */}
      <div className="demo-grid">
        <div className="demo-stat">
          <span className="demo-stat-value" style={{ color: '#00bcd4' }}>{c.total_population?.toLocaleString() || '—'}</span>
          <span className="demo-stat-label">Population</span>
        </div>
        <div className="demo-stat">
          <span className="demo-stat-value">{c.total_households?.toLocaleString() || '—'}</span>
          <span className="demo-stat-label">Households</span>
        </div>
        <div className="demo-stat">
          <span className="demo-stat-value" style={{ color: vacColor }}>{c.vacancy_rate != null ? `${c.vacancy_rate}%` : '—'}</span>
          <span className="demo-stat-label">Vacancy</span>
        </div>
      </div>

      {bench && (
        <div className="benchmark-county-label">
          vs {countyLabel} average <span className="benchmark-marker-inline" /> = county avg
        </div>
      )}

      {/* Housing & Tenure */}
      <DemographicsSection title="Housing & Tenure">
        <div className="tenure-section">
          <div className="tenure-bar">
            <div className="tenure-segment owner" style={{ width: `${ownerPct}%` }} />
            <div className="tenure-segment rented" style={{ width: `${rentPct}%` }} />
            <div className="tenure-segment other" style={{ width: `${otherPct}%` }} />
          </div>
          <div className="tenure-legend">
            <span><span className="legend-dot owner" />Owner {ownerPct.toFixed(0)}%</span>
            <span><span className="legend-dot rented" />Rented {rentPct.toFixed(0)}%</span>
            {otherPct > 1 && <span><span className="legend-dot other" />Other {otherPct.toFixed(0)}%</span>}
          </div>
        </div>
        <BenchmarkBar label="Apartments" value={c.apartment_pct} benchmark={bench?.apartment_pct} countyLabel={countyLabel} color="#8b5cf6" />
        <BenchmarkBar label="Avg Rooms" value={c.avg_rooms} benchmark={bench?.avg_rooms} countyLabel={countyLabel} suffix="" color="#6366f1" />
        <BenchmarkBar label="Avg Household" value={c.avg_household_size} benchmark={bench?.avg_household_size} countyLabel={countyLabel} suffix="" color="#06b6d4" />
        <BenchmarkBar label="Vacancy" value={c.vacancy_rate} benchmark={bench?.vacancy_rate} countyLabel={countyLabel} color={vacColor} invertColor />
      </DemographicsSection>

      {/* Socioeconomic */}
      <DemographicsSection title="Socioeconomic">
        <BenchmarkBar label="Employment" value={c.employment_rate} benchmark={bench?.employment_rate} countyLabel={countyLabel} color="#22c55e" />
        <BenchmarkBar label="3rd Level Edu" value={c.third_level_pct} benchmark={bench?.third_level_pct} countyLabel={countyLabel} color="#3b82f6" />
        <BenchmarkBar label="Work From Home" value={c.wfh_pct} benchmark={bench?.wfh_pct} countyLabel={countyLabel} color="#f59e0b" />
        <BenchmarkBar label="Good Health" value={c.health_good_pct} benchmark={bench?.health_good_pct} countyLabel={countyLabel} color="#10b981" />
        <BenchmarkBar label="Density" value={c.population_density ? Math.round(c.population_density) : null} benchmark={bench?.population_density ? Math.round(bench.population_density) : null} countyLabel={countyLabel} suffix="/km²" color="#00bcd4" />
      </DemographicsSection>

      {/* Age Profile */}
      {hasAge && ageItems.some(i => i.value > 0) && (
        <DemographicsSection title="Age Profile">
          <HorizontalBarChart items={ageItems} color="#00bcd4" />
        </DemographicsSection>
      )}

      {/* Housing Stock Age */}
      {hasHousingAge && housingAgeItems.some(i => i.value > 0) && (
        <DemographicsSection title="Housing Stock Age">
          <HorizontalBarChart items={housingAgeItems} color="#8b5cf6" />
        </DemographicsSection>
      )}
    </div>
  );
}

/* ── Other Detail Types ────────────────────────────────────────────────── */

function PlanningDetail({ props }: { props: PlanningProperties }) {
  const fmtDate = (d?: string) => {
    if (!d || d === '(null)') return '—';
    // Handle ISO date format (e.g. "2024-01-15" or "2024-01-15T...")
    if (d.includes('-') && d.length >= 10) {
      const parts = d.slice(0, 10).split('-');
      if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
    }
    // Handle compact format (e.g. "20240115")
    if (d.length >= 8 && !d.includes('/') && !d.includes('-')) {
      return `${d.slice(6, 8)}/${d.slice(4, 6)}/${d.slice(0, 4)}`;
    }
    return d;
  };

  // Normalize: support both DLR and national planning field names
  const planRef = props.plan_ref || props.applicationnumber;
  const description = props.descrptn || props.developmentdescription;
  const location = props.location || props.developmentaddress;
  const authority = props.plan_auth || props.planningauthority;
  const regDate = props.reg_date || props.received_date;

  const isGranted = props.decision?.toUpperCase().includes('GRANT');
  const isRefused = props.decision?.toUpperCase().includes('REFUS');
  const statusColor = isGranted ? '#2ecc71' : isRefused ? '#e74c3c' : '#f59e0b';
  const statusLabel = isGranted ? 'Granted' : isRefused ? 'Refused' : 'Pending';

  return (
    <div className="detail-cards">
      <div className="hero-card">
        <div className="hero-grid cols-1">
          <HeroStat value={planRef || '—'} label="Planning Reference" color="#2ecc71" />
        </div>
        <div className="hero-tags">
          <Tag text={statusLabel} color={statusColor} />
          {authority && <Tag text={authority} color="#6b7394" />}
        </div>
      </div>

      {description && (
        <Card title="Description" accent="#2ecc71">
          <p className="card-text">{description}</p>
        </Card>
      )}

      <Card title="Details" accent="#2ecc71">
        <Row label="Location" value={location || '—'} />
        <Row label="Stage" value={props.stage || '—'} />
        <Row label="Registered" value={fmtDate(regDate)} />
        <Row label="Decision Date" value={fmtDate(props.dec_date)} />
      </Card>

      {description && (
        <VisualizeButton
          description={description}
          location={location}
          decision={props.decision}
          planRef={planRef}
        />
      )}

      {props.more_info && props.more_info !== '(null)' && (
        <a href={props.more_info} target="_blank" rel="noopener noreferrer" className="detail-action-link">
          View on planning authority
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
            <polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" />
          </svg>
        </a>
      )}
    </div>
  );
}

function SoldDetail({ props }: { props: SoldPropertyProperties }) {
  const salePrice = props.sale_price ? `€${Number(props.sale_price).toLocaleString()}` : '—';

  return (
    <div className="detail-cards">
      <div className="hero-card">
        <div className="hero-grid cols-1">
          <HeroStat value={salePrice} label="Sale Price" color="#e74c3c" />
        </div>
        <div className="hero-tags">
          {props.property_type && <Tag text={props.property_type} color="#6b7394" />}
          {props.ber_rating && <Tag text={`BER ${props.ber_rating}`} color="#22c55e" />}
          {props.sale_price && props.asking_price && (
            <Tag
              text={`${((Number(props.sale_price) / Number(props.asking_price) - 1) * 100).toFixed(0)}% vs asking`}
              color={Number(props.sale_price) > Number(props.asking_price) ? '#22c55e' : '#e74c3c'}
            />
          )}
        </div>
      </div>

      <Card title="Property" accent="#e74c3c">
        <Row label="Address" value={props.address || '—'} />
        {props.beds && <Row label="Beds" value={props.beds} />}
        {props.baths && <Row label="Baths" value={props.baths} />}
        {props.floor_area_sqm && <Row label="Floor Area" value={`${props.floor_area_sqm} m²`} />}
        {props.price_per_sqm && <Row label="€/m²" value={`€${Number(props.price_per_sqm).toLocaleString()}`} />}
      </Card>

      <Card title="Sale" accent="#e74c3c">
        {props.asking_price && <Row label="Asking" value={`€${Number(props.asking_price).toLocaleString()}`} />}
        <Row label="Sale Date" value={props.sale_date || '—'} />
      </Card>
    </div>
  );
}

function CensusDetail({ props }: { props: CensusProperties }) {
  return (
    <div className="detail-cards">
      <div className="hero-card">
        <div className="hero-grid">
          <HeroStat value={props.total_population?.toLocaleString() || '—'} label="Population" color="#00bcd4" />
          <HeroStat value={props.population_density ? `${Math.round(props.population_density).toLocaleString()}` : '—'} label="Per km²" />
        </div>
        <div className="hero-tags">
          {props.sa_code && <Tag text={props.sa_code} color="#00bcd4" />}
          {props.county && <Tag text={props.county} color="#6b7394" />}
          {props.urban_area && <Tag text={props.urban_area} color="#6b7394" />}
        </div>
      </div>
      <Card title="Demographics" subtitle="Census 2022" accent="#00bcd4">
        <CensusCard census={props} />
      </Card>
    </div>
  );
}

function RzltDetail({ props }: { props: RzltProperties }) {
  return (
    <div className="detail-cards">
      <div className="alert-card danger">
        <div className="alert-icon">!</div>
        <div className="alert-content">
          <div className="alert-title">RZLT Site — 3% Annual Tax</div>
          <div className="alert-detail">Residential Zoned Land Tax applies to this site</div>
        </div>
      </div>
      <Card title="Zone Info" accent="#ef4444">
        <Row label="Zone" value={props.zone_desc || '—'} />
        <Row label="Code" value={props.zone_gzt || '—'} mono />
        <Row label="Description" value={props.gzt_desc || '—'} />
        <Row label="Site Area" value={props.site_area ? `${Number(props.site_area).toLocaleString()} m²` : '—'} />
        <Row label="Authority" value={props.local_authority || '—'} />
      </Card>
    </div>
  );
}

function SideSiteDetail({ props }: { props: SideSiteProperties }) {
  const score = props.score != null ? Math.round(props.score * 100) : null;
  const scoreColor = (score || 0) >= 70 ? '#22c55e' : (score || 0) >= 50 ? '#f59e0b' : '#ef4444';

  return (
    <div className="detail-cards">
      <div className="hero-card">
        <div className="hero-grid">
          <HeroStat value={score != null ? `${score}` : '—'} label="Score / 100" color={scoreColor} />
          <HeroStat value={props.area_sqm ? `${Number(props.area_sqm).toLocaleString()} m²` : '—'} label="Area" />
        </div>
        <div className="hero-tags">
          {(props.on_rzlt === true || props.on_rzlt === 'true') && <Tag text="RZLT" color="#ef4444" />}
          {(props.has_planning === true || props.has_planning === 'true') && <Tag text="Has Planning" color="#f59e0b" />}
        </div>
      </div>

      <Card title="Site Metrics" accent="#f9a825">
        <Row label="Compactness" value={props.compactness != null ? `${Number(props.compactness).toFixed(2)} ${Number(props.compactness) < 0.5 ? '(elongated)' : '(compact)'}` : '—'} />
        <Row label="Neighbors" value={`${props.neighbor_count || 0} adjacent parcels`} />
        <Row label="Cadastral Ref" value={props.national_ref || '—'} mono />
      </Card>

      <Card title="Area Context" accent="#f9a825">
        <Row label="Owner Occupied" value={props.owner_occupied_pct ? `${props.owner_occupied_pct}%` : '—'} />
        <Row label="Vacancy" value={props.vacancy_rate ? `${props.vacancy_rate}%` : '—'} />
      </Card>
    </div>
  );
}

function GenericDetail({ props }: { props: Record<string, unknown> }) {
  return (
    <div className="detail-cards">
      <Card title="Properties">
        {Object.entries(props)
          .filter(([k]) => k !== 'id' && !k.startsWith('_'))
          .slice(0, 15)
          .map(([k, v]) => (
            <Row key={k} label={k.replace(/_/g, ' ')} value={v != null ? String(v) : '—'} />
          ))}
      </Card>
    </div>
  );
}
