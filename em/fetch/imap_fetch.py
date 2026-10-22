"""IMAP 只读抓取：拉过去 N 小时邮件, 结果写 SQLite (不再只落 JSON)。

凭据从 em.config (走 keyring) 读, 不读 config.yaml 明文。
图片附件仍存 data/attachments/ (供本地 Ollama 视觉用), 但邮件正文进 SQLite。
"""
from __future__ import annotations

import base64
import datetime
import email as email_mod
import imaplib
import re
from email.header import decode_header
from pathlib import Path
from typing import Any, Optional

from em.config import Config

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
ATTACH_DIR = DATA_DIR / "attachments"


def _log(msg: str) -> None:
    print(msg, file=__import__("sys").stderr)


def decode_mime_words(s: Optional[str]) -> str:
    if not s:
        return ""
    parts = decode_header(s)
    out = []
    for p, enc in parts:
        if isinstance(p, bytes):
            out.append(p.decode(enc or "utf-8", "replace"))
        else:
            out.append(p)
    return "".join(out)


def get_text(msg: email_mod.message.Message) -> str:
    """取正文纯文本, 尽量猜对编码 (QQ 有时 gbk)。"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and \
               "attachment" not in str(part.get("Content-Disposition", "")).lower():
                payload = part.get_payload(decode=True)
                if payload is None:
                    p = part.get_payload()
                    body += p if isinstance(p, str) else str(p)
                else:
                    cs = part.get_content_charset() or "utf-8"
                    try:
                        body += payload.decode(cs, "replace")
                    except LookupError:
                        try:
                            body += payload.decode("gbk", "replace")
                        except LookupError:
                            body += payload.decode("utf-8", "replace")
                if body.strip():
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload is None:
            p = msg.get_payload()
            body = p if isinstance(p, str) else str(p)
        else:
            cs = msg.get_content_charset() or "utf-8"
            try:
                body = payload.decode(cs, "replace")
            except LookupError:
                body = payload.decode("utf-8", "replace")
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def _decoded_filename(fn: Optional[str]) -> Optional[str]:
    """把 MIME 编码的文件名 (=\?utf-8?B?...?=) 解出真实名; 纯 ASCII 名原样返回。"""
    if not fn:
        return None
    parts = decode_header(fn)
    out: list[str] = []
    for p, enc in parts:
        if isinstance(p, bytes):
            out.append(p.decode(enc or "utf-8", "replace"))
        else:
            out.append(p)
    return "".join(out) or None


def extract_images(msg: email_mod.message.Message, uid: str) -> list[str]:
    """提取图片附件存盘, 返回 base64 列表。QQ 把 JPEG 伪装成 octet-stream, 靠文件名认。

    文件名可能带 MIME 编码 (=?utf-8?B?...?=, 中文附件), 先 decode_header 解出真实名再判后缀,
    否则中文名附件的 .png 会被漏提。"""
    ATTACH_DIR.mkdir(parents=True, exist_ok=True)
    out: list[str] = []
    for part in msg.walk():
        ct = part.get_content_type()
        fn = part.get_filename()
        # QQ 中文附件名带 base64 编码, 解出真实名再判后缀
        fn_real = _decoded_filename(fn)
        is_img = ct.startswith("image/") or (
            ct == "application/octet-stream"
            and re.search(r"\.(jpe?g|png|gif|bmp|webp)$", fn_real or "", re.I)
        )
        if not is_img:
            continue
        raw = part.get_payload(decode=True)
        if raw is None:
            continue
        safe = re.sub(r"[^\w.\-]", "_", fn_real or f"img_{uid}_{len(out)}.jpg")
        (ATTACH_DIR / f"{uid}_{safe}").write_bytes(raw)
        out.append(base64.b64encode(raw).decode())
        _log(f"  [附件] {fn_real} → {len(raw)} bytes")
    return out


def fetch_recent(conn, cfg: Config) -> int:
    """抓过去 cfg.fetch_hours 小时的新邮件写 SQLite, 返回新增数。"""
    _log(f"[fetch] 连接 {cfg.imap_user}@{cfg.imap_host}:{cfg.imap_port} ...")
    try:
        imap = imaplib.IMAP4_SSL(cfg.imap_host, cfg.imap_port)
        imap.login(cfg.imap_user, cfg.imap_auth_code)
        imap.select("INBOX")
    except Exception as e:
        _log(f"[fetch] 登录失败: {e}")
        return -1
    _log("[fetch] 登录成功")

    from em.storage import upsert_mail
    now = datetime.datetime.now()
    since = (now - datetime.timedelta(hours=cfg.fetch_hours)).strftime("%d-%b-%Y")
    typ, data = imap.search(None, f"(SINCE {since})")
    ids = data[0].split()
    _log(f"[fetch] 过去 {cfg.fetch_hours:.0f}h 内 {len(ids)} 封候选")

    added = 0
    for mid in ids[: cfg.fetch_max]:
        mid_s = mid.decode() if isinstance(mid, bytes) else str(mid)
        typ, md = imap.fetch(mid_s, "(RFC822)")
        if typ != "OK" or not md or md[0] is None:
            continue
        msg = email_mod.message_from_bytes(md[0][1])
        frm = decode_mime_words(msg.get("From", ""))
        subj = decode_mime_words(msg.get("Subject", ""))
        date_raw = msg.get("Date", "")
        body = get_text(msg)
        images = extract_images(msg, mid_s)
        if upsert_mail(conn, mid_s, frm, subj, date_raw, body, images):
            added += 1
            _log(f"  + {frm[:30]} | {subj[:40]}")
    imap.logout()
    _log(f"[fetch] 新增 {added} 封")
    return added
