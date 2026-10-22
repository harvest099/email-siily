"""SQLite 主存储层：邮件入库 + 日期范围查询 + 旧 JSON 迁移。

打破原 24h JSON 限制——所有抓到的邮件按 uid 去重存入 SQLite, 支持任意历史日期检索。
表结构:
- mails      : 抓取到的原始邮件 (一 uid 一行)
- classified : 分类结果 (一 uid 一行)
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "em.db"


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS mails (
            uid        TEXT PRIMARY KEY,
            from_addr TEXT NOT NULL,
            subject    TEXT NOT NULL,
            date_raw   TEXT,
            body       TEXT,
            image_count INTEGER DEFAULT 0,
            images     TEXT,
            fetched_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS classified (
            uid        TEXT PRIMARY KEY,
            category   TEXT,
            deadline   TEXT,
            reason     TEXT,
            needs_action INTEGER,
            model      TEXT,
            classified_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_mails_date ON mails(date_raw);
        """
    )
    conn.commit()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: 允许 Web 服务多线程复用同一连接 (本机只读, 单进程, 安全)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def upsert_mail(
    conn: sqlite3.Connection,
    uid: str,
    frm: str,
    subject: str,
    date_raw: str,
    body: str,
    images: list,
) -> bool:
    """插入一封邮件，已存在则不重复。返回是否新增。"""
    cur = conn.execute("SELECT 1 FROM mails WHERE uid = ?", (uid,))
    if cur.fetchone():
        return False
    conn.execute(
        "INSERT INTO mails (uid, from_addr, subject, date_raw, body, image_count, images, fetched_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (uid, frm, subject, date_raw, body, len(images), json.dumps(images),
         datetime.now().isoformat()),
    )
    conn.commit()
    return True


def classify_exists(conn: sqlite3.Connection, uid: str) -> bool:
    row = conn.execute("SELECT 1 FROM classified WHERE uid = ?", (uid,)).fetchone()
    return row is not None


def store_classification(
    conn: sqlite3.Connection,
    uid: str,
    category: str,
    deadline: Optional[str],
    reason: str,
    needs_action: bool,
    model: str,
) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO classified "
        "(uid, category, deadline, reason, needs_action, model, classified_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (uid, category, deadline, reason, int(needs_action), model,
         datetime.now().isoformat()),
    )
    conn.commit()


def _rfc822_to_iso(s: str) -> str:
    """把邮件头日期 (RFC822 如 'Mon, 19 Oct 2026 23:19:18 +0800') 归一成 YYYY-MM-DD。"""
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(s)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return s


def query_date_range(
    conn: sqlite3.Connection,
    start: str,
    end: str,
) -> list[dict[str, Any]]:
    """按邮件原始日期范围查询, 关联分类结果。start/end 形如 2026-10-20。

    库里 date_raw 是 RFC822 头格式, 直接比字符串会错; 这里逐行归一化后再筛选。
    """
    rows = conn.execute(
        """
        SELECT m.uid, m.from_addr AS fr, m.subject, m.date_raw, m.body,
               m.image_count, m.fetched_at,
               c.category, c.deadline, c.reason, c.needs_action, c.model
        FROM mails m
        LEFT JOIN classified c ON c.uid = m.uid
        """
    ).fetchall()
    out = []
    for r in rows:
        d = _rfc822_to_iso(r["date_raw"] or "")
        if start <= d <= end:
            out.append(dict(r))
    out.sort(key=lambda x: _rfc822_to_iso(x["date_raw"] or ""))
    return out


def latest_unclassified(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """抓到了但还没分类的邮件（喂给 LLM 层）。"""
    rows = conn.execute(
        "SELECT m.* FROM mails m WHERE NOT EXISTS "
        "(SELECT 1 FROM classified c WHERE c.uid = m.uid)"
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["images"] = json.loads(d.get("images") or "[]")
        out.append(d)
    return out


def migrate_json_if_needed() -> int:
    """一次性迁移旧 data/*.json（非 classified_ 前缀）进 SQLite。返回迁移行数。"""
    data_dir = DB_PATH.parent
    if not data_dir.exists():
        return 0
    conn = connect()
    count = 0
    for f in sorted(data_dir.glob("*.json")):
        if f.name.startswith("classified_"):
            continue
        try:
            mails = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for m in mails:
            uid = str(m.get("uid", ""))
            if not uid:
                continue
            if upsert_mail(conn, uid, m.get("from", ""), m.get("subject", ""),
                           m.get("date", ""), m.get("body_preview", ""),
                           m.get("images", [])):
                count += 1
    # 迁移旧 classified_*.json
    for f in sorted(data_dir.glob("classified_*.json")):
        try:
            meta = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        result = meta.get("result", {})
        for cat, items in (result.get("categories") or {}).items():
            for it in items:
                uid = str(it.get("uid", ""))
                if not uid:
                    continue
                store_classification(
                    conn, uid, cat, it.get("deadline"), it.get("reason", ""),
                    bool(it.get("needs_action", cat == "需要我处理")),
                    meta.get("model", "unknown"),
                )
    conn.close()
    return count
