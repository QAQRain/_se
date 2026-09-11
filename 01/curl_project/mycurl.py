#!/usr/bin/env python3
import argparse
import sys

import requests


def parse_headers(raw_headers):
    headers = {}
    for item in raw_headers:
        if ":" in item:
            key, _, value = item.partition(":")
            headers[key.strip()] = value.strip()
    return headers


def build_arg_parser():
    parser = argparse.ArgumentParser(
        prog="mycurl",
        description="mycurl - 一個類似 curl 的 HTTP 客戶端工具",
    )
    parser.add_argument("url", help="要請求的 URL（例如 https://example.com/）")
    parser.add_argument(
        "-X", "--request", dest="method", default="GET",
        help="指定 HTTP 方法（GET / POST / PUT / DELETE / HEAD，預設 GET）",
    )
    parser.add_argument(
        "-H", "--header", dest="headers", action="append", default=[],
        help="自訂 request header，格式為 \"名稱: 值\"（可重複使用）",
    )
    parser.add_argument(
        "-d", "--data", dest="data",
        help="要送出的資料（POST/PUT 用），例如 \"name=hello&age=18\" 或 JSON",
    )
    parser.add_argument(
        "-j", "--json", dest="json", action="store_true",
        help="把 -d 的資料當成 JSON 格式送出",
    )
    parser.add_argument(
        "-i", "--include-headers", dest="include_headers", action="store_true",
        help="輸出時一併顯示 response header",
    )
    parser.add_argument(
        "-o", "--output", dest="output",
        help="把 response body 存到指定檔案，而不是印在螢幕上",
    )
    parser.add_argument(
        "-s", "--silent", dest="silent", action="store_true",
        help="靜默模式，不顯示錯誤以外的訊息",
    )
    parser.add_argument(
        "-t", "--timeout", dest="timeout", type=float, default=10.0,
        help="連線逾時秒數（預設 10 秒）",
    )
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    if not args.url.startswith("http://") and not args.url.startswith("https://"):
        args.url = "https://" + args.url

    headers = parse_headers(args.headers)
    method = args.method.upper()

    if method not in ("GET", "POST", "PUT", "DELETE", "HEAD", "PATCH"):
        parser.error(f"不支援的 HTTP 方法: {method}")

    kwargs = {}
    if args.data is not None:
        if args.json:
            import json
            try:
                kwargs["json"] = json.loads(args.data)
            except json.JSONDecodeError:
                parser.error("-j 模式需要合法的 JSON 資料")
        else:
            kwargs["data"] = args.data
    elif method in ("POST", "PUT", "PATCH"):
        kwargs["data"] = ""

    if headers:
        kwargs["headers"] = headers

    try:
        response = requests.request(method, args.url, timeout=args.timeout, **kwargs)
    except requests.exceptions.RequestException as exc:
        if not args.silent:
            print(f"[錯誤] 無法完成請求: {exc}", file=sys.stderr)
        sys.exit(1)

    if not args.silent:
        print(f"[狀態碼] {response.status_code} {response.reason}")
        print(f"[耗時] {response.elapsed.total_seconds():.3f} 秒")
        print()

    if args.include_headers:
        for key, value in response.headers.items():
            print(f"{key}: {value}")
        print()

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(response.text)
        if not args.silent:
            print(f"[已儲存] response body 已寫入 {args.output}")
    else:
        sys.stdout.write(response.text + "\n")

    return 0 if response.ok else 1


if __name__ == "__main__":
    sys.exit(main())