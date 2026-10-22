#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""main.py — 邮箱管家唯一入口。

行为:
  1. 读配置 + 系统 keyring
  2. 无邮箱凭据 → 跑首次向导 (em/wizard.py)
  3. 有凭据 → 跑流水线: 抓取(IMAP) → 分类(LLM 三级降级) → 简报 + ICS
  4. 全部走 SQLite 存储; 旧 JSON 一次性迁移

用法:
  python main.py                 # 常规: 抓过去 24h + 分类 + 简报
  python main.py --fetch 48      # 拉过去 48h
  python main.py --range 2026-10-20 2026-10-22   # 按日期生成简报+ICS
  python main.py --web           # 启动本地 Web 查询界面 (127.0.0.1)
"""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from em import config as em_config          # noqa: E402
from em.storage import (                    # noqa: E402
    connect, latest_unclassified, store_classification, migrate_json_if_needed,
)


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _classify_all(conn, cfg: em_config.Config, conn2=None) -> int:
    """把库里未分类的邮件逐封送 LLM 三级降级, 结果写回。返回新分类数。"""
    from em.llm import classify as llm_classify

    pending = latest_unclassified(conn)
    if not pending:
        _log("[classify] 无待分类邮件")
        return 0

    # 一次批量喂 LLM (比逐封快)
    result, backend = llm_classify(cfg, pending)
    _log(f"[classify] 后端={backend}, 共 {len(pending)} 封")

    # 按 uid 回填
    uid_map: dict[str, dict] = {}
    for cat, items in (result.get("categories") or {}).items():
        for it in items:
            uid_map[str(it.get("uid", ""))] = {
                "category": cat,
                "deadline": it.get("deadline"),
                "reason": it.get("reason", ""),
                "needs_action": bool(it.get("needs_action", cat == "需要我处理")),
            }
    added = 0
    for m in pending:
        uid = str(m.get("uid", ""))
        info = uid_map.get(uid) or {"category": "资讯速览", "deadline": None,
                                    "reason": result.get("summary", ""), "needs_action": False}
        store_classification(conn, uid, info["category"], info["deadline"],
                             info["reason"], info["needs_action"], backend)
        added += 1
    return added


def _write_daily_report(conn, day: str, cfg: em_config.Config) -> str:
    """按某天生成简报 markdown, 写 data/daily_report_YYYY-MM-DD.md。"""
    from em.report.daily_report import build_markdown
    return build_markdown(conn, day, cfg)


def _export_ics(conn, day: str, out_dir: Path) -> Path:
    from em.report.ics_export import export_day
    return export_day(conn, day, out_dir)


def main() -> int:
    ap = argparse.ArgumentParser(description="邮箱管家")
    ap.add_argument("--fetch", type=float, default=None, help="拉过去 N 小时")
    ap.add_argument("--range", nargs=2, metavar=("START", "END"), help="按日期范围生成简报+ICS")
    ap.add_argument("--web", action="store_true", help="启动本地 Web 查询 (127.0.0.1:8765)")
    args = ap.parse_args()

    cfg = em_config.load()

    # 无凭据 → 向导
    if not cfg.has_credentials():
        _log("未检测到邮箱凭据, 启动首次向导…")
        from em.wizard import run as wizard_run
        if wizard_run() != 0:
            return 1
        cfg = em_config.load()

    conn = connect(cfg.imap_user)
    migrated = migrate_json_if_needed(cfg.imap_user)
    if migrated:
        _log(f"[migrate] 迁移旧 JSON {migrated} 行进 SQLite")

    if args.web:
        from em.web import start_server
        start_server(cfg, conn, host="127.0.0.1", port=8765)
        return 0

    if args.range:
        start, end = args.range
        _log(f"[range] 生成 {start} ~ {end} 简报 + ICS")
        day = start if start == end else end
        for d in _date_range(start, end):
            md = _write_daily_report(conn, d, cfg)
            ics = _export_ics(conn, d, ROOT / "data")
            _log(f"  {d}: 简报 → {md}, ICS → {ics.name}")
        return 0

    # 常规: 抓 + 分类 + 当天简报
    if args.fetch is not None:
        cfg.fetch_hours = args.fetch
    from em.fetch import fetch_recent
    added = fetch_recent(conn, cfg)
    if added < 0:
        _log("IMAP 登录失败, 检查 config.yaml / keyring 凭据或网络")
        return 1

    _classify_all(conn, cfg)

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    md_path = _write_daily_report(conn, today, cfg)
    ics_path = _export_ics(conn, today, ROOT / "data")
    _log(f"[done] 简报 → {md_path}")
    _log(f"[done] ICS  → {ics_path}")

    # 同步桌面
    if cfg.report_output:
        try:
            desktop = Path(cfg.report_output)
            desktop.parent.mkdir(parents=True, exist_ok=True)
            desktop.write_text(Path(md_path).read_text(encoding="utf-8"), encoding="utf-8")
            _log(f"[done] 桌面简报 → {desktop.name}")
        except Exception as e:
            _log(f"[warn] 桌面同步失败: {e}")
    return 0


def _date_range(start: str, end: str) -> list[str]:
    d = datetime.date.fromisoformat(start)
    e = datetime.date.fromisoformat(end)
    out = []
    while d <= e:
        out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


if __name__ == "__main__":
    sys.exit(main())
