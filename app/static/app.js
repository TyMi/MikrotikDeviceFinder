const REFRESH_INTERVAL_MS = 30000;

const content = document.getElementById("content");
const statusEl = document.getElementById("status");
const refreshBtn = document.getElementById("refresh-btn");
const windowSelect = document.getElementById("window-select");
const inactiveToggle = document.getElementById("inactive-toggle");

const ssidFilterBtn = document.getElementById("ssid-filter-btn");
const ssidFilterPanel = document.getElementById("ssid-filter-panel");
const ssidFilterOptions = document.getElementById("ssid-filter-options");
const ssidFilterAllBtn = document.getElementById("ssid-filter-all");
const ssidFilterNoneBtn = document.getElementById("ssid-filter-none");

let selectedSsids = null; // null = noch nicht initialisiert -> Standard: alle
const knownSsids = new Set();
const collapsedFloors = new Set();
let lastData = null;

const searchToggleBtn = document.getElementById("search-toggle-btn");
const searchPanel = document.getElementById("search-panel");
const searchInput = document.getElementById("search-input");
const searchWindowSelect = document.getElementById("search-window-select");
const searchBtn = document.getElementById("search-btn");
const searchResults = document.getElementById("search-results");

function signalClass(signalStr) {
  const value = parseInt(signalStr, 10);
  if (Number.isNaN(value)) return "";
  if (value >= -60) return "signal-good";
  if (value >= -75) return "signal-warn";
  return "signal-bad";
}

function eventListElement(events) {
  const list = document.createElement("ul");
  list.className = "event-list";
  if (events.length === 0) {
    const li = document.createElement("li");
    li.className = "event-empty";
    li.textContent = "Keine Ereignisse in diesem Zeitraum";
    list.appendChild(li);
    return list;
  }
  events.forEach((ev) => {
    const li = document.createElement("li");
    li.className = "event-item event-" + ev.event_type;
    const time = document.createElement("span");
    time.className = "event-time";
    time.textContent = ev.timestamp_label;
    const label = document.createElement("span");
    label.className = "event-label";
    label.textContent = ev.event_label;
    const detail = document.createElement("span");
    detail.className = "event-detail";
    detail.textContent = ev.detail;
    li.appendChild(time);
    li.appendChild(label);
    li.appendChild(detail);
    list.appendChild(li);
  });
  return list;
}

async function toggleDetails(mac, container, btn, count) {
  const existing = container.querySelector(".details-panel");
  if (existing) {
    existing.remove();
    btn.textContent = "Details (" + count + ")";
    return;
  }
  btn.textContent = "laedt...";
  try {
    const res = await fetch("/api/device/" + encodeURIComponent(mac) + "/history?window=" + windowSelect.value);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    const panel = document.createElement("div");
    panel.className = "details-panel";
    panel.appendChild(eventListElement(data.events));
    container.appendChild(panel);
    btn.textContent = "Details ausblenden";
  } catch (err) {
    btn.textContent = "Details (" + count + ")";
    alert("Historie konnte nicht geladen werden: " + err.message);
  }
}

function buildClientCard(client) {
  const card = document.createElement("div");
  card.className = "client-card" + (client.active ? "" : " inactive");

  const name = document.createElement("div");
  name.className = "client-name";
  name.textContent = client.display_name;
  card.appendChild(name);

  const meta = document.createElement("div");
  meta.className = "client-meta";

  const ap = document.createElement("span");
  ap.className = "badge";
  ap.textContent = client.ap_label;
  meta.appendChild(ap);

  if (client.active && client.signal !== null && client.signal !== undefined) {
    const signal = document.createElement("span");
    const dot = document.createElement("span");
    dot.className = "signal-dot " + signalClass(client.signal);
    signal.appendChild(dot);
    signal.appendChild(document.createTextNode(client.signal + " dBm"));
    meta.appendChild(signal);
  }

  const status = document.createElement("span");
  status.textContent = client.status_label;
  meta.appendChild(status);

  if (client.ip) {
    const ip = document.createElement("span");
    ip.textContent = client.ip;
    meta.appendChild(ip);
  }

  card.appendChild(meta);

  const detailsBtn = document.createElement("button");
  detailsBtn.className = "details-btn";
  detailsBtn.textContent = "Details (" + client.event_count + ")";
  detailsBtn.addEventListener("click", () => toggleDetails(client.mac, card, detailsBtn, client.event_count));
  card.appendChild(detailsBtn);

  return card;
}

function buildSsidColumn(ssid, clients) {
  const col = document.createElement("div");
  col.className = "ssid-column";

  const h3 = document.createElement("h3");
  h3.textContent = ssid + " (" + clients.length + ")";
  col.appendChild(h3);

  if (clients.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-column";
    empty.textContent = "Keine Clients";
    col.appendChild(empty);
  } else {
    clients.forEach((c) => col.appendChild(buildClientCard(c)));
  }
  return col;
}

function buildFloorSection(floor, visibleSsids) {
  const section = document.createElement("section");
  section.className = "floor";

  const collapsed = collapsedFloors.has(floor.floor);

  const header = document.createElement("div");
  header.className = "floor-header";

  const toggleBtn = document.createElement("button");
  toggleBtn.className = "floor-toggle";
  toggleBtn.textContent = collapsed ? "▸" : "▾";
  toggleBtn.setAttribute("aria-label", "Stockwerk ein-/ausklappen");
  header.appendChild(toggleBtn);

  const h2 = document.createElement("h2");
  h2.textContent = floor.label;
  header.appendChild(h2);
  const count = document.createElement("span");
  count.className = "count";
  count.textContent = floor.client_count + " Client(s)";
  header.appendChild(count);
  section.appendChild(header);

  const grid = document.createElement("div");
  grid.className = "ssid-grid" + (collapsed ? " collapsed" : "");
  visibleSsids.forEach((ssid) => {
    grid.appendChild(buildSsidColumn(ssid, floor.ssids[ssid] || []));
  });
  section.appendChild(grid);

  const toggle = () => {
    if (collapsedFloors.has(floor.floor)) {
      collapsedFloors.delete(floor.floor);
      grid.classList.remove("collapsed");
      toggleBtn.textContent = "▾";
    } else {
      collapsedFloors.add(floor.floor);
      grid.classList.add("collapsed");
      toggleBtn.textContent = "▸";
    }
  };
  toggleBtn.addEventListener("click", toggle);
  header.addEventListener("click", (e) => {
    if (e.target !== toggleBtn) toggle();
  });

  return section;
}

async function loadOverview() {
  statusEl.textContent = "aktualisiere...";
  const params = new URLSearchParams({
    window: windowSelect.value,
    show_inactive: inactiveToggle.checked,
  });
  try {
    const res = await fetch("/api/overview?" + params.toString());
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    render(data);
    statusEl.textContent =
      "Zuletzt aktualisiert: " + data.generated_at_label + " - " + data.total_clients + " aktiv, " +
      data.total_shown + " angezeigt";
  } catch (err) {
    statusEl.textContent = "Fehler beim Laden";
    content.innerHTML = "";
    const p = document.createElement("p");
    p.className = "error";
    p.textContent = "Daten konnten nicht geladen werden: " + err.message;
    content.appendChild(p);
  }
}

function syncSsidFilterOptions(ssidOrder, forceRebuild = false) {
  let added = false;
  ssidOrder.forEach((ssid) => {
    if (!knownSsids.has(ssid)) {
      knownSsids.add(ssid);
      if (selectedSsids === null) selectedSsids = new Set();
      selectedSsids.add(ssid); // neue SSIDs sind standardmaessig sichtbar
      added = true;
    }
  });
  if (selectedSsids === null) {
    selectedSsids = new Set(ssidOrder);
  }
  if (!forceRebuild && !added && ssidFilterOptions.childElementCount === knownSsids.size) return;

  ssidFilterOptions.innerHTML = "";
  Array.from(knownSsids).sort().forEach((ssid) => {
    const label = document.createElement("label");
    label.className = "ssid-filter-option";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = selectedSsids.has(ssid);
    cb.addEventListener("change", () => {
      if (cb.checked) selectedSsids.add(ssid);
      else selectedSsids.delete(ssid);
      refreshSsidFilterLabel();
      if (lastData) render(lastData);
    });
    label.appendChild(cb);
    label.appendChild(document.createTextNode(" " + ssid));
    ssidFilterOptions.appendChild(label);
  });
  refreshSsidFilterLabel();
}

function refreshSsidFilterLabel() {
  const total = knownSsids.size;
  const selected = selectedSsids ? selectedSsids.size : total;
  ssidFilterBtn.textContent = selected >= total ? "SSIDs: alle" : "SSIDs: " + selected + "/" + total;
}

function render(data) {
  lastData = data;
  syncSsidFilterOptions(data.ssid_order);
  const visibleSsids = data.ssid_order.filter((s) => selectedSsids.has(s));

  content.innerHTML = "";
  data.floors.forEach((floor) => {
    content.appendChild(buildFloorSection(floor, visibleSsids));
  });
}

async function runSearch() {
  const query = searchInput.value.trim();
  searchResults.innerHTML = "";
  if (!query) return;
  const params = new URLSearchParams({ q: query, window: searchWindowSelect.value });
  const res = await fetch("/api/search?" + params.toString());
  const data = await res.json();

  if (data.results.length === 0) {
    const p = document.createElement("p");
    p.className = "empty-column";
    p.textContent = "Keine Treffer im gewaehlten Zeitraum";
    searchResults.appendChild(p);
    return;
  }

  data.results.forEach((device) => {
    const box = document.createElement("div");
    box.className = "search-result" + (device.active ? "" : " inactive");
    const title = document.createElement("div");
    title.className = "client-name";
    title.textContent = device.display_name + (device.active ? " (aktiv)" : "");
    box.appendChild(title);
    box.appendChild(eventListElement(device.events));
    searchResults.appendChild(box);
  });
}

refreshBtn.addEventListener("click", loadOverview);
windowSelect.addEventListener("change", loadOverview);
inactiveToggle.addEventListener("change", loadOverview);

ssidFilterBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  ssidFilterPanel.classList.toggle("hidden");
});
ssidFilterPanel.addEventListener("click", (e) => e.stopPropagation());
document.addEventListener("click", () => ssidFilterPanel.classList.add("hidden"));

ssidFilterAllBtn.addEventListener("click", () => {
  selectedSsids = new Set(knownSsids);
  syncSsidFilterOptions([], true);
  if (lastData) render(lastData);
});
ssidFilterNoneBtn.addEventListener("click", () => {
  selectedSsids = new Set();
  syncSsidFilterOptions([], true);
  if (lastData) render(lastData);
});

searchToggleBtn.addEventListener("click", () => searchPanel.classList.toggle("hidden"));
searchBtn.addEventListener("click", runSearch);
searchInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") runSearch();
});

loadOverview();
setInterval(loadOverview, REFRESH_INTERVAL_MS);
