"""找出要抓哪些頁面：robots.txt → sitemap → 首頁連結廣度搜尋。"""

from __future__ import annotations

import re
from collections import deque
from pathlib import Path
from urllib.parse import urlparse

from . import util

LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.I | re.S)

ANCHOR_JS = """
() => Array.from(document.querySelectorAll('a[href]'))
  .map((a) => a.href)
  .filter((h) => h && (h.startsWith('http://') || h.startsWith('https://')))
"""


def make_page_filter(profile: dict):
    """回傳「這個網址該不該當成頁面抓」的判斷函式。"""
    hosts = {util.host_key(profile["start"])}
    hosts |= {util.host_key(h) for h in profile.get("hosts") or []}
    include = [re.compile(p) for p in profile.get("include") or []]
    exclude = [re.compile(p) for p in profile.get("exclude") or []]
    robots = util.Robots(profile.get("user_agent", "*"), profile.get("respect_robots", True))

    def ok(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        if util.host_key(url) not in hosts:
            return False
        if Path(parsed.path).suffix.lower() in util.NON_PAGE_EXT:
            return False
        if include and not any(r.search(url) for r in include):
            return False
        if any(r.search(url) for r in exclude):
            return False
        return robots.allowed(url)

    return ok


def _sitemap_candidates(profile: dict) -> list[str]:
    parsed = urlparse(profile["start"])
    base = f"{parsed.scheme}://{parsed.netloc}"
    candidates = [base + "/sitemap.xml"]
    try:
        text = util.fetch(base + "/robots.txt", profile.get("user_agent", ""), 20).decode(
            "utf-8", "replace"
        )
        for line in text.splitlines():
            line = line.strip()
            if line.lower().startswith("sitemap:"):
                candidates.append(line.split(":", 1)[1].strip())
    except Exception:
        pass
    unique: list[str] = []
    for item in candidates:
        if item and item not in unique:
            unique.append(item)
    return unique


def sitemap_urls(profile: dict, log=print) -> list[str]:
    """讀 sitemap.xml；遇到 sitemapindex 會展開子 sitemap。"""
    seen: set[str] = set()
    queue = deque(_sitemap_candidates(profile))
    pages: list[str] = []
    guard = 0
    while queue and guard < 100:
        guard += 1
        loc = queue.popleft()
        if loc in seen:
            continue
        seen.add(loc)
        try:
            xml = util.fetch(loc, profile.get("user_agent", ""), 45).decode("utf-8", "replace")
        except Exception:
            continue
        locs = [x.strip() for x in LOC_RE.findall(xml)]
        if "<sitemapindex" in xml.lower():
            for child in locs:
                if child not in seen:
                    queue.append(child)
            continue
        pages.extend(locs)
    unique: list[str] = []
    found: set[str] = set()
    for url in pages:
        if url and url not in found:
            found.add(url)
            unique.append(url)
    return unique


def bfs_urls(profile: dict, limit: int, log=print) -> list[str]:
    """沒有 sitemap 時，從首頁開始沿著 <a href> 找同站頁面。"""
    from .capture import launch  # 延後匯入，避免循環

    from playwright.sync_api import sync_playwright

    allowed = make_page_filter(profile)
    start = profile["start"]
    cap = limit or int(profile.get("max_pages") or 3000)
    seen = {start}
    queue = deque([start])
    pages: list[str] = []

    with sync_playwright() as pw:
        browser, context = launch(pw, profile)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            while queue and len(pages) < cap:
                url = queue.popleft()
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(int(float(profile.get("delay") or 0) * 1000))
                except Exception:
                    continue
                pages.append(url)
                try:
                    hrefs = page.evaluate(ANCHOR_JS)
                except Exception:
                    hrefs = []
                for href in hrefs:
                    clean = href.split("#", 1)[0]
                    if clean in seen:
                        continue
                    if not allowed(clean):
                        continue
                    seen.add(clean)
                    queue.append(clean)
                if len(pages) % 10 == 0:
                    log(f"[discover] 已找到 {len(pages)} 頁，待看 {len(queue)} 個連結")
        finally:
            try:
                page.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
    return pages


def discover(profile: dict, limit: int = 0, log=print) -> tuple[list[str], str]:
    """回傳（頁面清單, 使用的方法）。"""
    allowed = make_page_filter(profile)
    cap = limit or int(profile.get("max_pages") or 3000)

    raw = sitemap_urls(profile, log=log)
    pages = [url for url in raw if allowed(url)]
    if pages:
        if limit:
            pages = pages[:limit]
        else:
            pages = pages[:cap]
        log(f"[discover] sitemap 找到 {len(raw)} 筆，可用 {len(pages)} 頁")
        if not limit and len(raw) > cap:
            log(f"[discover] 已達頁數上限 {cap}，其餘略過（可用 --max-pages 調整）")
        return pages, "sitemap"

    log("[discover] 沒有可用的 sitemap，改用首頁連結廣度搜尋")
    pages = bfs_urls(profile, limit, log=log)
    if not limit:
        pages = pages[:cap]
    return pages, "links"
