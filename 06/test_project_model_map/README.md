# 三國兵裝據點地圖（學校作業版）

《戰意：三國》互動輔助地圖：把全地圖 63 個據點的兵裝製造情報、徵兵人口、兵團馬種、145 個資源點整理成一張可操作的互動地圖。點據點看兵裝與材料，點兵裝反查製造據點，資源需求即時計算。

本資料夾是原版靜態網站的學校作業副本，並額外加入 **Node.js（Express）後端** 與 **三層自動化測試**：

- 前端、資料、圖片沿用原版。
- 新增 `server/`：在本機提供 `http://localhost:8000`，同時托管前端與 Web API。
- 新增 `tests/` 與 `server/test/`：單元測試、Web API 系統測試、Playwright E2E。
- 前端會優先呼叫 `/api/*`；若後端不存在（例如部署到 GitHub Pages），自動退回讀取 `data/*.json`，靜態版仍可運作。

原版網站：<https://rainchenblue.github.io/threekingdom_map/>

測試的詳細說明請看 **[readme.md](06/readme.md)**。

## 功能一覽

- **63 個據點**：點擊任一據點，顯示可製造的兵裝、所需材料與解鎖方式。
- **38 個兵裝／兵團**：點擊兵裝清單，地圖高亮所有能製造該兵裝的據點。
- **徵兵人口**：點擊人口，高亮擁有該人口的據點；點兵裝時只顯示所需人口。
- **馬種取得**：點擊良馬／軍馬，反查使用該馬種的兵團。
- **材料需求計算**：調整「數量」，合計材料自動乘以數量。
- **我的資源**：輸入皮／鐵／韌皮／精鐵庫存，不足的材料會標紅。
- **資源點模式**：145 個資源點（Lv.1–4），可依類型與等級篩選，並標記「已採過」。
- **雙模式切換**：「兵裝」與「資源點」一鍵切換。
- **手機版**：介面自動改為直排。

## 系統需求

| 項目 | 需求 |
| --- | --- |
| 作業系統 | Windows、macOS、Linux 皆可（本說明以 Windows 為主） |
| Node.js | 18 以上，建議安裝 LTS 版 |
| 瀏覽器 | Chrome／Edge／Firefox 任一現代瀏覽器 |
| 網路 | 僅第一次 `npm install` 與安裝 Playwright Chromium 時需要 |

Node.js 下載：<https://nodejs.org/>

## 安裝

在專案資料夾開啟終端機（Command Prompt 或 PowerShell），執行：

```bat
npm install
npx playwright install chromium
```

說明：

- `npm install` 安裝 Express、Supertest、Playwright 等相依套件。
- `npx playwright install chromium` 下載 E2E 測試用的無頭瀏覽器，約 150 MB，只需執行一次。
- 若 PowerShell 出現「已停用指令碼執行」錯誤，請改用 `npm.cmd` / `npx.cmd`，或參考下方「常見問題」。

## 啟動

### 方法一：雙擊 `start.bat`（建議）

- 第一次啟動會自動檢查並安裝相依套件。
- 啟動後會自動開啟瀏覽器：<http://localhost:8000>
- 終端機視窗會停留在執行中的伺服器；關閉視窗即停止。

### 方法二：手動啟動

```bat
npm start
```

或

```bat
node server/server.js
```

啟動後開啟 <http://localhost:8000>。

### 變更連接埠

預設使用 8000。若被占用，可在啟動前設定 `PORT`：

```bat
set PORT=8080
npm start
```

PowerShell：

```powershell
$env:PORT=8080
npm start
```

## 關閉

| 情況 | 關閉方式 |
| --- | --- |
| 用 `start.bat` 或 `npm start` 啟動 | 在該終端機視窗按 `Ctrl+C`，或直接關閉視窗 |
| 用 `test.bat` 跑測試 | E2E 會自動啟動並關閉測試用伺服器，不需要手動關 |
| 連接埠被殘留程序占用 | `netstat -ano | findstr :8000` 找到 PID，再 `taskkill /PID <PID> /F` |

## 測試

### 一鍵執行三層測試

雙擊 `test.bat`，會依序執行：

1. 單元測試（server）
2. 系統測試（Web API）
3. E2E 測試（Playwright）

全部通過會顯示：

```text
[PASS] All three test layers passed.
```

### 分開執行

```bat
npm run test:unit     :: 單元測試，21 項
npm run test:api      :: Web API 系統測試，20 項
npm run test:e2e      :: Playwright E2E，1 個測試內含 52 項檢查
npm test              :: 只跑單元 + API
```

預期結果：

| 指令 | 預期輸出 |
| --- | --- |
| `npm run test:unit` | `tests 21 / pass 21 / fail 0` |
| `npm run test:api` | `tests 20 / pass 20 / fail 0` |
| `npm run test:e2e` | `1 passed` |

E2E 會透過 `playwright.config.js` 自動啟動 `server/server.js`；若你已經開著 `start.bat`，會直接沿用同一個伺服器。

測試內容、檔案位置與設計說明：**[a_readme.md](a_readme.md)**

## Web API

後端由 `server/app.js` 提供，回應皆為 JSON（靜態檔除外）。

| 方法 | 路徑 | 說明 |
| --- | --- | --- |
| GET | `/api/health` | 健康檢查與資料筆數 |
| GET | `/api/summary` | 各類數量、資源類型／等級統計、材料總量 |
| GET | `/api/items` | 38 筆兵裝；可用 `?population=`、`?horse=`、`?craftable=true` 篩選 |
| GET | `/api/items/:id` | 單一兵裝，找不到回 404 |
| GET | `/api/markers` | 63 個據點 |
| GET | `/api/markers/:id` | 單一據點，找不到回 404 |
| GET | `/api/populations` | 7 種徵兵人口 |
| GET | `/api/horses` | 2 種馬 |
| GET | `/api/resources` | 145 個資源點；可用 `?type=pi,tie`、`?level=2` 篩選 |

其他不存在的 `/api/*` 會回傳 JSON 404；不存在的靜態路徑回傳文字 404。

## 專案結構

```text
test_project_model_map/
├── index.html               前端頁面
├── app.js                   前端邏輯（優先呼叫 /api/*，失敗退回 data/*.json）
├── style.css                樣式
├── assets/                  圖片素材
├── data/                    原始 JSON 資料（同時作為靜態 fallback）
├── server/
│   ├── data.js              資料載入、驗證、統計、篩選（純函式）
│   ├── app.js               Express app 與 API 路由
│   ├── server.js            啟動 http://localhost:8000
│   └── test/data.test.js    單元測試（21 項）
├── tests/
│   ├── api/api.test.js      系統測試（20 項）
│   └── e2e/map.spec.js      E2E 測試（52 項檢查）
├── playwright.config.js     Playwright 設定與自動啟動伺服器
├── package.json             npm scripts 與相依套件
├── start.bat                Windows 一鍵啟動
├── test.bat                 Windows 一鍵跑三層測試
├── README.md                本文件
└── a_readme.md              測試專用說明
```

## 使用說明

### 模式切換

標題列的「兵裝｜資源點」按鈕切換兩種模式，切換時會清除選取與高亮。

### 兵裝模式

- 點擊據點：左上方面板顯示可造兵裝、材料，人口欄同步高亮。
- 點擊兵裝：地圖高亮可製造該兵裝的據點，人口／馬欄只顯示該兵裝所需。
- 點擊人口：高亮擁有該人口的據點（可與兵裝篩選同時生效）。
- 點擊馬：高亮使用該馬種的兵團。
- 數量欄位：材料合計自動乘以數量。
- 我的資源：輸入庫存並勾選不足警示，材料不足會標紅。
- 重設：清除選取與高亮。

### 資源點模式

- 資源點依類型與等級顯示，游標停留可看名稱、類型、等級。
- 點擊資源點標記「已採過」，再點一次取消；狀態存在瀏覽器 `localStorage`。
- 右上角可切換 8 種資源類型與 Lv.1–4 等級；驛站／關口常駐顯示。
- 重設會清除選取、高亮與全部「已採過」標記。

### 縮放與移動

滑鼠滾輪或觸控板兩指縮放；按住地圖空白處拖曳平移；右下角可重設為 100%。

## 資料維護

所有資料都是 JSON，修改資料不需要動程式碼：

- `data/markers.json`：63 個據點（座標為地圖百分比 0–100，左上角為 0,0）。
- `data/items.json`：38 個兵裝／兵團（材料、人口、馬種、星級、解鎖方式）。
- `data/populations.json`：7 種徵兵人口。
- `data/horses.json`：2 種馬。
- `data/resources.json`：145 個資源點（類型、等級、座標）。

後端啟動時會驗證資料：id 不可重複、參照的兵裝／人口／馬種必須存在、座標需在 0–100、資源類型與等級需合法。驗證失敗會直接拒絕啟動並顯示原因。

更換據點地圖背景時，需同步更新 `style.css` 內 `.map-wrap` 的 `aspect-ratio`（目前為 `1122 / 771`）。

## 部署到 GitHub Pages

GitHub Pages 只能托管靜態檔，**無法執行 Node.js 後端**。本專案已在前端加入 fallback：

- 有後端（本機）→ 使用 `/api/*`。
- 無後端（GitHub Pages）→ 自動改讀 `data/*.json`，功能不受影響。

部署方式不變：push 到 `main` 後由 `.github/workflows/pages.yml` 自動部署。首次部署需在 repo 的 Settings → Pages 將 Source 設為「GitHub Actions」。

## 常見問題

### PowerShell 顯示「因為這個系統上已停用指令碼執行，所以無法載入 npm.ps1」

改用 `npm.cmd` / `npx.cmd`：

```powershell
npm.cmd install
npx.cmd playwright install chromium
```

或只對目前使用者解除限制：

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### 雙擊 `start.bat` 視窗一閃就關

`start.bat` 已改為 CRLF／ASCII 並在錯誤時 `pause`。若仍發生，請在資料夾網址列輸入 `cmd` 開啟命令提示字元，再執行 `start.bat`，即可看到完整錯誤訊息。

### `npm install` 或 E2E 失敗

- 確認 `node -v` 有輸出（需 18 以上）。
- 確認第一次已執行 `npx playwright install chromium`。
- 確認連接埠 8000 沒有被其他程式占用。

### 前端顯示「資料載入失敗」

代表 `/api/*` 與 `data/*.json` 都取不到。請確認你是透過 `start.bat`／`npm start` 啟動，而不是直接雙擊 `index.html`（直接開檔案無法使用 `fetch`）。

## 資料來源

原始專案與內容以原版網站為準：<https://rainchenblue.github.io/threekingdom_map/>
