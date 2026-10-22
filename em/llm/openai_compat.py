"""OpenAI 兼容接口：任意 base_url + model + key (OpenAI / 任意兼容网关 / 自建 vLLM)。

走此后端前, 正文先经 desensitize.py 脱敏再发, 控制 PII 外泄面。
用 requests (已装) 而非 urllib, 因 Windows 全局系统代理会劫持 urllib 直连。
"""
from __future__ import annotations

from typing import Optional

from em.llm.desensitize import desensitize


def _mime(b64: str) -> str:
    """按 base64 前缀嗅探图片 MIME, 不写死 jpeg (PNG/JPEG/GIF)。"""
    if b64.startswith("iVBOR"):
        return "image/png"
    if b64.startswith("/9j/"):
        return "image/jpeg"
    if b64.startswith("R0lB"):
        return "image/gif"
    return "image/jpeg"


def _shrink(b64: str, max_side: int = 768) -> str:
    """把 base64 图压到 max_side 像素内 (JPEG 质量 80), 减小发云体积。失败返回原图。"""
    import base64 as _b64
    import io
    try:
        from PIL import Image
        raw = _b64.b64decode(b64)
        im = Image.open(io.BytesIO(raw))
        im.thumbnail((max_side, max_side))
        out = io.BytesIO()
        im.convert("RGB").save(out, "JPEG", quality=80)
        return _b64.b64encode(out.getvalue()).decode()
    except Exception:
        return b64


def call(
    base_url: str,
    model: str,
    key: str,
    messages: list[dict],
    images: Optional[list] = None,
    timeout: int = 120,
    proxy: Optional[str] = None,
) -> str:
    """调 OpenAI 兼容 chat/completions, 返回文本。失败抛 Exception。"""
    import requests

    base_url = base_url.rstrip("/")
    url = base_url + "/chat/completions"

    msgs = [dict(m) for m in messages]
    if images:
        # 发云前压缩: 4B 视觉模型 768px 足够识图, 大原图(2MB+) 会让请求超时
        images = [_shrink(b64) for b64 in images]
        img_content = [
            {"type": "image_url", "image_url": {"url": f"data:{_mime(b64)};base64,{b64}"}}
            for b64 in images if b64
        ]
        img_content.append({
            "type": "text",
            "text": "请结合以上图片和邮件内容分类。图片中若有文字/日期/金额, 优先采信图片。",
        })
        msgs.append({"role": "user", "content": img_content})

    body = {"model": model, "messages": msgs, "max_tokens": 4096}

    # 脱敏发生在发往云端前, 对 text 内容统一过一遍 (图片不做)
    for m in body["messages"]:
        c = m.get("content")
        if isinstance(c, str):
            m["content"] = desensitize(c)

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    s = requests.Session()
    s.trust_env = False  # 不读系统/环境变量代理, 直连
    try:
        r = s.post(url, json=body, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except requests.HTTPError as e:
        try:
            detail = e.response.text[:300]
        except Exception:
            detail = str(e)
        raise RuntimeError(f"OpenAI 兼容接口失败: {detail}")
