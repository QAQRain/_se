"""站台設定檔（profile）：每個網站一份 JSON，放在 sites/。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
SITES = ROOT / "sites"
OUT = ROOT / "out"
CACHE = ROOT / ".cache"

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

DEFAULTS: dict = {
    "name": "",
    "start": "",
    "hosts": [],
    "extra_hosts": [],
    "include": [],
    "exclude": [],
    "api_prefixes": ["/api/"],
    "max_pages": 3000,
    "workers": 4,
    "delay": 0.4,
    "wait": 2.0,
    "media": True,
    "respect_robots": True,
    "mode": "auto",          # auto｜spa｜static
    "port": 8080,
    "headless": True,
    "channel": "msedge",
    "user_agent": DEFAULT_UA,
}

NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def path_of(name: str) -> Path:
    return SITES / f"{name}.json"


def cache_dir(name: str) -> Path:
    return CACHE / name


def out_dir(name: str) -> Path:
    return OUT / name


def check_name(name: str) -> str:
    if not NAME_RE.match(name or ""):
        raise ValueError("名稱只能使用英文字母、數字、底線與減號，例如 my-site")
    return name


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise ValueError("請提供網站位址")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError(f"網址格式不正確：{url}")
    clean = url.split("#", 1)[0]
    return clean


def slug_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    host = host.split(":")[0]
    slug = re.sub(r"[^a-z0-9]+", "-", host).strip("-")
    return slug or "site"


def create_from_url(url: str, name: str = "", **overrides) -> dict:
    url = normalize_url(url)
    host = urlparse(url).netloc.lower()
    if not name:
        name = slug_from_url(url)
    profile = dict(DEFAULTS)
    profile.update({"name": check_name(name), "start": url, "hosts": [host]})
    for key, value in overrides.items():
        if value is not None and key in DEFAULTS:
            profile[key] = value
    return profile


def load(name: str) -> dict:
    path = path_of(name)
    if not path.exists():
        raise FileNotFoundError(f"找不到設定檔 {path}，請先用 crawl 建立")
    data = json.loads(path.read_text(encoding="utf-8"))
    profile = dict(DEFAULTS)
    profile.update({k: v for k, v in data.items() if v is not None})
    profile["name"] = name
    if not profile.get("hosts"):
        profile["hosts"] = [urlparse(profile["start"]).netloc.lower()]
    return profile


def save(profile: dict) -> Path:
    name = check_name(profile["name"])
    SITES.mkdir(parents=True, exist_ok=True)
    path = path_of(name)
    ordered = {key: profile.get(key, DEFAULTS[key]) for key in DEFAULTS}
    ordered.update({k: v for k, v in profile.items() if k not in ordered})
    path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def exists(name: str) -> bool:
    return path_of(name).exists()


def list_names() -> list[str]:
    if not SITES.exists():
        return []
    return sorted(p.stem for p in SITES.glob("*.json") if not p.stem.startswith("_"))
