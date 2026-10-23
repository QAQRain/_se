"use strict";

const fs = require("fs");
const path = require("path");

const FILES = [
  { name: "items", key: "items" },
  { name: "markers", key: "markers" },
  { name: "populations", key: "populations" },
  { name: "horses", key: "horses" },
  { name: "resources", key: "resources" },
];

const RESOURCE_TYPES = ["pi", "mu", "liang", "ma", "tie", "shi", "yizhan", "guankou"];
const RESOURCE_LEVELS = [1, 2, 3, 4];

function readJson(file) {
  let text;
  try {
    text = fs.readFileSync(file, "utf8");
  } catch (err) {
    throw new Error(`無法讀取資料檔 ${path.basename(file)}（${err.code || err.message}）`);
  }
  try {
    return JSON.parse(text);
  } catch (err) {
    throw new Error(`資料檔 ${path.basename(file)} 不是合法 JSON：${err.message}`);
  }
}

function assertUniqueIds(list, label) {
  const seen = new Set();
  for (const row of list) {
    if (!row || typeof row.id !== "string" || row.id.length === 0) {
      throw new Error(`${label} 資料含有缺少 id 的項目`);
    }
    if (seen.has(row.id)) throw new Error(`${label} 資料出現重複 id：${row.id}`);
    seen.add(row.id);
  }
  return seen;
}

function assertRefs(ids, refs, label) {
  for (const ref of refs || []) {
    if (!ids.has(ref)) throw new Error(`${label} 參照到不存在的 id：${ref}`);
  }
}

function validateDataset(dataset) {
  const itemIds = assertUniqueIds(dataset.items, "items");
  const markerIds = assertUniqueIds(dataset.markers, "markers");
  const populationIds = assertUniqueIds(dataset.populations, "populations");
  const horseIds = assertUniqueIds(dataset.horses, "horses");
  assertUniqueIds(dataset.resources, "resources");

  for (const item of dataset.items) {
    if (!item.name) throw new Error(`兵裝 ${item.id} 缺少 name`);
    const materials = item.materials;
    if (!materials || typeof materials !== "object" || Array.isArray(materials)) {
      throw new Error(`兵裝 ${item.id} 缺少 materials`);
    }
    for (const [mat, amount] of Object.entries(materials)) {
      if (typeof amount !== "number" || !Number.isFinite(amount) || amount < 0) {
        throw new Error(`兵裝 ${item.id} 的材料 ${mat} 數量不合法`);
      }
    }
    assertRefs(populationIds, item.population, `兵裝 ${item.id} 的 population`);
    assertRefs(horseIds, item.horse, `兵裝 ${item.id} 的 horse`);
  }

  for (const marker of dataset.markers) {
    if (!marker.name) throw new Error(`據點 ${marker.id} 缺少 name`);
    for (const axis of ["x", "y"]) {
      const value = marker[axis];
      if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 100) {
        throw new Error(`據點 ${marker.id} 的 ${axis} 座標不合法（需 0–100）：${value}`);
      }
    }
    assertRefs(itemIds, marker.items, `據點 ${marker.id} 的 items`);
    assertRefs(populationIds, marker.population, `據點 ${marker.id} 的 population`);
  }

  for (const pop of dataset.populations) {
    if (!pop.name) throw new Error(`人口 ${pop.id} 缺少 name`);
  }

  for (const horse of dataset.horses) {
    if (!horse.name) throw new Error(`馬種 ${horse.id} 缺少 name`);
  }

  for (const point of dataset.resources) {
    if (!RESOURCE_TYPES.includes(point.type)) {
      throw new Error(`資源點 ${point.id} 的類型不合法：${point.type}`);
    }
    const level = point.level || 1;
    if (!RESOURCE_LEVELS.includes(level)) {
      throw new Error(`資源點 ${point.id} 的等級不合法：${level}`);
    }
    for (const axis of ["x", "y"]) {
      const value = point[axis];
      if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 100) {
        throw new Error(`資源點 ${point.id} 的 ${axis} 座標不合法（需 0–100）：${value}`);
      }
    }
  }

  return { markerIds, itemIds, populationIds, horseIds };
}

function loadDataset(dataDir) {
  if (!dataDir || !fs.existsSync(dataDir)) {
    throw new Error(`資料目錄不存在：${dataDir}`);
  }

  const dataset = {};
  for (const { name, key } of FILES) {
    const file = path.join(dataDir, `${name}.json`);
    const raw = readJson(file);
    if (!raw || !Array.isArray(raw[key])) {
      throw new Error(`資料檔 ${name}.json 缺少 ${key} 陣列`);
    }
    dataset[name] = raw[key];
  }

  validateDataset(dataset);
  return dataset;
}

function findItem(dataset, id) {
  return dataset.items.find((item) => item.id === id) || null;
}

function toArray(value) {
  if (value === undefined || value === null || value === "") return undefined;
  return Array.isArray(value) ? value : String(value).split(",").filter(Boolean);
}

function filterResources(dataset, options = {}) {
  let rows = dataset.resources;
  const types = toArray(options.type);
  const levels = toArray(options.level || options.levels);
  if (types) rows = rows.filter((row) => types.includes(row.type));
  if (levels) {
    const wanted = levels.map(Number);
    rows = rows.filter((row) => wanted.includes(row.level || 1));
  }
  return rows;
}

function computeMaterials(items, qty = 1) {
  const totals = {};
  for (const item of items) {
    for (const [material, amount] of Object.entries(item.materials || {})) {
      totals[material] = (totals[material] || 0) + amount * qty;
    }
  }
  return totals;
}

function buildSummary(dataset) {
  const resourceTypeCounts = {};
  for (const type of RESOURCE_TYPES) {
    resourceTypeCounts[type] = dataset.resources.filter((row) => row.type === type).length;
  }
  const levelCounts = {};
  for (const level of RESOURCE_LEVELS) {
    levelCounts[level] = dataset.resources.filter((row) => (row.level || 1) === level).length;
  }
  return {
    counts: {
      items: dataset.items.length,
      markers: dataset.markers.length,
      populations: dataset.populations.length,
      horses: dataset.horses.length,
      resources: dataset.resources.length,
    },
    resourceTypeCounts,
    levelCounts,
    materials: computeMaterials(dataset.items, 1),
  };
}

module.exports = {
  FILES,
  RESOURCE_TYPES,
  RESOURCE_LEVELS,
  loadDataset,
  validateDataset,
  findItem,
  filterResources,
  computeMaterials,
  buildSummary,
};
