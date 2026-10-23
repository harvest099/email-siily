"""em/web/server.py — 本机只读 Web 界面 (标准库 ThreadingHTTPServer, 仅 127.0.0.1)。

路由:
  /                   邮件列表 (分类着色 + 日期筛选)
  /mail/<uid>         单封详情 (正文 + 分类依据 + 截止 + ICS 链接)
  /calendar/<day>.ics 下载某天 .ics
  /fetch              POST 手动抓取 (em.fetch.fetch_recent)

用法: python main.py --web   或   python -m em.web.server
仅本机可访问, 无鉴权 (绑 127.0.0.1)。
"""
from __future__ import annotations

import html
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from em import config as em_config
from em.storage import sqlite_store as s
from em.report import ics_export
from em.web import templates as T


def _cat_class(cat: str | None) -> str:
    """分类 → css 色组 (0 处理 / 1 重要 / 2 资讯 / 其他)。"""
    if not cat:
        return "c3"
    return {"需要我处理": "c0", "重要通知": "c1", "资讯速览": "c2"}.get(cat, "c3")


def _esc(s: str) -> str:
    return html.escape(s or "", quote=False)


class Handler(BaseHTTPRequestHandler):
    # --- 响应工具 ---
    def _send(self, body: bytes, ctype: str = "text/html; charset=utf-8", status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _page(self, title: str, content: str) -> bytes:
        return T.PAGE.format(title=_esc(title), content=content).encode()

    # --- 路由 ---
    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/") or "/"
        conn = s.connect(self._user())
        try:
            if path == "/fetch":
                return self._fetch(conn)
            if path.startswith("/mail/"):
                return self._mail(conn, path[6:])
            if path.startswith("/calendar/") and path.endswith(".ics"):
                return self._ics(conn, path[len("/calendar/"):-4])
            return self._list(conn, path)
        except Exception as e:
            self._send(self._page("错误", f"<h1>错误</h1><div class='body'>{_esc(str(e))}</div>"), status=500)

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/") or "/"
        conn = s.connect(self._user())
        if path == "/fetch":
            return self._fetch(conn)
        self._send(b"not found", "text/plain", 404)

    def _user(self):
        """本服务绑定哪个账号的库: 启动时由 start_server 设到 self.server 上。"""
        return getattr(self.server, "em_user", "")

    # --- 页面 ---
    def _list(self, conn, path: str):
        rows = s.query_date_range(conn, "0001-01-01", "9999-12-31")
        last = conn.execute("SELECT MAX(fetched_at) FROM mails").fetchone()[0] or "无"
        fr_param = self._q("from")
        if fr_param:
            rows = [r for r in rows if self._day(r) >= fr_param]
        content_rows = "\n".join(
            T.ROW.format(
                date=s._rfc822_to_iso(r["date_raw"] or ""), fr=_esc(r["fr"]), uid=_esc(r["uid"]),
                subject=_esc(r["subject"]), cat=_esc(r["category"] or "未分类"),
                cls=_cat_class(r["category"]),
            ) for r in reversed(rows)
        ) or "<tr><td colspan=4 class='meta'>暂无邮件 — 点上方'手动抓取'或跑 main.py</td></tr>"
        body = T.LIST.format(count=len(rows), last=_esc(last), rows=content_rows,
                             from_date=fr_param or "")
        self._send(self._page("列表", body))

    def _mail(self, conn, uid: str):
        r = conn.execute(
            """SELECT m.uid, m.from_addr AS fr, m.subject, m.date_raw, m.body, m.image_count,
                      c.category, c.deadline, c.reason, c.needs_action
               FROM mails m LEFT JOIN classified c ON c.uid=m.uid WHERE m.uid=?""",
            (uid,),
        ).fetchone()
        if not r:
            self._send(self._page("未找到", "<h1>未找到</h1><p><a href='/'>返回列表</a></p>"), status=404)
            return
        d = self._day(r)
        action = f"<span class='tag' style='color:#d29922'>需处理</span>" if r["needs_action"] else ""
        deadline = f"<div class='meta'>截止: {_esc(r['deadline'])}</div>" if r["deadline"] else ""
        body = T.MAIL.format(
            subject=_esc(r["subject"]), fr=_esc(r["fr"]), date=d,
            cat=_esc(r["category"] or "未分类"), cls=_cat_class(r["category"]),
            action=action, reason=_esc(r["reason"] or ""), deadline=deadline,
            body=_esc(r["body"] or "(无正文)"),
        )
        self._send(self._page(_esc(r["subject"]), body))

    def _ics(self, conn, day: str):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            self._send(b"bad day", "text/plain", 400)
            return
        out = ics_export.export_day(conn, day, s.DATA_DIR)
        data = out.read_bytes() if out.exists() else b"no events"
        self.send_response(200)
        self.send_header("Content-Type", "text/calendar; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{out.name}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _fetch(self, conn):
        """手动抓取: 调 em.fetch.fetch_recent (需要 keyring 有凭据)。"""
        cfg = em_config.load()
        if not cfg.has_credentials():
            self._send(self._page("抓取", "<h1>无凭据</h1><p class='meta'>先在终端跑 <code>python main.py</code> 走首次向导, 或填 config.yaml + keyring。</p><p><a href='/'>返回列表</a></p>"))
            return
        from em.fetch import fetch_recent
        try:
            n = fetch_recent(conn, cfg)
        except Exception as e:
            self._send(self._page("抓取", f"<h1>抓取失败</h1><div class='body'>{_esc(str(e))}</div><p><a href='/'>返回列表</a></p>"))
            return
        self._send(self._page("抓取", f"<h1>抓取完成</h1><div class='result'>新增 {n} 封</div><p><a href='/'>返回列表</a></p>"))

    # --- 工具 ---
    def _q(self, key: str) -> str | None:
        m = re.search(rf"[?&]{key}=([^&]*)", self.path)
        return m.group(1) if m else None

    @staticmethod
    def _day(r) -> str:
        return s._rfc822_to_iso(r["date_raw"] or "")

    def log_message(self, *a):
        pass


def start_server(cfg, conn, host: str = "0.0.0.0", port: int = 8765):
    """启动 Web。conn 是调用方按账号开的库 (main.py 传入); 独立跑时自建。

    隔离: 服务只暴露当前账号的库; 绑 0.0.0.0 手机也能访问 (同一局域网)。
    """
    user = cfg.imap_user if cfg and getattr(cfg, "imap_user", "") else ""
    # 启动时: 旧数据迁到该账号库 (一次性, 幂等)
    s.migrate_json_if_needed(user)
    _migrate_legacy_db(user)
    if conn is None:
        conn = s.connect(user)
    for p in (port, port + 1, port + 2, port + 3):
        try:
            srv = ThreadingHTTPServer((host, p), Handler)
            break
        except OSError:
            continue
    else:
        raise RuntimeError(f"端口 {port}-{port+3} 全被占用")
    srv.em_user = user          # Handler 经 self.server.em_user 读账号
    print(f"邮箱管家 Web (只读, 账号 {user or 'default'}): http://{host}:{p}  (Ctrl+C 退出)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


def _migrate_legacy_db(user: str):
    """旧单库 em.db → 账号库 em_<前缀>.db 一次性迁移 (uid 去重, 幂等)。

    只在账号库还没有邮件时才拷入; 已有数据则不动, 不会覆盖。
    """
    import sqlite3
    legacy = s.DEFAULT_DB
    if not legacy.exists() or not user:
        return
    target = s.db_path_for(user)
    n = s.connect(user).execute("SELECT COUNT(*) FROM mails").fetchone()[0]
    if n > 0:
        return  # 账号库已有数据, 不覆盖
    src, dst = sqlite3.connect(str(legacy)), sqlite3.connect(str(target))
    src.backup(dst)
    src.close(); dst.close()
    print(f"[migrate] 旧 em.db → {target.name} (账号 {user.split('@')[0]})")


def main():
    start_server(None, None)


if __name__ == "__main__":
    main()
