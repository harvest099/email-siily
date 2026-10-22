"""首次运行向导：无凭据时交互式收集配置, 凭据写 keyring, 非敏感写 config.yaml。

调用方: em/main.py 检测到 has_credentials()==False 时 run()。
"""
from __future__ import annotations

import getpass
import os
import re
import sys
from pathlib import Path

from em import config as _config


def _ask(prompt: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    v = input(f"{prompt}{hint}: ").strip()
    return v or default


def _find_pi_key() -> str | None:
    """从 ~/.pi/agent/models.json 找 nvapi- 开头的 key (降级用)。"""
    p = Path.home() / ".pi" / "agent" / "models.json"
    if not p.exists():
        return None
    try:
        raw = p.read_text(encoding="utf-8")
    except Exception:
        return None
    m = re.search(r'"apiKey"\s*:\s*"(nvapi-[A-Za-z0-9_-]+)"', raw)
    if m:
        return m.group(1)
    m = re.search(r"nvapi-[A-Za-z0-9_-]+", raw)
    return m.group(0) if m else None


def run() -> int:
    """交互向导。返回 0 成功, 1 取消。"""
    print("=" * 50)
    print("邮箱管家 · 首次配置向导")
    print("=" * 50)
    print("凭据(邮箱授权码/API Key) 存入系统 keyring, 不落明文。")
    print("非敏感配置写入 config.yaml。\n")

    print("── IMAP 邮箱 ──")
    cur = _config.load()
    user = _ask("邮箱账号 (如 you@qq.com)", cur.imap_user)
    host = _ask("IMAP 服务器", cur.imap_host or "imap.qq.com")
    port = int(_ask("端口", str(cur.imap_port or 993)))

    print(f"\n请 {user} 的授权码/应用专用密码:")
    print("  QQ   : 邮箱设置→账户→开IMAP→生成授权码")
    print("  Gmail: 两步验证→应用专用密码")
    auth_code = getpass.getpass("授权码 (不回显): ")
    if not auth_code:
        print("未提供授权码, 向导取消。")
        return 1

    print("\n── 大模型分析 ──")
    use_llm = _ask("启用大模型分析? (y/n, 默认 y)", "y") != "n"
    cfg = _config.load()
    cfg.imap_host, cfg.imap_port, cfg.imap_user = host, port, user
    cfg.llm_enabled = use_llm

    if use_llm:
        backend = _ask("后端: openai / ollama", cfg.llm_backend or "openai").lower()
        if backend not in ("openai", "ollama"):
            backend = "openai"
        cfg.llm_backend = backend
        if backend == "openai":
            cfg.llm_base_url = _ask("Base URL (OpenAI 兼容)",
                                    cfg.llm_base_url or "https://integrate.api.nvidia.com/v1")
            key = getpass.getpass("API Key (不回显, 留空=自动找 ~/.pi/agent/models.json): ")
            if not key:
                key = _find_pi_key() or ""
                if key:
                    print(f"  自动读到 key: {key[:6]}...{key[-4:]}")
            else:
                print(f"  使用提供的 key: {key[:6]}...{key[-4:]}")
            cfg.llm_api_key = key
        else:
            cfg.llm_base_url = _ask("Ollama 地址", "http://localhost:11434")
            cfg.llm_api_key = ""
        cfg.llm_model = _ask("Model 名", cfg.llm_model or "nvidia/nemotron-3.5-super-vl-120b-a12b")

    default_out = Path(os.path.expanduser("~/Desktop")) / "每日简报.md"
    cfg.report_output = _ask("简报输出路径", cfg.report_output or str(default_out))

    _config.store_secrets(auth_code, cfg.llm_api_key)
    cfg.imap_auth_code = auth_code
    _config.write_config(cfg)
    print(f"\n完成: 配置写入 {_config.CONFIG_FILE.name}, 凭据已入系统 keyring。")
    return 0


if __name__ == "__main__":
    sys.exit(run())
