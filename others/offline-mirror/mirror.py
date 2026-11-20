"""命令列介面：crawl／build／run／update／serve／list／info。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mirrorlib import build as build_mod  # noqa: E402
from mirrorlib import capture, discover, profile as prof  # noqa: E402
from mirrorlib import serve as serve_mod  # noqa: E402
from mirrorlib.util import human_size  # noqa: E402


def _prepare(args) -> dict:
    """取得或建立 profile，並套用命令列覆寫。"""
    if prof.exists(args.name):
        data = prof.load(args.name)
        if getattr(args, "url", None):
            data["start"] = prof.normalize_url(args.url)
    else:
        if not getattr(args, "url", None):
            raise SystemExit(f"找不到設定檔 {args.name}，第一次請提供網址：\n"
                             f"  python mirror.py crawl https://example.com --name {args.name}")
        data = prof.create_from_url(
            args.url,
            args.name,
            workers=getattr(args, "workers", None),
            delay=getattr(args, "delay", None),
            wait=getattr(args, "wait", None),
            media=None if not getattr(args, "no_media", False) else False,
            max_pages=getattr(args, "max_pages", None),
            include=getattr(args, "include", None),
            exclude=getattr(args, "exclude", None),
            port=getattr(args, "port", None),
        )
    prof.save(data)
    return data


def _crawl(data: dict, limit: int, refresh: bool, refresh_path: str = "") -> dict:
    if refresh_path:
        capture.purge_paths(data, refresh_path)
    urls, method = discover.discover(data, limit=limit)
    print(f"[discover] 使用 {method}，共 {len(urls)} 頁待抓", flush=True)
    if not urls:
        raise SystemExit("找不到任何頁面，請確認網址或調整 include／exclude 規則")
    return capture.crawl(data, urls, refresh=refresh)


def cmd_crawl(args) -> int:
    if args.refresh and args.limit:
        raise SystemExit("錯誤：--refresh 會清掉整份快取，不能和 --limit 一起用（會只剩幾頁）")
    if args.refresh and getattr(args, "refresh_path", None):
        raise SystemExit("錯誤：--refresh 與 --refresh-path 不能同時使用")
    data = _prepare(args)
    stats = _crawl(data, args.limit, args.refresh, getattr(args, "refresh_path", ""))
    print(f"[crawl] 完成：頁面 {stats['pages']}、資料 {stats['api']}、"
          f"資源 {stats['assets']}、共 {human_size(stats['bytes'])}", flush=True)
    print(f"[crawl] 接著執行：python mirror.py build {data['name']}")
    return 0


def cmd_build(args) -> int:
    data = prof.load(args.name)
    result = build_mod.build(data)
    print("[build] 完成")
    print(f"  輸出：{prof.out_dir(args.name)}")
    print(f"  模式：{result['mode']}　頁面：{result['served_pages']}　"
          f"資料：{result['api']}　資源：{result['assets']}")
    print(f"  體積：{result['size_mb']} MB")
    print(f"  啟動：python mirror.py serve {args.name}")
    return 0


def cmd_run(args) -> int:
    if args.refresh and args.limit:
        raise SystemExit("錯誤：--refresh 會清掉整份快取，不能和 --limit 一起用（會只剩幾頁）")
    if args.refresh and getattr(args, "refresh_path", None):
        raise SystemExit("錯誤：--refresh 與 --refresh-path 不能同時使用")
    data = _prepare(args)
    _crawl(data, args.limit, args.refresh, getattr(args, "refresh_path", ""))
    return cmd_build(args)


def cmd_update(args) -> int:
    data = prof.load(args.name)
    stats = _crawl(data, 0, False)
    print(f"[crawl] 完成：頁面 {stats['pages']}、資料 {stats['api']}、"
          f"資源 {stats['assets']}、共 {human_size(stats['bytes'])}", flush=True)
    capture.fill_images(data)
    return cmd_build(args)


def cmd_fill_images(args) -> int:
    data = prof.load(args.name)
    result = capture.fill_images(data)
    print(f"[fill-images] 完成：快照引用 {result['found']} 張、新增 {result['added']} 張、"
          f"失敗 {len(result.get('failed', []))} 張")
    return 0


def cmd_serve(args) -> int:
    data = prof.load(args.name)
    site = prof.out_dir(args.name)
    if not site.exists():
        raise SystemExit(f"找不到輸出資料夾 {site}，請先執行 python mirror.py build {args.name}")
    port = args.port or int(data.get("port") or 8080)
    return serve_mod.serve_site(site, port, open_browser=args.open)


def cmd_list(args) -> int:
    names = prof.list_names()
    if not names:
        print("目前沒有任何站台設定（sites/ 是空的）")
        return 0
    for name in names:
        data = prof.load(name)
        built = prof.out_dir(name).exists()
        print(f"{name:20} {data['start']}　{'已建置' if built else '未建置'}")
    return 0


def cmd_info(args) -> int:
    data = prof.load(args.name)
    print(f"名稱：{data['name']}")
    print(f"網址：{data['start']}")
    print(f"網域：{', '.join(data['hosts'])}")
    if data.get("extra_hosts"):
        print(f"額外網域：{', '.join(data['extra_hosts'])}")
    print(f"最多頁數：{data['max_pages']}　平行分頁：{data['workers']}　"
          f"媒體：{'開' if data['media'] else '關'}")
    print(f"模式：{data['mode']}　連接埠：{data['port']}")
    manifest = prof.out_dir(args.name) / "manifest.json"
    if manifest.exists():
        import json
        info = json.loads(manifest.read_text(encoding="utf-8"))
        print(f"最近建置：{info.get('built_at')}　頁面 {info.get('served_pages')}　"
              f"資料 {info.get('api')}　{info.get('size_mb')} MB")
    else:
        cache = prof.cache_dir(args.name) / "meta.jsonl"
        if cache.exists():
            lines = sum(1 for _ in cache.open(encoding="utf-8"))
            print(f"快取記錄：{lines} 筆（尚未 build）")
        else:
            print("尚未抓取")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mirror.py",
        description="把指定網站抓成本機可離線瀏覽的副本",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("crawl", help="抓取網站並存進快取")
    p.add_argument("url", nargs="?", default=None,
                   help="起始網址；已有設定檔時可省略，直接沿用設定檔")
    p.add_argument("--name", required=True, help="站台名稱（英數、底線、減號）")
    p.add_argument("--limit", type=int, default=0, help="只抓前 N 頁（測試用）")
    p.add_argument("--max-pages", type=int, default=None, help="頁數上限")
    p.add_argument("--workers", type=int, default=None, help="同時開啟的分頁數")
    p.add_argument("--delay", type=float, default=None, help="每頁額外等待秒數")
    p.add_argument("--wait", type=float, default=None, help="頁面載入後等待秒數")
    p.add_argument("--no-media", action="store_true", help="不下載圖片、影片、字型")
    p.add_argument("--include", action="append", default=None, help="只抓符合此正則的網址（可重複）")
    p.add_argument("--exclude", action="append", default=None, help="排除符合此正則的網址（可重複）")
    p.add_argument("--port", type=int, default=None, help="預設連接埠（寫進設定檔）")
    p.add_argument("--refresh", action="store_true", help="清掉舊快取重新抓")
    p.add_argument("--refresh-path", default=None,
                   help="只重抓符合此正則的路徑（不清除其他快取）")
    p.set_defaults(func=cmd_crawl)

    p = sub.add_parser("build", help="把快取打包成離線網站")
    p.add_argument("name")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("fill-images", help="從既有 API 快照補抓漏掉的圖片")
    p.add_argument("name")
    p.set_defaults(func=cmd_fill_images)

    p = sub.add_parser("run", help="抓取後直接打包")
    p.add_argument("url")
    p.add_argument("--name", required=True)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--max-pages", type=int, default=None)
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--delay", type=float, default=None)
    p.add_argument("--wait", type=float, default=None)
    p.add_argument("--no-media", action="store_true")
    p.add_argument("--include", action="append", default=None)
    p.add_argument("--exclude", action="append", default=None)
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--refresh-path", default=None,
                   help="只重抓符合此正則的路徑（不清除其他快取）")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("update", help="依既有設定重新抓取並打包")
    p.add_argument("name")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("serve", help="啟動本機伺服器")
    p.add_argument("name")
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--open", action="store_true", help="啟動後自動開啟瀏覽器")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("list", help="列出所有站台")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("info", help="顯示單一站台資訊")
    p.add_argument("name")
    p.set_defaults(func=cmd_info)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"錯誤：{exc}")
        return 1
    except ValueError as exc:
        print(f"錯誤：{exc}")
        return 1
    except KeyboardInterrupt:
        print("\n已中止")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
