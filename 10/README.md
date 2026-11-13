# AI 工具總覽：`@qaqrain/ai-catalog`

一份把主流 AI 服務整理成結構化資料的 npm 套件，同時附上可直接瀏覽的靜態網站。
資料涵蓋 52 個服務，記錄每個服務能做什麼、支援哪些輸入、免費額度有多少。

程式與資料都在同層的 `ai-catalog/` 資料夾，本文件只做介紹。

| 項目 | 連結 |
| --- | --- |
| 網站 | <https://ai-catalog.qaqrain.workers.dev/> |
| npm 套件 | <https://www.npmjs.com/package/@qaqrain/ai-catalog> |
| 原始碼 | <https://github.com/QAQRain/ai-catalog/> |
| CDN（JSON） | <https://cdn.jsdelivr.net/npm/@qaqrain/ai-catalog@1/data.json> |

## 一、這個套件提供什麼

1. **結構化資料**：52 筆 AI 服務，包含分類、能力標記、免費額度，中英雙語。
2. **JavaScript 介面**：`items`、`byCategory()`、`search()`、`getById()`，附 TypeScript 型別。
3. **原始 JSON**：`data.json` 可直接下載或經 CDN 取用，不限語言。
4. **現成網站**：`public/` 內含完整靜態網站，下載後雙擊即可開啟。

專案沒有後端、沒有資料庫、執行時零依賴。

## 二、安裝

```powershell
npm install @qaqrain/ai-catalog
```

若只是要看網站或抓資料，不需要安裝任何東西。

## 三、使用範例

### 1. 匯入資料

```js
import catalog, { items, updated, byCategory, search, getById } from "@qaqrain/ai-catalog";

console.log(updated);              // 資料快照日期，例如 "2026-11-06"
console.log(items.length);         // 52

const chatTools = byCategory("chat");
const freeTools = items.filter((it) => it.free === "yes");
const found = search("語音", "zh");
const chatgpt = getById("chatgpt");

console.log(catalog.items === items); // true
```

### 2. 直接取用 JSON（不安裝）

```js
const res = await fetch("https://cdn.jsdelivr.net/npm/@qaqrain/ai-catalog@1/data.json");
const { updated, items } = await res.json();

const freeImageTools = items.filter((it) => it.caps.image && it.free !== "no");
```

### 3. 自己架網站

把 `ai-catalog/public/` 整個資料夾複製出來，雙擊 `index.html` 即可；
或使用專案附的預覽伺服器：

```powershell
npm run preview
```

啟動後開 <http://localhost:8787/>，按 `Ctrl+C` 結束。

## 四、資料格式

`data.json` 的結構：

```json
{
  "updated": "2026-11-06",
  "items": [
    {
      "id": "chatgpt",
      "name": "ChatGPT",
      "vendor": "OpenAI",
      "cat": "chat",
      "url": "https://chatgpt.com",
      "desc": { "zh": "…", "en": "…" },
      "free": "limited",
      "quota": { "zh": "…", "en": "…" },
      "caps": { "vision": true, "image": true, "video": false, "audio": true, "code": true }
    }
  ]
}
```

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `id` | string | 唯一識別碼，全小寫 |
| `name` | string | 服務名稱 |
| `vendor` | string | 提供廠商 |
| `cat` | string | 分類，見下表 |
| `url` | string | 官方網站 |
| `desc` | object | 一句話說明，`zh` / `en` 各一 |
| `free` | string | `yes`（完全免費）、`limited`（部分免費）、`no`（需付費） |
| `quota` | object | 免費額度說明，`zh` / `en` 各一 |
| `caps` | object | 能力標記：`vision`、`image`、`video`、`audio`、`code`，值為布林 |

分類共九種：

| 代號 | 意義 | 代號 | 意義 |
| --- | --- | --- | --- |
| `chat` | 對話 | `search` | 搜尋 |
| `image` | 圖像 | `agent` | 代理 |
| `video` | 影片 | `local` | 本機執行 |
| `audio` | 音樂語音 | `platform` | 綜合平台 |
| `code` | 程式 | | |

## 五、專案結構

```
ai-catalog/
├── data.json             資料唯一來源
├── data.mjs              由 data.json 產生的 ESM 資料檔
├── index.js              套件入口
├── index.d.ts            TypeScript 型別
├── scripts/
│   ├── build-data.mjs    由 data.json 產生 data.mjs 與 public/data.js
│   └── serve.mjs         本機預覽伺服器
├── public/               網站本體（index.html、style.css、app.js、data.js）
├── wrangler.jsonc        Cloudflare Workers 設定
├── LICENSE               程式碼授權（MIT）
└── LICENSE-DATA          資料授權（CC0 1.0）
```

## 六、開發流程

```powershell
npm run build          # 由 data.json 重新產生 data.mjs 與 public/data.js
npm run preview        # 本機預覽，http://localhost:8787/
npm publish            # 發佈新版本
```

`data.mjs` 與 `public/data.js` 都是產生檔，修改資料只需編輯 `data.json`，再執行 `npm run build`。

## 七、網站功能

- 卡片與比較表兩種檢視
- 中英雙語介面與說明
- 關鍵字搜尋名稱、廠商、功能
- 分類篩選、只顯示免費
- 五種能力標記（看圖、生圖、生影片、語音、寫程式）
- 深色模式、手機版

## 八、資料來源

資料由作者人工整理自各服務官方網站與定價頁面，為靜態快照。
免費額度與功能會隨官方政策變動，實際情況以各服務官網為準。
本專案與任何 AI 服務廠商無合作或背書關係。

## 九、授權

- 程式碼（`index.js`、`scripts/`、`public/` 內的 HTML / CSS / JS）：MIT。
- 資料（`data.json` 內容）：CC0 1.0 通用，屬於公共領域，可自由使用、修改、商業使用，不需標註來源。
- 各 AI 服務的名稱與商標仍屬各廠商所有。

## 十、版本

| 版本 | 日期 | 內容 |
| --- | --- | --- |
| 1.0.0 | 2026-11-13 | 首次發佈：52 筆資料、套件入口、型別、靜態網站 |
