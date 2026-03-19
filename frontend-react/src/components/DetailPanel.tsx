import { useEffect, useState } from 'react';
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
      {data.census && <CensusCard census={data.census} />}
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

/* ── Census Card ───────────────────────────────────────────────────────── */

function CensusCard({ census }: { census: CensusProperties }) {
  const c = census;
  const ownerPct = c.owner_occupied_pct || 0;
  const rentPct = c.rented_pct || 0;
  const otherPct = Math.max(0, 100 - ownerPct - rentPct);
  const vacColor = (c.vacancy_rate || 0) > 10 ? '#e74c3c' : (c.vacancy_rate || 0) > 5 ? '#f59e0b' : '#22c55e';

  return (
    <Card title="Demographics" subtitle="Census 2022" accent="#00bcd4">
      <div className="demo-grid">
        <div className="demo-stat">
          <span className="demo-stat-value" style={{ color: '#00bcd4' }}>{c.total_population?.toLocaleString() || '—'}</span>
          <span className="demo-stat-label">Population</span>
        </div>
        <div className="demo-stat">
          <span className="demo-stat-value">{c.population_density ? `${Math.round(c.population_density).toLocaleString()}` : '—'}</span>
          <span className="demo-stat-label">Per km²</span>
        </div>
        <div className="demo-stat">
          <span className="demo-stat-value" style={{ color: vacColor }}>{c.vacancy_rate != null ? `${c.vacancy_rate}%` : '—'}</span>
          <span className="demo-stat-label">Vacancy</span>
        </div>
      </div>

      <div className="tenure-section">
        <div className="tenure-label">Housing Tenure</div>
        <div className="tenure-bar">
          <div className="tenure-segment owner" style={{ width: `${ownerPct}%` }} />
          <div className="tenure-segment rented" style={{ width: `${rentPct}%` }} />
          <div className="tenure-segment other" style={{ width: `${otherPct}%` }} />
        </div>
        <div className="tenure-legend">
          <span><span className="legend-dot owner" />Owner {ownerPct}%</span>
          <span><span className="legend-dot rented" />Rented {rentPct}%</span>
          {otherPct > 0 && <span><span className="legend-dot other" />Other {Math.round(otherPct)}%</span>}
        </div>
      </div>

      <div className="demo-metrics">
        <Row label="Employment" value={c.employment_rate != null ? `${c.employment_rate}%` : '—'} />
        <Row label="3rd Level Edu" value={c.third_level_pct != null ? `${c.third_level_pct}%` : '—'} />
        {c.wfh_pct != null && c.wfh_pct > 0 && <Row label="WFH" value={`${c.wfh_pct}%`} />}
        {c.avg_household_size != null && <Row label="Avg Household" value={`${c.avg_household_size} people`} />}
      </div>
    </Card>
  );
}

/* ── Other Detail Types ────────────────────────────────────────────────── */

function PlanningDetail({ props }: { props: PlanningProperties }) {
  const fmtDate = (d?: string) => {
    if (!d || d === '(null)' || d.length < 8) return '—';
    return `${d.slice(6, 8)}/${d.slice(4, 6)}/${d.slice(0, 4)}`;
  };

  const isGranted = props.decision?.toUpperCase().includes('GRANT');
  const isRefused = props.decision?.toUpperCase().includes('REFUS');
  const statusColor = isGranted ? '#2ecc71' : isRefused ? '#e74c3c' : '#f59e0b';
  const statusLabel = isGranted ? 'Granted' : isRefused ? 'Refused' : 'Pending';

  return (
    <div className="detail-cards">
      <div className="hero-card">
        <div className="hero-grid cols-1">
          <HeroStat value={props.plan_ref || '—'} label="Planning Reference" color="#2ecc71" />
        </div>
        <div className="hero-tags">
          <Tag text={statusLabel} color={statusColor} />
          {props.plan_auth && <Tag text={props.plan_auth} color="#6b7394" />}
        </div>
      </div>

      {props.descrptn && (
        <Card title="Description" accent="#2ecc71">
          <p className="card-text">{props.descrptn}</p>
        </Card>
      )}

      <Card title="Details" accent="#2ecc71">
        <Row label="Location" value={props.location || '—'} />
        <Row label="Stage" value={props.stage || '—'} />
        <Row label="Registered" value={fmtDate(props.reg_date)} />
        <Row label="Decision Date" value={fmtDate(props.dec_date)} />
      </Card>

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
        </div>
      </div>
      <CensusCard census={props} />
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
