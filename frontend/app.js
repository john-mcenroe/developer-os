const API = "http://localhost:8000/api";
const PARCEL_MIN_ZOOM = 15;

// ── Circle analysis state ────────────────────────────────────────────────────
let circleMode = false;
let circleCenter = null;  // { lng, lat }
let circleRadiusM = 500;  // metres
let circleDrawing = false;  // true while dragging to define radius

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
    paint: {
      "fill-color": "rgba(255, 0, 0, 0.2)",
      "fill-outline-color": "rgba(255, 0, 0, 0)",
    },
  });

  map.addLayer({
    id: "rzlt-outline",
    type: "line",
    source: "rzlt",
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

    // Fetch full details and open sidebar
    fetch(`${API}/parcel/${id}?parcel_type=${parcelType}`)
      .then((r) => r.json())
      .then((data) => showSidebar(data))
      .catch(() => showSidebar(props));
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

    showPlanningSidebar(props);
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

    showSoldSidebar(props);
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

// ── Sidebar ──────────────────────────────────────────────────────────────────
function showSidebar(data) {
  const content = document.getElementById("sidebar-content");
  const areaSqm = data.area_sqm ? data.area_sqm.toLocaleString() : "—";
  const areaAcres = data.area_acres != null ? data.area_acres : "—";
  const typeLabel = (data.type || "freehold").charAt(0).toUpperCase() + (data.type || "freehold").slice(1);
  const typeColor = data.type === "leasehold" ? "#6495ed" : "#ff8c00";

  content.innerHTML = `
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

  document.getElementById("sidebar").classList.add("open");
}

function showPlanningSidebar(data) {
  const content = document.getElementById("sidebar-content");

  // Format date from YYYYMMDD to readable
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

  content.innerHTML = `
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

  document.getElementById("sidebar").classList.add("open");
}

function showSoldSidebar(data) {
  const content = document.getElementById("sidebar-content");

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

  content.innerHTML = `
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

  document.getElementById("sidebar").classList.add("open");
}

document.getElementById("sidebar-close").addEventListener("click", () => {
  document.getElementById("sidebar").classList.remove("open");
  map.setFilter("cadastral_freehold-selected", ["==", ["id"], -1]);
  map.setFilter("cadastral_leasehold-selected", ["==", ["id"], -1]);
  if (map.getLayer("dlr_planning_polygons-selected")) {
    map.setFilter("dlr_planning_polygons-selected", ["==", ["id"], -1]);
  }
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

function clearCircle() {
  circleCenter = null;
  circleDrawing = false;
  const src = map.getSource("analysis-circle");
  if (src) src.setData({ type: "FeatureCollection", features: [] });
  document.getElementById("sidebar").classList.remove("open");
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
      .then((data) => showCircleStatsSidebar(data))
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
const aiPanel = document.getElementById("ai-panel");
const aiMessages = document.getElementById("ai-messages");
const aiInput = document.getElementById("ai-input");
const aiSendBtn = document.getElementById("ai-send");
const aiSuggestionsEl = document.getElementById("ai-suggestions");
const aiResultsContainer = document.getElementById("ai-results-container");
const aiResultsList = document.getElementById("ai-results-list");
const aiResultsCount = document.getElementById("ai-results-count");
const aiInsightsContainer = document.getElementById("ai-insights-container");
const aiStarterOptions = document.getElementById("ai-starter-options");

let aiConversation = []; // {role, content}
let aiMarkers = [];       // MapLibre markers on the map
let aiActiveResultIdx = -1;
let aiHasStarted = false; // track if user has made first query

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
    btn.innerHTML = `<span class="ai-starter-icon">${opt.icon}</span><span class="ai-starter-label">${opt.label}</span>`;

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      // Show explainer first
      showStarterExplainer(opt, btn);
    });

    aiStarterOptions.appendChild(btn);
  });
}

function showStarterExplainer(opt, anchorBtn) {
  // Remove any existing explainer
  document.querySelectorAll(".ai-starter-explainer").forEach(el => el.remove());

  const explainer = document.createElement("div");
  explainer.className = "ai-starter-explainer";
  explainer.innerHTML = `
    <div class="ai-explainer-header">
      <span>${opt.icon} ${opt.label}</span>
      <button class="ai-explainer-close" title="Close">✕</button>
    </div>
    <div class="ai-explainer-reason">${opt.reason}</div>
    <button class="ai-explainer-run">Run this analysis →</button>
  `;

  // Insert after the starter options
  aiStarterOptions.parentNode.insertBefore(explainer, aiStarterOptions.nextSibling);

  // Close button
  explainer.querySelector(".ai-explainer-close").addEventListener("click", (e) => {
    e.stopPropagation();
    explainer.remove();
  });

  // Run button
  explainer.querySelector(".ai-explainer-run").addEventListener("click", (e) => {
    e.stopPropagation();
    explainer.remove();
    hideStarterOptions();
    sendAiMessage(opt.prompt);
  });

  // Scroll into view
  setTimeout(() => explainer.scrollIntoView({ behavior: "smooth", block: "nearest" }), 50);
}

function hideStarterOptions() {
  if (aiStarterOptions) aiStarterOptions.style.display = "none";
  aiHasStarted = true;
  // Remove any explainer too
  document.querySelectorAll(".ai-starter-explainer").forEach(el => el.remove());
}

// Toggle panel expand/collapse
function toggleAiPanel() {
  aiPanel.classList.toggle("expanded");
  if (aiPanel.classList.contains("expanded")) {
    setTimeout(() => aiInput.focus(), 350);
  }
}

document.getElementById("ai-panel-header").addEventListener("click", toggleAiPanel);
document.getElementById("ai-panel-expand").addEventListener("click", (e) => {
  e.stopPropagation();
  toggleAiPanel();
});

// Auto-expand on first load and render starters
setTimeout(() => {
  aiPanel.classList.add("expanded");
  renderStarterOptions();
}, 800);

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

  // Clear previous insights
  if (aiInsightsContainer) aiInsightsContainer.innerHTML = "";

  // Add to conversation
  aiConversation.push({ role: "user", content: text });

  // Show loading
  const loadingEl = addAiMessage("loading", "Analyzing across all data layers");
  aiSendBtn.classList.add("loading");

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
    loadingEl.remove();
    aiSendBtn.classList.remove("loading");

    // Store response in conversation
    aiConversation.push({ role: "assistant", content: JSON.stringify(data) });

    // Handle explore response (hypothesis-driven pipeline)
    if (data.type === "explore") {
      // Show title + summary as message
      const summaryText = data.title
        ? `${data.title}\n${data.summary || ""}`
        : data.summary || data.message || "Analysis complete.";
      addAiMessage("assistant", summaryText);

      // Show hypothesis cards
      if (data.hypotheses && data.hypotheses.length > 0) {
        showHypotheses(data.hypotheses);
      }

      // Show results on map
      if (data.results && data.results.length > 0) {
        showAiResults(data.results);
      } else {
        addAiMessage("assistant", "No matching results found on the map for this query. Try a different area or broader criteria.");
      }

      // Show follow-up chips
      if (data.follow_ups && data.follow_ups.length > 0) {
        showAiFollowUps(data.follow_ups);
      }
    }
    // Handle analysis response (legacy format)
    else if (data.type === "analysis") {
      const summaryText = data.title
        ? `${data.title}\n${data.summary || ""}`
        : data.summary || data.message || "Analysis complete.";
      addAiMessage("assistant", summaryText);

      if (data.insights && data.insights.length > 0) {
        showAiInsights(data.insights);
      }

      if (data.results && data.results.length > 0) {
        showAiResults(data.results);
      } else {
        addAiMessage("assistant", "No matching results found on the map for this query. Try a different area or broader criteria.");
      }

      if (data.follow_ups && data.follow_ups.length > 0) {
        showAiFollowUps(data.follow_ups);
      }
    }
    // Backwards compat for "search" type
    else if (data.type === "search") {
      addAiMessage("assistant", data.message || "Search complete.");
      if (data.results && data.results.length > 0) {
        showAiResults(data.results);
      }
    }
    // Fallback for clarify (shouldn't happen with new prompt)
    else if (data.type === "clarify") {
      addAiMessage("assistant", data.message || "Let me try that differently...");
      if (data.suggestions && data.suggestions.length > 0) {
        showAiFollowUps(data.suggestions.map(s => ({
          label: s.length > 30 ? s.substring(0, 28) + "…" : s,
          prompt: s,
          reason: ""
        })));
      }
    }
    else {
      addAiMessage("assistant", data.message || JSON.stringify(data));
    }
  } catch (err) {
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

function showAiInsights(insights) {
  if (!aiInsightsContainer) return;
  aiInsightsContainer.innerHTML = "";
  aiInsightsContainer.style.display = "block";

  insights.forEach((insight) => {
    const card = document.createElement("div");
    card.className = "ai-insight-card";
    card.innerHTML = `
      <div class="ai-insight-data">${insight.data_point || ""}</div>
      <div class="ai-insight-heading">${insight.heading || ""}</div>
      <div class="ai-insight-text">${insight.text || ""}</div>
    `;
    aiInsightsContainer.appendChild(card);
  });
}

function showHypotheses(hypotheses) {
  if (!aiInsightsContainer) return;
  aiInsightsContainer.innerHTML = "";
  aiInsightsContainer.style.display = "block";

  hypotheses.forEach((h) => {
    const card = document.createElement("div");
    const status = (h.status || "moderate").toLowerCase();
    card.className = `ai-hypothesis-card ai-hypothesis-${status}`;
    card.innerHTML = `
      <div class="ai-hypothesis-header">
        <span class="ai-hypothesis-name">${h.name || ""}</span>
        <span class="ai-hypothesis-badge ai-hypothesis-badge-${status}">${status}</span>
      </div>
      <div class="ai-hypothesis-verdict">${h.verdict || ""}</div>
    `;
    aiInsightsContainer.appendChild(card);
  });
}

function showAiFollowUps(followUps) {
  aiSuggestionsEl.innerHTML = "";
  followUps.forEach((fu) => {
    const chip = document.createElement("button");
    chip.className = "ai-followup-chip";

    const label = typeof fu === "string" ? fu : fu.label;
    const prompt = typeof fu === "string" ? fu : fu.prompt;
    const reason = typeof fu === "string" ? "" : (fu.reason || "");

    chip.innerHTML = `<span class="ai-followup-label">${label}</span>`;

    if (reason) {
      chip.setAttribute("title", reason);
      // Add a small info dot
      const dot = document.createElement("span");
      dot.className = "ai-followup-info";
      dot.textContent = "?";
      dot.addEventListener("click", (e) => {
        e.stopPropagation();
        showFollowUpReason(chip, reason);
      });
      chip.appendChild(dot);
    }

    chip.addEventListener("click", () => {
      // Remove any open reason tooltip
      document.querySelectorAll(".ai-followup-reason").forEach(el => el.remove());
      sendAiMessage(prompt);
    });
    aiSuggestionsEl.appendChild(chip);
  });
}

function showFollowUpReason(anchor, reason) {
  // Remove existing
  document.querySelectorAll(".ai-followup-reason").forEach(el => el.remove());

  const tip = document.createElement("div");
  tip.className = "ai-followup-reason";
  tip.textContent = reason;

  // Insert into the suggestions container
  const container = anchor.closest("#ai-suggestions");
  if (container) {
    container.appendChild(tip);
  }

  // Auto-dismiss after 5s
  setTimeout(() => tip.remove(), 5000);
}

function showAiResults(results) {
  clearAiMarkers();
  aiResultsContainer.style.display = "block";
  aiResultsCount.textContent = `${results.length} results`;
  aiResultsList.innerHTML = "";
  aiActiveResultIdx = -1;

  results.forEach((result, idx) => {
    const card = document.createElement("div");
    card.className = "ai-result-card";
    card.dataset.idx = idx;

    // Rank badge
    const rank = document.createElement("div");
    rank.className = "ai-result-rank";
    rank.textContent = idx + 1;

    // Info section
    const info = document.createElement("div");
    info.className = "ai-result-info";

    const title = document.createElement("div");
    title.className = "ai-result-title";
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
      title.textContent = result.national_ref || result.inspire_id || `Parcel #${result.id}`;
      const area = result.area_sqm ? `${Number(result.area_sqm).toLocaleString()}m²` : "";
      const acres = result.area_sqm ? `(${(result.area_sqm / 4046.86).toFixed(2)}ac)` : "";
      const type = table === "cadastral_freehold" ? "Freehold" : "Leasehold";
      meta.textContent = [type, area, acres].filter(Boolean).join(" · ");
    } else if (table === "rzlt") {
      title.textContent = result.zone_desc || "RZLT Site";
      const area = result.site_area ? `${Number(result.site_area).toLocaleString()}m²` : "";
      meta.textContent = [result.local_authority_name, area, "3% annual tax"].filter(Boolean).join(" · ");
    } else if (table === "dlr_planning_polygons") {
      title.textContent = result.plan_ref || "Planning App";
      meta.textContent = [result.decision, result.location].filter(Boolean).join(" · ");
    }

    info.appendChild(title);
    info.appendChild(meta);

    // Opportunity reason (from hypothesis evaluation)
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
    } else if (table === "dlr_planning_polygons") {
      badge.classList.add("planning");
      badge.textContent = result.decision ? result.decision.substring(0, 6) : "—";
    }

    card.appendChild(rank);
    card.appendChild(info);
    card.appendChild(badge);
    aiResultsList.appendChild(card);

    // Add map marker
    if (result.lng && result.lat) {
      const markerEl = document.createElement("div");
      markerEl.className = "ai-marker";
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

  // Fit map to show all results
  if (results.length > 0) {
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
    map.flyTo({ center: [result.lng, result.lat], zoom: 17, duration: 1000 });
  }

  // Show detail in sidebar based on type
  const table = result._table;
  if (table === "sold_properties") {
    showSoldSidebar(result);
  } else if (table === "cadastral_freehold" || table === "cadastral_leasehold") {
    showSidebar({
      id: result.id,
      national_ref: result.national_ref,
      inspire_id: result.inspire_id,
      area_sqm: result.area_sqm,
      area_acres: result.area_sqm ? +(result.area_sqm / 4046.86).toFixed(3) : null,
      type: table === "cadastral_freehold" ? "freehold" : "leasehold",
    });
  } else if (table === "rzlt") {
    showRzltSidebar(result);
  } else if (table === "dlr_planning_polygons") {
    showPlanningSidebar(result);
  }
}

function showRzltSidebar(data) {
  const content = document.getElementById("sidebar-content");
  const area = data.site_area ? `${Number(data.site_area).toLocaleString()}` : "—";

  content.innerHTML = `
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

  document.getElementById("sidebar").classList.add("open");
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

// Keyboard shortcut: Cmd/Ctrl+K to toggle AI panel
document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "k") {
    e.preventDefault();
    toggleAiPanel();
  }
});

// Move zoom hint up when AI panel is present
document.getElementById("zoom-hint").style.bottom = "90px";

// ── Circle analysis ──────────────────────────────────────────────────────────

function showCircleStatsSidebar(data) {
  const content = document.getElementById("sidebar-content");
  const count = data.count || 0;

  if (count === 0) {
    content.innerHTML = `
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
    document.getElementById("sidebar").classList.add("open");
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

  content.innerHTML = `
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

  document.getElementById("sidebar").classList.add("open");
}
