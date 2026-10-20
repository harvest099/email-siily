#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
report.py — 简报生成器
读取 data/classified_*.json，输出 Markdown 简报到 data/ 目录并同步到桌面（固定文件名覆盖）
"""
import json, os, datetime, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DESKTOP = Path(os.path.expanduser("~/Desktop"))

def _log(msg):
    print(msg, file=sys.stderr)

def load_latest_classified():
    if not DATA.exists():
        return None
    files = [x for x in DATA.glob("classified_*.json")]
    files.sort(key=lambda p: p.name, reverse=True)
    if not files:
        _log("没有分类结果，先跑 classify.py")
        return None
    return json.loads(files[0].read_text(encoding="utf-8")), files[0]

def build_md(meta, src_file):
    day = meta["day"]
    model = meta.get("model", "unknown")
    result = meta.get("result", {})

    if result.get("parse_error"):
        return (f"# 简报 {day}\n\nLLM 输出解析失败，原始回复：\n"
                f"```\n{result.get('raw_llm_response', '')}\n```\n")

    lines = [f"# 📬 每日邮箱简报 · {day}", ""]
    if result.get("summary"):
        lines += [f"**总结**：{result['summary']}", ""]

    cats = result.get("categories", {})
    for name in ["需要我处理", "重要通知", "资讯速览"]:
        items = cats.get(name, [])
        lines.append(f"## {name}（{len(items)}）")
        if not items:
            lines.append("- （无）")
        for it in items:
            dl = it.get("deadline")
            dl_str = f" ⏰ **{dl}**" if dl else ""
            lines.append(f"- **{it.get('subject', '(无主题)')}** ← {it.get('from', '?')}{dl_str}")
            if it.get("reason"):
                lines.append(f"  - 依据：{it['reason']}")
        lines.append("")

    if result.get("todo"):
        lines.append("## ✅ 待办")
        for t in result["todo"]:
            lines.append(f"- {t}")
        lines.append("")

    lines += [
        "---",
        f"*生成于 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} · 模型 {model} · 共 {meta.get('emails_count', 0)} 封邮件*",
        f"*数据来源: {os.path.basename(str(src_file))}*",
    ]
    return "\n".join(lines)

def main():
    loaded = load_latest_classified()
    if not loaded:
        return 0
    meta, src = loaded
    # 只有当天有分类结果才出简报
    day = meta["day"]
    if day != datetime.datetime.now().strftime("%Y-%m-%d"):
        _log(f"[跳过] 最新分类结果是 {day}，不是今天，不出简报")
        return 0
    md = build_md(meta, src)
    out = DATA / "daily_report.md"
    out.write_text(md, encoding="utf-8")
    _log(f"[1] 简报 → {out}")

    # 清理旧的带日期简报（只保留最新一份）
    for old in DATA.glob("report_*.md"):
        old.unlink()

    # 桌面：固定文件名，覆盖旧文件
    try:
        DESKTOP.mkdir(parents=True, exist_ok=True)
        desktop_out = DESKTOP / "📬 每日简报.md"
        desktop_out.write_text(md, encoding="utf-8")
        for old in DESKTOP.glob("📬 每日简报-*.md"):
            old.unlink()
        _log(f"[2] 已同步到桌面：{desktop_out.name}")
    except Exception as e:
        _log(f"[2] 桌面同步失败: {e}")

    print(md)
    return 0

if __name__ == "__main__":
    sys.exit(main())
