# 現代軟體工程 作品統整

## 專案簡介

本文件收錄「現代軟體工程」課程期間完成的 8 個實作專案，依技術演進可分為三條主線與兩個獨立作品：

- **校務系統主線**：單機版 SAS 校務行政系統 → Docker 微服務版
- **遊戲地圖主線**：靜態互動地圖 → 具備後端與三層自動化測試的版本
- **AI 目錄主線**：靜態網站 → 可重用的 npm 資料套件
- **獨立作品**：mycurl 命令列工具、AniDex 動漫資料站

內容包含每個作品的功能、使用技術、啟動與關閉方式，適合第一次接觸這些作品的人快速上手。

## 系統需求

| 項目 | 需求 |
| --- | --- |
| 作業系統 | Windows、macOS、Linux 皆可 |
| 瀏覽器 | Chrome、Edge、Firefox、Safari 任一現代瀏覽器 |
| Python | 3.7 以上（mycurl、SAS 校務系統） |
| Node.js | 18 以上，建議 LTS 版（三國地圖測試版） |
| Docker | Docker Desktop 或 Docker Engine，並含 Docker Compose（微服務版） |
| 網路 | 僅安裝相依套件、載入線上封面圖片與使用線上版時需要 |

## 安裝方式

閱讀本文件不需要安裝任何東西。各專案的安裝方式如下：

- **Python 專案**：`pip install -r requirements.txt` 或 `pip install flask`
- **Node 專案**：`npm install`；執行 E2E 測試前另需 `npx playwright install chromium`
- **Docker 專案**：安裝 Docker 後不需額外安裝，由 `docker compose up --build` 自動建置映像
- **靜態網站**：不需要安裝，雙擊 `index.html` 即可使用

## 使用方式

| 作品 | 啟動方式 | 開啟位置 |
| --- | --- | --- |
| mycurl | `python mycurl.py https://example.com/` | 命令列，無網頁介面 |
| SAS 校務系統 | `python app.py` | <http://localhost:5000> |
| 三國地圖（靜態版） | `python -m http.server 8000` | <http://localhost:8000> |
| SAS Docker 微服務 | `docker compose up --build` | <http://localhost> |
| 三國地圖（測試版） | 雙擊 `start.bat`，或執行 `npm start` | <http://localhost:8000> |
| AniDex | 雙擊 `index.html` 或 `start.bat` | <https://qaqrain.github.io/anidex/> |
| AI 工具總覽網站 | 雙擊 `public/index.html` | <https://ai-catalog.qaqrain.workers.dev/> |
| `@qaqrain/ai-catalog` | `npm install @qaqrain/ai-catalog` | 程式匯入或 jsDelivr CDN |

注意：三國地圖的資料由 `fetch` 載入，直接雙擊 `index.html` 無法運作，必須透過 HTTP 伺服器開啟。AniDex 的資料檔改用 JavaScript 格式，因此可以直接雙擊開啟。

## 關閉方式

| 類型 | 關閉方式 |
| --- | --- |
| mycurl | 指令執行完畢即自動結束 |
| Flask / Node 伺服器 | 在該終端機視窗按 `Ctrl+C`，或直接關閉視窗 |
| Docker 微服務 | 執行 `docker compose down`；若要連同資料一併清除，改用 `docker compose down -v` |
| 靜態網站 | 直接關閉瀏覽器分頁，沒有背景程式或常駐服務 |

Docker 補充：在 `docker compose up` 的前景畫面按 `Ctrl+C` 只是中斷日誌輸出，容器可能仍在背景執行，仍須執行 `docker compose down` 才會真正關閉；可用 `docker compose ps` 確認。

## 檔案結構

| 目錄 | 內容 |
| --- | --- |
| `01/curl_project/` | mycurl 原始碼與說明 |
| `02/SAS_project/` | SAS 校務行政系統，含後端、前端與種子資料產生器 |
| `03/project_threekingdom_map/` | 三國地圖靜態版，含 JSON 資料與圖片素材 |
| `05/SASforDocker_project/` | SAS Docker 微服務版，含編排檔、反向代理與三種語言的 API |
| `06/test_project_model_map/` | 三國地圖測試版，含 Express 後端與三層測試 |
| `08/anidex_project/` | AniDex 動漫資料站 |
| `09/` | AI 工具總覽網站說明，原始碼位於 <https://github.com/QAQRain/ai-catalog/> |
| `10/` | `@qaqrain/ai-catalog` 套件說明 |

## 功能說明

### 1. mycurl：Python HTTP 命令列工具

純 Python 實作的類 curl 工具，以 `requests` 為基礎，參數刻意模仿 curl 以降低學習成本。

- 支援 GET、POST、PUT、DELETE、HEAD、PATCH 六種方法
- 自訂請求標頭（`-H`，可重複）、表單或 JSON 資料（`-d`、`-j`）
- 顯示回應狀態、耗時與標頭（`-i`）、儲存回應內容（`-o`）
- 靜默模式（`-s`）與連線逾時設定（`-t`）
- 連線失敗時印出錯誤訊息並回傳非零結束碼，方便在指令稿中判斷

**介紹文件**：[mycurl README](https://github.com/QAQRain/_se/blob/main/01/curl_project/README.md)

### 2. SAS 校務行政系統

以「國立海嶼大學」為情境的校務行政系統，後端為 Flask + SQLite，前端為單一深色 SPA（原生 JavaScript + Chart.js）。

- **權限**：系統管理員、行政人員、教師、學生四種角色，每支 API 皆做角色驗證
- **教務**：學生與教職員資料管理、課程與開課管理、課表查詢、衝堂辨識
- **學務**：點名與出缺勤統計、請假核准、獎懲登錄、諮商輔導派案與約談紀錄
- **成績**：期中與期末成績輸入、GPA 採臺大 4.3 制、等級與分布圖表
- **選課**：三階段流程（關閉 → 初選志願 → 結算 → 加退選），志願上限 4 個、學分上限 28，結算依志願序與名額錄取
- **財務與報表**：學雜費繳費、獎學金、公告，以及含中文檔名的 CSV 報表
- **種子資料**：約 224 名學生、57 名教職員、183 門課程、2,016 筆修課紀錄
- **示範帳號**：`admin/admin123`、`clerk/clerk123`、`teacher/teacher123`、`student/student123`

**介紹文件**：[SAS_project README](https://github.com/QAQRain/_se/blob/main/02/SAS_project/README.md)

### 3. 三國兵裝據點地圖（靜態版）

《戰意：三國》互動輔助地圖，把遊戲內分散的情報整理成一張可操作的地圖，純靜態網站、無需建置流程。

- **資料規模**：63 個據點、38 個兵裝與兵團、7 種徵兵人口、2 種馬、145 個資源點
- **雙向查詢**：點據點看可製造的兵裝與材料；點兵裝反查所有可製造的據點；人口與馬種同樣可反查
- **材料計算**：調整數量後，所需材料合計自動乘以數量
- **資源管理**：輸入皮、鐵、韌皮、精鐵庫存，不足的材料標紅提示
- **資源點模式**：依 8 種類型與 Lv.1 至 Lv.4 篩選，可標記「已採過」並存於瀏覽器
- **操作**：滑鼠滾輪縮放、拖曳平移、一鍵回到 100%，手機版自動改為直排
- **部署**：資料存放於 JSON，搭配 GitHub Actions 自動部署到 GitHub Pages

**介紹文件**：[project_threekingdom_map README](https://github.com/QAQRain/_se/blob/main/03/project_threekingdom_map/README.md)

### 4. SAS Docker 微服務版

將 SAS 校務行政系統改造成六個容器的微服務架構，僅對外開放 80 埠。

- **服務組成**：Nginx（網頁伺服器與反向代理）、Flask + gunicorn、PostgreSQL，以及 Node.js（Express）、Rust（Axum）、Python（FastAPI）三個獨立 API
- **路由**：Nginx 將 `/api/node/*`、`/api/rust/*`、`/api/python/*` 導向對應服務，其餘導向 Flask
- **狀態面板**：在 SAS 首頁新增「Docker 微服務系統狀態」區塊，即時顯示各服務的健康檢查與資料庫連線結果
- **建置重點**：Flask 使用單一 gunicorn worker，避免初始化時多行程同時重建資料庫；Rust 映像採多階段建置以縮小體積
- **資料持久化**：PostgreSQL 使用 named volume `pgdata`，一般停止指令不會清除資料

**介紹文件**：[SASforDocker_project README](https://github.com/QAQRain/_se/blob/main/05/SASforDocker_project/README.md)、[Docker 學習筆記](https://github.com/QAQRain/_se/blob/main/05/README.md)

### 5. 三國地圖三層自動化測試

以三國地圖為受測系統，建立「單元測試 → 系統測試 → E2E 測試」三道防線；為了配合測試，另外加入 Node.js（Express）後端與 9 個 API。

**三層測試**

- **單元測試（21 項）**：使用 Node.js 內建 `node:test`，直接測試後端純函式的資料載入、格式驗證、統計、材料計算與篩選邏輯；不啟動伺服器、不發出 HTTP 請求，並使用暫存目錄避免污染正式資料
- **系統測試（20 項）**：使用 Supertest 直接對 Express app 發出請求，驗證 9 個 API 端點的狀態碼、內容型別、JSON 結構、資料筆數與篩選結果，不實際佔用連接埠
- **E2E 測試（1 個測試、52 項檢查）**：使用 Playwright 搭配無頭 Chromium，模擬完整使用者流程，涵蓋頁面渲染、兵裝與資源點篩選、材料數量計算、雙模式切換、`localStorage` 已採標記，並確認前端確實呼叫 `/api/*` 而非退回靜態資料
- **一鍵執行**：`test.bat` 依序跑完三層；`start.bat` 僅用於啟動伺服器

**搭配測試的系統調整**

- **後端**：新增 9 個 API 端點，並在啟動時驗證資料（id 唯一、參照完整、座標範圍、類型與等級合法）
- **前端容錯**：優先呼叫 `/api/*`，若後端不存在則自動退回讀取 `data/*.json`，讓靜態部署版本仍可正常運作
- **測試設計**：各層使用獨立的資料與環境，不依賴資料庫、不需外網、不修改正式資料，每次執行結果一致

**介紹文件**：[測試說明](https://github.com/QAQRain/_se/blob/main/06/readme.md)、[專案說明](https://github.com/QAQRain/_se/blob/main/06/test_project_model_map/README.md)

### 6. AniDex 動漫資料站

收錄 AniList 人氣前 500 名動畫的純前端網站，不需要資料庫、後端、建置流程或任何安裝。

- **搜尋**：支援中文名、日文原名與英文名
- **篩選**：類型、年份區間、最低評分、播出狀態，並可依人氣、評分、年份或名稱排序
- **比較**：最多加入 4 部作品，以表格並排呈現，評分與人氣最高者以綠色標示
- **分享**：所有篩選條件寫入網址；每部作品有獨立連結，例如 `index.html#/a/16498`
- **資料格式**：使用 `window.ANIME_DATA = ...` 的 JavaScript 檔，避開直接開啟本機檔案時瀏覽器對 `fetch` 的限制

**介紹文件**：[anidex_project README](https://github.com/QAQRain/_se/blob/main/08/anidex_project/README.md)

### 7. AI 工具總覽網站

把 52 個主流 AI 服務整理成可搜尋、可比較的清單，純 HTML、CSS 與 JavaScript，由 Cloudflare Workers 托管。

- **兩種檢視**：卡片與比較表可切換
- **雙語**：中英雙語介面，每一筆服務說明皆有雙語版本
- **篩選**：依名稱、廠商與功能關鍵字搜尋，並可依九種分類篩選、只顯示免費服務
- **能力標記**：標示看圖、生圖、生影片、語音、寫程式五種能力
- **其他**：深色模式與手機版介面

**介紹文件**：[09 README](https://github.com/QAQRain/_se/blob/main/09/README.md)

### 8. `@qaqrain/ai-catalog` npm 套件

將 AI 工具總覽的同一份資料發佈成可重用的套件，並附上一份可直接開啟的靜態網站。

- **結構化資料**：52 筆服務資料，含分類、能力標記與中英雙語免費額度說明
- **程式介面**：提供 `items`、`byCategory()`、`search()`、`getById()`，並附 TypeScript 型別
- **多種取用方式**：`npm install @qaqrain/ai-catalog` 匯入，或直接從 jsDelivr CDN 取得 `data.json`
- **開發流程**：修改 `data.json` 後執行 `npm run build` 重新產生資料檔；`npm run preview` 可在本機預覽網站

**介紹文件**：[10 README](https://github.com/QAQRain/_se/blob/main/10/README.md)

## 資料來源

| 作品 | 來源說明 |
| --- | --- |
| mycurl | 無外部資料 |
| SAS 校務系統 | 種子資料由程式隨機產生的虛構資料 |
| 三國地圖 | 遊戲資料與圖片取自原版網站：<https://rainchenblue.github.io/threekingdom_map/> |
| AniDex | 資料取自 [AniList](https://anilist.co) 的 GraphQL API，依人氣排序取前 500 名並排除成人內容；封面由 AniList 的 CDN 載入 |
| AI 工具總覽與套件 | 資料由人工整理自各服務官方網站與定價頁面，屬靜態快照，實際內容以官網為準；與各 AI 服務廠商無合作或背書關係 |
