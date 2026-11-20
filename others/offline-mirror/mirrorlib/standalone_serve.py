"""離線網站的本機伺服器（只用標準函式庫，可整個資料夾帶著走）。

啟動：
    python _serve.py [連接埠]

會讀取同資料夾的 manifest.json，決定要用 SPA 模式（所有找不到的路徑回首頁）
還是靜態模式（找不到就回 404）。
"""

from __future__ import annotations

import functools
import json
import os
import sys
import threading
import urllib.parse
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

EXT_MIME = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".eot": "application/vnd.ms-fontobject",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".wasm": "application/wasm",
    ".pdf": "application/pdf",
    ".zip": "application/zip",
}


class Handler(SimpleHTTPRequestHandler):
    spa = True

    def guess_type(self, path):
        # Windows 的登錄檔常把 .js 判成 text/plain，模組載入會失敗，所以自己指定。
        return EXT_MIME.get(Path(path).suffix.lower()) or super().guess_type(path)

    def do_GET(self):  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path
        fs = self.translate_path(self.path)
        if os.path.isdir(fs):
            if os.path.exists(os.path.join(fs, "index.html")) or os.path.exists(
                os.path.join(fs, "index.htm")
            ):
                return super().do_GET()
        elif os.path.isfile(fs):
            return super().do_GET()

        name = path.rsplit("/", 1)[-1]
        if not self.spa or "." in name:
            self.send_error(404)
            return
        # SPA 路由：交給首頁的程式處理
        self.path = "/index.html"
        return super().do_GET()

    def list_directory(self, path):  # 不開放目錄瀏覽
        self.send_error(404)
        return None

    def log_message(self, fmt, *args):
        pass


def run(root: Path, port: int = 8080, spa: bool | None = None, open_browser: bool = False) -> int:
    root = Path(root).resolve()
    if not (root / "index.html").exists():
        print(f"找不到 {root / 'index.html'}")
        return 1
    if spa is None:
        manifest = root / "manifest.json"
        mode = "spa"
        if manifest.exists():
            try:
                mode = json.loads(manifest.read_text(encoding="utf-8")).get("mode", "spa")
            except Exception:
                mode = "spa"
        spa = mode != "static"

    handler_cls = type("SiteHandler", (Handler,), {"spa": bool(spa)})
    handler = functools.partial(handler_cls, directory=str(root))
    ThreadingHTTPServer.allow_reuse_address = True
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        url = f"http://127.0.0.1:{port}"
        print(f"離線站已啟動：{url}（{'SPA' if spa else '靜態'} 模式）")
        print("按 Ctrl+C 結束")
        if open_browser:
            threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")
    return 0


def main() -> int:
    root = Path(__file__).resolve().parent
    port = 8080
    manifest = root / "manifest.json"
    if manifest.exists():
        try:
            port = int(json.loads(manifest.read_text(encoding="utf-8")).get("port") or port)
        except Exception:
            pass
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    return run(root, port)


if __name__ == "__main__":
    raise SystemExit(main())
