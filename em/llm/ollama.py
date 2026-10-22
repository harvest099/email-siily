"""Ollama 本地接口：无 key、不出机, 因此不做 PII 脱敏。

默认 base_url http://localhost:11434, 用原生 /api/chat。
"""
from __future__ import annotations

import json
import urllib.request
from typing import Optional

DEFAULT_BASE = "http://localhost:11434"


def call(
    model: str,
    messages: list[dict],
    base_url: str = DEFAULT_BASE,
    images: Optional[list] = None,
    timeout: int = 300,
) -> str:
    """调 Ollama /api/chat, 返回文本。失败抛 Exception。"""
    url = base_url.rstrip("/") + "/api/chat"
    prompt_parts: list[dict] = []
    text_msgs = []
    for m in messages:
        if isinstance(m.get("content"), str):
            text_msgs.append(m)

    body: dict = {
        "model": model,
        "messages": text_msgs,
        "stream": False,
    }
    if images:
        # Ollama 视觉: 在 messages 里加 image 字段 (base64 无 data: 前缀)
        if text_msgs:
            last = dict(text_msgs[-1])
            last["images"] = list(images)
            text_msgs[-1] = last
        else:
            text_msgs.append({"role": "user", "content": "请看图并分类。", "images": list(images)})

    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=timeout))
    return r["message"]["content"]
