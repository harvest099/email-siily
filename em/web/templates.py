"""em/web/templates.py — 纯字符串 HTML 模板 (无依赖, 标准库渲染)。"""
from __future__ import annotations

PAGE = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · 邮箱管家</title>
<style>
 body{{font-family:'Segoe UI','Microsoft YaHei',sans-serif;margin:0;background:#0f1115;color:#e6e6e6}}
 .wrap{{max-width:960px;margin:0 auto;padding:16px}}
 h1{{font-size:20px}} a{{color:#58a6ff;text-decoration:none}} a:hover{{text-decoration:underline}}
 .bar{{background:#161b22;border-radius:8px;padding:10px 14px;margin:10px 0;font-size:14px}}
 table{{border-collapse:collapse;width:100%}} td,th{{border:1px solid #30363d;padding:8px 10px;font-size:13px;text-align:left}}
 th{{background:#161b22}} tr:hover td{{background:#161b22}}
 .cat{{font-weight:bold}} .c0{{color:#3fb950}} .c1{{color:#d29922}} .c2{{color:#58a6ff}} .c3{{color:#8b949e}}
 .meta{{font-size:12px;color:#8b949e}} .body{{white-space:pre-wrap;background:#161b22;padding:12px;border-radius:6px;font-size:14px;line-height:1.6;max-height:60vh;overflow:auto}}
 .tag{{display:inline-block;background:#161b22;border:1px solid #30363d;border-radius:4px;padding:2px 8px;font-size:12px;margin-right:6px}}
 button{{background:#238636;color:#fff;border:0;border-radius:6px;padding:8px 16px;font-size:14px;cursor:pointer}}
 button:hover{{background:#2ea043}} .result{{margin-top:10px;font-size:13px;color:#3fb950}}
 input[type=date]{{background:#161b22;color:#e6e6e6;border:1px solid #30363d;border-radius:4px;padding:4px 8px}}
</style></head><body><div class="wrap">{content}</div></body></html>"""

LIST = """<h1>邮件列表</h1>
<div class="bar">共 {count} 封 | 最近抓取: {last} | <a href="/fetch"><button style="padding:4px 12px;font-size:12px">手动抓取</button></a></div>
<table><tr><th>日期</th><th>发件人</th><th>主题</th><th>分类</th></tr>
{rows}
</table>
<p class="meta">筛选: <input type="date" onchange="location='/?from='+this.value" value="{from_date}"> 起 | <a href="/">全部</a></p>"""

ROW = """<tr><td class="meta">{date}</td><td>{fr}</td><td><a href="/mail/{uid}">{subject}</a></td><td class="cat {cls}">{cat}</td></tr>"""

MAIL = """<h1>{subject}</h1>
<div class="bar">
<span class="tag">{fr}</span>
<span class="tag">{date}</span>
<span class="tag cat {cls}">{cat}</span>
{action}
</div>
<div class="meta">{reason}</div>
{deadline}
<div class="body">{body}</div>
<p class="meta"><a href="/calendar/{date}.ics">下载当天日历 (.ics)</a> | <a href="/">返回列表</a></p>"""
