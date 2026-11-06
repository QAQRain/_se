# AI 工具總覽

把主流 AI 服務整理成一份可搜尋、可比較的清單：能做什麼、支援哪些輸入、免費額度有多少，一次看完。

**網站：<https://ai-catalog.qaqrain.workers.dev/>**
**專案位址：<https://github.com/QAQRain/ai-catalog/>**

## 功能

- **卡片 / 比較表**兩種檢視，可切換
- **中英雙語**介面，含每一筆的說明
- **搜尋**名稱、廠商、功能關鍵字
- **分類篩選**：對話、圖像、影片、音樂語音、程式、搜尋、代理、本機、平台
- **只顯示免費**，並標示看圖／生圖／生影片／語音／寫程式五種能力
- 深色模式、手機版

目前收錄 52 個服務。

## 技術

純 HTML / CSS / JavaScript，沒有框架、沒有 `npm install`、沒有建置流程，也沒有後端。
資料寫在 `public/data.js`，由 Cloudflare Workers 托管靜態檔案。

```
ai-catalog/
├── public/           網站本體（index.html、style.css、app.js、data.js）
├── wrangler.jsonc    Cloudflare 設定
└── README.md
```

## 本機預覽

直接雙擊 `public/index.html`。

## 部署

```powershell
npm install -g wrangler
wrangler login
wrangler deploy
```

或在 Cloudflare 後台接上 GitHub repo，之後 push 就自動部署。

## 更新資料

打開 `public/data.js`，照現有格式加一筆即可，`id` 不重複、`cat` 用下面九種之一：

`chat` `image` `video` `audio` `code` `search` `agent` `local` `platform`

免費額度會隨官方政策變動，資料為人工整理的靜態快照，實際以各服務官網為準。
