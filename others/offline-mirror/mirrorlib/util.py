"""共用小工具：型別對照、雜湊、體積格式、robots.txt 檢查。"""

from __future__ import annotations

import hashlib
import urllib.request
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

# content-type → 存檔副檔名（打包時使用）
CT_EXT = {
    "text/html": ".html",
    "application/xhtml+xml": ".html",
    "text/css": ".css",
    "text/javascript": ".js",
    "application/javascript": ".js",
    "application/x-javascript": ".js",
    "application/json": ".json",
    "text/json": ".json",
    "application/manifest+json": ".webmanifest",
    "text/plain": ".txt",
    "text/xml": ".xml",
    "application/xml": ".xml",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "image/avif": ".avif",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
    "font/woff2": ".woff2",
    "font/woff": ".woff",
    "font/ttf": ".ttf",
    "font/otf": ".otf",
    "application/font-woff": ".woff",
    "application/font-woff2": ".woff2",
    "application/vnd.ms-fontobject": ".eot",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "application/wasm": ".wasm",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
}

# 副檔名 → content-type（本機伺服器使用，避免 Windows 登錄檔把 .js 判成 text/plain）
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

MEDIA_EXT = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico", ".avif",
    ".mp4", ".webm", ".mp3", ".ogg", ".wav",
}

# 不會是「頁面」的副檔名，探索連結時直接跳過
NON_PAGE_EXT = MEDIA_EXT | {
    ".pdf", ".zip", ".rar", ".7z", ".exe", ".msi", ".dmg", ".apk",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".css", ".js", ".mjs",
    ".json", ".xml", ".txt", ".csv", ".ics", ".map", ".wasm",
}

HTML_EXT = {".html", ".htm"}


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def human_size(n: float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{int(n)} B" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def content_type_ext(ct: str) -> str:
    base = (ct or "").split(";")[0].strip().lower()
    return CT_EXT.get(base, "")


def guess_ext(url: str, ct: str) -> str:
    """先看網址副檔名，沒有才依 content-type 推測。"""
    ext = Path(urlparse(url).path).suffix.lower()
    if ext:
        return ext
    return content_type_ext(ct) or ".bin"


def is_json(ct: str) -> bool:
    base = (ct or "").split(";")[0].strip().lower()
    return base in ("application/json", "text/json") or base.endswith("+json")


def host_key(value: str) -> str:
    """把網址或網域正規化成比較用的鍵（去掉 www.、連接埠、帳密）。"""
    text = (value or "").strip()
    if "//" in text:
        text = urlparse(text).netloc
    text = text.split("@")[-1].split(":")[0].lower()
    return text[4:] if text.startswith("www.") else text


def fetch(url: str, user_agent: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent or "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


class Robots:
    """記住每個網域的 robots.txt，避免重複下載。"""

    def __init__(self, user_agent: str = "*", enabled: bool = True) -> None:
        self.user_agent = user_agent or "*"
        self.enabled = enabled
        self._cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def allowed(self, url: str) -> bool:
        if not self.enabled:
            return True
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._cache:
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(base + "/robots.txt")
            try:
                parser.read()
            except Exception:
                parser = None  # type: ignore[assignment]
            self._cache[base] = parser
        parser = self._cache[base]
        if parser is None:
            return True
        try:
            return parser.can_fetch(self.user_agent, url)
        except Exception:
            return True
