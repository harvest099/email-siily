"""配置模型：非敏感配置读 config.yaml，敏感凭据走 keyring（系统凭据管理器，不落明文）。

设计:
- config.yaml 只存 host/port/model/base_url 等非敏感项
- 邮箱授权码、LLM API Key 存 keyring (Windows Credential Manager), 读/写都经本模块
- 无 keyring 或 keyring 读取失败时, 允许回落到 config.yaml 明文(仅离线降级用), 但不推荐
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config.yaml"

# keyring 服务名（系统凭据管理器里的分组）
_SERVICE = "em-email-manager"


def _read_yaml() -> dict:
    """极简 YAML 读取: 支持 两层 section: -> 缩进 key: value, 不引 pyyaml。"""
    if not CONFIG_FILE.exists():
        return {}
    out: dict = {}
    cur: Optional[str] = None   # 当前 section 名
    for raw_line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, sep, val = stripped.partition(":")
        key = key.strip()
        val = val.split("#", 1)[0].strip().strip('"').strip("'")
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            if sep and val:
                out[key] = val            # 顶级 key: value
                cur = None
            else:
                out[key] = {}             # 顶级 section 头
                cur = key
        elif indent > 0 and cur is not None and sep:
            out[cur][key] = val            # 缩进的 key: value 归到当前 section
    return out


def _yaml_path(d: dict, *keys: str) -> str:
    node = d
    for k in keys:
        if not isinstance(node, dict) or k not in node:
            return ""
        node = node[k]
    return str(node)


@dataclass
class Config:
    """运行时配置对象。"""

    # IMAP (非敏感部分在 yaml, 凭据在 keyring)
    imap_host: str = "imap.qq.com"
    imap_port: int = 993
    imap_user: str = ""
    imap_auth_code: str = ""

    fetch_hours: float = 24
    fetch_max: int = 50

    # LLM
    llm_enabled: bool = False
    llm_backend: str = "openai"          # openai | ollama
    llm_base_url: str = ""              # OpenAI 兼容 / Ollama 都用 base_url
    llm_model: str = ""
    llm_api_key: str = ""              # 只存 keyring 的读缓存, 不在 yaml 明文

    report_output: str = ""            # 桌面简报路径

    def has_credentials(self) -> bool:
        """是否已配置邮箱凭据（决定要不要跑向导）。"""
        return bool(self.imap_user and self.imap_auth_code)

    def llm_ready(self) -> bool:
        """LLM 是否可用（启用 + 有模型 + 若走 OpenAI 需有 key）。"""
        if not self.llm_enabled:
            return False
        if not self.llm_model:
            return False
        if self.llm_backend == "openai" and not self.llm_api_key:
            return False
        return True


def load() -> Config:
    """从 config.yaml + keyring 组装 Config。keyring 优先，yaml 兜底。"""
    raw = _read_yaml()
    cfg = Config(
        imap_host=_yaml_path(raw, "imap", "host") or "imap.qq.com",
        imap_port=int(_yaml_path(raw, "imap", "port") or 993),
        imap_user=_yaml_path(raw, "imap", "user"),
        imap_auth_code=_yaml_path(raw, "imap", "auth_code"),
        fetch_hours=float(_yaml_path(raw, "fetch", "hours") or 24),
        fetch_max=int(_yaml_path(raw, "fetch", "max_per_run") or 50),
        llm_enabled=_yaml_path(raw, "llm", "enabled") in ("true", "True", "1"),
        llm_backend=_yaml_path(raw, "llm", "backend") or "openai",
        llm_base_url=_yaml_path(raw, "llm", "base_url"),
        llm_model=_yaml_path(raw, "llm", "model"),
        llm_api_key=_yaml_path(raw, "llm", "api_key"),
        report_output=_yaml_path(raw, "report", "output"),
    )

    # 敏感字段一律从 keyring 覆盖（系统凭据管理器, 不落盘明文）
    try:
        import keyring
        kc = keyring.get_password(_SERVICE, "imap_auth_code")
        if kc:
            cfg.imap_auth_code = kc
        lk = keyring.get_password(_SERVICE, "llm_api_key")
        if lk:
            cfg.llm_api_key = lk
    except Exception:
        pass  # keyring 不可用(如无系统凭据管理器), 回落到 yaml

    return cfg


def store_secrets(imap_auth_code: str, llm_api_key: str = "") -> None:
    """把敏感凭据写进 keyring。失败则记日志不抛（向导里会提示）。"""
    try:
        import keyring
        keyring.set_password(_SERVICE, "imap_auth_code", imap_auth_code)
        if llm_api_key:
            keyring.set_password(_SERVICE, "llm_api_key", llm_api_key)
    except Exception as e:
        print(f"[warn] keyring 写入失败: {e}（凭据将临时留在 config.yaml, 建议装 keyring）",
              file=__import__("sys").stderr)


def clear_secrets() -> None:
    try:
        import keyring
        keyring.delete_password(_SERVICE, "imap_auth_code")
        keyring.delete_password(_SERVICE, "llm_api_key")
    except Exception:
        pass


def write_config(cfg: Config) -> None:
    """把非敏感配置写回 config.yaml (敏感凭据不进文件, 走 keyring)。
    向导调用, 保证用户下次启动能读到。"""
    import os
    lines = [
        "# em 邮箱管家配置 (非敏感项; 凭据存系统 keyring, 不在此文件)",
        "# 用法: 首次运行 python main.py 自动向导, 或手改本文件",
        "",
        "imap:",
        f"  host: {cfg.imap_host}",
        f"  port: {cfg.imap_port}",
        f'  user: "{cfg.imap_user}"',
        "  # auth_code 存 keyring, 不在本文件",
        "",
        "fetch:",
        f"  hours: {cfg.fetch_hours}",
        f"  max_per_run: {cfg.fetch_max}",
        "",
        "llm:",
        f"  enabled: {'true' if cfg.llm_enabled else 'false'}",
        f"  backend: {cfg.llm_backend}",           # openai | ollama
        f"  base_url: {cfg.llm_base_url}",
        f"  model: {cfg.llm_model}",
        "  # api_key 存 keyring, 不在本文件",
        "",
        "report:",
        f"  output: {cfg.report_output or str(Path(os.path.expanduser('~/Desktop')) / '每日简报.md')}",
        "",
        "smtp:",
        "  enabled: false   # 本项目只用 IMAP 只读, 不代发不删",
    ]
    CONFIG_FILE.write_text("\n".join(lines), encoding="utf-8")
