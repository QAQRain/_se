# Docker 學習筆記

## Docker 是什麼
Docker 是一個容器化平台，利用「容器」（Container）將應用程式及其執行環境打包在一起，達到「在這台電腦能跑，到別台電腦也能跑」的目的。

## Image（映像） vs Container（容器）
- **Image（映像）**：唯讀的模板，用來定義容器裡應該有哪些檔案、套件、環境設定。
- **Container（容器）**：根據 Image 建立的執行實體，可以讀寫，但離開後若沒保存資料就會消失。
- 類比：Image 像食譜，Container 像照著食譜做出來的菜。

## 怎麼使用 Docker（常用指令）
| 指令 | 用途 | 範例 |
|---|---|---|
| `docker --version` | 確認 Docker 是否安裝成功 | `docker --version` |
| `docker pull <image>` | 從 Docker Hub 或其他 registry 拉取映像 | `docker pull alpine:latest` |
| `docker images` | 列出本機已下載的映像 | `docker images` |
| `docker run [選項] <image> [指令]` | 根據映像啟動一個容器 | `docker run --rm -it alpine sh` |
| `docker ps` | 顯示目前正在執行的容器 | `docker ps` |
| `docker ps -a` | 顯示所有容器（包含已停止的） | `docker ps -a` |
| `docker exec -it <container> <指令>` | 進入已在執行中的容器內執行指令 | `docker exec -it abc123 sh` |
| `docker stop <container>` | 停止執行中的容器 | `docker stop abc123` |
| `docker rm <container>` | 刪除容器（需先停止或加 `-f`） | `docker rm abc123` |
| `docker build -t <名稱> .` | 從 Dockerfile 建立自訂映像 | `docker build -t my-app .` |
| `docker compose up --build` | 建置並啟動 compose 內所有服務 | `docker compose up --build` |
| `docker compose down` | 停止並移除 compose 內所有容器與網路 | `docker compose down` |

## 實際應用：透過 Docker 使用 OpenCode

在本次練習中，我是透過 Docker 的 `--rm` 類型容器來使用 OpenCode，簡單的方式如下：

```bash
docker run --rm -it -v "$(pwd)":/workspace -w /workspace ghcr.io/anomalyco/opencode:latest
```

簡短說明：
- `--rm`：容器執行結束後自動刪除，保持環境乾淨。
- `-it`：以互動式終端啟動。
- `-v "$(pwd)":/workspace`：將目前資料夾掛載到容器的 `/workspace`，讓主機與容器的檔案即時同步。
- `-w /workspace`：設定容器內的工作目錄為 `/workspace`。
- `ghcr.io/anomalyco/opencode:latest`：直接使用現成的映像來執行。

> 本次繳交的內容主要集中在 `schooluse/docker_project/`，因此不列出原始 Windows `.bat` 的完整細節。

## Dockerfile 是做什麼的？
Dockerfile 是一個純文字檔，用來**定義如何從既有的 Image 建立一個自訂的 Image**。

簡單來說：
- **目的**：自動化建置映像（不用每次手動進入容器一行一行安裝）。
- **差別**：`Dockerfile` = 製作食譜；`Image` = 煮好的成品；`docker build` 用食譜做出成品；`docker run` 用成品啟動容器。

常見指令（簡短）：
- `FROM`：指定基底映像（例如 `alpine:latest`、`node:20`）
- `RUN`：建置 Image 時執行的指令（安裝套件、設定環境）
- `COPY`：把主機檔案複製到 Image 內
- `WORKDIR`：設定工作目錄
- `CMD`：容器啟動時預設要執行的指令

## 總結
- 用現成的 Image（像本專案用的 `ghcr.io/anomalyco/opencode:latest`）就能直接 `docker run` 啟動容器來使用工具。
- 想客製化環境時，就寫個 `Dockerfile`，用 `docker build` 產生自己的 Image，再用 `docker run` 執行。

## SASforDocker_project（Docker 微服務版）

路徑：`schooluse/docker_project/SASforDocker_project/`

此目錄是將原始 SAS 校務行政系統改造成「nginx + PostgreSQL + Node.js + Rust + Python」微服務架構的練習專案。

重點檔案：
- `docker-compose.yml`：多服務編排（僅對外暴露 80）
- `Dockerfile`：Flask + gunicorn
- `nginx/`：Web Server + Reverse Proxy（`/api/*` 轉發）
- `services/api-node/`、`services/api-rust/`、`services/api-python/`：各自獨立映像的極簡 API
- `db/init.sql`：PostgreSQL 初始化
- `templates/index.html`：新增「Docker 微服務系統狀態」展示區塊
- `README-DOCKER.md`：啟動方式與架構說明

啟動方式（移到 VSCode 後執行）：
```bash
cd schooluse/docker_project/SASforDocker_project
docker compose up --build
```
完成後開啟 `http://localhost` 查看系統狀態。

## 實作練習：用 Docker 建置微服務系統（SASforDocker_project）

為了實際學會 Docker 的用法，這裡也做了一個簡短練習：

- **目標**：學會用 `Dockerfile` 建立映像，以及用 `docker-compose.yml` 編排多個容器（微服務）。
- **練習專案**：`schooluse/docker_project/SASforDocker_project/`
- **架構**：`nginx`（Web Server + Reverse Proxy）＋ `PostgreSQL`＋ `Flask（SAS）`＋ `Node.js API`＋ `Rust API`＋ `Python API`，每個服務各自一個映像。
- **展示**：在 SAS 首頁新增「Docker 微服務系統狀態」區塊，透過 `/api/*` 檢查各 API 及 PostgreSQL 是否正常運作。
- **重點概念**：`docker build`（用 Dockerfile 製作映像）、`docker run`（用映像啟動容器）、`docker compose up --build`（一次建置並啟動全部服務）、多容器間用服務名稱（如 `postgres`）作為主機名稱溝通、volume 用於資料持久化。

**最簡啟動：**
```bash
cd schooluse/docker_project/SASforDocker_project
docker compose up --build
```

**檢查：** 打開瀏覽器 `http://localhost`，查看頁面下方的狀態是否全部顯示 OK。

**關閉系統：**
```bash
# 停止並移除所有容器與網路（Postgres 資料會保留）
docker compose down

# 連同資料 volume 一起清除
docker compose down -v
```

> 在 `docker compose up` 的前台畫面按 `Ctrl+C` 只是中斷日誌，容器可能仍在背景執行，還是要用 `docker compose down` 才能真正關閉。可用 `docker compose ps` 確認是否已全部關閉。

> 補充：`Dockerfile` 是「建置映像的食譜」，`docker-compose.yml` 則是「統一管理多個容器怎麼跑」的編排檔。

## 繳交檔案與架構

### 繳交檔案清單（位於 `SASforDocker_project/`）

| 檔案 / 資料夾 | 說明 |
| --- | --- |
| `docker-compose.yml` | **必要**：多服務編排 |
| `Dockerfile` | **必要**：Flask（SAS）映像，用 gunicorn 執行 |
| `services/api-node/Dockerfile` | Node.js 映像（Express API） |
| `services/api-rust/Dockerfile` | Rust 映像（Axum API，多階段建置） |
| `services/api-python/Dockerfile` | Python 映像（FastAPI API） |
| `nginx/Dockerfile`、`nginx/nginx.conf` | Nginx 映像與反向代理設定 |
| `db/init.sql` | PostgreSQL 初始化腳本 |
| `requirements.txt` | Flask 相關相依套件 |
| `app.py`、`db.py`、`seed.py`、`schema.sql`、`static/`、`templates/` | SAS 應用本體 |
| `.dockerignore` | 建置時排除不必要的檔案 |
| `README-DOCKER.md` | 本專案的 Docker 說明 |

### 架構圖

```text
                    瀏覽器 http://localhost
                            │
                            ▼
                    ┌───────────────┐
                    │  nginx (80)   │  Web Server + Reverse Proxy
                    └───────┬───────┘
        ┌───────────────┬───┴────────┬───────────────┐
        ▼               ▼            ▼               ▼
   / (Flask)      /api/node/*   /api/rust/*    /api/python/*
   web:5000       api-node:3000 api-rust:8080  api-python:8000
        │               │            │               │
        └───────────────┴────────────┴───────────────┘
                            │  (Docker 內部網路 sasnet)
                            ▼
                    ┌───────────────┐
                    │ postgres:5432 │  PostgreSQL
                    └───────────────┘
```

六個服務各自獨立映像：`nginx`、`web`(Flask)、`api-node`、`api-rust`、`api-python`、`postgres`。
