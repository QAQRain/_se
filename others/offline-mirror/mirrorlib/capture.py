"""用 Playwright 逐頁開啟目標網站，側錄所有回應與頁面 HTML。"""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright

from . import util
from .profile import cache_dir


def launch(pw, profile: dict):
    """啟動瀏覽器：優先用系統 Edge，失敗才退回內建 Chromium。"""
    kwargs: dict = {"headless": bool(profile.get("headless", True))}
    channel = (profile.get("channel") or "").strip()
    if channel:
        kwargs["channel"] = channel
    try:
        browser = pw.chromium.launch(**kwargs)
    except Exception:
        kwargs.pop("channel", None)
        browser = pw.chromium.launch(**kwargs)
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        locale="zh-TW",
        ignore_https_errors=True,
        user_agent=profile.get("user_agent") or None,
    )
    return browser, context


def _is_api(profile: dict, path: str, rtype: str, ct: str) -> bool:
    if any(path.startswith(prefix) for prefix in profile.get("api_prefixes") or []):
        return True
    return rtype in ("xhr", "fetch") and util.is_json(ct)


def _seen_key(method: str, url: str) -> str:
    """POST 與 GET 可能是同一個網址，要用方法區分。"""
    return f"{method} {url}" if method == "POST" else url


IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico", ".avif"}
_LAZY_ATTRS = ("src", "data-src", "data-lazy-src", "data-original", "data-url", "poster", "srcset", "data-srcset")
_TEXT_CSS_URL_RE = re.compile(r"url\(\s*['\"]?([^'\")\s]+)", re.I)
_TEXT_HTML_SRC_RE = re.compile(r"(?:src|data-src|data-lazy-src|data-original|poster)=[\"']([^\"']+)[\"']", re.I)
_TEXT_JS_IMG_RE = re.compile(r"['\"](/[^'\"\s]+\.(?:png|jpg|jpeg|webp|gif|svg|ico|avif)(?:\?[^'\"\s]*)?)['\"]", re.I)


def _image_url(value, base: str) -> str | None:
    """字串若看起來是圖片網址，回傳絕對 URL；否則回傳 None。"""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text.startswith(("data:", "blob:", "javascript:", "#")):
        return None
    # 只接受絕對網址或以 / 開頭的路徑；單純檔名（如 source.file）不是可下載網址
    if not (text.startswith("/") or re.match(r"^https?://", text, re.I)):
        return None
    low = text.lower().split("?")[0].split("#")[0]
    if not any(low.endswith(ext) for ext in IMAGE_EXT):
        return None
    try:
        return urljoin(base, text)
    except Exception:
        return None


def _collect_image_urls(obj, base: str, out: set[str], depth: int = 0) -> None:
    """遞迴掃出 JSON 中的所有圖片網址（含 lazy-load 用的欄位）。"""
    if depth > 12:
        return
    if isinstance(obj, str):
        url = _image_url(obj, base)
        if url:
            out.add(url)
    elif isinstance(obj, dict):
        for value in obj.values():
            _collect_image_urls(value, base, out, depth + 1)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            _collect_image_urls(value, base, out, depth + 1)


def _collect_text_image_urls(text: str, base: str, out: set[str]) -> None:
    """從 HTML／CSS／JS 文字中收集圖片網址。"""
    if not text:
        return
    for rx in (_TEXT_CSS_URL_RE, _TEXT_HTML_SRC_RE, _TEXT_JS_IMG_RE):
        for m in rx.finditer(text):
            url = _image_url(m.group(1), base)
            if url:
                out.add(url)


_DOM_IMAGES_JS = r"""() => {
  const found = [];
  const add = (u) => { if (typeof u === 'string' && u) found.push(u); };
  const addAttr = (a, v) => {
    if (a.toLowerCase().indexOf('srcset') >= 0) {
      (v || '').split(',').forEach((part) => {
        const u = part.trim().split(/\s+/)[0];
        if (u) add(u);
      });
    } else add(v);
  };
  document.querySelectorAll('img,source,video,embed,object').forEach((el) => {
    %s.forEach((a) => addAttr(a, el.getAttribute(a)));
  });
  document.querySelectorAll('[style]').forEach((el) => {
    const s = el.getAttribute('style') || '';
    (s.match(/url\(['"]?[^'")]+['"]?\)/g) || []).forEach((x) => {
      add(x.replace(/^url\(['"]?/, '').replace(/['"]?\)$/, ''));
    });
  });
  return found;
}""" % json.dumps(_LAZY_ATTRS)

_CLICK_NEXT_JS = r"""() => {
  const els = Array.from(document.querySelectorAll('a,button,[role="button"]'));
  const hit = els.find((el) => {
    if (el.disabled || el.getAttribute('aria-disabled') === 'true') return false;
    const t = (el.textContent || '').trim();
    const a = (el.getAttribute('aria-label') || '').trim();
    const rel = (el.getAttribute('rel') || '').trim();
    return rel === 'next'
      || /下一頁|下一页|next\s*page|^next$|^>$|^»$/i.test(t)
      || /next|下一/i.test(a);
  });
  if (!hit) return false;
  hit.click();
  return true;
}"""


def _get_with_retry(context, url: str, tries: int = 3):
    """短暫失敗時重試，避免單一逾時就永久漏抓。"""
    last = None
    for i in range(tries):
        try:
            resp = context.request.get(url, timeout=15000)
            if resp.ok:
                return resp
            last = RuntimeError(f"HTTP {resp.status}")
        except Exception as exc:
            last = exc
        if i + 1 < tries:
            time.sleep(0.5 * (i + 1))
    raise last if last else RuntimeError("請求失敗")


def _store_item(url, body, ct, rtype, profile, raw, seen, fh, stats,
                host: str | None = None, is_extra: bool = False,
                api: bool = False, method: str = "GET") -> bool:
    """把一份回應寫入快取，回傳是否新增。"""
    skey = _seen_key(method, url)
    if not body or skey in seen:
        return False
    key = util.sha1(skey)
    try:
        (raw / key).write_bytes(body)
    except OSError:
        return False
    parsed = urlparse(url)
    item = {
        "url": url,
        "path": parsed.path or "/",
        "query": parsed.query,
        "host": host or util.host_key(url),
        "ct": ct,
        "kind": rtype,
        "api": api,
        "method": method,
        "size": len(body),
        "file": key,
        "host_extra": is_extra,
    }
    seen[skey] = item
    fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    _count(stats, item)
    return True


def _count(stats: dict, item: dict) -> None:
    if item.get("kind") == "page":
        stats["pages"] += 1
    elif item.get("api"):
        stats["api"] += 1
    else:
        stats["assets"] += 1
        if item.get("kind") in ("image", "media", "font"):
            stats["media"] += 1
    stats["bytes"] += int(item.get("size") or 0)


def _load_seen(meta_path: Path, stats: dict) -> dict[str, dict]:
    seen: dict[str, dict] = {}
    if not meta_path.exists():
        return seen
    for line in meta_path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not item.get("url"):
            continue
        method = str(item.get("method") or "GET").upper()
        seen[_seen_key(method, item["url"])] = item
        _count(stats, item)
    return seen


def _save_page(page, requested: str, seen: dict, raw: Path, fh, stats: dict) -> None:
    if requested in seen:
        return
    try:
        final = page.url or requested
        html = page.content()
    except Exception:
        return
    if not html or len(html) < 50:
        return
    key = util.sha1("page:" + requested)
    try:
        (raw / key).write_bytes(html.encode("utf-8"))
    except OSError:
        return
    parsed = urlparse(requested)
    item = {
        "url": requested,
        "final": final,
        "path": parsed.path or "/",
        "query": parsed.query,
        "host": util.host_key(requested),
        "ct": "text/html; charset=utf-8",
        "kind": "page",
        "api": False,
        "method": "GET",
        "size": len(html),
        "file": key,
        "host_extra": False,
    }
    seen[requested] = item
    fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    _count(stats, item)


def crawl(profile: dict, urls: list[str], refresh: bool = False, log=print) -> dict:
    name = profile["name"]
    base = cache_dir(name)
    raw = base / "raw"
    meta_path = base / "meta.jsonl"

    if refresh:
        if meta_path.exists():
            meta_path.unlink()
        if raw.exists():
            shutil.rmtree(raw)

    raw.mkdir(parents=True, exist_ok=True)
    stats = {"pages": 0, "api": 0, "assets": 0, "media": 0, "bytes": 0}
    seen = _load_seen(meta_path, stats)
    if seen:
        log(f"[crawl] 已有 {len(seen)} 筆快取，會跳過已抓過的網址（要重抓請加 --refresh）")

    main_hosts = {util.host_key(profile["start"])}
    main_hosts |= {util.host_key(h) for h in profile.get("hosts") or []}
    extra_hosts = {util.host_key(h) for h in profile.get("extra_hosts") or []}
    with_media = bool(profile.get("media", True))

    fh = meta_path.open("a", encoding="utf-8")
    pending_images: set[str] = set()
    ws_messages: list[dict] = []

    def make_handler():
        def on_response(resp):
            try:
                url = resp.url
                parsed = urlparse(url)
                if parsed.scheme not in ("http", "https"):
                    return
                host = util.host_key(url)
                is_extra = host in extra_hosts
                if host not in main_hosts and not is_extra:
                    return
                request = resp.request
                method = request.method.upper()
                if method not in ("GET", "POST"):
                    return
                if _seen_key(method, url) in seen:
                    return
                rtype = request.resource_type
                if rtype in ("document", "websocket"):
                    return
                status = resp.status
                if status and not (200 <= status < 300):
                    return
                headers = resp.headers or {}
                ct = headers.get("content-type", "")
                suffix = Path(parsed.path).suffix.lower()
                if not with_media and not is_extra and (
                    rtype in ("image", "media", "font") or suffix in util.MEDIA_EXT
                ):
                    return
                body = resp.body()
                if _is_api(profile, parsed.path, rtype, ct):
                    try:
                        obj = json.loads(body.decode("utf-8", "replace"))
                        _collect_image_urls(obj, url, pending_images)
                    except Exception:
                        pass
            except Exception:
                return
            if not body:
                return
            skey = _seen_key(method, url)
            key = util.sha1(skey)
            try:
                (raw / key).write_bytes(body)
            except OSError:
                return
            item = {
                "url": url,
                "path": parsed.path or "/",
                "query": parsed.query,
                "host": host,
                "ct": ct,
                "kind": rtype,
                "api": _is_api(profile, parsed.path, rtype, ct),
                "method": method,
                "size": len(body),
                "file": key,
                "host_extra": is_extra,
            }
            seen[skey] = item
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
            _count(stats, item)

        return on_response

    total = len(urls)
    workers = max(1, int(profile.get("workers") or 1))
    wait_ms = int(float(profile.get("wait") or 0) * 1000)
    started = time.time()
    done = 0
    progress_path = base / "progress.txt"

    log(f"[crawl] 目標 {total} 頁，平行 {workers} 個分頁，媒體={'開' if with_media else '關'}")

    pw = None
    browser = None
    try:
        pw = sync_playwright().start()
        browser, context = launch(pw, profile)
        pool = []
        for _ in range(workers):
            page = context.new_page()
            page.on("response", make_handler())

            def on_ws(ws):
                ws.on("framereceived", lambda msg: ws_messages.append(
                    {"url": ws.url, "message": msg}
                ))
            page.on("websocket", on_ws)
            pool.append(page)

        for start in range(0, total, workers):
            wave = urls[start:start + workers]
            failed: set[int] = set()
            for page, url in zip(pool, wave):
                try:
                    page.goto(url, wait_until="commit", timeout=45000)
                except Exception:
                    failed.add(id(page))
            for page, url in zip(pool, wave):
                try:
                    page.wait_for_load_state("load", timeout=25000)
                except Exception:
                    pass
                if wait_ms:
                    try:
                        page.wait_for_timeout(wait_ms)
                    except Exception:
                        pass
                if id(page) not in failed:
                    for _ in range(12):
                        try:
                            if not page.evaluate(_CLICK_NEXT_JS):
                                break
                            page.wait_for_timeout(400)
                        except Exception:
                            break
                    try:
                        for u in page.evaluate(_DOM_IMAGES_JS):
                            full = urljoin(page.url or url, u)
                            h = util.host_key(full)
                            if h in main_hosts or h in extra_hosts:
                                pending_images.add(full)
                    except Exception:
                        pass
                    _save_page(page, url, seen, raw, fh, stats)

            done = min(start + len(wave), total)
            if done % max(1, workers * 5) < workers or done == total:
                fh.flush()
                elapsed = max(0.1, time.time() - started)
                rate = done / elapsed
                eta = (total - done) / rate / 60 if rate else 0
                line = (
                    f"[crawl] {done}/{total}　頁面 {stats['pages']}、資料 {stats['api']}、"
                    f"資源 {stats['assets']}　{util.human_size(stats['bytes'])}　"
                    f"{rate:.1f} 頁/秒　剩約 {eta:.0f} 分"
                )
                log(line)
                try:
                    progress_path.write_text(
                        f"{time.strftime('%H:%M:%S')}\n{line}\n", encoding="utf-8"
                    )
                except OSError:
                    pass

        if pending_images and with_media:
            todo = sorted(u for u in pending_images if u not in seen)
            if todo:
                log(f"[crawl] 補抓 API／延遲載入圖片 {len(todo)} 張")
                for u in todo:
                    h = util.host_key(u)
                    is_extra = h in extra_hosts
                    if h not in main_hosts and not is_extra:
                        continue
                    try:
                        resp = _get_with_retry(context, u)
                        _store_item(
                            u, resp.body(), resp.headers.get("content-type", ""),
                            "image", profile, raw, seen, fh, stats,
                            host=h, is_extra=is_extra,
                        )
                    except Exception:
                        continue
                fh.flush()

        if ws_messages:
            try:
                (base / "websocket.jsonl").write_text(
                    "\n".join(json.dumps(m, ensure_ascii=False) for m in ws_messages) + "\n",
                    encoding="utf-8",
                )
                log(f"[crawl] 記錄 WebSocket 訊息 {len(ws_messages)} 則")
            except OSError:
                pass

        for page in pool:
            try:
                page.close()
            except Exception:
                pass
    finally:
        fh.close()
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if pw is not None:
            try:
                pw.stop()
            except Exception:
                pass

    stats["elapsed"] = round(time.time() - started, 1)
    return stats


def fill_images(profile: dict, log=print) -> dict:
    """從既有快取的 API 快照補抓漏掉的圖片，不重新抓頁面。"""
    name = profile["name"]
    base = cache_dir(name)
    raw = base / "raw"
    meta_path = base / "meta.jsonl"
    if not meta_path.exists():
        raise SystemExit("沒有快取資料，請先執行 crawl")

    stats = {"pages": 0, "api": 0, "assets": 0, "media": 0, "bytes": 0}
    seen = _load_seen(meta_path, stats)
    main_hosts = {util.host_key(profile["start"])}
    main_hosts |= {util.host_key(h) for h in profile.get("hosts") or []}
    extra_hosts = {util.host_key(h) for h in profile.get("extra_hosts") or []}

    wanted: set[str] = set()
    for item in list(seen.values()):
        path = raw / item["file"]
        if not path.exists():
            continue
        if item.get("api"):
            try:
                obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            _collect_image_urls(obj, item["url"], wanted)
        elif item.get("kind") == "page" or str(item.get("url", "")).lower().endswith(
            (".css", ".js", ".mjs", ".html", ".htm")
        ):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            _collect_text_image_urls(text, item["url"], wanted)

    todo = []
    for u in sorted(wanted):
        if u in seen:
            continue
        h = util.host_key(u)
        if h not in main_hosts and h not in extra_hosts:
            continue
        todo.append((u, h in extra_hosts))

    log(f"[fill-images] API 快照引用 {len(wanted)} 張圖片，缺 {len(todo)} 張")
    failed_path = base / "failed-images.txt"
    if not todo:
        try:
            if failed_path.exists():
                failed_path.unlink()
        except OSError:
            pass
        return {"found": len(wanted), "added": 0, "failed": []}

    fh = meta_path.open("a", encoding="utf-8")
    added = 0
    failed: list[str] = []
    pw = None
    browser = None
    try:
        pw = sync_playwright().start()
        browser, context = launch(pw, profile)
        for u, is_extra in todo:
            try:
                resp = _get_with_retry(context, u)
                if _store_item(
                    u, resp.body(), resp.headers.get("content-type", ""),
                    "image", profile, raw, seen, fh, stats,
                    host=util.host_key(u), is_extra=is_extra,
                ):
                    added += 1
            except Exception:
                failed.append(u)
                continue
    finally:
        fh.close()
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if pw is not None:
            try:
                pw.stop()
            except Exception:
                pass

    try:
        if failed:
            failed_path.write_text("\n".join(failed) + "\n", encoding="utf-8")
        elif failed_path.exists():
            failed_path.unlink()
    except OSError:
        pass
    log(f"[fill-images] 已補抓 {added} 張，失敗 {len(failed)} 張"
        + ("（詳見 failed-images.txt）" if failed else ""))
    return {"found": len(wanted), "added": added, "failed": failed}


def purge_paths(profile: dict, pattern: str, log=print) -> int:
    """移除符合正則的快取項目，供 --refresh-path 使用。"""
    import re
    base = cache_dir(profile["name"])
    meta_path = base / "meta.jsonl"
    if not meta_path.exists():
        return 0
    rx = re.compile(pattern)
    kept: list[str] = []
    removed = 0
    for line in meta_path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            kept.append(line)
            continue
        path = item.get("path") or ""
        url = item.get("url") or ""
        if rx.search(path) or rx.search(url):
            target = base / "raw" / str(item.get("file") or "")
            if target.exists():
                target.unlink()
            removed += 1
        else:
            kept.append(line)
    meta_path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    log(f"[purge] 已移除 {removed} 筆符合 {pattern} 的快取")
    return removed
