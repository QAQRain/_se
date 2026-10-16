"""資料庫連線與初始化。"""
import os
import sqlite3
import hashlib
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "sas.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

_tls = threading.local()


def get_conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    _tls.conns = getattr(_tls, "conns", [])
    _tls.conns.append(conn)
    return conn


def close_all():  # 請求結束時關閉本執行緒仍未關閉的連線（防 exception 洩漏鎖）
    for conn in getattr(_tls, "conns", []):
        try:
            conn.close()
        except Exception:
            pass
    _tls.conns = []


def hash_pw(plain):
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def row_to_dict(row):
    return dict(row) if row is not None else None


def rows_to_list(rows):
    return [dict(r) for r in rows]


def init_db():
    conn = get_conn()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def is_seeded():
    conn = get_conn()
    try:
        n = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        return n > 0
    except Exception:
        return False
    finally:
        conn.close()