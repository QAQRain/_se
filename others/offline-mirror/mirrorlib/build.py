"""把快取打包成可離線瀏覽的網站。"""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse

from . import util
from .profile import cache_dir, out_dir

SHIM = r"""/* 離線副本：攔截同源 API 的 GET／POST 請求，改回傳 offline-data.js 內嵌的快照 */
(function () {
  var DATA = window.__OFFLINE_DATA__ || {};
  var origFetch = window.fetch ? window.fetch.bind(window) : null;

  function norm(u) {
    try {
      var x = new URL(u, location.href);
      if (x.origin !== location.origin) return null;
      return { full: x.pathname + x.search, path: x.pathname };
    } catch (e) {
      return null;
    }
  }

  function lookup(u, method) {
    var k = norm(u);
    if (!k) return undefined;
    var m = String(method || 'GET').toUpperCase();
    var p = m === 'GET' ? '' : m + ' ';
    if (Object.prototype.hasOwnProperty.call(DATA, p + k.full)) return DATA[p + k.full];
    if (Object.prototype.hasOwnProperty.call(DATA, p + k.path)) return DATA[p + k.path];
    var bp = DATA.__byPath || {};
    if (Object.prototype.hasOwnProperty.call(bp, p + k.path)) return DATA[bp[p + k.path]];
    return undefined;
  }

  if (origFetch) {
    window.fetch = function (input, init) {
      var url = typeof input === 'string' ? input : (input && input.url) || '';
      var method = (init && init.method) || (input && input.method) || 'GET';
      var hit = lookup(url, method);
      if (hit !== undefined) {
        return Promise.resolve(new Response(JSON.stringify(hit), {
          status: 200,
          headers: { 'Content-Type': 'application/json; charset=utf-8' }
        }));
      }
      console.warn('OFFLINE_MISS ' + url);
      return origFetch(input, init);
    };
  }

  var OrigXHR = window.XMLHttpRequest;
  function PatchedXHR() {
    var xhr = new OrigXHR();
    var mocked = false;
    var payload = null;

    var openOrig = xhr.open;
    xhr.open = function (method, url) {
      var hit = lookup(url, method);
      if (hit !== undefined) {
        mocked = true;
        payload = hit;
        return;
      }
      mocked = false;
      return openOrig.apply(xhr, arguments);
    };

    var setHeaderOrig = xhr.setRequestHeader;
    xhr.setRequestHeader = function () {
      if (mocked) return;
      return setHeaderOrig.apply(xhr, arguments);
    };

    var sendOrig = xhr.send;
    xhr.send = function () {
      if (mocked) {
        var blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
        var blobUrl = URL.createObjectURL(blob);
        var rt = xhr.responseType;
        openOrig.call(xhr, 'GET', blobUrl, true);
        try { if (rt) xhr.responseType = rt; } catch (e) {}
        xhr.addEventListener('loadend', function () { URL.revokeObjectURL(blobUrl); });
        return sendOrig.call(xhr);
      }
      return sendOrig.apply(xhr, arguments);
    };

    return xhr;
  }
  PatchedXHR.prototype = OrigXHR.prototype;
  window.XMLHttpRequest = PatchedXHR;
})();
"""

INJECT = ('<script src="/offline-data.js"></script>\n    '
          '<script src="/offline-shim.js"></script>\n')

SPA_MARKERS = (
    'id="app"', "id='app'", 'id="root"', "id='root'",
    'id="__nuxt"', "data-v-app", "__NEXT_DATA__", "__NUXT__",
)


def _entries(name: str) -> list[dict]:
    meta = cache_dir(name) / "meta.jsonl"
    if not meta.exists():
        return []
    items: list[dict] = []
    for line in meta.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("url") and item.get("file"):
            items.append(item)
    return items


def _raw_path(name: str, item: dict) -> Path:
    return cache_dir(name) / "raw" / item["file"]


def _read_text(name: str, item: dict) -> str:
    path = _raw_path(name, item)
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _read_json(name: str, item: dict):
    path = _raw_path(name, item)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _page_rel(path: str) -> str:
    path = path or "/"
    if path.endswith("/"):
        return path.lstrip("/") + "index.html"
    if Path(path).suffix:
        return path.lstrip("/")
    return path.lstrip("/") + "/index.html"


def _asset_rel(item: dict) -> str:
    path = item.get("path") or "/"
    ext = util.guess_ext(item["url"], item.get("ct", ""))
    if path != "/" and not Path(path).suffix:
        path = path + ext
    rel = path.lstrip("/")
    if item.get("host_extra"):
        rel = f"_ext/{item['host']}/{rel}"
    return rel


IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico", ".avif"}
_CSS_URL_RE = re.compile(r"url\(\s*['\"]?([^'\")\s]+)", re.I)
_HTML_SRC_RE = re.compile(r"(?:src|data-src|data-lazy-src|data-original|poster)=[\"']([^\"']+)[\"']", re.I)
_JS_IMG_RE = re.compile(r"['\"](/[^'\"\s]+\.(?:png|jpg|jpeg|webp|gif|svg|ico|avif)(?:\?[^'\"\s]*)?)['\"]", re.I)


def _add_ref(text, out: set) -> None:
    """把一個可能的圖片網址正規化成 (host, path) 加入集合。"""
    text = (text or "").strip()
    if not text or text.startswith(("data:", "blob:", "javascript:", "#")):
        return
    if not (text.startswith("/") or re.match(r"^https?://", text, re.I)):
        return
    low = text.split("?")[0].split("#")[0].lower()
    if not any(low.endswith(ext) for ext in IMG_EXT):
        return
    parsed = urlparse(text)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        out.add((util.host_key(parsed.netloc), parsed.path))
    elif text.startswith("/"):
        out.add((None, parsed.path))


def _collect_image_refs(obj, out: set, depth: int = 0) -> None:
    """遞迴收集 JSON 中的圖片網址，正規化成 (host, path)。"""
    if depth > 12:
        return
    if isinstance(obj, str):
        _add_ref(obj, out)
    elif isinstance(obj, dict):
        for value in obj.values():
            _collect_image_refs(value, out, depth + 1)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            _collect_image_refs(value, out, depth + 1)


def _rewrite_hosts(text: str, extra_hosts: list[str]) -> str:
    for host in extra_hosts:
        if not host:
            continue
        text = text.replace(f"https://{host}", f"/_ext/{host}")
        text = text.replace(f"http://{host}", f"/_ext/{host}")
        text = text.replace(f"//{host}", f"/_ext/{host}")
    return text


_STATIC_OVERLAY_RE = re.compile(r'<div\b[^>]*\bclass="[^"]*\bel-overlay\b[^"]*"[^>]*>')


def _strip_static_overlays(html: str) -> str:
    """移除抓取當下已展開的對話框，避免與 Vue 掛載後產生的重疊而擋住點擊。"""
    out = html
    seen = 0
    while seen < 100:
        match = _STATIC_OVERLAY_RE.search(out)
        if not match:
            break
        start = match.start()
        depth = 1
        pos = match.end()
        tag_re = re.compile(r"<(/?)div\b[^>]*>", re.I)
        while depth > 0:
            tag = tag_re.search(out, pos)
            if not tag:
                break
            depth += -1 if tag.group(1) else 1
            pos = tag.end()
        if depth != 0:
            break
        out = out[:start] + out[pos:]
        seen += 1
    # 抓取當下因彈窗而鎖住捲動；Vue 掛載後會自行管理，先移除避免干擾。
    out = out.replace('class="el-popup-parent--hidden"', 'class=""', 1)
    return out


def _inject(html: str) -> str:
    html = _strip_static_overlays(html)
    if "offline-shim.js" in html:
        return html
    index = html.lower().rfind("</head>")
    if index >= 0:
        return html[:index] + INJECT + html[index:]
    return INJECT + html


def _detect_mode(profile: dict, root_html: str) -> str:
    mode = (profile.get("mode") or "auto").lower()
    if mode in ("spa", "static"):
        return mode
    low = (root_html or "").lower()
    return "spa" if any(marker in low for marker in SPA_MARKERS) else "static"


def _write_cmd_files(site: Path, name: str, port: int) -> None:
    start = f"""@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if not exist _serve.py goto nofile
start "offline-{name}" cmd /k python _serve.py {port}
ping -n 4 127.0.0.1 >nul
start "" http://127.0.0.1:{port}
exit /b 0
:nofile
echo 找不到 _serve.py，請確認檔案完整。
pause
"""
    stop = f"""@echo off
chcp 65001 >nul
setlocal
set PORT=%~1
if "%PORT%"=="" set PORT={port}
set FOUND=
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /r /c:":%PORT% .*LISTENING"') do (
  taskkill /PID %%a /F >nul 2>nul
  set FOUND=1
)
if defined FOUND (
  echo 已停止連接埠 %PORT% 的伺服器
) else (
  echo 連接埠 %PORT% 沒有在執行
)
"""
    for filename, text in (("start.cmd", start), ("stop.cmd", stop)):
        with (site / filename).open("w", encoding="utf-8", newline="\r\n") as fh:
            fh.write(text)


def _write_site_readme(site: Path, profile: dict, info: dict) -> None:
    name = profile["name"]
    source = profile["start"]
    port = info["port"]
    mode_text = "單頁應用程式（SPA）" if info["mode"] == "spa" else "多頁靜態網站"
    updated = info["built_at"]

    text = f"""# {name} 離線副本

## 簡介

本資料夾是 <{source}> 在本機使用的離線副本，由 offline-mirror 於 {updated} 打包產生。

擷取範圍：{info['served_pages']} 個頁面、{info['assets']} 個資源檔、{info['api']} 筆資料回應，
合計約 {info['size_mb']} MB。網站的呈現方式判定為{mode_text}。

用途是沒有網路或原站回應很慢時仍可查閱。瀏覽過程中不會連到外部網路。

## 系統需求

- Windows 10 或 11
- Python 3.10 以上（需可執行 `python`）
- 瀏覽器：Edge、Chrome 或其他 Chromium 系瀏覽器
- 網路：**不需要**

## 安裝方式

不需要安裝。所有檔案已包含在本資料夾內。

## 使用方式

雙擊 `start.cmd`，會開啟一個標題為 `offline-{name}` 的命令視窗啟動伺服器，
3 秒後自動開啟瀏覽器。

也可以手動啟動（在本資料夾內）：

```
python _serve.py {port}
```

啟動後開啟 <http://127.0.0.1:{port}>，連接埠為 **{port}**。
若連接埠被占用，可在指令後面換一個號碼，例如 `python _serve.py 8090`。

## 關閉方式

伺服器跑在 `offline-{name}` 命令視窗裡。關閉方式有三種：

- 直接關掉該視窗（最快，程序一起結束）
- 在該視窗按 `Ctrl + C`，看到「已停止」後再關視窗
- 雙擊 `stop.cmd`：依連接埠 {port} 找出程序並強制結束，適合視窗已經遺失的時候

若改用其他連接埠，可帶參數：`stop.cmd 8090`。

確認已關閉：重新整理 <http://127.0.0.1:{port}> 應該出現「無法連上這個網站」。

## 檔案結構

```
index.html          進入點，已插入離線攔截腳本
offline-data.js     所有 API 回應的快照
offline-shim.js     把 API 請求導向本機資料
manifest.json       打包資訊（來源、時間、頁數、模式）
_serve.py           本機伺服器（只用標準函式庫）
start.cmd           一鍵啟動
stop.cmd            一鍵停止（依連接埠找程序）
```

其餘資料夾依原站路徑保存資源；跨網域資源放在 `_ext/<網域>/`。

## 功能說明

可直接使用的部分：

- 瀏覽已擷取的頁面與內容
- 站內路由切換（SPA 模式由前端程式處理）
- 以快照資料呈現的列表、詳情與搜尋功能

無法使用的部分：

- 登入、註冊、收藏、評分、留言等需要伺服器寫入的功能
- 擷取當下沒有產生請求的資料（例如需要點擊才會載入的內容）
- 即時更新、通知、WebSocket 訊息

## 資料來源與授權

內容來自 <{source}>，著作權屬原作者所有。本副本僅供個人離線查閱，
請勿公開散布、重新上傳或作為商業用途。原作者若要求移除，應立即刪除本資料夾。

## 已知限制

- 資料為擷取當時的快照，之後原站更新不會自動同步
- 擷取時未登入，因此不包含會員限定內容
- 需要 POST／PUT 等寫入操作的 API 無法在離線環境運作
- 極少數頁面若在擷取時未載入完成，可能顯示空白或舊資料
"""
    (site / "README.md").write_text(text, encoding="utf-8")


def build(profile: dict, log=print) -> dict:
    name = profile["name"]
    raw_dir = cache_dir(name) / "raw"
    entries = _entries(name)
    if not entries:
        raise SystemExit("沒有快取資料，請先執行 crawl")

    site = out_dir(name)
    if site.exists():
        shutil.rmtree(site)
    site.mkdir(parents=True)

    pages = [e for e in entries if e.get("kind") == "page"]
    apis = [e for e in entries if e.get("api")]
    assets = [e for e in entries if e.get("kind") != "page" and not e.get("api")]
    extra_hosts = [h for h in profile.get("extra_hosts") or [] if h]

    root = None
    for item in pages:
        if (item.get("path") or "/") in ("/", "") and not item.get("query"):
            root = item
            break
    root_html = _read_text(name, root) if root else ""
    if not root_html:
        try:
            root_html = util.fetch(
                profile["start"], profile.get("user_agent", ""), 45
            ).decode("utf-8", "replace")
        except Exception:
            root_html = ""

    mode = _detect_mode(profile, root_html)

    # ── API 資料 ───────────────────────────────────────────────
    data: dict = {}
    by_path: dict[str, str] = {}
    api_count = 0
    for item in apis:
        obj = _read_json(name, item)
        if obj is None:
            continue
        method = str(item.get("method") or "GET").upper()
        prefix = "" if method == "GET" else method + " "
        key = prefix + item["path"] + (("?" + item["query"]) if item.get("query") else "")
        data[key] = obj
        api_count += 1
        if not item.get("query"):
            by_path[prefix + item["path"]] = key
    data["__byPath"] = by_path

    ws_path = cache_dir(name) / "websocket.jsonl"
    if ws_path.exists():
        try:
            data["__websocket"] = [
                json.loads(line) for line in ws_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except Exception:
            pass

    data_js = "window.__OFFLINE_DATA__ = " + json.dumps(data, ensure_ascii=False) + ";\n"
    data_js = data_js.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    (site / "offline-data.js").write_text(data_js, encoding="utf-8")
    (site / "offline-shim.js").write_text(SHIM, encoding="utf-8")

    # ── 靜態資源 ───────────────────────────────────────────────
    asset_count = 0
    for item in assets:
        src = raw_dir / item["file"]
        if not src.exists():
            continue
        rel = _asset_rel(item)
        if not rel or rel.endswith("/"):
            continue
        target = site / rel
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        suffix = target.suffix.lower()
        if suffix in (".css", ".html", ".htm", ".js") and extra_hosts:
            text = src.read_text(encoding="utf-8", errors="replace")
            rewritten = _rewrite_hosts(text, extra_hosts)
            target.write_text(rewritten, encoding="utf-8")
        else:
            target.write_bytes(src.read_bytes())
        asset_count += 1

    # ── 缺圖檢查 ───────────────────────────────────────────────
    main_hosts = {util.host_key(profile["start"])}
    main_hosts |= {util.host_key(h) for h in profile.get("hosts") or []}
    extra_hosts = {util.host_key(h) for h in profile.get("extra_hosts") or []}

    refs: set[tuple[str | None, str]] = set()
    for key, value in data.items():
        if key in ("__byPath", "__websocket"):
            continue
        _collect_image_refs(value, refs)

    for item in pages:
        html = _read_text(name, item)
        for m in _CSS_URL_RE.finditer(html):
            _add_ref(m.group(1), refs)
        for m in _HTML_SRC_RE.finditer(html):
            _add_ref(m.group(1), refs)
    for item in assets:
        url = item.get("url") or ""
        if url.lower().endswith(".css") or str(item.get("ct", "")).startswith("text/css"):
            for m in _CSS_URL_RE.finditer(_read_text(name, item)):
                _add_ref(m.group(1), refs)
        elif url.lower().endswith((".js", ".mjs")):
            for m in _JS_IMG_RE.finditer(_read_text(name, item)):
                _add_ref(m.group(1), refs)

    have: set[tuple[str | None, str]] = set()
    for item in assets:
        rel = _asset_rel(item)
        if not rel:
            continue
        have.add((None, "/" + rel.lstrip("/")))
        if rel.startswith("_ext/") and item.get("host"):
            have.add((item["host"], "/" + rel.split("/", 2)[-1]))

    missing: list[tuple[str, str]] = []
    external: list[tuple[str, str]] = []
    for host, path in sorted(refs, key=lambda x: (x[0] or "", x[1])):
        if host and host not in main_hosts and host not in extra_hosts:
            external.append((host, path))
            continue
        if (None, path) in have or (host, path) in have:
            continue
        missing.append((host or "", path))

    failed_src = cache_dir(name) / "failed-images.txt"
    if failed_src.exists():
        try:
            shutil.copyfile(failed_src, site / "failed-images.txt")
        except OSError:
            pass

    if external:
        lines = ["# 外部網域圖片（未打包，可考慮加入 extra_hosts）", ""]
        lines += [f"{h} {p}" for h, p in external]
        (site / "external-images.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        log(f"[build] 提示：{len(external)} 張外部網域圖片未打包，詳見 external-images.txt")

    if missing:
        lines = ["# 離線副本缺圖清單", "# 格式：網域 路徑（網域空白表示同源）", ""]
        lines += [f"{h} {p}" for h, p in missing]
        (site / "missing-images.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        log(f"[build] 警告：{len(missing)} 張引用的圖片未打包，詳見 missing-images.txt")
    else:
        log("[build] 缺圖檢查：引用的圖片皆已打包")

    # ── 頁面 ───────────────────────────────────────────────────
    served_pages = 0
    if mode == "spa":
        for item in pages:
            if (item.get("path") or "/") not in ("/", ""):
                continue
            html = _read_text(name, item)
            if not html:
                continue
            html = _inject(_rewrite_hosts(html, extra_hosts))
            (site / "index.html").write_text(html, encoding="utf-8")
            served_pages = 1
            break
    else:
        written: set[str] = set()
        for item in pages:
            html = _read_text(name, item)
            if not html:
                continue
            rel = _page_rel(item.get("path") or "/")
            if rel in written:
                continue
            target = site / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_inject(_rewrite_hosts(html, extra_hosts)), encoding="utf-8")
            written.add(rel)
            served_pages += 1

    if not (site / "index.html").exists():
        html = _inject(_rewrite_hosts(root_html, extra_hosts)) if root_html else (
            "<!doctype html><meta charset=\"utf-8\"><title>離線副本</title>" \
            "<p>擷取時沒有取得首頁內容。</p>"
        )
        (site / "index.html").write_text(html, encoding="utf-8")
        served_pages = max(served_pages, 1)

    # 讓輸出資料夾可以整包複製到別台電腦使用
    shutil.copyfile(
        Path(__file__).resolve().parent / "standalone_serve.py", site / "_serve.py"
    )

    total_bytes = sum(f.stat().st_size for f in site.rglob("*") if f.is_file())
    info = {
        "name": name,
        "source": profile["start"],
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode,
        "port": int(profile.get("port") or 8080),
        "pages": len(pages),
        "served_pages": served_pages,
        "api": api_count,
        "assets": asset_count,
        "missing_images": len(missing),
        "external_images": len(external),
        "size_mb": round(total_bytes / 1048576, 2),
    }
    (site / "manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_cmd_files(site, name, info["port"])
    _write_site_readme(site, profile, info)
    info["path"] = str(site)
    log(f"[build] 已輸出 {site}（{info['size_mb']} MB）")
    return info
