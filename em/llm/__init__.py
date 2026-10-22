"""llm 域统一入口：三级降级 classify()。

优先级:
  1. 云端 OpenAI 兼容 (配了 base_url+model+key)
  2. 本地 Ollama (配了 backend=ollama + model, 本地服务可达)
  3. 正则关键词 (前两者都不可用/失败) —— 永不崩

每级成功返回结果; 全部失败才落到正则, 正则永不抛异常。
"""
from __future__ import annotations

import json
from typing import Any, Optional

from em.config import Config
from em.llm import openai_compat, ollama, regex_fallback, desensitize
from em.llm.regex_fallback import classify as _regex


def _find_proxy() -> Optional[str]:
    """找一个开着的代理端口, 没有返回 None (直连)。仅云端 OpenAI 需要。"""
    import socket
    for port in ("7890", "7897", "7891", "1080", "10808"):
        try:
            s = socket.create_connection(("127.0.0.1", int(port)), timeout=1)
            s.close()
            return f"http://127.0.0.1:{port}"
        except Exception:
            continue
    return None


def _extract_json(text: str) -> dict:
    """从 LLM 回复里抽 JSON (容错 ```json 包裹)。"""
    import re
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if m:
        return json.loads(m.group(1))
    m = re.search(r"(\{.*\})", text, re.S)
    if m:
        return json.loads(m.group(1))
    raise ValueError("LLM 未返回 JSON: " + text[:200])


def _prompt_for(mails: list[dict]) -> str:
    """组 prompt: 读 prompts/classify.md + 邮件列表 (剔除超长 base64)。"""
    from pathlib import Path
    pfile = Path(__file__).resolve().parent.parent.parent / "prompts" / "classify.md"
    base = pfile.read_text(encoding="utf-8") if pfile.exists() else "对这些邮件分类为 需要我处理/重要通知/资讯速览。"
    trimmed = []
    for m in mails:
        m2 = {k: v for k, v in m.items() if k != "images"}
        m2["image_count"] = len(m.get("images", []))
        trimmed.append(m2)
    return base + "\n\n## 邮件列表\n" + json.dumps(trimmed, ensure_ascii=False, indent=2)


def classify(cfg: Config, mails: list[dict]) -> tuple[dict[str, Any], str]:
    """对邮件列表分类。返回 (result, backend_used)。

    result 结构:
      {categories: {类别: [项]}, todo: [str], summary: str, fallback: bool}
    backend_used: "openai" | "ollama" | "regex"
    """
    all_images: list = []
    for m in mails:
        all_images.extend(m.get("images", []))
    prompt = _prompt_for(mails)
    user_msgs = [{"role": "user", "content": prompt}]

    # 1. 云端 OpenAI 兼容
    if cfg.llm_backend == "openai" and cfg.llm_enabled and cfg.llm_model and cfg.llm_api_key:
        try:
            proxy = _find_proxy()
            raw = openai_compat.call(cfg.llm_base_url, cfg.llm_model, cfg.llm_api_key,
                                     user_msgs, images=all_images or None, proxy=proxy)
            return _extract_json(raw), "openai"
        except Exception as e:
            print(f"[llm] 云端失败({e}), 试 Ollama…", file=__import__("sys").stderr)

    # 2. 本地 Ollama
    if cfg.llm_backend == "ollama" and cfg.llm_enabled and cfg.llm_model:
        try:
            raw = ollama.call(cfg.llm_model, user_msgs, base_url=cfg.llm_base_url or "http://localhost:11434",
                               images=all_images or None)
            return _extract_json(raw), "ollama"
        except Exception as e:
            print(f"[llm] Ollama 失败({e}), 降到正则…", file=__import__("sys").stderr)

    # 3. 正则兜底 (永不崩)
    res = _regex(mails)
    res["backend"] = "regex"
    return res, "regex"
