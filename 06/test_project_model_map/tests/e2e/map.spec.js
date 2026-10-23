"use strict";

const { test, expect } = require("@playwright/test");
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..", "..");
const readJson = (name) => JSON.parse(fs.readFileSync(path.join(ROOT, "data", `${name}.json`), "utf8"));

const items = readJson("items").items;
const markers = readJson("markers").markers;
const pops = readJson("populations").populations;
const horses = readJson("horses").horses;
const resources = readJson("resources").resources;

test("三國地圖：功能、資料與 API 整合驗證", async ({ page }) => {
  const failures = [];
  const check = (name, condition, extra) => {
    if (!condition) failures.push(name + (extra === undefined ? "" : ` => ${JSON.stringify(extra)}`));
  };

  const apiResponses = [];
  const dataRequests = [];
  page.on("response", (response) => {
    const url = response.url();
    if (url.includes("/api/")) apiResponses.push({ url, status: response.status() });
  });
  page.on("request", (request) => {
    if (request.url().includes("/data/")) dataRequests.push(request.url());
  });
  page.on("pageerror", (error) => failures.push(`pageerror: ${error.message}`));

  await page.goto("/index.html", { waitUntil: "load" });
  await page.waitForFunction(() => document.querySelectorAll("#markersLayer .marker").length > 0, null, { timeout: 15000 });

  const elements = (selector) =>
    page.$$eval(selector, (nodes) =>
      nodes.map((node) => ({
        id:
          node.dataset.markerId ||
          node.dataset.itemId ||
          node.dataset.popId ||
          node.dataset.horseId ||
          node.dataset.resId,
        type: node.dataset.resType,
        level: node.dataset.resLevel,
        display: node.style.display,
        cls: node.className,
        text: node.textContent.trim(),
      }))
    );

  check("標題正確", (await page.title()) === "三國地圖 · 兵裝據點", await page.title());
  check("版本日期 20260816.1", (await page.textContent(".update-date")).trim() === "20260816.1");
  const modeButtons = await page.$$eval("#modeSwitch .mode-btn", (nodes) =>
    nodes.map((node) => `${node.dataset.mode}:${node.classList.contains("active")}`)
  );
  check(
    "兵裝按鈕預設 active",
    JSON.stringify(modeButtons) === JSON.stringify(["craft:true", "resource:false"]),
    modeButtons
  );

  let rows = await elements("#markersLayer .marker");
  check("據點 63", rows.length === markers.length, rows.length);
  check("據點 id 完整", rows.every((row, index) => row.id === markers[index].id));
  rows = await elements("#itemList li[data-item-id]");
  check("兵裝清單 38", rows.length === items.length, rows.length);
  rows = await elements("#popList [data-pop-id]");
  check("人口 7", rows.length === pops.length, rows.length);
  rows = await elements("#horseList [data-horse-id]");
  check("馬 2", rows.length === horses.length, rows.length);
  rows = await elements("#resTypeBtns button[data-type]");
  check("資源類型按鈕 8（craft 模式隱藏）", rows.length === 8, rows.length);
  check(
    "craft 模式無資源點可見（visibility hidden）",
    (await page.$eval("#resourcesLayer", (node) => getComputedStyle(node).visibility)) === "hidden"
  );

  const marker = markers[0];
  await page.locator(`#markersLayer .marker[data-marker-id="${marker.id}"]`).click();
  await page.waitForTimeout(150);
  const detailName = (await page.textContent("#dpName")).trim();
  check(
    "據點名稱 + 可造數",
    detailName.indexOf(marker.name) === 0 && detailName.indexOf(`可造 ${marker.items.length} 種兵裝`) !== -1,
    detailName
  );
  const detailRows = await page.$$eval("#dpItems [data-item-id]", (nodes) => nodes.length);
  check("面板兵裝數 = 據點 items 數", detailRows === marker.items.length, detailRows);
  check(
    "面板 item id 與資料一致",
    JSON.stringify((await page.$$eval("#dpItems [data-item-id]", (nodes) => nodes.map((node) => node.dataset.itemId))).sort()) ===
      JSON.stringify([...marker.items].sort())
  );
  const availablePops = await page.$$eval("#popList [data-pop-id].available", (nodes) =>
    nodes.map((node) => node.dataset.popId)
  );
  check(
    "人口欄高亮據點所需人口",
    JSON.stringify(availablePops) === JSON.stringify(marker.population || []),
    availablePops
  );

  await page.evaluate(() => document.querySelector("#resetBtn").click());
  await page.waitForTimeout(100);
  const target = items.find((item) => item.craftable !== false);
  const targetMarkers = markers.filter((row) => row.items.includes(target.id));
  await page.locator(`#itemList li[data-item-id="${target.id}"]`).click();
  await page.waitForTimeout(150);
  const matchCount = await page.$$eval("#markersLayer .marker.match", (nodes) => nodes.length);
  check("高亮據點數 = 資料中可造該兵裝數", matchCount === targetMarkers.length, `${matchCount} vs ${targetMarkers.length}`);
  check(
    "點兵裝人口欄只剩所需人口",
    (await page.$$eval("#popList [data-pop-id]", (nodes) => nodes.length)) === (target.population || []).length
  );
  const shownHorses = await page.$$eval("#horseList [data-horse-id]", (nodes) => nodes.map((node) => node.dataset.horseId));
  check(
    "點兵裝馬欄 = 該兵裝需要的馬",
    JSON.stringify(shownHorses) === JSON.stringify(target.horse || []),
    `${JSON.stringify(shownHorses)} vs ${JSON.stringify(target.horse || [])}`
  );

  const materialKeys = Object.keys(target.materials);
  await page.locator("#qtyInput").fill("3");
  await page.waitForTimeout(100);
  let totals = await page.textContent("#dpTotals");
  check(
    "數量=3 合計正確",
    materialKeys.every((key) => totals.includes(key) && totals.includes(String(target.materials[key] * 3))),
    totals
  );
  await page.locator("#qtyInput").fill("");
  await page.waitForTimeout(100);
  check("數量清空不被強制補回", (await page.inputValue("#qtyInput")) === "");
  await page.locator("#qtyInput").fill("2");
  await page.locator("#qtyInput").blur();
  await page.waitForTimeout(100);
  check("失焦後顯示 2", (await page.inputValue("#qtyInput")) === "2");
  totals = await page.textContent("#dpTotals");
  check(
    "數量=2 合計正確",
    materialKeys.every((key) => totals.includes(String(target.materials[key] * 2))),
    totals
  );

  if (target.unlock) {
    const unlockText = await page.$$eval(".dp-unlock-text", (nodes) => nodes.map((node) => node.textContent.trim()));
    check("顯示解鎖方式區塊", unlockText.length === 1 && unlockText[0] === target.unlock, unlockText);
  }
  await page.evaluate(() => document.querySelector("#resetBtn").click());

  const population = pops[0];
  const populationMarkers = markers.filter((row) => (row.population || []).includes(population.id));
  await page.locator(`#popList [data-pop-id="${population.id}"]`).click();
  await page.waitForTimeout(150);
  const populationMatch = await page.$$eval("#markersLayer .marker.match", (nodes) => nodes.length);
  check("點人口高亮數", populationMatch === populationMarkers.length, `${populationMatch} vs ${populationMarkers.length}`);

  const horse = horses[0];
  const horseItems = items.filter((item) => (item.horse || []).includes(horse.id)).map((item) => item.id);
  await page.locator(`#horseList [data-horse-id="${horse.id}"]`).click();
  await page.waitForTimeout(150);
  const horseMatchItems = await page.$$eval("#itemList li.horse-match", (nodes) => nodes.map((node) => node.dataset.itemId));
  check(
    "點馬高亮使用該馬的兵團",
    JSON.stringify(horseMatchItems.sort()) === JSON.stringify(horseItems.sort()),
    horseMatchItems
  );

  await page.locator('#modeSwitch .mode-btn[data-mode="resource"]').click();
  await page.waitForFunction(() => document.querySelector("#mapImg").getAttribute("src") === "assets/resource-map.png", null, {
    timeout: 10000,
  });
  await page.waitForTimeout(200);
  check("body.mode-resource", await page.evaluate(() => document.body.classList.contains("mode-resource")));
  check(
    "mapImg 換成 resource-map.png",
    (await page.$eval("#mapImg", (node) => node.getAttribute("src"))) === "assets/resource-map.png"
  );
  check("sidebar 隱藏", (await page.$eval(".sidebar", (node) => getComputedStyle(node).display)) === "none");
  check("detailPanel 隱藏", (await page.$eval("#detailPanel", (node) => getComputedStyle(node).display)) === "none");
  check("markersLayer 隱藏", (await page.$eval("#markersLayer", (node) => getComputedStyle(node).display)) === "none");

  rows = await elements("#resourcesLayer .res-point");
  check("資源點 145", rows.length === resources.length, rows.length);
  check("預設全部可見 145", rows.filter((row) => row.display !== "none").length === resources.length);
  check("id 順序與資料一致", rows.every((row, index) => row.id === resources[index].id));

  const typeButtons = await elements("#resTypeBtns button");
  check("類型按鈕 8", typeButtons.length === 8, typeButtons.length);
  const typeIds = await page.$$eval("#resTypeBtns button", (nodes) => nodes.map((node) => node.dataset.type));
  check(
    "類型齊全 pi..guankou",
    ["pi", "tie", "shi", "mu", "liang", "ma", "yizhan", "guankou"].every((type) => typeIds.includes(type)),
    typeIds
  );
  const levelButtons = await elements("#resLevelBtns button");
  check("等級按鈕 5（全部+Lv1-4）", levelButtons.length === 5, levelButtons.length);
  const level1NonSpecial = resources.filter(
    (row) => (row.level || 1) === 1 && row.type !== "yizhan" && row.type !== "guankou"
  ).length;

  await page.locator('#resLevelBtns button[data-level="1"]').click();
  await page.waitForTimeout(100);
  const visibleAfterLevel1 = (await elements("#resourcesLayer .res-point")).filter((row) => row.display !== "none").length;
  check(
    `關閉 Lv.1 → 可見 = 145 - ${level1NonSpecial}`,
    visibleAfterLevel1 === resources.length - level1NonSpecial,
    visibleAfterLevel1
  );
  const level1Shown = (await elements("#resourcesLayer .res-point")).filter(
    (row) => row.display !== "none" && row.type !== "yizhan" && row.type !== "guankou"
  );
  check("剩下可見皆非 Lv.1", level1Shown.every((row) => Number(row.level) !== 1));
  check(
    "驛站/關口仍常駐可見",
    (await elements("#resourcesLayer .res-point")).filter(
      (row) => row.display !== "none" && (row.type === "yizhan" || row.type === "guankou")
    ).length === resources.filter((row) => row.type === "yizhan" || row.type === "guankou").length
  );

  await page.locator('#resLevelBtns button[data-level="all"]').click();
  await page.waitForTimeout(100);
  const visibleAll = (await elements("#resourcesLayer .res-point")).filter((row) => row.display !== "none").length;
  const allOn = await page.$$eval("#resLevelBtns button", (nodes) => nodes.map((node) => node.classList.contains("on")));
  check("按全部→所有等級按鈕 on", allOn.every(Boolean), allOn);
  check("按全部→145 全可見", visibleAll === resources.length, visibleAll);

  const typeToggle = typeIds.find((type) => type !== "yizhan" && type !== "guankou");
  const countOfType = resources.filter((row) => row.type === typeToggle).length;
  await page.locator(`#resTypeBtns button[data-type="${typeToggle}"]`).click();
  await page.waitForTimeout(100);
  const visibleAfterType = (await elements("#resourcesLayer .res-point")).filter((row) => row.display !== "none").length;
  check(`關閉類型 ${typeToggle} → 145 - ${countOfType}`, visibleAfterType === resources.length - countOfType, visibleAfterType);

  const resource = resources.find((row) => row.type === "pi" || row.type === "liang");
  await page.evaluate(
    (id) => document.querySelector(`#resourcesLayer .res-point[data-res-id="${id}"]`).click(),
    resource.id
  );
  await page.waitForTimeout(100);
  check(
    "點擊→visited class",
    await page.$eval(`#resourcesLayer .res-point[data-res-id="${resource.id}"]`, (node) =>
      node.classList.contains("visited")
    )
  );
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem("sanguo_visited") || "{}"));
  check("localStorage 已存", !!stored[resource.id]);
  await page.evaluate(
    (id) => document.querySelector(`#resourcesLayer .res-point[data-res-id="${id}"]`).click(),
    resource.id
  );
  await page.waitForTimeout(100);
  check(
    "再點→取消 visited",
    !(await page.$eval(`#resourcesLayer .res-point[data-res-id="${resource.id}"]`, (node) =>
      node.classList.contains("visited")
    ))
  );
  const storedAfterToggle = await page.evaluate(() => JSON.parse(localStorage.getItem("sanguo_visited") || "{}"));
  check("localStorage 已移除", !storedAfterToggle[resource.id]);

  await page.evaluate(
    (id) => document.querySelector(`#resourcesLayer .res-point[data-res-id="${id}"]`).click(),
    resource.id
  );
  await page.waitForTimeout(100);
  await page.evaluate(() => document.querySelector("#resetBtn").click());
  await page.waitForTimeout(100);
  check(
    "重設後清除 visited class",
    !(await page.$eval(`#resourcesLayer .res-point[data-res-id="${resource.id}"]`, (node) =>
      node.classList.contains("visited")
    ))
  );
  const storedAfterReset = await page.evaluate(() => JSON.parse(localStorage.getItem("sanguo_visited") || "{}"));
  check("重設後 localStorage 清空", Object.keys(storedAfterReset).length === 0, storedAfterReset);

  await page.locator('#modeSwitch .mode-btn[data-mode="craft"]').click();
  await page.waitForFunction(() => document.querySelector("#mapImg").getAttribute("src") === "assets/map.png", null, {
    timeout: 10000,
  });
  await page.waitForTimeout(200);
  check("body.mode-craft", await page.evaluate(() => document.body.classList.contains("mode-craft")));
  check("sidebar 恢復顯示", (await page.$eval(".sidebar", (node) => getComputedStyle(node).display)) !== "none");
  check("據點 63 仍渲染", (await elements("#markersLayer .marker")).length === markers.length);

  check(
    "前端確實呼叫後端 API",
    apiResponses.some((entry) => entry.url.endsWith("/api/items") && entry.status === 200),
    apiResponses.slice(0, 5)
  );
  check("前端未退回靜態 data/*.json", dataRequests.length === 0, dataRequests);

  expect(failures, failures.join("\n")).toEqual([]);
});
