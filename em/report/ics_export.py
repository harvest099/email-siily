"""ICS 日历导出：把某天"需处理 + 有截止时间"的事项写成 .ics, 可导入任意日历。

输出写到 out_dir/calendar_YYYY-MM-DD.ics, 返回 Path。
只挑 needs_action 且有 deadline 的, 其余不进日历 (YAGNI)。
deadline 形如 YYYY-MM-DD[ HH:MM] / ISO; 解析不了就跳过该条, 不崩。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


def _parse_dt(v: Optional[str]) -> Optional[datetime]:
    """把 deadline 字符串解析成 naive datetime。支持 ISO / YYYY-MM-DD[ HH:MM]。"""
    if not v:
        return None
    v = v.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return None


def export_day(conn, day: str, out_dir: Path) -> Path:
    """导出 day 的事项为 .ics。返回 ics 路径。"""
    from em.storage.sqlite_store import query_date_range

    rows = query_date_range(conn, day, day)
    items = []
    for r in rows:
        if not r.get("needs_action"):
            continue
        dt = _parse_dt(r.get("deadline"))
        if dt is None:
            # 需处理但没可解析截止时间 → 放到当天 09:00 提醒
            dt = datetime.strptime(day, "%Y-%m-%d").replace(hour=9, minute=0)
        items.append((r, dt))

    out_dir.mkdir(parents=True, exist_ok=True)
    ics_path = out_dir / f"calendar_{day}.ics"

    dtstamp = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//em-email-manager//ICS//ZH",
        "CALSCALE:GREGORIAN",
    ]
    for i, (r, dt) in enumerate(items, start=1):
        end = dt.replace(minute=0, second=0) + timedelta(minutes=59)
        subj = (r["subject"] or "待办").replace("\\", "\\\\")
        frm = (r.get("fr") or "").replace(",", "，")
        reason = (r.get("reason") or "").replace(",", "，")
        summary = f"[邮箱待办] {subj}"[:200]
        desc = f"来自: {frm} / 类别: 需处理 / 原因: {reason}"
        lines += [
            "BEGIN:VEVENT",
            f"UID:em-{day}-{i}@email-manager",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART:{dt.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:{_esc(summary)}",
            f"DESCRIPTION:{_esc(desc)}",
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            "DESCRIPTION:邮箱待办提醒",
            "TRIGGER:-PT15M",
            "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    # ICS 要求 CRLF 行尾
    ics_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    return ics_path


def _esc(s: str) -> str:
    """ICS 文本转义: 反斜杠 / 分号 / 逗号 / 换行。"""
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
