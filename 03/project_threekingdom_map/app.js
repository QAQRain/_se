"use strict";

const state = {
  items: [],
  itemsById: {},
  populations: [],
  populationsById: {},
  horses: [],
  horsesById: {},
  markers: [],
  resources: [],
  resourceVisible: {},
  levelVisible: {},
  selectedMarkerId: null,
  activeFilter: null,
  activePopulation: null,
  activeHorse: null,
  zoom: 1,
  baseW: null,
  qty: 1,
  resCheck: false,
  playerRes: { 皮: 0, 鐵: 0, 韌皮: 0, 精鐵: 0 },
  mode: "craft",
  visited: {},
};

const mapViewport = document.getElementById("mapViewport");
const mapWrap = document.getElementById("mapWrap");
const markersLayer = document.getElementById("markersLayer");
const resourcesLayer = document.getElementById("resourcesLayer");
const resTypeBtns = document.getElementById("resTypeBtns");
const resLevelBtns = document.getElementById("resLevelBtns");
const itemList = document.getElementById("itemList");
const popList = document.getElementById("popList");
const horseList = document.getElementById("horseList");
const dpName = document.getElementById("dpName");
const dpItems = document.getElementById("dpItems");
const dpTotals = document.getElementById("dpTotals");
const dpCloseBtn = document.getElementById("dpClose");
const qtyInput = document.getElementById("qtyInput");
const resToggle = document.getElementById("resToggle");
const resInputs = {
  皮: document.getElementById("resPi"),
  鐵: document.getElementById("resTie"),
  韌皮: document.getElementById("resRen"),
  精鐵: document.getElementById("resJing"),
};
const statusEl = document.getElementById("status");
const resetBtn = document.getElementById("resetBtn");
const zoomInBtn = document.getElementById("zoomInBtn");
const zoomOutBtn = document.getElementById("zoomOutBtn");
const zoomResetBtn = document.getElementById("zoomResetBtn");
const modeSwitch = document.getElementById("modeSwitch");
const mapImg = document.getElementById("mapImg");

const isMobile = () => window.matchMedia("(max-width: 900px)").matches;

const tierRank = (it) => (typeof it.tier === "number" ? it.tier : 0);

const RES_ORDER = ["皮", "鐵", "韌皮", "精鐵"];
const RES_ICON = {
  皮: "assets/resources/pi.png",
  鐵: "assets/resources/tie.png",
  韌皮: "assets/resources/renpi.png",
  精鐵: "assets/resources/jingtie.png",
};

const RESOURCE_TYPES = [
  { id: "pi", name: "皮", color: "#a1887f", image: "assets/res-points/pi.png" },
  { id: "tie", name: "鐵", color: "#90a4ae", image: "assets/res-points/tie.png" },
  { id: "shi", name: "石", color: "#9e9e9e", image: "assets/res-points/shi.png" },
  { id: "mu", name: "木", color: "#5d4037", image: "assets/res-points/mu.png" },
  { id: "liang", name: "糧", color: "#ffb74d", image: "assets/res-points/liang.png" },
  { id: "ma", name: "馬", color: "#b39ddb", image: "assets/res-points/ma.png" },
  { id: "yizhan", name: "驛站", color: "#ffffff" },
  { id: "guankou", name: "關口", color: "#ef5350" },
];

const LEVEL_COLORS = {
  1: "#ffffff",
  2: "#4caf72",
  3: "#4a90d9",
  4: "#9a6bd1",
};

const LEVEL_NAMES = { 1: "Lv.1", 2: "Lv.2", 3: "Lv.3", 4: "Lv.4" };

function makeChip(mat, need, checkRes) {
  const chip = document.createElement("span");
  chip.className = "mat-chip mat-" + mat;
  if (RES_ICON[mat]) {
    const img = document.createElement("img");
    img.className = "res-icon";
    img.src = RES_ICON[mat];
    img.alt = mat;
    chip.appendChild(img);
  }
  chip.appendChild(document.createTextNode(mat + " ×" + need));
  if (checkRes && (state.playerRes[mat] || 0) < need) chip.classList.add("insufficient");
  return chip;
}

init();

async function init() {
  try {
    const [itemsRes, markersRes, popsRes, resourcesRes, horsesRes] = await Promise.all([
      fetch("data/items.json"),
      fetch("data/markers.json"),
      fetch("data/populations.json"),
      fetch("data/resources.json"),
      fetch("data/horses.json"),
    ]);
    if (!itemsRes.ok || !markersRes.ok || !popsRes.ok || !resourcesRes.ok || !horsesRes.ok) throw new Error("資料載入失敗");
    const itemsData = await itemsRes.json();
    const markersData = await markersRes.json();
    const popsData = await popsRes.json();
    const resourcesData = await resourcesRes.json();
    const horsesData = await horsesRes.json();

    state.items = itemsData.items;
    state.markers = markersData.markers;
    for (const it of state.items) state.itemsById[it.id] = it;
    state.populations = popsData.populations || [];
    for (const p of state.populations) state.populationsById[p.id] = p;
    state.horses = horsesData.horses || [];
    for (const h of state.horses) state.horsesById[h.id] = h;
    state.resources = resourcesData.resources || [];

    loadPlayerRes();
    loadVisited();
    renderSidebar();
    renderPopList();
    renderHorseList();
    renderMarkers();
    renderResources();
    buildResTypeBtns();
    buildResLevelBtns();
    applyView();
    renderPanel();
    initModeSwitch();
  } catch (err) {
    statusEl.textContent = "⚠ 資料載入失敗：" + err.message;
  }
}

function renderSidebar() {
  itemList.innerHTML = "";
  if (state.items.length === 0) {
    const li = document.createElement("li");
    li.className = "item-row empty-hint";
    li.textContent = "兵裝資料待提供";
    itemList.appendChild(li);
    return;
  }
  [...state.items]
    .sort((a, b) => {
      const ca = a.craftable === false ? 1 : 0;
      const cb = b.craftable === false ? 1 : 0;
      if (ca !== cb) return ca - cb;
      return tierRank(b) - tierRank(a);
    })
    .forEach((it) => {
      const inactive = it.craftable === false;
      const li = document.createElement("li");
      li.className = "item-row" + (inactive ? " inactive" : "");
      li.dataset.itemId = it.id;
      li.title = it.name;

      const img = document.createElement("img");
      img.className = "item-img";
      img.src = it.image;
      img.alt = it.name;
      li.appendChild(img);

      li.addEventListener("click", (e) => {
        e.stopPropagation();
        setFilter(it.id);
      });
      itemList.appendChild(li);
    });
}

function renderPopList() {
  popList.innerHTML = "";
  let list;
  if (state.activeFilter) {
    const it = state.itemsById[state.activeFilter];
    const popIds = it ? it.population || [] : [];
    if (popIds.length === 0) {
      const li = document.createElement("div");
      li.className = "pop-row empty-hint";
      li.textContent = "此兵團不需徵兵人口";
      popList.appendChild(li);
      return;
    }
    list = popIds.map((id) => state.populationsById[id]).filter(Boolean);
  } else {
    list = state.populations.slice();
  }

  if (list.length === 0) {
    const li = document.createElement("div");
    li.className = "pop-row empty-hint";
    li.textContent = "徵兵人口資料待提供";
    popList.appendChild(li);
    return;
  }

  for (const p of list) {
    const li = document.createElement("div");
    li.className = "pop-row";
    li.dataset.popId = p.id;
    li.title = p.name;
    const img = document.createElement("img");
    img.className = "pop-img";
    img.src = p.image;
    img.alt = p.name;
    li.appendChild(img);
    li.addEventListener("click", (e) => {
      e.stopPropagation();
      togglePopulation(p.id);
    });
    popList.appendChild(li);
  }
}

function togglePopulation(popId) {
  state.activePopulation = state.activePopulation === popId ? null : popId;
  const row = popList.querySelector('[data-pop-id="' + popId + '"]');
  if (row) {
    row.scrollIntoView({ block: "nearest" });
    row.classList.remove("flash");
    void row.offsetWidth;
    row.classList.add("flash");
  }
  applyView();
}

function renderHorseList() {
  horseList.innerHTML = "";
  let list;
  if (state.activeFilter) {
    const it = state.itemsById[state.activeFilter];
    const horseIds = it ? it.horse || [] : [];
    if (horseIds.length === 0) {
      const div = document.createElement("div");
      div.className = "empty-hint";
      div.textContent = "此兵團不需馬";
      horseList.appendChild(div);
      return;
    }
    list = horseIds.map((id) => state.horsesById[id]).filter(Boolean);
  } else {
    list = state.horses.slice();
  }

  if (list.length === 0) {
    const div = document.createElement("div");
    div.className = "empty-hint";
    div.textContent = "馬資料待提供";
    horseList.appendChild(div);
    return;
  }

  for (const h of list) {
    const li = document.createElement("div");
    li.className = "horse-item";
    li.dataset.horseId = h.id;
    li.title = h.name;
    const img = document.createElement("img");
    img.className = "horse-img";
    img.src = h.image;
    img.alt = h.name;
    li.appendChild(img);
    li.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleHorse(h.id);
    });
    horseList.appendChild(li);
  }
}

function toggleHorse(horseId) {
  state.activeHorse = state.activeHorse === horseId ? null : horseId;
  const row = horseList.querySelector('[data-horse-id="' + horseId + '"]');
  if (row) {
    row.classList.remove("flash");
    void row.offsetWidth;
    row.classList.add("flash");
  }
  applyView();
}

function renderMarkers() {
  markersLayer.innerHTML = "";
  state.markers.forEach((m, idx) => {
    const div = document.createElement("div");
    div.className = "marker";
    div.dataset.markerId = m.id;
    div.style.left = m.x + "%";
    div.style.top = m.y + "%";

    const pin = document.createElement("div");
    pin.className = "pin";

    const label = document.createElement("div");
    label.className = "label";
    label.textContent = m.name;

    div.appendChild(pin);
    div.appendChild(label);

    div.addEventListener("click", (e) => {
      e.stopPropagation();
      selectMarker(m.id);
    });
    markersLayer.appendChild(div);
  });
}

function resourceType(type) {
  return RESOURCE_TYPES.find((t) => t.id === type) || RESOURCE_TYPES[0];
}

function renderResources() {
  resourcesLayer.innerHTML = "";
  state.resources.forEach((r) => {
    const t = resourceType(r.type);
    const lv = r.level || 1;
    const lvColor = LEVEL_COLORS[lv] || LEVEL_COLORS[1];

    const div = document.createElement("div");
    div.className = "res-point" + (state.visited[r.id] ? " visited" : "");
    div.dataset.resId = r.id;
    div.dataset.resType = r.type;
    div.dataset.resLevel = lv;
    div.style.left = r.x + "%";
    div.style.top = r.y + "%";
    div.style.setProperty("--lv-color", lvColor);

    const inner = document.createElement("div");
    inner.className = "res-inner";
    inner.style.background = t.color;
    if (t.image) {
      const im = document.createElement("img");
      im.className = "res-img";
      im.src = t.image;
      im.alt = t.name;
      im.draggable = false;
      im.addEventListener("error", () => im.remove());
      inner.appendChild(im);
    }

    const label = document.createElement("div");
    label.className = "res-label";
    label.textContent = (r.name ? r.name + " · " : "") + t.name + " · " + (LEVEL_NAMES[lv] || "Lv.1");

    div.appendChild(inner);
    div.appendChild(label);

    div.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleVisited(r.id);
    });

    resourcesLayer.appendChild(div);
  });
  applyResourceVisibility();
}

function buildResTypeBtns() {
  resTypeBtns.innerHTML = "";
  for (const t of RESOURCE_TYPES) {
    if (state.resourceVisible[t.id] === undefined) state.resourceVisible[t.id] = true;
    const b = document.createElement("button");
    b.dataset.type = t.id;
    b.innerHTML = '<span class="r-dot" style="background:' + t.color + '"></span>' + t.name;
    b.addEventListener("click", () => {
      state.resourceVisible[t.id] = !state.resourceVisible[t.id];
      applyResourceVisibility();
    });
    resTypeBtns.appendChild(b);
  }
  applyResourceVisibility();
}

function buildResLevelBtns() {
  resLevelBtns.innerHTML = "";
  const all = document.createElement("button");
  all.dataset.level = "all";
  all.textContent = "全部";
  all.addEventListener("click", () => {
    for (const k of Object.keys(state.levelVisible)) state.levelVisible[k] = true;
    applyResourceVisibility();
  });
  resLevelBtns.appendChild(all);
  for (let lv = 1; lv <= 4; lv++) {
    if (state.levelVisible[lv] === undefined) state.levelVisible[lv] = true;
    const b = document.createElement("button");
    b.dataset.level = String(lv);
    b.innerHTML = '<span class="lv-dot" style="background:' + (LEVEL_COLORS[lv] || "#ffffff") + '"></span>Lv.' + lv;
    b.addEventListener("click", () => {
      state.levelVisible[lv] = !state.levelVisible[lv];
      applyResourceVisibility();
    });
    resLevelBtns.appendChild(b);
  }
  applyResourceVisibility();
}

function applyLevelBtnStates() {
  for (const b of resLevelBtns.children) {
    if (b.dataset.level === "all") {
      const allOn = [1, 2, 3, 4].every((lv) => !!state.levelVisible[lv]);
      b.classList.toggle("on", allOn);
      b.classList.toggle("off", !allOn);
    } else {
      const on = !!state.levelVisible[Number(b.dataset.level)];
      b.classList.toggle("on", on);
      b.classList.toggle("off", !on);
    }
  }
}

function applyResourceVisibility() {
  for (const b of resTypeBtns.children) {
    b.classList.toggle("on", !!state.resourceVisible[b.dataset.type]);
    b.classList.toggle("off", !state.resourceVisible[b.dataset.type]);
  }
  applyLevelBtnStates();
  for (const el of resourcesLayer.children) {
    let show = !!state.resourceVisible[el.dataset.resType];
    if (show && el.dataset.resType !== "yizhan" && el.dataset.resType !== "guankou") {
      const lv = Number(el.dataset.resLevel) || 1;
      if (!state.levelVisible[lv]) show = false;
    }
    el.style.display = show ? "" : "none";
  }
}

function loadVisited() {
  try {
    const saved = JSON.parse(localStorage.getItem("sanguo_visited") || "{}");
    state.visited = saved;
  } catch (e) { state.visited = {}; }
}

function saveVisited() {
  try {
    localStorage.setItem("sanguo_visited", JSON.stringify(state.visited));
  } catch (e) { /* ignore */ }
}

function toggleVisited(resId) {
  if (state.visited[resId]) {
    delete state.visited[resId];
  } else {
    state.visited[resId] = true;
  }
  saveVisited();
  const el = resourcesLayer.querySelector('[data-res-id="' + resId + '"]');
  if (el) el.classList.toggle("visited", !!state.visited[resId]);
}

function initModeSwitch() {
  const btns = modeSwitch.querySelectorAll(".mode-btn");
  btns.forEach((btn) => {
    btn.addEventListener("click", () => {
      switchMode(btn.dataset.mode);
    });
  });
  applyMode();
}

function switchMode(mode) {
  if (state.mode === mode) return;
  state.mode = mode;
  clearSelection();
  clearFilter();
  applyMode();
  resetZoom();
}

function applyMode() {
  const isResource = state.mode === "resource";
  document.body.classList.toggle("mode-resource", isResource);
  document.body.classList.toggle("mode-craft", !isResource);

  const btns = modeSwitch.querySelectorAll(".mode-btn");
  btns.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.mode === state.mode);
  });

  if (isResource) {
    mapImg.src = "assets/resource-map.png";
    mapImg.onload = () => {
      computeBaseW();
      resetZoom();
    };
    statusEl.textContent = "點擊資源點標記「已採過」，再點一次取消";
  } else {
    mapImg.src = "assets/map.png";
    mapImg.onload = () => {
      computeBaseW();
      resetZoom();
    };
    applyView();
  }
}

function isInactiveFilter() {
  const it = state.activeFilter ? state.itemsById[state.activeFilter] : null;
  return !!it && it.craftable === false;
}

function matchCount() {
  const inactiveFilter = isInactiveFilter();
  return state.markers.filter((m) => {
    if (state.activeFilter && !inactiveFilter && !(m.items || []).includes(state.activeFilter)) return false;
    if (state.activePopulation && !(m.population || []).includes(state.activePopulation)) return false;
    return true;
  }).length;
}

function selectMarker(markerId) {
  if (state.selectedMarkerId === markerId) {
    clearSelection();
    return;
  }
  state.selectedMarkerId = markerId;
  renderPanel();
  applyView();
}

function clearSelection() {
  state.selectedMarkerId = null;
  renderPanel();
  applyView();
}

function setFilter(itemId) {
  state.activeFilter = state.activeFilter === itemId ? null : itemId;
  state.activePopulation = null;
  state.activeHorse = null;
  const row = itemList.querySelector('[data-item-id="' + itemId + '"]');
  if (row) {
    row.scrollIntoView({ block: "nearest" });
    row.classList.remove("flash");
    void row.offsetWidth;
    row.classList.add("flash");
  }
  applyView();
  renderPanel();
  renderPopList();
  renderHorseList();
}

function clearFilter() {
  state.activeFilter = null;
  state.activePopulation = null;
  state.activeHorse = null;
  applyView();
  renderPopList();
  renderHorseList();
}

function applyView() {
  if (state.mode === "resource") return;
  const filter = state.activeFilter;
  const popFilter = state.activePopulation;
  const horseFilter = state.activeHorse;
  const inactiveFilter = isInactiveFilter();

  for (const mEl of markersLayer.children) {
    const m = state.markers.find((x) => x.id === mEl.dataset.markerId);
    mEl.classList.remove("match", "dim", "selected");
    let isMatch = true;
    if (filter && !inactiveFilter && !(m.items || []).includes(filter)) isMatch = false;
    if (popFilter && !(m.population || []).includes(popFilter)) isMatch = false;
    if ((filter && !inactiveFilter) || popFilter) {
      if (isMatch) mEl.classList.add("match");
      else mEl.classList.add("dim");
    }
    if (state.selectedMarkerId === m.id) mEl.classList.add("selected");
  }

  for (const row of itemList.children) {
    row.classList.remove("active", "available", "horse-match");
    if (filter && row.dataset.itemId === filter) row.classList.add("active");
    if (horseFilter && row.dataset.itemId) {
      const it = state.itemsById[row.dataset.itemId];
      if (it && (it.horse || []).includes(horseFilter)) row.classList.add("horse-match");
    }
    if (state.selectedMarkerId) {
      const m = state.markers.find((x) => x.id === state.selectedMarkerId);
      if (m && m.items.includes(row.dataset.itemId)) row.classList.add("available");
    }
  }

  for (const row of popList.children) {
    row.classList.remove("active", "available");
    if (state.selectedMarkerId) {
      const m = state.markers.find((x) => x.id === state.selectedMarkerId);
      if (m && m.population && m.population.includes(row.dataset.popId)) row.classList.add("available");
    }
    if (popFilter && row.dataset.popId === popFilter) {
      row.classList.remove("available");
      row.classList.add("active");
    }
  }

  for (const row of horseList.children) {
    row.classList.remove("active");
    if (horseFilter && row.dataset.horseId === horseFilter) row.classList.add("active");
  }

  if (inactiveFilter) {
    const it = state.itemsById[filter];
    const popName = popFilter
      ? (state.populationsById[popFilter] ? state.populationsById[popFilter].name : popFilter)
      : (it.population && state.populationsById[it.population[0]]
          ? state.populationsById[it.population[0]].name
          : "");
    if (popFilter) {
      statusEl.textContent = "高亮：有「" + popName + "」人口的據點（" + matchCount() + " 處）";
    } else {
      statusEl.textContent = "「" + it.name + "」無固定製造據點，所需人口：「" + popName + "」";
    }
    return;
  }

  const parts = [];
  if (filter) parts.push("可造「" + state.itemsById[filter].name + "」");
  if (popFilter) {
    const p = state.populationsById[popFilter];
    parts.push("有「" + (p ? p.name : popFilter) + "」人口");
  }
  if (parts.length) {
    statusEl.textContent = "高亮：" + parts.join("且") + "的據點（" + matchCount() + " 處）";
  } else if (horseFilter) {
    const h = state.horsesById[horseFilter];
    statusEl.textContent = "高亮：使用「" + (h ? h.name : horseFilter) + "」馬的兵團";
  } else {
    statusEl.textContent = "點擊左側兵裝可高亮對應據點，點擊據點查看兵裝與材料";
  }
}

function loadPlayerRes() {
  try {
    const saved = JSON.parse(localStorage.getItem("sanguo_player_res") || "{}");
    for (const k of Object.keys(state.playerRes)) {
      if (typeof saved[k] === "number" && saved[k] >= 0) state.playerRes[k] = saved[k];
    }
    if (typeof saved.resCheck === "boolean") state.resCheck = saved.resCheck;
  } catch (e) { /* ignore */ }
  for (const k of Object.keys(resInputs)) resInputs[k].value = state.playerRes[k];
  resToggle.checked = state.resCheck;
}

function savePlayerRes() {
  try {
    localStorage.setItem("sanguo_player_res", JSON.stringify(Object.assign({}, state.playerRes, { resCheck: state.resCheck })));
  } catch (e) { /* ignore */ }
}

function renderPanel() {
  const marker = state.markers.find((m) => m.id === state.selectedMarkerId);
  const filter = state.activeFilter;
  const qty = state.qty;
  const checkRes = state.resCheck;
  const totals = {};

  if (!marker) {
    if (!filter) {
      dpName.textContent = "尚未選取據點";
      dpItems.innerHTML = '<div class="dp-empty">點擊地圖據點，查看該處可造的兵裝與所需資源</div>';
      dpTotals.innerHTML = "";
      return;
    }
    const it = state.itemsById[filter];
    if (!it) return;
    dpName.textContent = it.name + " · 材料需求";
    dpItems.innerHTML = "";
    const row = document.createElement("div");
    row.className = "dp-item";
    const row1 = document.createElement("div");
    row1.className = "row1";
    const iname = document.createElement("div");
    iname.className = "iname";
    iname.textContent = it.name;
    row1.appendChild(iname);
    const mats = document.createElement("div");
    mats.className = "materials";
    for (const mat of RES_ORDER) {
      if (!(mat in it.materials)) continue;
      const need = it.materials[mat] * qty;
      totals[mat] = need;
      mats.appendChild(makeChip(mat, it.materials[mat], checkRes));
    }
    row.appendChild(row1);
    row.appendChild(mats);
    dpItems.appendChild(row);
    if (it.unlock) {
      const urow = document.createElement("div");
      urow.className = "dp-unlock";
      const ulabel = document.createElement("div");
      ulabel.className = "dp-unlock-label";
      ulabel.textContent = "解鎖方式";
      const utxt = document.createElement("div");
      utxt.className = "dp-unlock-text";
      utxt.textContent = it.unlock;
      urow.appendChild(ulabel);
      urow.appendChild(utxt);
      dpItems.appendChild(urow);
    }
    dpTotals.innerHTML = "";
    for (const mat of RES_ORDER) {
      if (!(mat in totals)) continue;
      dpTotals.appendChild(makeChip(mat, totals[mat], checkRes));
    }
    return;
  }

  let canCraft = state.items
    .filter((it) => marker.items.includes(it.id))
    .sort((a, b) => tierRank(b) - tierRank(a));
  if (filter) {
    canCraft = marker.items.includes(filter)
      ? [state.itemsById[filter]]
      : [];
  }

  if (canCraft.length === 0 && filter) {
    const f = state.itemsById[filter];
    dpName.textContent = marker.name;
    dpItems.innerHTML = '<div class="dp-empty">此據點無法製造「' + f.name + '」</div>';
    dpTotals.innerHTML = "";
    return;
  }

  dpName.textContent = marker.name + " · 可造 " + canCraft.length + " 種兵裝";
  dpItems.innerHTML = "";

  for (const it of canCraft) {
    const row = document.createElement("div");
    row.className = "dp-item";
    row.dataset.itemId = it.id;

    const row1 = document.createElement("div");
    row1.className = "row1";
    const iname = document.createElement("div");
    iname.className = "iname";
    iname.textContent = it.name;
    row1.appendChild(iname);

    const mats = document.createElement("div");
    mats.className = "materials";
    for (const mat of RES_ORDER) {
      if (!(mat in it.materials)) continue;
      const need = it.materials[mat] * qty;
      totals[mat] = (totals[mat] || 0) + need;
      mats.appendChild(makeChip(mat, it.materials[mat], checkRes));
    }

    row.appendChild(row1);
    row.appendChild(mats);
    row.addEventListener("click", (e) => {
      e.stopPropagation();
      setFilter(it.id);
    });
    dpItems.appendChild(row);
    if (canCraft.length === 1 && it.unlock) {
      const urow = document.createElement("div");
      urow.className = "dp-unlock";
      const ulabel = document.createElement("div");
      ulabel.className = "dp-unlock-label";
      ulabel.textContent = "解鎖方式";
      const utxt = document.createElement("div");
      utxt.className = "dp-unlock-text";
      utxt.textContent = it.unlock;
      urow.appendChild(ulabel);
      urow.appendChild(utxt);
      dpItems.appendChild(urow);
    }
  }

  dpTotals.innerHTML = "";
  for (const mat of RES_ORDER) {
    if (!(mat in totals)) continue;
    dpTotals.appendChild(makeChip(mat, totals[mat], checkRes));
  }
}

function computeBaseW() {
  mapWrap.style.width = "";
  state.baseW = mapWrap.clientWidth;
}

function mapAspect() {
  return state.mode === "resource" ? 1246 / 2000 : 771 / 1122;
}

function applyZoom(z, keepCenter) {
  if (!state.baseW) computeBaseW();
  const prevW = state.baseW * state.zoom;
  state.zoom = Math.min(3, Math.max(0.5, z));
  const newW = state.baseW * state.zoom;
  const aspect = mapAspect();

  if (keepCenter) {
    const vw = mapViewport.clientWidth;
    const vh = mapViewport.clientHeight;
    const prevH = prevW * aspect;
    const newH = newW * aspect;
    const offXBefore = Math.max(16, (vw - prevW) / 2);
    const offXAfter = Math.max(16, (vw - newW) / 2);
    const offYBefore = Math.max(16, (vh - prevH) / 2);
    const offYAfter = Math.max(16, (vh - newH) / 2);
    const u = mapViewport.scrollLeft + vw / 2 - offXBefore;
    const v = mapViewport.scrollTop + vh / 2 - offYBefore;
    mapViewport.scrollLeft = u + offXAfter - vw / 2;
    mapViewport.scrollTop = v + offYAfter - vh / 2;
  }

  mapWrap.style.width = newW + "px";
}

function resetZoom() {
  state.zoom = 1;
  computeBaseW();
  mapWrap.style.width = state.baseW + "px";
  mapViewport.scrollLeft = 0;
  mapViewport.scrollTop = 0;
}

zoomInBtn.addEventListener("click", () => applyZoom(state.zoom * 1.25, true));
zoomOutBtn.addEventListener("click", () => applyZoom(state.zoom / 1.25, true));
zoomResetBtn.addEventListener("click", resetZoom);

mapViewport.addEventListener("wheel", (e) => {
  if (Math.abs(e.deltaY) < 1) return;
  e.preventDefault();
  const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
  applyZoom(state.zoom * factor, true);
}, { passive: false });

let dragState = null;

mapViewport.addEventListener("mousedown", (e) => {
  if (e.button !== 0) return;
  dragState = {
    x: e.clientX,
    y: e.clientY,
    sl: mapViewport.scrollLeft,
    st: mapViewport.scrollTop,
    moved: false,
  };
  e.preventDefault();
});

window.addEventListener("mousemove", (e) => {
  if (!dragState) return;
  const dx = e.clientX - dragState.x;
  const dy = e.clientY - dragState.y;
  if (!dragState.moved && Math.hypot(dx, dy) > 4) {
    dragState.moved = true;
    mapViewport.classList.add("dragging");
  }
  if (dragState.moved) {
    mapViewport.scrollLeft = dragState.sl - dx;
    mapViewport.scrollTop = dragState.st - dy;
  }
});

window.addEventListener("mouseup", () => {
  if (dragState && dragState.moved) {
    mapViewport.addEventListener(
      "click",
      (ev) => {
        ev.stopImmediatePropagation();
        ev.preventDefault();
      },
      { capture: true, once: true }
    );
  }
  if (dragState) mapViewport.classList.remove("dragging");
  dragState = null;
});

mapViewport.addEventListener("scroll", () => {});

mapWrap.addEventListener("click", (e) => {
  if (e.target === mapWrap || e.target.id === "mapImg") {
    clearSelection();
  }
});

resetBtn.addEventListener("click", () => {
  clearSelection();
  clearFilter();
  if (state.mode === "resource") {
    state.visited = {};
    saveVisited();
    for (const el of resourcesLayer.children) {
      el.classList.remove("visited");
    }
  }
});

dpCloseBtn.addEventListener("click", () => {
  clearSelection();
});

qtyInput.addEventListener("input", () => {
  const v = parseInt(qtyInput.value, 10);
  if (!isNaN(v) && v >= 1) {
    state.qty = v;
    qtyInput.value = v;
    renderPanel();
  }
});

qtyInput.addEventListener("change", () => {
  let v = parseInt(qtyInput.value, 10);
  if (isNaN(v) || v < 1) v = 1;
  state.qty = v;
  qtyInput.value = v;
  renderPanel();
});

resToggle.addEventListener("change", () => {
  state.resCheck = resToggle.checked;
  savePlayerRes();
  renderPanel();
});

for (const [mat, el] of Object.entries(resInputs)) {
  el.addEventListener("input", () => {
    let v = parseInt(el.value, 10);
    if (isNaN(v) || v < 0) v = 0;
    state.playerRes[mat] = v;
    savePlayerRes();
    renderPanel();
  });
}

window.addEventListener("resize", () => {
  if (isMobile()) return;
  computeBaseW();
  applyZoom(state.zoom, false);
});
