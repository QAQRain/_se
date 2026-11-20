# offline-mirror 離線網站打包器

## 簡介

把指定網站抓下來，打包成本機可離線瀏覽的副本。

工具會用真實瀏覽器（Playwright 驅動系統 Edge）逐頁開啟目標網站，側錄頁面 HTML、
JavaScript、CSS、字型、圖片，以及前端程式呼叫的 JSON API 回應，再整理成一個
可直接開啟的靜態網站。適合需要 JavaScript 渲染、資料來自 API 的網站；
一般的多頁靜態網站也能處理。

抓取結果是「當下的快照」，之後原站更新不會自動同步，需要重新執行才會更新。

## 系統需求

- Windows 10 或 11
- Python 3.10 以上（需可執行 `python`）
- 瀏覽器：Microsoft Edge（預設使用系統 Edge）
- 網路：**抓取時需要**；瀏覽已打包的離線副本時不需要

若系統沒有 Edge，Playwright 會退回內建 Chromium，需先執行 `playwright install chromium`。

## 安裝方式

在本資料夾（`project/offline-mirror`）執行：

```
pip install -r requirements.txt
```

只有 `playwright` 一個相依套件，不需要 Node.js。

## 使用方式

### 網頁介面

雙擊 `start_ui.cmd`，會開啟一個標題為 `offline-mirror 介面` 的命令視窗，
並自動開啟介面：<http://127.0.0.1:9000>。

使用步驟：

1. 在「網站網址」輸入要抓的網址，例如 `https://example.com/`
2. 名稱可留空（會自動取網域），或自行指定
3. 需要時展開「進階選項」調整頁數上限、平行分頁、媒體下載與 include／exclude
4. 按「開始抓取並打包」
5. 完成後在「站台清單」按「開啟」，或直接按進度區的「開啟 <名稱>」

介面下方清單可以對既有站台執行「開啟」、「停止」、「更新」、「重建」。
介面連接埠預設 **9000**，要更換可手動啟動：

```
python webui.py --port 9010
```

### 命令列

三步驟：

```
python mirror.py crawl https://example.com/ --name example
python mirror.py build example
python mirror.py serve example --open
```

1. `crawl`：探索頁面並抓取，資料暫存在 `.cache/<名稱>/`
2. `build`：把快取打包到 `out/<名稱>/`
3. `serve`：啟動本機伺服器，預設網址 <http://127.0.0.1:8080>

連接埠預設 **8080**。要換連接埠可在啟動時指定：

```
python mirror.py serve example --port 8090
```

### 常用指令

| 指令 | 用途 |
| --- | --- |
| `python mirror.py run <網址> --name <名稱>` | 抓取後直接打包 |
| `python mirror.py crawl --name <名稱>` | 已有設定檔時，沿用設定重抓 |
| `python mirror.py update <名稱>` | 重新抓取並重建（已抓過的網址會跳過，並自動補圖） |
| `python mirror.py fill-images <名稱>` | 從既有快取補抓漏掉的圖片，不重抓頁面 |
| `python mirror.py list` | 列出所有站台 |
| `python mirror.py info <名稱>` | 顯示設定與建置資訊 |

### 抓取參數

| 參數 | 說明 |
| --- | --- |
| `--limit N` | 只抓前 N 頁，適合先確認流程 |
| `--max-pages N` | 頁數上限，預設 3000 |
| `--workers N` | 同時開啟的分頁數，預設 4 |
| `--delay 秒` | 每頁額外等待時間，預設 0.4 |
| `--wait 秒` | 頁面載入後等待非同步資料的時間，預設 2.0 |
| `--no-media` | 不下載圖片、影片、字型，體積更小 |
| `--include 正則` | 只抓符合的網址（可重複指定） |
| `--exclude 正則` | 排除符合的網址（可重複指定） |
| `--refresh` | 清掉舊快取重新抓（不能和 `--limit` 併用） |
| `--refresh-path 正則` | 只重抓符合的正則路徑，不清除其他快取（不能和 `--refresh` 併用） |

### 缺圖檢查與補圖

`build` 會比對 API 快照、HTML、CSS、JavaScript 引用的圖片是否都已打包，並在 `out/<名稱>/` 產生報表：

| 檔案 | 內容 |
| --- | --- |
| `missing-images.txt` | 同源但未打包的圖片，出現時代表副本可能破圖 |
| `external-images.txt` | 外部網域的圖片；要一併打包需把網域加入 `extra_hosts` 後重新抓取 |
| `failed-images.txt` | 補圖時下載失敗的網址 |

不重抓頁面也能補圖：

```
python mirror.py fill-images <名稱>
python mirror.py build <名稱>
```

`update` 會在抓取完成後自動補圖。

### 站台設定檔

第一次抓取會自動產生 `sites/<名稱>.json`，之後可直接編輯：

| 欄位 | 說明 |
| --- | --- |
| `start` | 起始網址 |
| `hosts` | 要抓的網域（同站自動加入） |
| `extra_hosts` | 額外的跨網域資源，例如 CDN 網域；會存到 `_ext/<網域>/` |
| `include` / `exclude` | 網址正則白名單／黑名單 |
| `api_prefixes` | 視為資料回應的網址前綴，預設 `/api/` |
| `max_pages` | 頁數上限 |
| `workers` / `delay` / `wait` | 抓取速度與等待時間 |
| `media` | 是否下載圖片、影片、字型 |
| `respect_robots` | 是否遵守 robots.txt，預設 `true` |
| `mode` | `auto`（自動偵測）、`spa`（未知路徑回首頁）、`static`（未知路徑回 404） |
| `port` | 預設連接埠 |
| `headless` / `channel` | 瀏覽器設定，`channel` 預設 `msedge` |

`sites/_template.json` 是空白範本，可複製後修改。

## 關閉方式

### 網頁介面

- 關掉標題為 `offline-mirror 介面` 的命令視窗（最快）
- 在該視窗按 `Ctrl + C`
- 雙擊 `stop_ui.cmd`：依連接埠 9000 找出程序並結束（其他連接埠：`stop_ui.cmd 9010`）

關閉介面時，由它啟動的離線副本也會一起停止。
確認已關閉：重新整理 <http://127.0.0.1:9000> 應顯示「無法連上這個網站」。

### 命令列

`serve` 在前景執行時，按 `Ctrl + C` 即可停止。

若使用輸出資料夾裡的 `start.cmd`，伺服器會跑在標題為 `offline-<名稱>` 的命令視窗，
關閉方式有三種：

- 直接關掉該視窗
- 在該視窗按 `Ctrl + C`，看到「已停止」後再關
- 雙擊 `out/<名稱>/stop.cmd`，依連接埠找出程序並結束

使用非預設連接埠時：`stop.cmd 8090`。

確認已關閉：重新整理 <http://127.0.0.1:8080> 應顯示「無法連上這個網站」，
或確認工作管理員沒有殘留的 `python.exe`。

## 檔案結構

```
project/offline-mirror/
  mirror.py                命令列入口
  webui.py                 本機網頁介面（輸入網址、看進度、開副本）
  ui/index.html            介面頁面（無外部資源，可離線使用）
  start_ui.cmd             雙擊啟動介面並開瀏覽器
  stop_ui.cmd              依連接埠停止介面
  mirrorlib/
    profile.py             站台設定檔讀寫與預設值
    discover.py            頁面探索（robots.txt、sitemap、連結廣度搜尋）
    capture.py             Playwright 擷取與快取
    build.py               打包、路徑改寫、注入離線腳本
    serve.py               serve 子命令
    standalone_serve.py    可獨立複製的本機伺服器
    util.py                MIME、雜湊、robots.txt 等共用工具
  sites/                   每個網站一份設定 JSON
  .cache/<名稱>/           原始快取（raw/ 與 meta.jsonl）
  out/<名稱>/              打包後的離線網站
  requirements.txt
```

`out/<名稱>/` 會包含：

```
index.html          進入點，已插入離線腳本
offline-data.js     API 回應快照與 WebSocket 訊息記錄
offline-shim.js     攔截 fetch／XHR 的 GET／POST 請求
manifest.json       來源、建置時間、頁數、模式、連接埠
missing-images.txt  同源缺圖清單（僅在有缺漏時產生）
external-images.txt 外部網域圖片清單（僅在未打包的外部資源時產生）
failed-images.txt   補圖失敗清單（僅在失敗時產生）
_serve.py           本機伺服器（只用標準函式庫）
start.cmd           一鍵啟動並開啟瀏覽器
stop.cmd            一鍵停止
README.md           該副本的使用說明
```

整個 `out/<名稱>/` 可以直接複製到其他電腦使用，只要有 Python 就能啟動。

## 功能說明

- 網頁介面：輸入網址即可抓取，即時顯示進度與日誌，完成後一鍵開啟離線副本
- 介面可管理既有站台：開啟、停止、更新、重建、補圖，以及編輯抓取設定與刪除設定
- 同一時間只執行一個抓取或打包工作，避免互相覆寫
- 頁面探索順序：`robots.txt` 的 Sitemap → `/sitemap.xml`（支援 sitemapindex）→ 首頁連結廣度搜尋
- 以系統 Edge 的 headless 模式開啟頁面，取得 JavaScript 渲染後的內容
- 側錄同網域的所有回應，依 `content-type` 分類為頁面、資料或資源
- 包含 POST 在內的 API 回應統一輸出成 `offline-data.js`，由 `offline-shim.js` 在瀏覽器端攔截
- 從 API、HTML、CSS、JavaScript 收集圖片網址並補抓，涵蓋延遲載入與背景圖
- 遇到分頁按鈕會自動點擊，補抓後續頁面的資料
- 打包時檢查圖片是否齊全，輸出缺圖、外部網域與下載失敗清單
- 跨網域資源（CDN 圖片、字型）可透過 `extra_hosts` 一併下載並改寫路徑
- 支援續抓：中斷後重跑會跳過已抓過的網址
- 遵守 `robots.txt`、固定延遲、頁數上限，避免對目標站造成負擔
- WebSocket 收到的訊息會記錄在 `offline-data.js` 的 `__websocket` 欄位，供事後查閱
- 每個副本自帶伺服器、啟動與停止腳本、說明文件

## 資料來源與授權

本工具只負責抓取，不做內容審查。被抓取網站的內容著作權屬各站原作者所有。

使用前請確認目標網站的服務條款與 `robots.txt`，並只用於個人離線查閱；
請勿公開散布、重新上傳或作為商業用途。原作者要求移除時應立即刪除對應的
`.cache/` 與 `out/` 資料夾。

## 已知限制

- 需要登入才看得到的內容抓不到，工具不會繞過任何驗證
- 需要 PUT／DELETE 等寫入操作的 API 無法離線運作
- WebSocket 只記錄訊息內容，不會模擬即時連線；SSE（伺服器推送）不支援
- 跨網域資源必須明列在 `extra_hosts`，否則會缺圖或缺字型
- 不支援 `file://` 直接開啟，一定要透過本機伺服器（SPA 與 API 攔截需要 HTTP）
- SPA 模式只保留首頁快照，深層頁面由前端路由搭配 `offline-data.js` 產生；
  若某頁資料需要點擊後才載入，可能顯示空白
- 大量圖片與影片會佔用可觀空間，可用 `--no-media` 降低體積
- 介面只綁定 `127.0.0.1`，不對外開放；同一時間只執行一個抓取或打包工作
- 若主控台中文顯示亂碼，可在指令前加 `python -X utf8`
