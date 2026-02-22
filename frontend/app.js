const API = "http://localhost:8000/api";
const PARCEL_MIN_ZOOM = 15;

// ── Circle analysis state ────────────────────────────────────────────────────
let circleMode = false;
let circleCenter = null;  // { lng, lat }
let circleRadiusM = 500;  // metres
let circleDrawing = false;  // true while dragging to define radius

// ── Panel state ──────────────────────────────────────────────────────────────
let mapCollapsed = false;
let savedMapWidth = 75; // percentage

// ── Map initialisation ───────────────────────────────────────────────────────
const map = new maplibregl.Map({
  container: "map",
  style: {
    version: 8,
    sources: {
      osm: {
        type: "raster",
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        tileSize: 256,
        attribution: "© <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors",
        maxzoom: 19,
      },
    },
    layers: [{ id: "osm-tiles", type: "raster", source: "osm" }],
  },
  center: [-6.2603, 53.3498], // Dublin city centre
  zoom: 12,
});

// ── GeoJSON sources + layers for cadastral parcels ───────────────────────────
map.on("load", () => {
  // Freehold — orange
  map.addSource("cadastral-freehold", {
    type: "geojson",
    data: { type: "FeatureCollection", features: [] },
  });

  map.addLayer({
    id: "cadastral_freehold-fill",
    type: "fill",
    source: "cadastral-freehold",
    paint: {
      "fill-color": "rgba(255, 165, 0, 0.15)",
      "fill-outline-color": "rgba(255, 140, 0, 0)",
    },
  });

  map.addLayer({
    id: "cadastral_freehold-outline",
    type: "line",
    source: "cadastral-freehold",
    paint: {
      "line-color": "#ff8c00",
      "line-width": 1,
    },
  });

  map.addLayer({
    id: "cadastral_freehold-selected",
    type: "fill",
    source: "cadastral-freehold",
    filter: ["==", ["id"], -1],
    paint: {
      "fill-color": "rgba(255, 200, 0, 0.4)",
      "fill-outline-color": "#ffc800",
    },
  });

  // Leasehold — blue
  map.addSource("cadastral-leasehold", {
    type: "geojson",
    data: { type: "FeatureCollection", features: [] },
  });

  map.addLayer({
    id: "cadastral_leasehold-fill",
    type: "fill",
    source: "cadastral-leasehold",
    paint: {
      "fill-color": "rgba(100, 149, 237, 0.15)",
      "fill-outline-color": "rgba(100, 149, 237, 0)",
    },
  });

  map.addLayer({
    id: "cadastral_leasehold-outline",
    type: "line",
    source: "cadastral-leasehold",
    paint: {
      "line-color": "#6495ed",
      "line-width": 1,
    },
  });

  map.addLayer({
    id: "cadastral_leasehold-selected",
    type: "fill",
    source: "cadastral-leasehold",
    filter: ["==", ["id"], -1],
    paint: {
      "fill-color": "rgba(100, 200, 255, 0.4)",
      "fill-outline-color": "#64c8ff",
    },
  });

  // RZLT (red hatching for motivated sellers) — lower zoom level
  map.addSource("rzlt", {
    type: "geojson",
    data: { type: "FeatureCollection", features: [] },
  });

  map.addLayer({
    id: "rzlt-fill",
    type: "fill",
    source: "rzlt",
    layout: { visibility: "none" },
    paint: {
      "fill-color": "rgba(255, 0, 0, 0.2)",
      "fill-outline-color": "rgba(255, 0, 0, 0)",
    },
  });

  map.addLayer({
    id: "rzlt-outline",
    type: "line",
    source: "rzlt",
    layout: { visibility: "none" },
    paint: {
      "line-color": "#ff0000",
      "line-width": 2,
    },
  });

  // DLR Planning Applications (Polygons) — green
  map.addSource("dlr-planning-polygons", {
    type: "geojson",
    data: { type: "FeatureCollection", features: [] },
  });

  map.addLayer({
    id: "dlr_planning_polygons-fill",
    type: "fill",
    source: "dlr-planning-polygons",
    paint: {
      "fill-color": "rgba(46, 204, 113, 0.25)",
      "fill-outline-color": "rgba(46, 204, 113, 0)",
    },
  });

  map.addLayer({
    id: "dlr_planning_polygons-outline",
    type: "line",
    source: "dlr-planning-polygons",
    paint: {
      "line-color": "#2ecc71",
      "line-width": 2,
    },
  });

  map.addLayer({
    id: "dlr_planning_polygons-selected",
    type: "fill",
    source: "dlr-planning-polygons",
    filter: ["==", ["id"], -1],
    paint: {
      "fill-color": "rgba(46, 204, 113, 0.45)",
      "fill-outline-color": "#27ae60",
    },
  });

  // DLR Planning Applications (Points) — darker green circles
  map.addSource("dlr-planning-points", {
    type: "geojson",
    data: { type: "FeatureCollection", features: [] },
  });

  map.addLayer({
    id: "dlr_planning_points-fill",
    type: "circle",
    source: "dlr-planning-points",
    paint: {
      "circle-radius": 5,
      "circle-color": "#27ae60",
      "circle-stroke-color": "#1e8449",
      "circle-stroke-width": 1,
    },
  });

  // Sold Properties — price-colored circles
  map.addSource("sold-properties", {
    type: "geojson",
    data: { type: "FeatureCollection", features: [] },
  });

  map.addLayer({
    id: "sold_properties-fill",
    type: "circle",
    source: "sold-properties",
    paint: {
      "circle-radius": [
        "interpolate", ["linear"], ["zoom"],
        13, 3,
        16, 6,
        18, 9,
      ],
      "circle-color": [
        "interpolate", ["linear"], ["coalesce", ["get", "sale_price"], 0],
        100000, "#f1c40f",
        300000, "#e67e22",
        500000, "#e74c3c",
        1000000, "#8e44ad",
        3000000, "#2c3e50",
      ],
      "circle-stroke-color": "#fff",
      "circle-stroke-width": 0.5,
      "circle-opacity": 0.85,
    },
  });

  // Circle analysis overlay
  map.addSource("analysis-circle", {
    type: "geojson",
    data: { type: "FeatureCollection", features: [] },
  });

  map.addLayer({
    id: "analysis-circle-fill",
    type: "fill",
    source: "analysis-circle",
    paint: {
      "fill-color": "rgba(155, 89, 182, 0.15)",
      "fill-outline-color": "rgba(155, 89, 182, 0)",
    },
  });

  map.addLayer({
    id: "analysis-circle-outline",
    type: "line",
    source: "analysis-circle",
    paint: {
      "line-color": "#9b59b6",
      "line-width": 2,
      "line-dasharray": [4, 3],
    },
  });

  // Initial load
  loadParcels();
  loadLayers();
});

// ── Load parcels for current viewport ───────────────────────────────────────
let parcelLoadTimer = null;

function loadParcels() {
  const zoom = map.getZoom();
  updateZoomHint(zoom);

  const bounds = map.getBounds();
  const bbox = [
    bounds.getWest().toFixed(6),
    bounds.getSouth().toFixed(6),
    bounds.getEast().toFixed(6),
    bounds.getNorth().toFixed(6),
  ].join(",");

  // Cadastral parcels (freehold + leasehold) — only show above zoom 15
  if (zoom < PARCEL_MIN_ZOOM) {
    const srcF = map.getSource("cadastral-freehold");
    const srcL = map.getSource("cadastral-leasehold");
    if (srcF) srcF.setData({ type: "FeatureCollection", features: [] });
    if (srcL) srcL.setData({ type: "FeatureCollection", features: [] });
  } else {
    // Freehold
    if (isLayerVisible("cadastral_freehold")) {
      fetch(`${API}/parcels?bbox=${bbox}`)
        .then((r) => r.json())
        .then((geojson) => {
          const src = map.getSource("cadastral-freehold");
          if (src) src.setData(geojson);
        })
        .catch((err) => console.error("Failed to load freehold parcels:", err));
    }

    // Leasehold
    if (isLayerVisible("cadastral_leasehold")) {
      fetch(`${API}/parcels_leasehold?bbox=${bbox}`)
        .then((r) => r.json())
        .then((geojson) => {
          const src = map.getSource("cadastral-leasehold");
          if (src) src.setData(geojson);
        })
        .catch((err) => console.error("Failed to load leasehold parcels:", err));
    }
  }

  // RZLT (visible at all zoom levels)
  if (isLayerVisible("rzlt")) {
    fetch(`${API}/rzlt?bbox=${bbox}`)
      .then((r) => r.json())
      .then((geojson) => {
        const src = map.getSource("rzlt");
        if (src) src.setData(geojson);
      })
      .catch((err) => console.error("Failed to load RZLT:", err));
  }

  // DLR Planning Applications — polygons (zoom 13+)
  if (zoom >= 13 && isLayerVisible("dlr_planning_polygons")) {
    fetch(`${API}/planning_apps?bbox=${bbox}`)
      .then((r) => r.json())
      .then((geojson) => {
        const src = map.getSource("dlr-planning-polygons");
        if (src) src.setData(geojson);
      })
      .catch((err) => console.error("Failed to load DLR planning polygons:", err));
  } else if (zoom < 13) {
    const srcPoly = map.getSource("dlr-planning-polygons");
    if (srcPoly) srcPoly.setData({ type: "FeatureCollection", features: [] });
  }

  // DLR Planning Applications — points (zoom 12+)
  if (zoom >= 12 && isLayerVisible("dlr_planning_points")) {
    fetch(`${API}/planning_apps_points?bbox=${bbox}`)
      .then((r) => r.json())
      .then((geojson) => {
        const src = map.getSource("dlr-planning-points");
        if (src) src.setData(geojson);
      })
      .catch((err) => console.error("Failed to load DLR planning points:", err));
  } else if (zoom < 12) {
    const srcPts = map.getSource("dlr-planning-points");
    if (srcPts) srcPts.setData({ type: "FeatureCollection", features: [] });
  }

  // Sold Properties — points (zoom 13+)
  if (zoom >= 13 && isLayerVisible("sold_properties")) {
    fetch(`${API}/sold_properties?bbox=${bbox}`)
      .then((r) => r.json())
      .then((geojson) => {
        const src = map.getSource("sold-properties");
        if (src) src.setData(geojson);
      })
      .catch((err) => console.error("Failed to load sold properties:", err));
  } else if (zoom < 13) {
    const srcSold = map.getSource("sold-properties");
    if (srcSold) srcSold.setData({ type: "FeatureCollection", features: [] });
  }
}

function isLayerVisible(layerName) {
  const fillLayer = `${layerName}-fill`;
  if (!map.getLayer(fillLayer)) return false;
  return map.getLayoutProperty(fillLayer, "visibility") !== "none";
}

function scheduleParcels() {
  clearTimeout(parcelLoadTimer);
  parcelLoadTimer = setTimeout(loadParcels, 250);
}

map.on("moveend", scheduleParcels);
map.on("zoomend", scheduleParcels);

// ── Zoom hint ────────────────────────────────────────────────────────────────
function updateZoomHint(zoom) {
  const hint = document.getElementById("zoom-hint");
  const zoomLevel = Math.round(zoom * 10) / 10;
  if (zoom < PARCEL_MIN_ZOOM) {
    hint.textContent = `Zoom in to see parcels (zoom ${PARCEL_MIN_ZOOM}+) · Zoom: ${zoomLevel}`;
  } else {
    hint.textContent = `Zoom: ${zoomLevel}`;
  }
  hint.style.opacity = "1";
}

// ── Parcel click (works for both freehold and leasehold) ─────────────────────
function setupParcelClick(fillLayerId, selectedLayerId, parcelType) {
  map.on("click", fillLayerId, (e) => {
    if (circleMode) return;
    if (!e.features || e.features.length === 0) return;
    const feature = e.features[0];
    const id = feature.id;
    const props = feature.properties;

    // Clear both selections, then highlight clicked
    map.setFilter("cadastral_freehold-selected", ["==", ["id"], -1]);
    map.setFilter("cadastral_leasehold-selected", ["==", ["id"], -1]);
    map.setFilter(selectedLayerId, ["==", ["id"], id]);

    // Fetch full details and open flyout
    fetch(`${API}/parcel/${id}?parcel_type=${parcelType}`)
      .then((r) => r.json())
      .then((data) => showParcelFlyout(data))
      .catch(() => showParcelFlyout(props));
  });

  map.on("mouseenter", fillLayerId, () => {
    map.getCanvas().style.cursor = "pointer";
  });
  map.on("mouseleave", fillLayerId, () => {
    map.getCanvas().style.cursor = "";
  });
}

// ── Planning app click handler ────────────────────────────────────────────────
function setupPlanningClick(fillLayerId, selectedLayerId) {
  map.on("click", fillLayerId, (e) => {
    if (circleMode) return;
    if (!e.features || e.features.length === 0) return;
    const feature = e.features[0];
    const id = feature.id;
    const props = feature.properties;

    // Clear all selections
    map.setFilter("cadastral_freehold-selected", ["==", ["id"], -1]);
    map.setFilter("cadastral_leasehold-selected", ["==", ["id"], -1]);
    if (selectedLayerId && map.getLayer(selectedLayerId)) {
      map.setFilter(selectedLayerId, ["==", ["id"], id]);
    }

    showPlanningFlyout(props);
  });

  map.on("mouseenter", fillLayerId, () => {
    map.getCanvas().style.cursor = "pointer";
  });
  map.on("mouseleave", fillLayerId, () => {
    map.getCanvas().style.cursor = "";
  });
}

// ── Sold property click handler ───────────────────────────────────────────────
function setupSoldPropertyClick() {
  map.on("click", "sold_properties-fill", (e) => {
    if (circleMode) return;
    if (!e.features || e.features.length === 0) return;
    const props = e.features[0].properties;

    // Clear other selections
    map.setFilter("cadastral_freehold-selected", ["==", ["id"], -1]);
    map.setFilter("cadastral_leasehold-selected", ["==", ["id"], -1]);
    if (map.getLayer("dlr_planning_polygons-selected")) {
      map.setFilter("dlr_planning_polygons-selected", ["==", ["id"], -1]);
    }

    showSoldFlyout(props);
  });

  map.on("mouseenter", "sold_properties-fill", () => {
    map.getCanvas().style.cursor = "pointer";
  });
  map.on("mouseleave", "sold_properties-fill", () => {
    map.getCanvas().style.cursor = "";
  });
}

map.on("load", () => {
  setupParcelClick("cadastral_freehold-fill", "cadastral_freehold-selected", "freehold");
  setupParcelClick("cadastral_leasehold-fill", "cadastral_leasehold-selected", "leasehold");
  setupPlanningClick("dlr_planning_polygons-fill", "dlr_planning_polygons-selected");
  setupPlanningClick("dlr_planning_points-fill", null);
  setupSoldPropertyClick();
});

// ── Flyout Panel ─────────────────────────────────────────────────────────────
const flyoutPanel = document.getElementById("flyout-panel");
const flyoutContent = document.getElementById("flyout-content");
const flyoutTitle = document.getElementById("flyout-title");

function openFlyout(title) {
  flyoutTitle.textContent = title || "Detail";
  flyoutPanel.classList.add("open");
}

function closeFlyout() {
  flyoutPanel.classList.remove("open");
  map.setFilter("cadastral_freehold-selected", ["==", ["id"], -1]);
  map.setFilter("cadastral_leasehold-selected", ["==", ["id"], -1]);
  if (map.getLayer("dlr_planning_polygons-selected")) {
    map.setFilter("dlr_planning_polygons-selected", ["==", ["id"], -1]);
  }
}

document.getElementById("flyout-close").addEventListener("click", closeFlyout);

document.getElementById("flyout-back").addEventListener("click", () => {
  closeFlyout();
  document.getElementById("ai-input").focus();
});

// Escape closes flyout
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && flyoutPanel.classList.contains("open")) {
    closeFlyout();
  }
});

function showParcelFlyout(data) {
  const areaSqm = data.area_sqm ? data.area_sqm.toLocaleString() : "—";
  const areaAcres = data.area_acres != null ? data.area_acres : "—";
  const typeLabel = (data.type || "freehold").charAt(0).toUpperCase() + (data.type || "freehold").slice(1);
  const typeColor = data.type === "leasehold" ? "#6495ed" : "#ff8c00";

  flyoutContent.innerHTML = `
    <div class="detail-row">
      <div class="detail-label">Area</div>
      <div class="detail-value large">${areaSqm} m²</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Acres</div>
      <div class="detail-value">${areaAcres} ac</div>
    </div>
    <hr>
    <div class="detail-row">
      <div class="detail-label">National Cadastral Ref</div>
      <div class="detail-value">${data.national_ref || "—"}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">INSPIRE ID</div>
      <div class="detail-value">${data.inspire_id || "—"}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Parcel Type</div>
      <div class="detail-value" style="color:${typeColor}">${typeLabel}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Internal ID</div>
      <div class="detail-value">${data.id || "—"}</div>
    </div>
  `;

  openFlyout("Parcel Detail");
}

function showPlanningFlyout(data) {
  function fmtDate(d) {
    if (!d || d === "(null)" || d.length < 8) return "—";
    return `${d.slice(6, 8)}/${d.slice(4, 6)}/${d.slice(0, 4)}`;
  }

  const decisionColor =
    data.decision && data.decision.toUpperCase().includes("GRANT")
      ? "#2ecc71"
      : data.decision && data.decision.toUpperCase().includes("REFUS")
        ? "#e74c3c"
        : "#ccc";

  const moreInfoLink = data.more_info && data.more_info !== "(null)"
    ? `<a href="${data.more_info}" target="_blank" rel="noopener" style="color:#3498db;word-break:break-all;">View on DLR</a>`
    : "—";

  flyoutContent.innerHTML = `
    <div class="detail-row">
      <div class="detail-label">Planning Ref</div>
      <div class="detail-value large" style="color:#2ecc71">${data.plan_ref || "—"}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Decision</div>
      <div class="detail-value" style="color:${decisionColor}">${data.decision || "—"}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Stage</div>
      <div class="detail-value">${data.stage || "—"}</div>
    </div>
    <hr>
    <div class="detail-row">
      <div class="detail-label">Location</div>
      <div class="detail-value">${data.location || "—"}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Description</div>
      <div class="detail-value" style="font-size:0.85em;line-height:1.4">${data.descrptn || "—"}</div>
    </div>
    <hr>
    <div class="detail-row">
      <div class="detail-label">Registered</div>
      <div class="detail-value">${fmtDate(data.reg_date)}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Decision Date</div>
      <div class="detail-value">${fmtDate(data.dec_date)}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Planning Authority</div>
      <div class="detail-value">${data.plan_auth || "—"}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">More Info</div>
      <div class="detail-value">${moreInfoLink}</div>
    </div>
  `;

  openFlyout("Planning Application");
}

function showSoldFlyout(data) {
  const salePrice = data.sale_price ? `€${Number(data.sale_price).toLocaleString()}` : "—";
  const askingPrice = data.asking_price ? `€${Number(data.asking_price).toLocaleString()}` : "—";
  const priceDelta = data.sale_price && data.asking_price
    ? `${data.sale_price > data.asking_price ? "+" : ""}€${(data.sale_price - data.asking_price).toLocaleString()}`
    : null;
  const deltaColor = priceDelta && data.sale_price > data.asking_price ? "#e74c3c" : "#2ecc71";
  const pricePerSqm = data.price_per_sqm ? `€${Number(data.price_per_sqm).toLocaleString()}/m²` : "—";
  const floorArea = data.floor_area_m2 ? `${data.floor_area_m2} m²` : "—";
  const beds = data.beds != null ? data.beds : "—";
  const baths = data.baths != null ? data.baths : "—";
  const saleDate = data.sale_date || "—";
  const listingLink = data.url
    ? `<a href="${data.url}" target="_blank" rel="noopener" style="color:#3498db;word-break:break-all;">View Listing</a>`
    : "—";

  flyoutContent.innerHTML = `
    <div class="detail-row">
      <div class="detail-label">Sale Price</div>
      <div class="detail-value large" style="color:#e74c3c">${salePrice}</div>
    </div>
    ${priceDelta ? `<div class="detail-row">
      <div class="detail-label">vs Asking</div>
      <div class="detail-value" style="color:${deltaColor}">${priceDelta} (asking ${askingPrice})</div>
    </div>` : `<div class="detail-row">
      <div class="detail-label">Asking Price</div>
      <div class="detail-value">${askingPrice}</div>
    </div>`}
    <div class="detail-row">
      <div class="detail-label">Price / m²</div>
      <div class="detail-value">${pricePerSqm}</div>
    </div>
    <hr>
    <div class="detail-row">
      <div class="detail-label">Address</div>
      <div class="detail-value" style="font-size:0.85em;line-height:1.4">${data.address || "—"}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Beds / Baths</div>
      <div class="detail-value">${beds} bed · ${baths} bath</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Floor Area</div>
      <div class="detail-value">${floorArea}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Property Type</div>
      <div class="detail-value">${data.property_type || "—"}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">BER</div>
      <div class="detail-value">${data.energy_rating || "—"}</div>
    </div>
    <hr>
    <div class="detail-row">
      <div class="detail-label">Sale Date</div>
      <div class="detail-value">${saleDate}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Agent</div>
      <div class="detail-value">${data.agent_name || "—"}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Listing</div>
      <div class="detail-value">${listingLink}</div>
    </div>
  `;

  openFlyout("Sold Property");
}

function showRzltFlyout(data) {
  const area = data.site_area ? `${Number(data.site_area).toLocaleString()}` : "—";

  flyoutContent.innerHTML = `
    <div class="detail-row">
      <div class="detail-label">Zone Description</div>
      <div class="detail-value large" style="color:#ff6b6b">${data.zone_desc || "—"}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Site Area</div>
      <div class="detail-value">${area} m²</div>
    </div>
    <hr>
    <div class="detail-row">
      <div class="detail-label">Zone GZT</div>
      <div class="detail-value">${data.zone_gzt || "—"}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">GZT Description</div>
      <div class="detail-value" style="font-size:0.85em;line-height:1.4">${data.gzt_desc || "—"}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Local Authority</div>
      <div class="detail-value">${data.local_authority_name || "—"}</div>
    </div>
    <hr>
    <div class="detail-row">
      <div class="detail-label" style="color:#ff6b6b">RZLT Status</div>
      <div class="detail-value" style="color:#ff6b6b;font-size:12px;line-height:1.4">Subject to 3% annual Residential Zoned Land Tax — strong motivated seller signal</div>
    </div>
  `;

  openFlyout("RZLT Site");
}

function showGenericFlyout(data) {
  // Build a generic detail view from whatever properties the result has
  const rows = [];
  const skipKeys = new Set(["geometry", "_table", "_rank", "_score", "opportunity_reason", "lng", "lat"]);

  // Show score and reason first
  if (data._score) {
    const scoreColor = data._score >= 80 ? "#22c55e" : data._score >= 60 ? "#f59e0b" : "#888";
    rows.push(`<div class="detail-row"><div class="detail-label">Opportunity Score</div><div class="detail-value large" style="color:${scoreColor}">${data._score}/100</div></div>`);
  }
  if (data.opportunity_reason) {
    rows.push(`<div class="detail-row"><div class="detail-label">Why</div><div class="detail-value" style="color:#22c55e;font-size:12px;line-height:1.4">${data.opportunity_reason}</div></div>`);
  }
  if (rows.length > 0) rows.push("<hr>");

  // Show all other properties
  for (const [key, value] of Object.entries(data)) {
    if (skipKeys.has(key) || key.startsWith("_") || value == null || value === "") continue;
    const label = key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    let displayVal = value;
    if (typeof value === "number") {
      displayVal = key.includes("price") || key.includes("sale") ? `€${value.toLocaleString()}` : value.toLocaleString();
    }
    rows.push(`<div class="detail-row"><div class="detail-label">${label}</div><div class="detail-value">${displayVal}</div></div>`);
  }

  flyoutContent.innerHTML = rows.join("\n");
  openFlyout("Site Detail");
}

// ── Map Panel Collapse / Expand ─────────────────────────────────────────────
const mapPanel = document.getElementById("map-panel");
const resizeDivider = document.getElementById("resize-divider");
const mapCollapseBtn = document.getElementById("map-collapse-btn");
const mapExpandBtn = document.getElementById("map-expand-btn");

function toggleMapPanel() {
  mapCollapsed = !mapCollapsed;

  if (mapCollapsed) {
    savedMapWidth = parseFloat(mapPanel.style.width) || 75;
    mapPanel.classList.add("collapsed");
    resizeDivider.classList.add("hidden");
    mapCollapseBtn.style.display = "none";
    mapExpandBtn.style.display = "inline-flex";
  } else {
    mapPanel.classList.remove("collapsed");
    mapPanel.style.width = savedMapWidth + "%";
    resizeDivider.classList.remove("hidden");
    mapCollapseBtn.style.display = "flex";
    mapExpandBtn.style.display = "none";
    // MapLibre needs to know the container changed
    setTimeout(() => map.resize(), 350);
  }
}

mapCollapseBtn.addEventListener("click", toggleMapPanel);
mapExpandBtn.addEventListener("click", toggleMapPanel);

// Keyboard shortcut: Cmd/Ctrl+\ to toggle map
document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "\\") {
    e.preventDefault();
    toggleMapPanel();
  }
});

// ── Resize divider drag ─────────────────────────────────────────────────────
let isDragging = false;

resizeDivider.addEventListener("mousedown", (e) => {
  e.preventDefault();
  isDragging = true;
  resizeDivider.classList.add("dragging");
  document.body.style.cursor = "col-resize";
  document.body.style.userSelect = "none";
});

document.addEventListener("mousemove", (e) => {
  if (!isDragging) return;
  const appWidth = document.getElementById("app").offsetWidth;
  const newWidth = (e.clientX / appWidth) * 100;
  // Clamp between 20% and 80%
  const clampedWidth = Math.max(20, Math.min(80, newWidth));
  mapPanel.style.width = clampedWidth + "%";
});

document.addEventListener("mouseup", () => {
  if (!isDragging) return;
  isDragging = false;
  resizeDivider.classList.remove("dragging");
  document.body.style.cursor = "";
  document.body.style.userSelect = "";
  // Notify MapLibre of resize
  map.resize();
});

// ── Search ───────────────────────────────────────────────────────────────────
const searchInput = document.getElementById("search-input");
const searchResults = document.getElementById("search-results");

async function doSearch() {
  const q = searchInput.value.trim();
  if (!q) return;

  try {
    const resp = await fetch(`${API}/search?q=${encodeURIComponent(q)}`);
    const data = await resp.json();
    renderSearchResults(data.results || []);
  } catch (err) {
    console.error("Search failed:", err);
  }
}

function renderSearchResults(results) {
  searchResults.innerHTML = "";
  if (results.length === 0) {
    searchResults.innerHTML = '<div class="search-result-item">No results found</div>';
    searchResults.style.display = "block";
    return;
  }

  results.forEach((r) => {
    const item = document.createElement("div");
    item.className = "search-result-item";
    item.textContent = r.display_name;
    item.addEventListener("click", () => {
      map.flyTo({ center: [r.lng, r.lat], zoom: 16, duration: 1200 });
      searchResults.style.display = "none";
      searchInput.value = r.display_name;
    });
    searchResults.appendChild(item);
  });

  searchResults.style.display = "block";
}

document.getElementById("search-btn").addEventListener("click", doSearch);

searchInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") doSearch();
  if (e.key === "Escape") searchResults.style.display = "none";
});

// Hide results on outside click
document.addEventListener("click", (e) => {
  if (!e.target.closest("#search-container")) {
    searchResults.style.display = "none";
  }
});

// ── Layer toggles ────────────────────────────────────────────────────────────
async function loadLayers() {
  try {
    const resp = await fetch(`${API}/layers`);
    const data = await resp.json();
    renderLayerPanel(data.layers || []);
  } catch (err) {
    console.error("Failed to load layers:", err);
    renderLayerPanel([
      { name: "cadastral_freehold", display_name: "Cadastral Parcels (Freehold)", is_active: true },
      { name: "cadastral_leasehold", display_name: "Cadastral Parcels (Leasehold)", is_active: true },
    ]);
  }
}

function renderLayerPanel(layers) {
  const panel = document.getElementById("layer-list");
  panel.innerHTML = "";

  layers.forEach((layer) => {
    const item = document.createElement("div");
    item.className = "layer-item";

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.id = `layer-${layer.name}`;
    cb.checked = layer.is_active !== false;

    const label = document.createElement("label");
    label.htmlFor = cb.id;
    label.textContent = layer.display_name;

    cb.addEventListener("change", () => {
      const visible = cb.checked;
      const visibility = visible ? "visible" : "none";
      console.log(`Toggle ${layer.name}: ${visibility}`);

      // Set visibility on all sub-layers
      [`${layer.name}-fill`, `${layer.name}-outline`, `${layer.name}-selected`].forEach((lid) => {
        if (map.getLayer(lid)) {
          map.setLayoutProperty(lid, "visibility", visibility);
        } else {
          console.warn(`Layer not found: ${lid}`);
        }
      });

      // Convert layer.name (underscores) to source name (hyphens)
      const sourceName = layer.name.replace(/_/g, "-");
      if (!visible) {
        // Clear source data when hiding
        const src = map.getSource(sourceName);
        if (src) src.setData({ type: "FeatureCollection", features: [] });
      } else {
        // Reload data when showing
        loadParcels();
      }
    });

    item.appendChild(cb);
    item.appendChild(label);
    panel.appendChild(item);
  });
}

// ── Circle analysis tool ──────────────────────────────────────────────────────

// Distance in metres between two lng/lat points (Haversine)
function haversineMetres(lng1, lat1, lng2, lat2) {
  const R = 6371000;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lng2 - lng1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

// Generate a GeoJSON circle polygon from center + radius (no library needed)
function makeCircleGeoJSON(center, radiusM, steps = 64) {
  const coords = [];
  const earthRadius = 6371000; // metres
  const lat = (center.lat * Math.PI) / 180;
  const lng = (center.lng * Math.PI) / 180;
  for (let i = 0; i <= steps; i++) {
    const angle = (i / steps) * 2 * Math.PI;
    const dx = radiusM * Math.cos(angle);
    const dy = radiusM * Math.sin(angle);
    const newLat = lat + dy / earthRadius;
    const newLng = lng + dx / (earthRadius * Math.cos(lat));
    coords.push([(newLng * 180) / Math.PI, (newLat * 180) / Math.PI]);
  }
  return {
    type: "FeatureCollection",
    features: [{ type: "Feature", geometry: { type: "Polygon", coordinates: [coords] }, properties: {} }],
  };
}

function toggleCircleMode() {
  circleMode = !circleMode;
  const btn = document.getElementById("circle-mode-btn");
  if (!btn) return;
  const mapEl = document.getElementById("map");
  if (circleMode) {
    btn.classList.add("active");
    if (mapEl) mapEl.classList.add("circle-mode");
    if (map && map.dragPan) map.dragPan.disable();
  } else {
    btn.classList.remove("active");
    if (mapEl) mapEl.classList.remove("circle-mode");
    if (map && map.dragPan) map.dragPan.enable();
    clearCircle();
  }
}

document.getElementById("circle-mode-btn")?.addEventListener("click", toggleCircleMode);

// Layer panel expand/collapse
const layerPanel = document.getElementById("layer-panel");
document.getElementById("layer-toggle-btn")?.addEventListener("click", () => {
  layerPanel?.classList.toggle("collapsed");
});

function clearCircle() {
  circleCenter = null;
  circleDrawing = false;
  const src = map.getSource("analysis-circle");
  if (src) src.setData({ type: "FeatureCollection", features: [] });
  closeFlyout();
}

// Draw circle by click-and-drag: mousedown = center, drag = radius
map.on("mousedown", (e) => {
  if (!circleMode) return;
  e.preventDefault();
  circleCenter = { lng: e.lngLat.lng, lat: e.lngLat.lat };
  circleRadiusM = 100;  // start small
  circleDrawing = true;
  updateCircle();
});

map.on("mousemove", (e) => {
  if (!circleMode || !circleDrawing || !circleCenter) return;
  const dist = haversineMetres(circleCenter.lng, circleCenter.lat, e.lngLat.lng, e.lngLat.lat);
  circleRadiusM = Math.max(100, Math.min(2000, Math.round(dist / 50) * 50));
  updateCircle();
  fetchCircleStats();
});

map.on("mouseup", (e) => {
  if (!circleMode || !circleDrawing) return;
  circleDrawing = false;
  fetchCircleStats();
});

map.on("mouseleave", () => {
  if (circleMode && circleDrawing) {
    circleDrawing = false;
    fetchCircleStats();
  }
});

function updateCircle() {
  if (!circleCenter) return;
  const geoJSON = makeCircleGeoJSON(circleCenter, circleRadiusM);
  const src = map.getSource("analysis-circle");
  if (src) src.setData(geoJSON);
}

let circleStatsTimer = null;
function fetchCircleStats() {
  if (!circleCenter) return;
  clearTimeout(circleStatsTimer);
  circleStatsTimer = setTimeout(() => {
    const url = `${API}/sold_stats?lng=${circleCenter.lng}&lat=${circleCenter.lat}&radius=${circleRadiusM}`;
    fetch(url)
      .then((r) => r.json())
      .then((data) => showCircleStatsFlyout(data))
      .catch((err) => console.error("Failed to fetch circle stats:", err));
  }, 200);
}

function onRadiusChange(val) {
  circleRadiusM = Number(val);
  document.getElementById("radius-display").textContent = `${circleRadiusM}m`;
  updateCircle();
  fetchCircleStats();
}

// ── AI Assistant ─────────────────────────────────────────────────────────────
const aiMessages = document.getElementById("chat-messages");
const aiInput = document.getElementById("ai-input");
const aiSendBtn = document.getElementById("ai-send");
const aiSuggestionsEl = document.getElementById("ai-suggestions");
const aiResultsContainer = document.getElementById("ai-results-container");
const aiResultsList = document.getElementById("ai-results-list");
const aiResultsCount = document.getElementById("ai-results-count");
const aiStarterOptions = document.getElementById("ai-starter-options");

let aiConversation = []; // {role, content}
let aiMarkers = [];       // MapLibre markers on the map
let aiActiveResultIdx = -1;
let aiHasStarted = false; // track if user has made first query

// ── Chat Session Management ─────────────────────────────────────────────────
const CHATS_STORAGE_KEY = "landos_chats";
let chatSessions = [];    // array of {id, title, created_at, updated_at, messages, results}
let activeChatId = null;
let sidebarOpen = false;

function generateChatId() {
  return "chat_" + Date.now() + "_" + Math.random().toString(36).substring(2, 7);
}

function loadChatsFromStorage() {
  try {
    const raw = localStorage.getItem(CHATS_STORAGE_KEY);
    if (raw) {
      const data = JSON.parse(raw);
      chatSessions = data.chats || [];
      activeChatId = data.active_chat_id || null;
    }
  } catch (e) {
    console.error("Failed to load chats from storage:", e);
    chatSessions = [];
    activeChatId = null;
  }
}

function saveChatsToStorage() {
  try {
    localStorage.setItem(CHATS_STORAGE_KEY, JSON.stringify({
      chats: chatSessions,
      active_chat_id: activeChatId,
    }));
  } catch (e) {
    console.error("Failed to save chats to storage:", e);
  }
}

function getActiveChat() {
  return chatSessions.find(c => c.id === activeChatId) || null;
}

function autoTitleChat(chat) {
  if (!chat || chat.title) return;
  const firstUserMsg = chat.messages.find(m => m.role === "user");
  if (firstUserMsg) {
    const text = firstUserMsg.content;
    chat.title = text.length > 50 ? text.substring(0, 47) + "…" : text;
  }
}

function createNewChat(skipRender) {
  // Save current state before switching
  syncCurrentChatState();

  const chat = {
    id: generateChatId(),
    title: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    messages: [],
    lastResults: null,
  };
  chatSessions.unshift(chat);
  activeChatId = chat.id;
  saveChatsToStorage();

  // Reset UI
  resetChatUI();

  if (!skipRender) renderChatList();
}

function switchToChat(chatId) {
  if (chatId === activeChatId) return;

  // Save current state
  syncCurrentChatState();

  activeChatId = chatId;
  const chat = getActiveChat();
  if (!chat) return;

  saveChatsToStorage();

  // Reset UI and replay messages
  resetChatUI();
  replayChatMessages(chat);
  renderChatList();
}

function deleteChat(chatId) {
  chatSessions = chatSessions.filter(c => c.id !== chatId);
  if (activeChatId === chatId) {
    if (chatSessions.length > 0) {
      activeChatId = chatSessions[0].id;
      resetChatUI();
      replayChatMessages(getActiveChat());
    } else {
      createNewChat(true);
    }
  }
  saveChatsToStorage();
  renderChatList();
}

function syncCurrentChatState() {
  const chat = getActiveChat();
  if (!chat) return;
  chat.messages = [...aiConversation];
  chat.updated_at = new Date().toISOString();
  autoTitleChat(chat);
  // Store last results for restoring map markers
  if (showAiResults._currentResults) {
    chat.lastResults = showAiResults._currentResults;
  }
}

function resetChatUI() {
  // Clear messages
  aiMessages.innerHTML = `<div class="ai-msg ai-msg-assistant">
    <div class="ai-msg-content">Explore Dublin development opportunities. Pick an analysis below or type your own query.</div>
  </div>`;
  aiConversation = [];
  aiSuggestionsEl.innerHTML = "";
  aiResultsContainer.style.display = "none";
  aiResultsList.innerHTML = "";
  clearAiMarkers();
  showAiResults._currentResults = null;
  aiActiveResultIdx = -1;
  closeFlyout();

  // Show starters again
  aiHasStarted = false;
  if (aiStarterOptions) {
    aiStarterOptions.style.display = "";
    renderStarterOptions();
  }
  aiInput.value = "";
  aiInput.focus();
}

function replayChatMessages(chat) {
  if (!chat || chat.messages.length === 0) return;

  aiHasStarted = true;
  if (aiStarterOptions) aiStarterOptions.style.display = "none";
  aiConversation = [...chat.messages];

  // Replay visible messages
  chat.messages.forEach(msg => {
    if (msg.role === "user") {
      addAiMessage("user", msg.content);
    } else if (msg.role === "assistant") {
      // Try to parse structured response
      try {
        const data = JSON.parse(msg.content);
        if (data.type === "explore" && data.title) {
          addAiMessage("assistant", `${data.title}\n${data.summary || ""}`);
        } else if (data.message) {
          addAiMessage("assistant", data.message);
        } else {
          addAiMessage("assistant", msg.content);
        }
      } catch {
        addAiMessage("assistant", msg.content);
      }
    }
  });

  // Restore last results on map if available
  if (chat.lastResults && chat.lastResults.length > 0) {
    showAiResults(chat.lastResults);
  }
}

function relativeTime(dateStr) {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffSec = Math.floor((now - then) / 1000);
  if (diffSec < 60) return "just now";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

function renderChatList() {
  const chatList = document.getElementById("chat-list");
  if (!chatList) return;
  chatList.innerHTML = "";

  // Sort by most recent
  const sorted = [...chatSessions].sort((a, b) =>
    new Date(b.updated_at) - new Date(a.updated_at)
  );

  sorted.forEach(chat => {
    const item = document.createElement("div");
    item.className = `chat-list-item${chat.id === activeChatId ? " active" : ""}`;
    item.dataset.chatId = chat.id;

    const title = chat.title || "New chat";
    const time = relativeTime(chat.updated_at);
    const msgCount = chat.messages.filter(m => m.role === "user").length;

    item.innerHTML = `
      <div class="chat-item-content">
        <div class="chat-item-title">${title}</div>
        <div class="chat-item-meta">${msgCount} message${msgCount !== 1 ? "s" : ""} · ${time}</div>
      </div>
      <button class="chat-item-delete" title="Delete chat">&#x2715;</button>
    `;

    item.addEventListener("click", (e) => {
      if (e.target.closest(".chat-item-delete")) return;
      switchToChat(chat.id);
      if (window.innerWidth < 768) toggleSidebar(); // auto-close on mobile
    });

    item.querySelector(".chat-item-delete").addEventListener("click", (e) => {
      e.stopPropagation();
      deleteChat(chat.id);
    });

    chatList.appendChild(item);
  });
}

function toggleSidebar() {
  sidebarOpen = !sidebarOpen;
  const sidebar = document.getElementById("chat-sidebar");
  if (sidebar) {
    sidebar.classList.toggle("open", sidebarOpen);
  }
}

// Wire up sidebar toggle and new chat buttons
document.getElementById("sidebar-toggle-btn")?.addEventListener("click", toggleSidebar);
document.getElementById("new-chat-btn")?.addEventListener("click", () => {
  createNewChat();
  if (window.innerWidth < 768) toggleSidebar();
});

// Keyboard shortcut: Cmd/Ctrl+N for new chat
document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "n") {
    e.preventDefault();
    createNewChat();
  }
});

// Initialize: load chats and restore active session
loadChatsFromStorage();
if (chatSessions.length === 0) {
  createNewChat(true);
} else if (activeChatId) {
  const chat = getActiveChat();
  if (chat && chat.messages.length > 0) {
    replayChatMessages(chat);
  }
}
renderChatList();

// ── 5 Starter analysis options ──────────────────────────────────────────────
const STARTER_OPTIONS = [
  {
    icon: "📉",
    label: "Undervalued areas",
    prompt: "Find areas in Dublin where properties are selling significantly below asking price. Cross-reference with nearby RZLT sites and large parcels to identify development opportunities where land may be undervalued.",
    reason: "Properties selling below asking price signal weak demand or motivated sellers. Combined with RZLT tax pressure and available land, these areas often represent the best entry points for developers before prices correct upward."
  },
  {
    icon: "🔥",
    label: "RZLT motivated sellers",
    prompt: "Find the largest RZLT (Residential Zoned Land Tax) sites in Dublin. For each area with RZLT sites, also show nearby sold property prices to estimate land value and development potential.",
    reason: "RZLT imposes a 3% annual tax on idle zoned land — owners of large sites face growing holding costs every year. This creates urgency to sell or develop, giving buyers negotiation leverage that doesn't exist in normal market conditions."
  },
  {
    icon: "🏗️",
    label: "Large development sites",
    prompt: "Find the largest freehold parcels (1000+ sqm) across Dublin. Cross-reference with RZLT zones, nearby sold property prices per sqm, and any planning applications to assess development feasibility.",
    reason: "Large freehold parcels are the raw material for multi-unit developments. By cross-referencing with zoning, nearby prices, and planning history, you can quickly identify which big sites are actually buildable and what the end-sale revenue might look like."
  },
  {
    icon: "✅",
    label: "Planning approval hotspots",
    prompt: "Analyze planning applications in Dún Laoghaire-Rathdown. Find areas with the most granted planning permissions, especially for multi-unit residential. Show nearby property prices to estimate post-development values.",
    reason: "Areas with high planning approval rates have a proven permitting pathway — the council has already said yes to similar projects nearby. This dramatically reduces your biggest risk (planning refusal) and gives you precedent to reference in your own application."
  },
  {
    icon: "💰",
    label: "Best price-per-sqm value",
    prompt: "Find properties and areas with the lowest price per square metre in Dublin. Compare different neighborhoods and property types. Identify where floor space is cheapest relative to the Dublin average and cross-reference with development land availability.",
    reason: "Low price-per-sqm areas that are adjacent to expensive neighborhoods represent the classic 'gentrification frontier.' Developers who build quality stock in these transition zones capture the price convergence as the area improves."
  },
];

function renderStarterOptions() {
  if (!aiStarterOptions) return;
  aiStarterOptions.innerHTML = "";

  STARTER_OPTIONS.forEach((opt, idx) => {
    const btn = document.createElement("button");
    btn.className = "ai-starter-btn";
    btn.dataset.idx = idx;
    btn.innerHTML = `
      <span class="ai-starter-icon">${opt.icon}</span>
      <div class="ai-starter-text">
        <span class="ai-starter-label">${opt.label}</span>
        <span class="ai-starter-desc">${opt.reason.split('.')[0]}.</span>
      </div>
    `;

    // Single click runs the analysis immediately — no explainer friction
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      hideStarterOptions();
      sendAiMessage(opt.prompt);
    });

    aiStarterOptions.appendChild(btn);
  });
}

function hideStarterOptions() {
  if (aiStarterOptions) aiStarterOptions.style.display = "none";
  aiHasStarted = true;
  // Remove any explainer too
  document.querySelectorAll(".ai-starter-explainer").forEach(el => el.remove());
}

// Render starters on load
setTimeout(() => {
  renderStarterOptions();
  aiInput.focus();
}, 400);

// Send message
async function sendAiMessage(text) {
  if (!text || !text.trim()) return;
  text = text.trim();

  // Hide starters on first use
  if (!aiHasStarted) hideStarterOptions();

  // Add user message to UI
  addAiMessage("user", text);
  aiInput.value = "";
  aiSuggestionsEl.innerHTML = "";

  // Add to conversation
  aiConversation.push({ role: "user", content: text });

  // Persist user message immediately
  syncCurrentChatState();
  saveChatsToStorage();
  renderChatList();

  // Show loading with staged progress messages
  const loadingEl = addAiMessage("loading", "Thinking");
  aiSendBtn.classList.add("loading");

  // Staged loading messages for polish
  const loadingStages = [
    { text: "Forming analysis strategy", delay: 1500 },
    { text: "Querying property database", delay: 4000 },
    { text: "Ranking opportunities", delay: 7000 },
  ];
  const stageTimers = loadingStages.map(stage =>
    setTimeout(() => {
      const content = loadingEl.querySelector(".ai-msg-content");
      if (content) content.innerHTML = `<span class="ai-loading-icon">&#9889;</span>${stage.text}<span class="ai-loading-dots"></span>`;
    }, stage.delay)
  );

  try {
    const resp = await fetch(`${API}/ai/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: aiConversation }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `Error ${resp.status}`);
    }

    const data = await resp.json();

    // Remove loading
    stageTimers.forEach(clearTimeout);
    loadingEl.remove();
    aiSendBtn.classList.remove("loading");

    // Store response in conversation
    aiConversation.push({ role: "assistant", content: JSON.stringify(data) });

    // Persist chat session
    syncCurrentChatState();
    saveChatsToStorage();
    renderChatList();

    // Handle explore response — flat ranked results, no hypothesis switching
    if (data.type === "explore") {
      const summaryText = data.title
        ? `${data.title}\n${data.summary || ""}`
        : data.summary || data.message || "Analysis complete.";
      addAiMessage("assistant", summaryText);

      // Show query stats as a subtle indicator
      if (data.query_stats) {
        const stats = data.query_stats;
        if (stats.total > 0 && stats.successful < stats.total) {
          addAiMessage("assistant", `Ran ${stats.total} queries across the database (${stats.successful} returned results).`);
        }
      }

      if (data.results && data.results.length > 0) {
        showAiResults(data.results);
      } else {
        addAiMessage("assistant", "No matching sites found for this query. Try a different area or broader criteria.");
      }

      if (data.follow_ups && data.follow_ups.length > 0) {
        showAiFollowUps(data.follow_ups);
      }
    }
    // Fallback for clarify
    else if (data.type === "clarify") {
      addAiMessage("assistant", data.message || "Let me try that differently...");
      if (data.suggestions && data.suggestions.length > 0) {
        showAiFollowUps(data.suggestions.map(s => ({
          label: s.length > 30 ? s.substring(0, 28) + "…" : s,
          prompt: s,
        })));
      }
    }
    else {
      addAiMessage("assistant", data.message || JSON.stringify(data));
    }
  } catch (err) {
    stageTimers.forEach(clearTimeout);
    loadingEl.remove();
    aiSendBtn.classList.remove("loading");
    addAiMessage("assistant", `Something went wrong: ${err.message}`);
    console.error("AI chat error:", err);
  }
}

function addAiMessage(role, text) {
  const div = document.createElement("div");
  div.className = `ai-msg ai-msg-${role}`;

  const content = document.createElement("div");
  content.className = "ai-msg-content";

  if (role === "loading") {
    content.innerHTML = `<span class="ai-loading-icon">⚡</span>${text}<span class="ai-loading-dots"></span>`;
  } else if (role === "assistant" && text.includes("\n")) {
    // Title + summary split
    const lines = text.split("\n");
    const titleEl = document.createElement("div");
    titleEl.className = "ai-msg-title";
    titleEl.textContent = lines[0];
    const bodyEl = document.createElement("div");
    bodyEl.className = "ai-msg-body";
    bodyEl.textContent = lines.slice(1).join("\n").trim();
    content.appendChild(titleEl);
    content.appendChild(bodyEl);
  } else {
    content.textContent = text;
  }

  div.appendChild(content);
  aiMessages.appendChild(div);
  aiMessages.scrollTop = aiMessages.scrollHeight;

  return div;
}


function showAiFollowUps(followUps) {
  aiSuggestionsEl.innerHTML = "";
  followUps.forEach((fu) => {
    const chip = document.createElement("button");
    chip.className = "ai-followup-chip";

    const label = typeof fu === "string" ? fu : fu.label;
    const prompt = typeof fu === "string" ? fu : fu.prompt;

    chip.innerHTML = `<span class="ai-followup-label">${label}</span>`;
    chip.setAttribute("title", prompt);

    chip.addEventListener("click", () => {
      sendAiMessage(prompt);
    });
    aiSuggestionsEl.appendChild(chip);
  });
}

function showAiResults(results) {
  clearAiMarkers();
  aiResultsContainer.style.display = "block";
  aiResultsCount.textContent = `${results.length} site${results.length !== 1 ? "s" : ""} found`;
  aiResultsList.innerHTML = "";
  aiActiveResultIdx = -1;

  // Store results reference for keyboard navigation
  showAiResults._currentResults = results;

  results.forEach((result, idx) => {
    const isTopPick = idx === 0;
    const score = result._score || 0;
    const card = document.createElement("div");
    card.className = `ai-result-card${isTopPick ? " ai-result-top-pick" : ""}`;
    card.dataset.idx = idx;

    // Rank badge with score ring
    const rank = document.createElement("div");
    rank.className = `ai-result-rank${isTopPick ? " ai-result-rank-top" : ""}`;
    rank.textContent = idx + 1;

    // Info section
    const info = document.createElement("div");
    info.className = "ai-result-info";

    const titleRow = document.createElement("div");
    titleRow.className = "ai-result-title-row";
    const title = document.createElement("div");
    title.className = "ai-result-title";

    // Score pill
    const scorePill = document.createElement("span");
    scorePill.className = `ai-result-score${score >= 80 ? " score-high" : score >= 60 ? " score-mid" : " score-low"}`;
    scorePill.textContent = score;

    const meta = document.createElement("div");
    meta.className = "ai-result-meta";

    // Format based on table type
    const table = result._table;
    if (table === "sold_properties") {
      title.textContent = result.address || "Unknown Address";
      const price = result.sale_price ? `€${Number(result.sale_price).toLocaleString()}` : "—";
      const area = result.floor_area_m2 ? `${result.floor_area_m2}m²` : "";
      const beds = result.beds ? `${result.beds}bed` : "";
      meta.textContent = [price, result.property_type, area, beds].filter(Boolean).join(" · ");
    } else if (table === "cadastral_freehold" || table === "cadastral_leasehold") {
      title.textContent = result.nationalcadastralreference || result.national_ref || result.inspire_id || `Parcel #${result.ogc_fid || result.id || ""}`;
      const area = result.area_sqm ? `${Number(result.area_sqm).toLocaleString()}m²` : "";
      const acres = result.area_sqm ? `(${(result.area_sqm / 4046.86).toFixed(2)}ac)` : "";
      const type = table === "cadastral_freehold" ? "Freehold" : "Leasehold";
      meta.textContent = [type, area, acres].filter(Boolean).join(" · ");
    } else if (table === "rzlt") {
      title.textContent = result.zone_desc || "RZLT Site";
      const area = result.site_area ? `${Number(result.site_area).toLocaleString()}m²` : "";
      meta.textContent = [result.local_authority_name, area, "3% annual tax"].filter(Boolean).join(" · ");
    } else if (table === "dlr_planning_polygons" || table === "dlr_planning_points") {
      title.textContent = result.plan_ref || "Planning App";
      meta.textContent = [result.decision, result.location].filter(Boolean).join(" · ");
    } else {
      // Generic fallback for unknown table types
      title.textContent = result.address || result.nationalcadastralreference || result.plan_ref || result.zone_desc || `Site #${idx + 1}`;
      const metaParts = [];
      if (result.sale_price) metaParts.push(`€${Number(result.sale_price).toLocaleString()}`);
      if (result.area_sqm) metaParts.push(`${Number(result.area_sqm).toLocaleString()}m²`);
      if (result.site_area) metaParts.push(`${Number(result.site_area).toLocaleString()}m²`);
      if (result.property_type) metaParts.push(result.property_type);
      if (result.decision) metaParts.push(result.decision);
      meta.textContent = metaParts.join(" · ") || `${result.lat?.toFixed(4)}, ${result.lng?.toFixed(4)}`;
    }

    titleRow.appendChild(title);
    titleRow.appendChild(scorePill);
    info.appendChild(titleRow);
    info.appendChild(meta);

    // Opportunity reason
    if (result.opportunity_reason) {
      const reason = document.createElement("div");
      reason.className = "ai-result-reason";
      reason.textContent = result.opportunity_reason;
      info.appendChild(reason);
    }

    // Badge
    const badge = document.createElement("div");
    badge.className = "ai-result-badge";
    if (table === "sold_properties") {
      badge.classList.add("price");
      badge.textContent = result.sale_price ? `€${(result.sale_price / 1000).toFixed(0)}k` : "—";
    } else if (table && table.startsWith("cadastral")) {
      badge.classList.add("area");
      badge.textContent = result.area_sqm ? `${(result.area_sqm / 1000).toFixed(1)}k m²` : "—";
    } else if (table === "rzlt") {
      badge.classList.add("rzlt");
      badge.textContent = "RZLT";
    } else if (table === "dlr_planning_polygons" || table === "dlr_planning_points") {
      badge.classList.add("planning");
      badge.textContent = result.decision ? result.decision.substring(0, 6) : "Plan";
    } else {
      // Generic badge
      badge.textContent = score ? `${score}` : "—";
    }

    card.appendChild(rank);
    card.appendChild(info);
    card.appendChild(badge);
    aiResultsList.appendChild(card);

    // Add map marker
    if (result.lng && result.lat) {
      const markerEl = document.createElement("div");
      markerEl.className = `ai-marker${isTopPick ? " ai-marker-top" : ""}`;
      markerEl.textContent = idx + 1;
      markerEl.dataset.idx = idx;

      const marker = new maplibregl.Marker({ element: markerEl })
        .setLngLat([result.lng, result.lat])
        .addTo(map);

      markerEl.addEventListener("click", (e) => {
        e.stopPropagation();
        selectAiResult(idx, results);
      });

      aiMarkers.push({ marker, result });
    }

    // Click handler
    card.addEventListener("click", () => selectAiResult(idx, results));
  });

  // Fit map to show all results and auto-select top pick
  if (results.length > 0) {
    // If map is collapsed, expand it first
    if (mapCollapsed) toggleMapPanel();

    const bounds = new maplibregl.LngLatBounds();
    let hasPoints = false;
    results.forEach((r) => {
      if (r.lng && r.lat) {
        bounds.extend([r.lng, r.lat]);
        hasPoints = true;
      }
    });
    if (hasPoints) {
      map.fitBounds(bounds, { padding: 80, maxZoom: 16, duration: 1200 });
    }

    // Auto-select top pick after map animation
    setTimeout(() => {
      const firstCard = aiResultsList.querySelector(".ai-result-card");
      if (firstCard) {
        firstCard.classList.add("active");
        aiActiveResultIdx = 0;
        document.querySelectorAll(".ai-marker").forEach((m) => {
          m.classList.toggle("active", parseInt(m.dataset.idx) === 0);
        });
      }
    }, 1400);
  }
}

function selectAiResult(idx, results) {
  const result = results[idx];
  if (!result) return;

  aiActiveResultIdx = idx;

  // Highlight card
  aiResultsList.querySelectorAll(".ai-result-card").forEach((c, i) => {
    c.classList.toggle("active", i === idx);
  });

  // Highlight marker
  document.querySelectorAll(".ai-marker").forEach((m) => {
    m.classList.toggle("active", parseInt(m.dataset.idx) === idx);
  });

  // Fly to location
  if (result.lng && result.lat) {
    // If map is collapsed, expand it first
    if (mapCollapsed) toggleMapPanel();
    map.flyTo({ center: [result.lng, result.lat], zoom: 17, duration: 1000 });
  }

  // Show detail in flyout based on type
  const table = result._table;
  if (table === "sold_properties") {
    showSoldFlyout(result);
  } else if (table === "cadastral_freehold" || table === "cadastral_leasehold") {
    showParcelFlyout({
      id: result.ogc_fid || result.id,
      national_ref: result.nationalcadastralreference || result.national_ref,
      inspire_id: result.gml_id || result.inspire_id,
      area_sqm: result.area_sqm,
      area_acres: result.area_sqm ? +(result.area_sqm / 4046.86).toFixed(3) : null,
      type: table === "cadastral_freehold" ? "freehold" : "leasehold",
    });
  } else if (table === "rzlt") {
    showRzltFlyout(result);
  } else if (table === "dlr_planning_polygons" || table === "dlr_planning_points") {
    showPlanningFlyout(result);
  } else {
    showGenericFlyout(result);
  }
}

function clearAiMarkers() {
  aiMarkers.forEach((m) => m.marker.remove());
  aiMarkers = [];
}

document.getElementById("ai-results-close").addEventListener("click", () => {
  aiResultsContainer.style.display = "none";
  aiResultsList.innerHTML = "";
  clearAiMarkers();
});

// Input handlers
aiSendBtn.addEventListener("click", () => sendAiMessage(aiInput.value));

aiInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendAiMessage(aiInput.value);
  }
});

// Keyboard shortcut: Cmd/Ctrl+K to focus chat input
document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "k") {
    e.preventDefault();
    aiInput.focus();
  }
});

// ── Keyboard navigation between results ─────────────────────────────────────
document.addEventListener("keydown", (e) => {
  // Only when results are showing and input is not focused
  if (document.activeElement === aiInput) return;
  const results = showAiResults._currentResults;
  if (!results || results.length === 0) return;

  let targetIdx = -1;

  // Number keys 1-9 jump to that result directly
  if (e.key >= "1" && e.key <= "9") {
    targetIdx = parseInt(e.key) - 1;
  }
  // Arrow down / j = next
  else if (e.key === "ArrowDown" || e.key === "j") {
    e.preventDefault();
    targetIdx = Math.min((aiActiveResultIdx < 0 ? -1 : aiActiveResultIdx) + 1, results.length - 1);
  }
  // Arrow up / k = previous
  else if (e.key === "ArrowUp" || e.key === "k") {
    e.preventDefault();
    targetIdx = Math.max((aiActiveResultIdx < 0 ? 1 : aiActiveResultIdx) - 1, 0);
  }

  if (targetIdx >= 0 && targetIdx < results.length) {
    selectAiResult(targetIdx, results);
    // Scroll the card into view
    const card = aiResultsList.querySelector(`[data-idx="${targetIdx}"]`);
    if (card) card.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
});

// ── Circle analysis ──────────────────────────────────────────────────────────

function showCircleStatsFlyout(data) {
  const count = data.count || 0;

  if (count === 0) {
    flyoutContent.innerHTML = `
      <div class="detail-row">
        <div class="detail-label">Radius</div>
        <div class="detail-value large" style="color:#9b59b6">${data.radius_m}m</div>
      </div>
      <div class="circle-radius-control">
        <input type="range" id="radius-slider" min="100" max="2000" step="50" value="${circleRadiusM}"
          oninput="onRadiusChange(this.value)">
        <span id="radius-display">${circleRadiusM}m</span>
      </div>
      <hr>
      <p style="color:#888; font-size:13px; text-align:center; margin-top:20px;">No sold properties found within this radius.</p>
    `;
    openFlyout("Circle Analysis");
    return;
  }

  const avgSale = `€${data.avg_sale_price.toLocaleString()}`;
  const medianSale = `€${data.median_sale_price.toLocaleString()}`;
  const minSale = `€${data.min_sale_price.toLocaleString()}`;
  const maxSale = `€${data.max_sale_price.toLocaleString()}`;
  const stddev = `€${data.stddev_sale_price.toLocaleString()}`;
  const avgAsking = data.avg_asking_price ? `€${data.avg_asking_price.toLocaleString()}` : "—";
  const avgPsm = data.avg_price_per_sqm ? `€${data.avg_price_per_sqm.toLocaleString()}/m²` : "—";
  const avgArea = data.avg_floor_area_m2 ? `${data.avg_floor_area_m2} m²` : "—";

  // Property type breakdown bars
  const totalForTypes = Object.values(data.property_type_breakdown).reduce((a, b) => a + b, 0);
  const typeBars = Object.entries(data.property_type_breakdown)
    .map(([type, cnt]) => {
      const pct = Math.round((cnt / totalForTypes) * 100);
      return `<div class="type-bar-row">
        <span class="type-bar-label">${type || "Unknown"}</span>
        <div class="type-bar-track"><div class="type-bar-fill" style="width:${pct}%"></div></div>
        <span class="type-bar-count">${cnt}</span>
      </div>`;
    })
    .join("");

  flyoutContent.innerHTML = `
    <div class="detail-row">
      <div class="detail-label">Radius</div>
      <div class="detail-value large" style="color:#9b59b6">${data.radius_m}m</div>
    </div>
    <div class="circle-radius-control">
      <input type="range" id="radius-slider" min="100" max="2000" step="50" value="${circleRadiusM}"
        oninput="onRadiusChange(this.value)">
      <span id="radius-display">${circleRadiusM}m</span>
    </div>
    <hr>
    <div class="detail-row">
      <div class="detail-label">Properties Found</div>
      <div class="detail-value large" style="color:#9b59b6">${count}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Avg Sale Price</div>
      <div class="detail-value large" style="color:#e74c3c">${avgSale}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Median Sale Price</div>
      <div class="detail-value">${medianSale}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Range</div>
      <div class="detail-value">${minSale} — ${maxSale}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Std Deviation</div>
      <div class="detail-value">${stddev}</div>
    </div>
    <hr>
    <div class="detail-row">
      <div class="detail-label">Avg Asking Price</div>
      <div class="detail-value">${avgAsking}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Avg Price / m²</div>
      <div class="detail-value">${avgPsm}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Avg Floor Area</div>
      <div class="detail-value">${avgArea}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Avg Beds / Baths</div>
      <div class="detail-value">${data.avg_beds} bed · ${data.avg_baths} bath</div>
    </div>
    <hr>
    <div class="detail-row">
      <div class="detail-label">Property Types</div>
    </div>
    ${typeBars}
  `;

  openFlyout("Circle Analysis");
}
