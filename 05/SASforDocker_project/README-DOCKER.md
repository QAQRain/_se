# SASforDocker_project（Docker 微服務版）

此專案將原本的 SAS 校務行政系統改造成可透過 Docker 執行的微服務系統。

## 目標
- 使用 Docker 建置微服務
- 具備：nginx（Web Server + Reverse Proxy）、PostgreSQL（資料庫）
- 開發執行環境：Node.js、Rust、Python
- 最終有一個簡易 Web 介面（沿用 SAS 頁面），展示 Docker 系統各服務狀態

## 目錄結構（重點）
```
SASforDocker_project/
├── Dockerfile                # Flask（SAS）Dockerfile（使用 gunicorn）
├── docker-compose.yml        # 多服務編排
├── requirements.txt          # Flask 相關套件
├── app.py                    # SAS 主程式（保留原始邏輯）
├── db.py / schema.sql / seed.py / data/ / static/ / templates/
├── db/
│   └── init.sql              # PostgreSQL 初始化（health_check 測試表）
├── nginx/
│   ├── Dockerfile
│   └── nginx.conf             # 反向代理設定（/api/* 導向對應服務）
├── services/
│   ├── api-node/             # Node.js（Express）極簡 API
│   ├── api-rust/             # Rust（Axum）極簡 API（multi-stage build）
│   └── api-python/           # Python（FastAPI）極簡 API
└── README-DOCKER.md
```

## 系統架構
瀏覽器（http://localhost）→ nginx（port 80）
- `/` 代理到 `web:5000`（Flask SAS）
- `/api/node/*` 代理到 `api-node:3000`
- `/api/rust/*` 代理到 `api-rust:8080`
- `/api/python/*` 代理到 `api-python:8000`
各 API 透過內部網路連接 PostgreSQL（`postgres:5432`）。

## 啟動方式（在 VSCode 或含 Docker 環境下執行）
1. 進入專案目錄
   ```bash
   cd schooluse/docker_project/SASforDocker_project
   ```
2. 建置並啟動所有服務
   ```bash
   docker compose up --build
   ```
3. 開啟瀏覽器
   ```text
   http://localhost
   ```
   登入可用 demo 帳號（參考 app.py 註解）：admin/admin123 等。
   首頁下方會有「Docker 微服務系統狀態」區塊，會自動呼叫各 API 的 /health、/db 顯示 OK/FAIL。

## 驗證步驟
1. 確認全部容器在執行（6 個服務應全為 `running`）
   ```bash
   docker compose ps
   ```
2. 瀏覽器開啟 `http://localhost`，能出現 SAS 登入頁 → nginx + web 正常。
3. 首頁下方「Docker 微服務系統狀態」的 Health / DB 全部顯示綠色 OK → 系統完成。
4. 若某項顯示 FAIL，單獨查該服務日誌：
   ```bash
   docker compose logs api-rust --tail=30
   ```
   （`api-rust` 換成出問題的服務名稱，如 `api-node`、`api-python`、`postgres`）
5. 小提醒：Postgres 啟動需要幾秒，若剛開頁面 DB 顯示 FAIL，稍等幾秒按「重新檢查」即可。

## 停止與清除
```bash
# 停止並移除容器、網路
docker compose down

# 停止並移除容器、網路、volume（清除 Postgres 資料）
docker compose down -v
```

## 每個服務一個映像（符合微服務要求）
- web（Flask + gunicorn）
- api-node（Node.js）
- api-rust（Rust，多階段建置）
- api-python（Python）
- nginx（web server + reverse proxy）
- postgres（官方映像）

## 實作注意事項
- **web 使用單一 gunicorn worker（`-w 1`）**：`seed.py` 首次啟動會先刪除再重建 SQLite 檔，若用多個 worker，會有多個行程同時初始化而互相刪檔，導致 `sqlite3.OperationalError: disk I/O error` 或 `no such table`。因此改為單一 worker，確保初始化只發生一次。
- **Rust 映像使用多階段建置（multi-stage build）**：第一階段用 `rust:1.88-alpine` 編譯出 release binary，第二階段只複製 binary 到 `alpine`，縮小最終映像。
  - 注意：Rust builder 版本需 ≥ 1.85，否則相依套件（需要 `edition2024`）會編譯失敗。
- **PostgreSQL 資料持久化**：透過 `docker-compose.yml` 的 named volume `pgdata`，`docker compose down` 不會清除，需 `down -v`。
- **只對外開放 80 埠**：各 API 與 Postgres 僅在 Docker 內部網路（`sasnet`）互通，不直接對外暴露。
- **`.dockerignore`**：排除 `__pycache__/`、`data/`、`*.md` 等，避免垃圾被打包進映像。

## 展示重點
首頁新增的「Docker 微服務系統狀態」區塊會同時檢查：
- Node.js API：/api/node/health、/api/node/db
- Rust API：/api/rust/health、/api/rust/db
- Python API：/api/python/health、/api/python/db

若全部顯示 OK，代表 nginx、PostgreSQL、三個開發執行環境（Node.js/Rust/Python）皆正常運作。
