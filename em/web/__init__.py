"""em/web — 本机只读 Web 查阅界面 (标准库 http.server, 仅绑 127.0.0.1)。

路由:
  /                    邮件列表 (分类着色 + 日期筛选)
  /mail/<uid>          单封详情 (正文 + 分类依据 + 附件图)
  /calendar/<day>.ics  下载某天 .ics
  /fetch               手动抓取按钮 (POST, 调 em.fetch)
"""
from em.web.server import main, start_server

__all__ = ["main", "start_server"]
