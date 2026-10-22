"""每日简报生成：查 SQLite 某天邮件 + 分类, 出 markdown。

输出写到 data/daily_report_YYYY-MM-DD.md, 返回该路径 (str)。
纯本地数据, 不涉及网络 / 脱敏。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from em.storage.sqlite_store import DB_PATH

_CAT_ORDER = ["需要我处理", "重要通知", "资讯速览"]


def build_markdown(conn, day: str, cfg) -> str:
    """生成 day (YYYY-MM-DD) 的简报 markdown, 写文件, 返回路径。"""
    from em.storage.sqlite_store import query_date_range

    rows = query_date_range(conn, day, day)
    out_dir = Path(DB_PATH.parent)
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"daily_report_{day}.md"

    lines: list[str] = [f"# 邮箱管家 · 每日简报 · {day}", ""]

    if not rows:
        lines += ["_当天无新邮件。_", ""]
    else:
        # 汇总
        counts: dict[str, int] = {}
        for r in rows:
            cat = r["category"] or "资讯速览"
            counts[cat] = counts.get(cat, 0) + 1
        lines.append("## 概览")
        lines.append("")
        for c in _CAT_ORDER:
            if c in counts:
                lines.append(f"- **{c}**: {counts[c]} 封")
        for c in counts:
            if c not in _CAT_ORDER:
                lines.append(f"- **{c}**: {counts[c]} 封")
        lines.append("")

        for c in _CAT_ORDER:
            items = [r for r in rows if (r["category"] or "资讯速览") == c]
            if not items:
                continue
            lines.append(f"## {c}")
            lines.append("")
            for r in items:
                subj = r["subject"] or "(无主题)"
                frm = r["fr"] or ""
                dl = r["deadline"]
                reason = (r["reason"] or "").strip()
                img = r["image_count"]
                head = f"### {subj}"
                lines.append(head)
                meta = [f"> 发件人: {frm}" if frm else None,
                        f"> 截止: {dl}" if dl else None,
                        f"> 原因: {reason}" if reason else None,
                        f"> 附图: {img} 张" if img else None]
                lines.extend(x for x in meta if x)
                lines.append("")

    lines.append("")
    lines.append(f"_生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · 邮箱管家 · 只读声明: 本简报仅读取, 未代发未删除_")
    lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return str(md_path)
