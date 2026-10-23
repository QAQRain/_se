# 測試說明（Test README）

本文件專門說明本專案的三層測試：**單元測試（server）**、**系統測試（Web API）**、**E2E 測試（Playwright）**。內容包含測試程式碼位置、測試範圍、案例設計、執行方式與預期結果。

一般安裝與啟動說明請看 [README.md](test_project_model_map/README.md)。

## 1. 對應作業要求

| 作業要求 | 本專案對應 | 狀態 |
| --- | --- | --- |
| 單元測試（server 一定要測） | `server/test/data.test.js`，21 項 | 完成 |
| 系統測試（Web API 測試） | `tests/api/api.test.js`，20 項 | 完成 |
| E2E 測試（無頭瀏覽器、Playwright） | `tests/e2e/map.spec.js`，52 項檢查 | 完成 |
| client 單元測試（可不測） | 未獨立做；client 行為由 E2E 覆蓋 | 依要求可選 |

## 2. 受測系統

```text
瀏覽器
  │  GET /index.html, app.js, assets/*
  │  GET /api/items, /api/markers, ...
  ▼
Node.js + Express（server/server.js → server/app.js）
  │  載入、驗證、聚合
  ▼
data/*.json（items / markers / populations / horses / resources）
```

- 後端邏輯：`server/data.js`（純函式）與 `server/app.js`（路由）。
- 前端邏輯：`app.js`（優先呼叫 API，失敗時 fallback 到 `data/*.json`）。
- 測試不依賴資料庫、不需外網、不修改正式資料。

## 3. 測試程式碼位置

| 層級 | 檔案 | 測試框架 | 數量 |
| --- | --- | --- | --- |
| 單元測試 | `server/test/data.test.js` | Node.js 內建 `node:test` + `node:assert` | 21 項 |
| 系統測試 | `tests/api/api.test.js` | `node:test` + `supertest` | 20 項 |
| E2E | `tests/e2e/map.spec.js` | `@playwright/test`（Chromium 無頭） | 1 個測試、52 項檢查 |
| E2E 設定 | `playwright.config.js` | Playwright | 自動啟動／關閉 server |
| 被測後端邏輯 | `server/data.js` | — | 載入、驗證、統計、篩選、材料計算 |
| 被測 API | `server/app.js` | — | 9 個 API 端點 + 靜態檔托管 |
| 被測前端 | `app.js` | — | 模式切換、篩選、面板、localStorage |
| 測試資料 | `data/*.json` | — | 63 據點 / 38 兵裝 / 7 人口 / 2 馬 / 145 資源點 |

## 4. 單元測試（server）

### 位置與執行

- 程式碼：`server/test/data.test.js`
- 執行：`npm run test:unit`
- 特性：直接呼叫 `server/data.js` 的函式，**不啟動伺服器、不發 HTTP、不連資料庫**，因此速度快且結果穩定。

### 測試對象

| 函式 | 行為 |
| --- | --- |
| `loadDataset(dataDir)` | 讀取五個 JSON、檢查格式、驗證資料、回傳 dataset |
| `validateDataset(dataset)` | id 唯一、參照完整、座標範圍、類型與等級合法 |
| `buildSummary(dataset)` | 各類數量、資源類型／等級統計、材料總量 |
| `computeMaterials(items, qty)` | 依數量累加材料需求 |
| `filterResources(dataset, options)` | 依類型／等級篩選資源點 |
| `findItem(dataset, id)` | 查詢單一兵裝，找不到回 `null` |

### 案例分類（21 項）

1. **正常載入**
   - 五個資料檔可載入，數量為 63 / 38 / 7 / 2 / 145。
   - 各資料表 id 皆唯一。
2. **參照完整性**
   - 據點引用的兵裝與人口都存在。
   - 兵裝引用的人口與馬種都存在。
3. **資料合法性**
   - 據點與資源點座標都在 0–100。
   - 資源類型與等級合法，且涵蓋全部 8 種類型與 Lv.1–4。
4. **統計與計算**
   - `buildSummary` 的數量、類型總和、等級總和、材料總量正確。
   - `computeMaterials` 單一兵裝乘數量、多兵裝累加皆正確。
5. **篩選**
   - 依類型、依等級、類型＋等級、多類型（逗號分隔）、未知類型回空陣列。
6. **查詢**
   - 存在的兵裝回物件，不存在回 `null`。
7. **錯誤處理**
   - 資料目錄不存在、缺少資料檔、JSON 格式錯誤、缺少主要陣列、參照不存在、座標超出範圍，皆拋出對應錯誤。

### 隔離方式

錯誤處理測試會用 `fs.mkdtempSync` 建立暫存目錄，複製正式資料後只破壞其中一個檔案，測試結束以 `fs.rmSync` 刪除，**不會污染 `data/`**。

### 預期輸出

```text
ℹ tests 21
ℹ pass 21
ℹ fail 0
```

## 5. 系統測試（Web API）

### 位置與執行

- 程式碼：`tests/api/api.test.js`
- 執行：`npm run test:api`
- 方式：以 `createApp()` 取得 Express app，透過 `supertest` 直接發送 HTTP 請求，**不佔用實際連接埠**。

### 端點與案例（20 項）

| 端點 | 測試重點 |
| --- | --- |
| `GET /api/health` | 200、JSON Content-Type、`status=ok`、五類數量正確 |
| `GET /api/summary` | 數量統計、資源類型總和為 145 |
| `GET /api/items` | 200、38 筆、每筆具備 id / name / materials |
| `GET /api/items?population=` | 只回傳含指定人口的兵裝 |
| `GET /api/items?horse=` | 只回傳含指定馬種的兵裝 |
| `GET /api/items/:id` | 存在回 200 與正確內容；不存在回 404 JSON |
| `GET /api/markers` | 200、63 筆、第一筆 id 為 `m1` |
| `GET /api/markers/:id` | 存在／不存在（404） |
| `GET /api/populations` | 7 筆 |
| `GET /api/horses` | 2 筆 |
| `GET /api/resources` | 145 筆 |
| `GET /api/resources?type=` | 只回傳指定類型 |
| `GET /api/resources?type=&level=` | 類型與等級同時篩選 |
| `GET /api/resources?type=pi,tie` | 支援逗號分隔多類型 |
| `GET /api/unknown` | 404 JSON |
| `GET /` | 200、`text/html`、含頁面標題 |
| `GET /app.js` | 200、JavaScript Content-Type、含 `loadJson` |
| `GET /data/items.json` | 靜態 fallback 仍可取用（38 筆） |
| 不存在的靜態路徑 | 404 |

### 驗證重點

- HTTP 狀態碼（200 / 404）。
- `Content-Type` 是否正確。
- JSON 結構與欄位型別。
- 資料筆數與篩選結果是否正確。
- API 404 與靜態檔 404 的行為差異。

### 預期輸出

```text
ℹ tests 20
ℹ pass 20
ℹ fail 0
```

## 6. E2E 測試（Playwright）

### 位置與執行

- 程式碼：`tests/e2e/map.spec.js`
- 設定：`playwright.config.js`
- 執行：`npm run test:e2e`
- 瀏覽器：Chromium（無頭）
- 自動化：`webServer` 會啟動 `node server/server.js`，等待 `/api/health` 可用後才開始測試，結束後自動關閉。
- 若你已經用 `start.bat` 開著伺服器，Playwright 會沿用（`reuseExistingServer`）。

### 測試流程

1. 啟動後端。
2. 開啟 `http://127.0.0.1:8000/index.html`。
3. 等待 63 個據點渲染完成。
4. 依序操作兵裝模式、資源點模式、篩選、數量計算、localStorage。
5. 收集所有失敗項目，最後一次斷言；任何一項失敗，整個測試即失敗並列出原因。

### 52 項檢查的分類

| 類別 | 檢查內容 |
| --- | --- |
| 頁面載入 | 標題、版本日期、預設模式按鈕狀態 |
| 資料渲染 | 63 據點、38 兵裝、7 人口、2 馬、8 類型按鈕、資源層預設隱藏 |
| 據點面板 | 名稱與可造數、兵裝列數與 id、人口高亮 |
| 兵裝篩選 | 高亮據點數、人口欄縮減、馬欄內容 |
| 數量計算 | 數量 3／2 的材料合計、清空不被補回、失焦保留 |
| 解鎖方式 | 有 unlock 時顯示正確文字 |
| 人口與馬 | 點人口的高亮數、點馬的兵團高亮 |
| 模式切換 | body class、地圖圖檔、側欄／面板／據點層隱藏與恢復 |
| 資源點渲染 | 145 點、預設全可見、id 順序 |
| 類型與等級篩選 | 8 類型、5 等級按鈕、關閉 Lv.1 的數量、驛站／關口常駐、全部恢復 |
| 已採過標記 | 點擊加入 `visited`、寫入 localStorage、再點取消、重設清空 |
| API 整合 | 前端確實呼叫 `/api/items` 且回 200；未退回 `data/*.json` |

API 整合的兩項檢查會記錄所有 `/api/*` 回應與 `/data/*` 請求，確保本機執行時真的走後端，而不是靠靜態 fallback。

### 預期輸出

```text
Running 1 test using 1 worker

  ok 1 [chromium] › tests\e2e\map.spec.js › 三國地圖：功能、資料與 API 整合驗證

  1 passed
```

## 7. 測試設計原則

- **Arrange–Act–Assert**：每個案例先準備資料、執行操作、再驗證結果。
- **隔離性**：單元測試使用暫存目錄；API 測試不開實際埠；E2E 使用獨立瀏覽器 context。
- **可重現**：不依賴資料庫、不需外網、不修改正式資料；同一份資料每次結果一致。
- **分層負責**：單元測邏輯、系統測契約、E2E 測使用者流程，避免重複測試同一件事。
- **快速回饋**：單元與 API 測試約 1–2 秒；E2E 約 3–5 秒。
- **失敗可讀**：E2E 會累積所有失敗檢查並一次列出，不會只看到第一個錯誤。

## 8. 涵蓋範圍與未涵蓋範圍

### 已涵蓋

- 後端資料載入、驗證、統計、篩選、材料計算。
- Web API 的狀態碼、JSON 結構、數量、篩選與錯誤處理。
- 前端主要操作流程與後端整合。
- 瀏覽器 `localStorage` 的「已採過」狀態。

### 未涵蓋（依作業範圍取捨）

- **Client 單元測試**：作業允許不做；client 行為已由 E2E 覆蓋。
- **效能／壓力測試**：目前資料量固定，未測高併發或大量請求。
- **安全性測試**：未做滲透測試、權限繞過、XSS 自動化掃描。
- **跨瀏覽器測試**：只跑 Chromium；未測 Firefox／WebKit。
- **無障礙測試**：未做 WCAG 自動化檢查。

## 9. 如何新增測試

### 新增單元測試

在 `server/test/data.test.js` 加入 `test("名稱", () => { ... })`，直接呼叫 `server/data.js` 的函式。

### 新增 API 測試

在 `tests/api/api.test.js` 加入：

```js
test("GET /api/xxx：說明", async () => {
  const res = await request(app).get("/api/xxx").expect(200);
  assert.equal(res.body.xxx, "預期值");
});
```

### 新增 E2E 檢查

在 `tests/e2e/map.spec.js` 的流程中加入：

```js
check("檢查名稱", 實際值 === 預期值, 實際值);
```

最後的 `expect(failures).toEqual([])` 會統一判定成敗。

## 10. 執行與繳交建議

- 一鍵跑完三層：雙擊 `test.bat`。
- 分開跑：`npm run test:unit`、`npm run test:api`、`npm run test:e2e`。
- 報告用截圖：執行 `test.bat` 後，將終端機的 `[1/3]`、`[2/3]`、`[3/3]` 與 `[PASS]` 畫面截圖。
- Playwright 產生的 `test-results/`、`playwright-report/` 已被 `.gitignore` 排除，不會進版控。
- 若資料筆數有變動，請同步更新單元與 API 測試中的預期數量，以及 E2E 的相關斷言。
