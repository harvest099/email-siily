#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tool_imap.py — 只读 IMAP 抓取工具（支持 QQ / Gmail / 163 等）
用法：python tools/tool_imap.py [小时数]
输出：data/YYYY-MM-DD.json （新邮件）+ 更新 data/.processed（去重表）
"""
import imaplib, email, json, re, sys, datetime, base64
from email.header import decode_header
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ATTACH_DIR = DATA / "attachments"

def _log(msg):
    print(msg, file=sys.stderr)

def load_cfg():
    cfg_path = ROOT / "config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"找不到 {cfg_path}，请从 config.yaml.example 复制并填写")
    raw = open(cfg_path, encoding="utf-8").read()
    out = {}
    m = re.search(r"user:\s*(\S+)", raw)
    if not m: raise ValueError("config.yaml 缺少 user")
    out["user"] = m.group(1)
    m = re.search(r"auth_code:\s*(\S+)", raw) or re.search(r"app_password:\s*(\S+)", raw)
    if not m: raise ValueError("config.yaml 缺少 auth_code")
    out["pw"] = m.group(1).strip('"')
    m = re.search(r"hours:\s*(\S+)", raw); out["hours"] = float(m.group(1)) if m else 24
    m = re.search(r"max_per_run:\s*(\S+)", raw); out["max"] = int(m.group(1)) if m else 50
    m = re.search(r"host:\s*(\S+)", raw);  out["host"] = m.group(1) if m else "imap.qq.com"
    m = re.search(r"port:\s*(\S+)", raw);   out["port"] = int(m.group(1)) if m else 993
    return out

def decode_mime_words(s):
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

def _body_from_bytes(raw):
    """从 payload 字节里取纯文本，尽量猜对编码"""
    text = raw.decode("utf-8", "replace")
    if "替代" in text or "Ã" in text[:200]:
        try:
            text = raw.decode("gbk")
        except (UnicodeDecodeError, LookupError):
            pass
    return text

def get_text(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition", "")).lower():
                payload = part.get_payload(decode=True)
                if payload is None:
                    p = part.get_payload()
                    body += p if isinstance(p, str) else str(p)
                else:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body += payload.decode(charset, "replace")
                    except LookupError:
                        body += _body_from_bytes(payload)
                if body.strip():
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload is None:
            p = msg.get_payload()
            body = p if isinstance(p, str) else str(p)
        else:
            charset = msg.get_content_charset() or "utf-8"
            try:
                body = payload.decode(charset, "replace")
            except LookupError:
                body = _body_from_bytes(payload)
    return re.sub(r"\n{3,}", "\n\n", body).strip()

def extract_attachments(msg, uid):
    """提取图片附件，存到 data/attachments/，返回 base64 列表"""
    ATTACH_DIR.mkdir(parents=True, exist_ok=True)
    b64_list = []
    for part in msg.walk():
        ct = part.get_content_type()
        fn = part.get_filename()
        # QQ 把图片邮件里的 JPEG 伪装成 application/octet-stream，得靠文件名认
        is_img = ct.startswith("image/") or (
            ct == "application/octet-stream"
            and re.search(r"\.(jpe?g|png|gif|bmp|webp)$", fn or "", re.I)
        )
        if not is_img:
            continue
        raw = part.get_payload(decode=True)
        if raw is None:
            continue
        safe_fn = re.sub(r"[^\w.\-]", "_", fn or f"img_{uid}_{len(b64_list)}.jpg")
        out = ATTACH_DIR / f"{uid}_{safe_fn}"
        out.write_bytes(raw)
        b64_list.append(base64.b64encode(raw).decode())
        _log(f"  [附件] {fn} → {out.name} ({len(raw)} bytes)")
    return b64_list

def main():
    hours = float(sys.argv[1]) if len(sys.argv) > 1 else None
    try:
        cfg = load_cfg()
    except FileNotFoundError as e:
        _log(str(e))
        return 1
    if hours:
        cfg["hours"] = hours

    DATA.mkdir(exist_ok=True)
    processed = DATA / ".processed"
    seen = set()
    if processed.exists():
        seen = set(processed.read_text(encoding="utf-8").split())

    now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(hours=cfg["hours"])

    _log(f"[1] 连接 {cfg['user']} @ {cfg['host']}:{cfg['port']} ...")
    try:
        imap = imaplib.IMAP4_SSL(cfg["host"], cfg["port"])
        imap.login(cfg["user"], cfg["pw"])
        imap.select("INBOX")
    except Exception as e:
        _log(f"[1] 登录失败: {e}")
        return 1
    _log("[1] 登录成功，INBOX 打开")

    since = cutoff.strftime("%d-%b-%Y")
    typ, data = imap.search(None, f"(SINCE {since})")
    ids = data[0].split()
    _log(f"[2] 过去 {cfg['hours']:.0f}h 内找到 {len(ids)} 封候选邮件")

    mails = []
    for i, mid in enumerate(ids[:cfg["max"]]):
        mid_s = mid.decode() if isinstance(mid, bytes) else str(mid)
        if mid_s in seen:
            continue
        typ, md = imap.fetch(mid_s, "(RFC822)")
        if typ != "OK" or not md or md[0] is None:
            continue
        msg = email.message_from_bytes(md[0][1])
        img_b64 = extract_attachments(msg, mid_s)
        entry = {
            "uid": mid_s,
            "from": decode_mime_words(msg.get("From", "")),
            "subject": decode_mime_words(msg.get("Subject", "")),
            "date": msg.get("Date", ""),
            "body_preview": get_text(msg)[:800],
            "images": img_b64,   # 图片附件 base64，LLM 视觉模型可用
        }
        mails.append(entry)
        seen.add(mid_s)
        _log(f"  - [{i+1}] {entry['from'][:40]} | {entry['subject'][:50]}")

    imap.logout()

    processed.write_text("\n".join(sorted(seen)), encoding="utf-8")

    day = now.strftime("%Y-%m-%d")
    out = DATA / f"{day}.json"
    if out.exists():
        out.unlink()
    out.write_text(json.dumps(mails, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"\n[3] 新增 {len(mails)} 封 → {out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
