const API = "http://localhost:8000/api";
const PARCEL_MIN_ZOOM = 15;

// ── Circle analysis state ────────────────────────────────────────────────────
let circleMode = false;
let circleCenter = null;  // { lng, lat }
let circleRadiusM = 500;  // metres

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
  if (circleMode) {
    btn.classList.add("active");
    map.getCanvas().style.cursor = "crosshair";
  } else {
    btn.classList.remove("active");
    map.getCanvas().style.cursor = "";
    clearCircle();
  }
}

function clearCircle() {
  circleCenter = null;
  const src = map.getSource("analysis-circle");
  if (src) src.setData({ type: "FeatureCollection", features: [] });
  document.getElementById("sidebar").classList.remove("open");
}

// Map click handler for circle placement
map.on("click", (e) => {
  if (!circleMode) return;

  circleCenter = { lng: e.lngLat.lng, lat: e.lngLat.lat };
  updateCircle();
  fetchCircleStats();

  // Stop propagation to prevent parcel/property click handlers
  e.preventDefault();
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
