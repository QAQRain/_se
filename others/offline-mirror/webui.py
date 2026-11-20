"""本機網頁介面：開啟後輸入網址就能抓取、打包、啟動離線副本。

用法：
    python webui.py              # 開在 http://127.0.0.1:9000
    python webui.py --port 9010 --open

介面只綁 127.0.0.1，不對外開放；關掉這個程式，所有由它啟動的離線站也會一起停止。
"""

from __future__ import annotations

import functools
import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from mirrorlib import discover as discover_mod  # noqa: E402
from mirrorlib import profile as prof  # noqa: E402
from mirrorlib.standalone_serve import Handler as StaticHandler  # noqa: E402

UI_DIR = ROOT / "ui"
PYTHON = sys.executable

PORT = 9000
_lock = threading.Lock()
_job: dict | None = None
_servers: dict[str, dict] = {}


# ── 工作管理 ────────────────────────────────────────────────

def _clean_options(raw: dict) -> dict:
    def num(key, cast, minimum=None):
        value = raw.get(key)
        if value in (None, "", 0, "0"):
            return None
        try:
            number = cast(value)
        except (TypeError, ValueError):
            raise ValueError(f"參數 {key} 格式不正確")
        if minimum is not None and number < minimum:
            raise ValueError(f"參數 {key} 不能小於 {minimum}")
        return number

    def patterns(key):
        text = str(raw.get(key) or "").strip()
        if not text:
            return None
        return [part.strip() for part in text.split(",") if part.strip()]

    return {
        "limit": num("limit", int, 1),
        "max_pages": num("max_pages", int, 1),
        "workers": num("workers", int, 1),
        "delay": num("delay", float, 0),
        "wait": num("wait", float, 0),
        "port": num("port", int, 1024),
        "no_media": bool(raw.get("no_media")),
        "include": patterns("include"),
        "exclude": patterns("exclude"),
    }


def _argv(action: str, name: str, url: str, options: dict) -> list[str]:
    script = str(ROOT / "mirror.py")
    if action in ("run", "crawl"):
        argv = [PYTHON, "-u", "-X", "utf8", script, action, url, "--name", name]
    else:
        argv = [PYTHON, "-u", "-X", "utf8", script, action, name]

    if action in ("run", "crawl"):
        if options.get("limit"):
            argv += ["--limit", str(options["limit"])]
        for key, flag in (("max_pages", "--max-pages"), ("workers", "--workers"),
                          ("delay", "--delay"), ("wait", "--wait"), ("port", "--port")):
            if options.get(key) is not None:
                argv += [flag, str(options[key])]
        if options.get("no_media"):
            argv.append("--no-media")
        for pattern in options.get("include") or []:
            argv += ["--include", pattern]
        for pattern in options.get("exclude") or []:
            argv += ["--exclude", pattern]
    return argv


def _run_job(job: dict) -> None:
    job["lines"].append("$ " + " ".join(job["argv"]))
    try:
        proc = subprocess.Popen(
            job["argv"],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        job["proc"] = proc
        assert proc.stdout is not None
        for line in proc.stdout:
            text = line.rstrip("\r\n")
            if text:
                job["lines"].append(text)
                if len(job["lines"]) > 3000:
                    del job["lines"][:1000]
        proc.wait()
        job["returncode"] = proc.returncode
        job["status"] = "done" if proc.returncode == 0 else "error"
    except Exception as exc:  # noqa: BLE001
        job["lines"].append(f"[錯誤] {type(exc).__name__}: {exc}")
        job["status"] = "error"
    finally:
        job["ended"] = time.strftime("%H:%M:%S")


def apply_settings(name: str, options: dict) -> dict:
    """把 UI 表單的抓取設定寫回既有站台的設定檔，只更新有填寫的欄位。"""
    if not prof.exists(name):
        raise FileNotFoundError(f"找不到站台「{name}」")
    data = prof.load(name)
    for key in ("max_pages", "workers", "wait", "port"):
        value = options.get(key)
        if value is not None:
            data[key] = value
    if "no_media" in options and options["no_media"] is not None:
        data["media"] = not bool(options["no_media"])
    for key in ("include", "exclude"):
        value = options.get(key)
        if value is not None:
            data[key] = list(value)
    prof.save(data)
    return data


# 預覽時用來標記「通常不該抓」的路徑特徵；純規則，不需 AI 判斷。
SUSPICIOUS_RULES = [
    ("admin", "管理後台"),
    ("dashboard", "管理儀表板"),
    ("login", "登入頁"),
    ("logout", "登出頁"),
    ("register", "註冊頁"),
    ("signup", "註冊頁"),
    ("profile", "個人資料頁"),
    ("account", "帳號頁"),
    ("settings", "設定頁"),
    ("password", "密碼頁"),
    ("reset", "重設頁"),
    ("verify", "驗證頁"),
    ("draft", "草稿頁"),
    ("edit", "編輯頁"),
    ("cart", "購物車"),
    ("checkout", "結帳頁"),
    ("payment", "付款頁"),
    ("private", "私密頁"),
    ("member", "會員頁"),
]


def analyze_preview(profile: dict) -> dict:
    """只探索網址、不下載內容；回傳統計與自動標記的可疑路徑。"""
    urls, method = discover_mod.discover(profile, limit=0, log=lambda *a: None)
    from urllib.parse import urlparse
    groups: dict[str, int] = {}
    suspicious: dict[str, dict] = {}
    for url in urls:
        path = urlparse(url).path.lower()
        first = "/" + (path.strip("/").split("/")[0] or "")
        groups[first] = groups.get(first, 0) + 1
        for keyword, reason in SUSPICIOUS_RULES:
            if keyword in path:
                if first not in suspicious:
                    suspicious[first] = {"path": first, "count": 0, "reasons": []}
                suspicious[first]["count"] += 1
                if reason not in suspicious[first]["reasons"]:
                    suspicious[first]["reasons"].append(reason)
                break
    top = sorted(groups.items(), key=lambda item: -item[1])[:20]
    return {
        "method": method,
        "total": len(urls),
        "groups": [{"path": p, "count": c} for p, c in top],
        "suspicious": sorted(suspicious.values(), key=lambda s: -s["count"]),
    }


def remove_site(name: str) -> bool:
    """只移除站台設定檔；快取與輸出資料夾保留，以便日後重新打包。"""
    prof.check_name(name)
    path = prof.path_of(name)
    if not path.exists():
        return False
    path.unlink()
    return True


def settings_of(name: str) -> dict:
    """回傳單一站台目前可編輯的抓取設定，供 UI 表單載入。"""
    if not prof.exists(name):
        raise FileNotFoundError(f"找不到站台「{name}」")
    data = prof.load(name)
    return {
        "name": name,
        "url": data.get("start", ""),
        "max_pages": data.get("max_pages"),
        "workers": data.get("workers"),
        "delay": data.get("delay"),
        "wait": data.get("wait"),
        "port": data.get("port"),
        "media": bool(data.get("media", True)),
        "include": data.get("include") or [],
        "exclude": data.get("exclude") or [],
    }


def start_job(payload: dict) -> dict:
    global _job
    action = str(payload.get("action") or "run")
    if action not in ("run", "crawl", "build", "update", "fill-images"):
        raise ValueError("不支援的操作")

    with _lock:
        if _job and _job["status"] == "running":
            raise RuntimeError("已經有工作在執行，請等它結束")

        if action in ("build", "update", "fill-images"):
            name = str(payload.get("name") or "").strip()
            if not prof.exists(name):
                raise ValueError(f"找不到站台「{name}」")
            url = ""
        else:
            url = prof.normalize_url(str(payload.get("url") or ""))
            name = str(payload.get("name") or "").strip() or prof.slug_from_url(url)
            prof.check_name(name)

        options = _clean_options(payload.get("options") or {})
        if action == "update":
            options["limit"] = None

        _job = {
            "id": str(int(time.time() * 1000)),
            "action": action,
            "name": name,
            "url": url,
            "argv": _argv(action, name, url, options),
            "lines": [],
            "status": "running",
            "returncode": None,
            "started": time.strftime("%H:%M:%S"),
            "ended": None,
        }
        job = _job

    threading.Thread(target=_run_job, args=(job,), daemon=True).start()
    return job


def public_job() -> dict | None:
    job = _job
    if not job:
        return None
    return {
        "id": job["id"],
        "action": job["action"],
        "name": job["name"],
        "url": job["url"],
        "status": job["status"],
        "returncode": job["returncode"],
        "started": job["started"],
        "ended": job["ended"],
        "line_count": len(job["lines"]),
    }


# ── 離線站伺服器 ────────────────────────────────────────────

def _site_mode(name: str) -> str:
    manifest = prof.out_dir(name) / "manifest.json"
    if manifest.exists():
        try:
            return json.loads(manifest.read_text(encoding="utf-8")).get("mode", "spa")
        except Exception:
            return "spa"
    return "spa"


def start_site(name: str) -> str:
    site = prof.out_dir(name)
    if not (site / "index.html").exists():
        raise RuntimeError("這個站台還沒建置，請先按「重建」")

    with _lock:
        running = _servers.get(name)
        if running:
            return running["url"]

        data = prof.load(name)
        base_port = int(data.get("port") or 8080)
        mode = _site_mode(name)
        handler_cls = type("SiteHandler", (StaticHandler,), {"spa": mode != "static"})
        httpd = None
        chosen = base_port
        for candidate in range(base_port, base_port + 40):
            try:
                handler = functools.partial(handler_cls, directory=str(site))
                httpd = ThreadingHTTPServer(("127.0.0.1", candidate), handler)
                chosen = candidate
                break
            except OSError:
                continue
        if httpd is None:
            raise RuntimeError(f"連接埠 {base_port}～{base_port + 39} 都被佔用")

        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        _servers[name] = {
            "httpd": httpd,
            "thread": thread,
            "url": f"http://127.0.0.1:{chosen}",
            "port": chosen,
        }
        return _servers[name]["url"]


def stop_site(name: str) -> bool:
    with _lock:
        running = _servers.pop(name, None)
    if not running:
        return False
    try:
        running["httpd"].shutdown()
        running["httpd"].server_close()
        running["thread"].join(timeout=3)
    except Exception:
        pass
    return True


def stop_all_sites() -> None:
    for name in list(_servers):
        stop_site(name)


# ── 狀態 ────────────────────────────────────────────────────

def site_state() -> list[dict]:
    sites = []
    for name in prof.list_names():
        try:
            data = prof.load(name)
        except Exception:
            continue
        site = prof.out_dir(name)
        manifest: dict = {}
        manifest_path = site / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                manifest = {}
        running = _servers.get(name)
        cached = prof.cache_dir(name) / "meta.jsonl"
        cache_lines = 0
        if cached.exists():
            try:
                cache_lines = sum(1 for _ in cached.open(encoding="utf-8"))
            except OSError:
                cache_lines = 0
        sites.append({
            "name": name,
            "url": data.get("start", ""),
            "built": bool(manifest),
            "built_at": manifest.get("built_at", ""),
            "mode": manifest.get("mode", data.get("mode", "auto")),
            "served_pages": manifest.get("served_pages", 0),
            "api": manifest.get("api", 0),
            "size_mb": manifest.get("size_mb", 0),
            "cache_lines": cache_lines,
            "running_url": running["url"] if running else "",
            "port": running["port"] if running else int(data.get("port") or 8080),
            "media": bool(data.get("media", True)),
        })
    return sites


# ── HTTP ────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    server_version = "offline-mirror-ui"

    def _send(self, body: bytes, content_type: str, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: dict, code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(body, "application/json; charset=utf-8", code)

    def _error(self, message: str, code: int = 400) -> None:
        self._json({"error": message}, code)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            index = UI_DIR / "index.html"
            if not index.exists():
                return self._send("找不到 ui/index.html".encode("utf-8"),
                                  "text/plain; charset=utf-8", 500)
            return self._send(index.read_bytes(), "text/html; charset=utf-8")

        if path == "/api/state":
            return self._json({
                "sites": site_state(),
                "job": public_job(),
                "ui_port": PORT,
            })

        if path == "/api/settings":
            name = parse_qs(parsed.query).get("name", [""])[0].strip()
            try:
                return self._json(settings_of(name))
            except FileNotFoundError as exc:
                return self._error(str(exc), 404)

        if path == "/api/job":
            since = 0
            try:
                since = int(parse_qs(parsed.query).get("since", ["0"])[0] or 0)
            except ValueError:
                since = 0
            job = _job
            if not job:
                return self._json({"status": None, "lines": [], "next": 0})
            lines = job["lines"]
            payload = public_job() or {}
            payload.update({"lines": lines[since:], "next": len(lines)})
            return self._json(payload)

        if path == "/favicon.ico":
            return self._send(b"", "image/x-icon", 204)

        self._error("找不到路徑", 404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return self._error("請求內容不是有效的 JSON")

        if parsed.path == "/api/start":
            try:
                job = start_job(payload)
            except RuntimeError as exc:
                return self._error(str(exc), 409)
            except (ValueError, FileNotFoundError) as exc:
                return self._error(str(exc), 400)
            return self._json({"job": public_job(), "name": job["name"]})

        if parsed.path == "/api/settings":
            name = str(payload.get("name") or "").strip()
            try:
                options = _clean_options(payload.get("options") or {})
                data = apply_settings(name, options)
            except FileNotFoundError as exc:
                return self._error(str(exc), 404)
            except ValueError as exc:
                return self._error(str(exc), 400)
            return self._json({"settings": settings_of(name), "saved": bool(data)})

        if parsed.path == "/api/serve":
            name = str(payload.get("name") or "").strip()
            try:
                url = start_site(name)
            except FileNotFoundError as exc:
                return self._error(str(exc), 404)
            except (RuntimeError, ValueError) as exc:
                return self._error(str(exc), 409)
            return self._json({"url": url})

        if parsed.path == "/api/stop":
            name = str(payload.get("name") or "").strip()
            return self._json({"stopped": stop_site(name)})

        if parsed.path == "/api/preview":
            try:
                url = prof.normalize_url(str(payload.get("url") or ""))
                name = str(payload.get("name") or "").strip() or prof.slug_from_url(url)
                options = _clean_options(payload.get("options") or {})
                profile = prof.create_from_url(
                    url,
                    name,
                    max_pages=options.get("max_pages"),
                    workers=options.get("workers"),
                    delay=options.get("delay"),
                    wait=options.get("wait"),
                    media=None if not options.get("no_media") else False,
                    include=options.get("include"),
                    exclude=options.get("exclude"),
                )
                result = analyze_preview(profile)
            except ValueError as exc:
                return self._error(str(exc), 400)
            except Exception as exc:  # noqa: BLE001
                return self._error("預覽失敗：" + str(exc), 500)
            return self._json(result)

        if parsed.path == "/api/delete":
            name = str(payload.get("name") or "").strip()
            try:
                removed = remove_site(name)
            except ValueError as exc:
                return self._error(str(exc), 400)
            if not removed:
                return self._error(f"找不到站台「{name}」", 404)
            return self._json({"deleted": name})

        self._error("找不到路徑", 404)

    def log_message(self, fmt: str, *args) -> None:
        pass


def main() -> int:
    global PORT
    import argparse

    parser = argparse.ArgumentParser(description="離線網站打包器的本機網頁介面")
    parser.add_argument("--port", type=int, default=9000, help="介面連接埠，預設 9000")
    parser.add_argument("--open", action="store_true", help="啟動後自動開啟瀏覽器")
    args = parser.parse_args()
    PORT = args.port

    if not (UI_DIR / "index.html").exists():
        print(f"找不到介面檔案：{UI_DIR / 'index.html'}")
        return 1

    ThreadingHTTPServer.allow_reuse_address = True
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        print(f"連接埠 {PORT} 已被占用，請換一個：python webui.py --port 9010")
        return 1

    url = f"http://127.0.0.1:{PORT}"
    print(f"介面已啟動：{url}")
    print("按 Ctrl+C 或直接關閉這個視窗結束")
    if args.open:
        threading.Timer(1.0, lambda: __import__("webbrowser").open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        stop_all_sites()
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
