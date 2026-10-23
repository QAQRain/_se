"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");

const {
  loadDataset,
  findItem,
  filterResources,
  computeMaterials,
  buildSummary,
  RESOURCE_TYPES,
  RESOURCE_LEVELS,
} = require("../data");

const DATA_DIR = path.join(__dirname, "..", "..", "data");
const dataset = loadDataset(DATA_DIR);

function readData(dir, name) {
  return JSON.parse(fs.readFileSync(path.join(dir, `${name}.json`), "utf8"));
}

function writeData(dir, name, data) {
  fs.writeFileSync(path.join(dir, `${name}.json`), JSON.stringify(data, null, 2));
}

test("loadDataset：載入五個資料檔並取得正確數量", () => {
  assert.equal(dataset.items.length, 38);
  assert.equal(dataset.markers.length, 63);
  assert.equal(dataset.populations.length, 7);
  assert.equal(dataset.horses.length, 2);
  assert.equal(dataset.resources.length, 145);
});

test("validateDataset：各資料表的 id 皆唯一", () => {
  for (const name of ["items", "markers", "populations", "horses", "resources"]) {
    const ids = dataset[name].map((row) => row.id);
    assert.equal(new Set(ids).size, ids.length, `${name} 有重複 id`);
  }
});

test("validateDataset：據點參照的兵裝與人口都存在", () => {
  const itemIds = new Set(dataset.items.map((row) => row.id));
  const populationIds = new Set(dataset.populations.map((row) => row.id));
  for (const marker of dataset.markers) {
    for (const id of marker.items || []) assert.ok(itemIds.has(id), `據點 ${marker.id} 參照不存在的兵裝 ${id}`);
    for (const id of marker.population || []) {
      assert.ok(populationIds.has(id), `據點 ${marker.id} 參照不存在的人口 ${id}`);
    }
  }
});

test("validateDataset：兵裝參照的人口與馬種都存在", () => {
  const populationIds = new Set(dataset.populations.map((row) => row.id));
  const horseIds = new Set(dataset.horses.map((row) => row.id));
  for (const item of dataset.items) {
    for (const id of item.population || []) {
      assert.ok(populationIds.has(id), `兵裝 ${item.id} 參照不存在的人口 ${id}`);
    }
    for (const id of item.horse || []) assert.ok(horseIds.has(id), `兵裝 ${item.id} 參照不存在的馬種 ${id}`);
  }
});

test("validateDataset：據點與資源點座標都在 0–100", () => {
  for (const marker of dataset.markers) {
    assert.ok(marker.x >= 0 && marker.x <= 100, `據點 ${marker.id} x 超出範圍`);
    assert.ok(marker.y >= 0 && marker.y <= 100, `據點 ${marker.id} y 超出範圍`);
  }
  for (const point of dataset.resources) {
    assert.ok(point.x >= 0 && point.x <= 100, `資源點 ${point.id} x 超出範圍`);
    assert.ok(point.y >= 0 && point.y <= 100, `資源點 ${point.id} y 超出範圍`);
  }
});

test("validateDataset：資源點類型與等級都合法且涵蓋全部種類", () => {
  for (const point of dataset.resources) {
    assert.ok(RESOURCE_TYPES.includes(point.type), `資源點 ${point.id} 類型不合法`);
    assert.ok(RESOURCE_LEVELS.includes(point.level || 1), `資源點 ${point.id} 等級不合法`);
  }
  const types = new Set(dataset.resources.map((row) => row.type));
  assert.deepEqual([...types].sort(), [...RESOURCE_TYPES].sort());
  const levels = new Set(dataset.resources.map((row) => row.level || 1));
  assert.deepEqual([...levels].sort(), [...RESOURCE_LEVELS].sort());
});

test("buildSummary：數量、資源類型與等級統計正確", () => {
  const summary = buildSummary(dataset);
  assert.deepEqual(summary.counts, {
    items: 38,
    markers: 63,
    populations: 7,
    horses: 2,
    resources: 145,
  });
  const typeTotal = Object.values(summary.resourceTypeCounts).reduce((a, b) => a + b, 0);
  const levelTotal = Object.values(summary.levelCounts).reduce((a, b) => a + b, 0);
  assert.equal(typeTotal, 145);
  assert.equal(levelTotal, 145);
  assert.ok(summary.materials["皮"] > 0);
  assert.ok(summary.materials["鐵"] > 0);
});

test("computeMaterials：單一兵裝乘上數量", () => {
  const item = findItem(dataset, "danyangbing");
  assert.ok(item);
  assert.deepEqual(computeMaterials([item], 3), { 皮: 249, 鐵: 249 });
});

test("computeMaterials：多個兵裝材料會累加", () => {
  const [first, second] = dataset.items;
  const totals = computeMaterials([first, second], 2);
  const expected = {};
  for (const item of [first, second]) {
    for (const [material, amount] of Object.entries(item.materials)) {
      expected[material] = (expected[material] || 0) + amount * 2;
    }
  }
  assert.deepEqual(totals, expected);
});

test("filterResources：依類型篩選", () => {
  const rows = filterResources(dataset, { type: "pi" });
  assert.ok(rows.length > 0);
  assert.ok(rows.every((row) => row.type === "pi"));
  assert.equal(rows.length, dataset.resources.filter((row) => row.type === "pi").length);
});

test("filterResources：依等級篩選", () => {
  const rows = filterResources(dataset, { level: 2 });
  assert.ok(rows.length > 0);
  assert.ok(rows.every((row) => (row.level || 1) === 2));
});

test("filterResources：類型與等級可同時篩選", () => {
  const rows = filterResources(dataset, { type: "tie", level: 3 });
  assert.ok(rows.every((row) => row.type === "tie" && (row.level || 1) === 3));
  assert.equal(rows.length, dataset.resources.filter((row) => row.type === "tie" && (row.level || 1) === 3).length);
});

test("filterResources：多個類型以逗號分隔", () => {
  const rows = filterResources(dataset, { type: "pi,tie" });
  assert.ok(rows.every((row) => row.type === "pi" || row.type === "tie"));
});

test("filterResources：未知類型回傳空陣列", () => {
  assert.deepEqual(filterResources(dataset, { type: "not-a-type" }), []);
});

test("findItem：存在的兵裝回傳物件，不存在回傳 null", () => {
  assert.equal(findItem(dataset, "danyangbing").name, "丹陽兵");
  assert.equal(findItem(dataset, "no-such-item"), null);
});

test("loadDataset：資料目錄不存在時拋出錯誤", () => {
  assert.throws(() => loadDataset(path.join(os.tmpdir(), "no-such-map-data-dir")), /資料目錄不存在/);
});

test("loadDataset：缺少資料檔時拋出錯誤", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "map-data-"));
  fs.cpSync(DATA_DIR, dir, { recursive: true });
  fs.rmSync(path.join(dir, "items.json"));
  try {
    assert.throws(() => loadDataset(dir), /無法讀取資料檔 items\.json/);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("loadDataset：JSON 格式錯誤時拋出錯誤", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "map-data-"));
  fs.cpSync(DATA_DIR, dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "items.json"), "{ not json");
  try {
    assert.throws(() => loadDataset(dir), /不是合法 JSON/);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("loadDataset：資料檔缺少主要陣列時拋出錯誤", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "map-data-"));
  fs.cpSync(DATA_DIR, dir, { recursive: true });
  writeData(dir, "horses", {});
  try {
    assert.throws(() => loadDataset(dir), /缺少 horses 陣列/);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("loadDataset：參照到不存在的兵裝時拋出錯誤", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "map-data-"));
  fs.cpSync(DATA_DIR, dir, { recursive: true });
  const markers = readData(dir, "markers");
  markers.markers[0].items.push("no-such-item");
  writeData(dir, "markers", markers);
  try {
    assert.throws(() => loadDataset(dir), /參照到不存在的 id/);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("loadDataset：座標超出範圍時拋出錯誤", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "map-data-"));
  fs.cpSync(DATA_DIR, dir, { recursive: true });
  const markers = readData(dir, "markers");
  markers.markers[0].x = 150;
  writeData(dir, "markers", markers);
  try {
    assert.throws(() => loadDataset(dir), /座標不合法/);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
