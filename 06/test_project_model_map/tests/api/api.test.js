"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const request = require("supertest");

const { createApp } = require("../../server/app");

const app = createApp();

test("GET /api/health：回傳 200 與服務狀態", async () => {
  const res = await request(app).get("/api/health").expect(200);
  assert.match(res.headers["content-type"], /application\/json/);
  assert.equal(res.body.status, "ok");
  assert.equal(res.body.service, "map-api");
  assert.deepEqual(res.body.counts, {
    items: 38,
    markers: 63,
    populations: 7,
    horses: 2,
    resources: 145,
  });
});

test("GET /api/summary：回傳統計數量", async () => {
  const res = await request(app).get("/api/summary").expect(200);
  assert.equal(res.body.counts.items, 38);
  assert.equal(res.body.counts.markers, 63);
  assert.equal(res.body.counts.resources, 145);
  assert.equal(Object.values(res.body.resourceTypeCounts).reduce((a, b) => a + b, 0), 145);
});

test("GET /api/items：回傳 38 筆且欄位完整", async () => {
  const res = await request(app).get("/api/items").expect(200);
  assert.equal(res.body.items.length, 38);
  for (const item of res.body.items) {
    assert.equal(typeof item.id, "string");
    assert.equal(typeof item.name, "string");
    assert.equal(typeof item.materials, "object");
  }
});

test("GET /api/items?population=：依人口篩選", async () => {
  const res = await request(app).get("/api/items?population=xiangyong").expect(200);
  assert.ok(res.body.items.length > 0);
  assert.ok(res.body.items.every((item) => (item.population || []).includes("xiangyong")));
});

test("GET /api/items?horse=：依馬種篩選", async () => {
  const res = await request(app).get("/api/items?horse=liangma").expect(200);
  assert.ok(res.body.items.length > 0);
  assert.ok(res.body.items.every((item) => (item.horse || []).includes("liangma")));
});

test("GET /api/items/:id：回傳單一兵裝", async () => {
  const res = await request(app).get("/api/items/danyangbing").expect(200);
  assert.equal(res.body.id, "danyangbing");
  assert.equal(res.body.name, "丹陽兵");
  assert.equal(res.body.materials["皮"], 83);
});

test("GET /api/items/:id：不存在時回傳 404 JSON", async () => {
  const res = await request(app).get("/api/items/no-such-item").expect(404);
  assert.equal(res.body.error, "not_found");
  assert.match(res.body.message, /找不到兵裝/);
});

test("GET /api/markers：回傳 63 個據點", async () => {
  const res = await request(app).get("/api/markers").expect(200);
  assert.equal(res.body.markers.length, 63);
  assert.equal(res.body.markers[0].id, "m1");
});

test("GET /api/markers/:id：存在與不存在", async () => {
  const found = await request(app).get("/api/markers/m1").expect(200);
  assert.equal(found.body.id, "m1");
  const missing = await request(app).get("/api/markers/nope").expect(404);
  assert.equal(missing.body.error, "not_found");
});

test("GET /api/populations：回傳 7 種人口", async () => {
  const res = await request(app).get("/api/populations").expect(200);
  assert.equal(res.body.populations.length, 7);
});

test("GET /api/horses：回傳 2 種馬", async () => {
  const res = await request(app).get("/api/horses").expect(200);
  assert.equal(res.body.horses.length, 2);
});

test("GET /api/resources：回傳 145 個資源點", async () => {
  const res = await request(app).get("/api/resources").expect(200);
  assert.equal(res.body.resources.length, 145);
});

test("GET /api/resources?type=：依類型篩選", async () => {
  const res = await request(app).get("/api/resources?type=pi").expect(200);
  assert.ok(res.body.resources.length > 0);
  assert.ok(res.body.resources.every((row) => row.type === "pi"));
});

test("GET /api/resources?type=&level=：同時篩選", async () => {
  const res = await request(app).get("/api/resources?type=tie&level=3").expect(200);
  assert.ok(res.body.resources.every((row) => row.type === "tie" && (row.level || 1) === 3));
});

test("GET /api/resources?type=pi,tie：支援多類型", async () => {
  const res = await request(app).get("/api/resources?type=pi,tie").expect(200);
  assert.ok(res.body.resources.every((row) => row.type === "pi" || row.type === "tie"));
});

test("GET /api/unknown：回傳 404 JSON", async () => {
  const res = await request(app).get("/api/unknown").expect(404);
  assert.equal(res.body.error, "not_found");
});

test("GET /：回傳前端首頁", async () => {
  const res = await request(app).get("/").expect(200);
  assert.match(res.headers["content-type"], /text\/html/);
  assert.match(res.text, /三國地圖/);
});

test("GET /app.js：回傳 JavaScript 靜態檔", async () => {
  const res = await request(app).get("/app.js").expect(200);
  assert.match(res.headers["content-type"], /javascript/);
  assert.match(res.text, /loadJson/);
});

test("GET /data/items.json：靜態 fallback 仍可取得", async () => {
  const res = await request(app).get("/data/items.json").expect(200);
  assert.equal(res.body.items.length, 38);
});

test("不存在的靜態路徑回傳 404", async () => {
  await request(app).get("/no-such-file.html").expect(404);
});
