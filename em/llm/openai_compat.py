"""OpenAI 兼容接口：任意 base_url + model + key (OpenAI / 任意兼容网关 / 自建 vLLM)。

走此后端前, 正文先经 desensitize.py 脱敏再发, 控制 PII 外泄面。
"""
from __future__ import annotations

import json
import urllib.request
from typing import Optional

from em.llm.desensitize import desensitize


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
    base_url = base_url.rstrip("/")
    url = base_url + "/chat/completions"

    msgs = [dict(m) for m in messages]
    if images:
        img_content = [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            for b64 in images
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

    data = json.dumps(body).encode()
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers)

    if proxy:
        ph = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        opener = urllib.request.build_opener(ph)
        r = json.load(opener.open(req, timeout=timeout))
    else:
        r = json.load(urllib.request.urlopen(req, timeout=timeout))
    return r["choices"][0]["message"]["content"]
