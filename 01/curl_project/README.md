# mycurl

一個用 Python 寫的、類似 curl 的 HTTP 客戶端命令列工具。可以發送 HTTP 請求、抓取網頁、測試 API。

- 純 Python，不需安裝額外系統套件
- CLI 參數刻意模仿 curl，學習成本低
- 支援 GET / POST / PUT / DELETE / HEAD / PATCH

## 內容

- [需求](#需求)
- [安裝](#安裝)
- [快速開始](#快速開始)
- [完整參數](#完整參數)
- [範例](#範例)
- [與 curl 對照](#與-curl-對照)
- [測試用免費 API](#測試用免費-api)
- [專案結構](#專案結構)

## 需求

- Python 3.7+
- `requests` 套件（於安裝步驟自動安裝）

## 安裝

```bash
pip install -r requirements.txt
```

若沒有 Python，請先至 [python.org](https://www.python.org/downloads/) 安裝（勾選 *Add Python to PATH*，Windows)。

## 快速開始

```bash
# 基本 GET，抓取網頁內容
python mycurl.py https://example.com/

# 送出 POST 表單資料
python mycurl.py -X POST -d "name=小明&age=18" https://httpbin.org/post

# 送出 JSON 並帶自訂 header
python mycurl.py -X POST -j -d '{"name": "小明"}' -H "Authorization: Bearer abc123" https://httpbin.org/post

# 顯示 response header
python mycurl.py -i https://example.com/

# 把內容存成檔案（等同 curl -o）
python mycurl.py -o index.html https://example.com/
```

## 完整參數

```
usage: mycurl [-h] [-X METHOD] [-H HEADERS] [-d DATA] [-j] [-i] [-o OUTPUT]
              [-s] [-t TIMEOUT]
              url
```

| 參數 | 說明 | 預設值 |
|------|------|--------|
| `url` | 要請求的 URL（可省略 `http://` / `https://`，會自動補上） | 必填 |
| `-X, --request` | HTTP 方法：GET / POST / PUT / DELETE / HEAD / PATCH | `GET` |
| `-H, --header` | 自訂 header，格式 `"名稱: 值"`，可重複使用 | 無 |
| `-d, --data` | 要送出的資料（表單格式或 JSON 字串） | 無 |
| `-j, --json` | 把 `-d` 的資料當 JSON 送出 | 關閉 |
| `-i, --include-headers` | 輸出時一併顯示 response header | 關閉 |
| `-o, --output` | 把 response body 存到指定檔案 | 無（印到螢幕） |
| `-s, --silent` | 靜默模式，只輸出必要內容與錯誤 | 關閉 |
| `-t, --timeout` | 連線逾時秒數 | `10` |

## 範例

### GET 抓取網頁
```bash
python mycurl.py https://httpbin.org/get
```

### 指定 HTTP 方法
```bash
python mycurl.py -X DELETE https://httpbin.org/delete
```

### 帶自訂 header（可多次使用）
```bash
python mycurl.py -H "Content-Type: application/json" -H "Authorization: Bearer 123" https://httpbin.org/anything
```

### 送出 JSON 資料
```bash
python mycurl.py -X POST -j -d '{"name": "小明", "age": 18}' https://httpbin.org/post
```

### 顯示 response 狀態與 header
```bash
python mycurl.py -i https://example.com/
```
輸出會先顯示 `[狀態碼]` 與 `[耗時]`，接著是所有 response header，最後是 body。

### 儲存成檔案
```bash
python mycurl.py -o page.html https://example.com/
```

### 錯誤處理
連線失敗或逾時時，程式會印出錯誤訊息並回傳非零結束碼（方便在 shell 判斷失敗）：
```bash
python mycurl.py https://不存在的網域.com/
# [錯誤] 無法完成請求: ...
```

## 與 curl 對照

| 功能 | 本工具 | curl |
|------|--------|------|
| GET 請求 | `python mycurl.py URL` | `curl URL` |
| 指定方法 | `-X POST` | `-X POST` |
| 自訂 header | `-H "K: v"` | `-H "K: v"` |
| 送出資料 | `-d "a=b"` | `-d "a=b"` |
| JSON 資料 | `-j` | `-H "Content-Type: application/json"` + `-d '{"..":..}'` |
| 顯示 header | `-i` | `-i` |
| 存成檔案 | `-o 檔名` | `-o 檔名` |
| 靜默模式 | `-s` | `-s` |
| 逾時設定 | `-t 秒` | `--max-time 秒` |

## 測試用免費 API

| URL | 用途 |
|-----|------|
| `https://httpbin.org/anything` | 原樣回傳你送的請求（方法、header、資料），最適合除錯 |
| `https://httpbin.org/get` | 回傳 GET 請求資訊 |
| `https://httpbin.org/post` | 回傳 POST 請求資訊 |
| `https://example.com/` | 標準測試網頁 |

## 專案結構

```
curl_project/
├── mycurl.py          # 主程式（命令列工具本體）
├── requirements.txt   # 依賴套件
└── README.md          # 本說明文件
```

---

專案為課程專題「製作類似 curl 的命令列工具」，以 Python 實作，透過 CLI 參數涵蓋 HTTP 請求的常用操作。