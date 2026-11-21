"""Trwałe przechowywanie materiałów (SQLite – zero konfiguracji, jeden plik)."""
import json
import os
import sqlite3
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("FTF_DB", os.path.join(ROOT, "data", "ftf.sqlite"))
_lock = threading.RLock()


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.execute("CREATE TABLE IF NOT EXISTS materials (id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT, data TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS thumbs (id INTEGER PRIMARY KEY, data TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT)")
    return c


def add(rec, thumb=None):
    with _lock, _conn() as c:
        cur = c.execute("INSERT INTO materials (created, data) VALUES (?, ?)", (rec.get("date"), json.dumps(rec, ensure_ascii=False)))
        rid = cur.lastrowid
        if thumb:
            c.execute("INSERT OR REPLACE INTO thumbs (id, data) VALUES (?, ?)", (rid, thumb))
        return rid


def update(rid, rec):
    with _lock, _conn() as c:
        c.execute("UPDATE materials SET data=? WHERE id=?", (json.dumps(rec, ensure_ascii=False), rid))


def all_items():
    with _lock, _conn() as c:
        rows = c.execute("SELECT id, data FROM materials ORDER BY id").fetchall()
    out = []
    for rid, data in rows:
        d = json.loads(data)
        d["id"] = rid
        out.append(d)
    return out


def get(rid):
    with _lock, _conn() as c:
        r = c.execute("SELECT data FROM materials WHERE id=?", (rid,)).fetchone()
    if not r:
        return None
    d = json.loads(r[0])
    d["id"] = rid
    return d


def thumb(rid):
    with _lock, _conn() as c:
        r = c.execute("SELECT data FROM thumbs WHERE id=?", (rid,)).fetchone()
    return r[0] if r else None


def thumb_ids():
    with _lock, _conn() as c:
        return {r[0] for r in c.execute("SELECT id FROM thumbs").fetchall()}


def delete(rid):
    with _lock, _conn() as c:
        c.execute("DELETE FROM materials WHERE id=?", (rid,))
        c.execute("DELETE FROM thumbs WHERE id=?", (rid,))


def clear():
    with _lock, _conn() as c:
        c.execute("DELETE FROM materials")
        c.execute("DELETE FROM thumbs")
        c.execute("DELETE FROM sqlite_sequence WHERE name='materials'")


def kv_get(k, default=None):
    with _lock, _conn() as c:
        r = c.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    return json.loads(r[0]) if r else default


def kv_set(k, v):
    with _lock, _conn() as c:
        c.execute("INSERT OR REPLACE INTO kv (k, v) VALUES (?, ?)", (k, json.dumps(v, ensure_ascii=False)))
