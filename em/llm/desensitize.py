"""PII 脱敏：发往云端 LLM 前, 把正文里的手机号/银行卡/身份证/邮箱等打码, 降低隐私外泄面。

只在「走 OpenAI 兼容云端」时调用；本地 Ollama 不出机, 不脱敏。
"""
from __future__ import annotations

import re

# 手机号: 11 位, 1 开头 (中国)
_PHONE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
# 身份证: 18 位 (17 位数字+X) 或 15 位
_IDCARD = re.compile(r"(?<!\d)(\d{17}[\dXx]|\d{15})(?!\d)")
# 银行卡: 13-19 位纯数字
_BANKCARD = re.compile(r"(?<!\d)(\d{13,19})(?!\d)")
# 邮箱地址
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def mask_phone(m: re.Match) -> str:
    s = m.group(0)
    return s[:3] + "****" + s[7:]


def mask_idcard(m: re.Match) -> str:
    s = m.group(0)
    return s[:4] + "****" + s[-4:]


def mask_bankcard(m: re.Match) -> str:
    s = m.group(0)
    return s[:4] + "****" + s[-4:]


def mask_email(m: re.Match) -> str:
    s = m.group(0)
    user, _, dom = s.partition("@")
    return (user[:2] or "*") + "***@" + dom


def desensitize(text: str) -> str:
    """对文本做 PII 打码, 返回脱敏后文本。无 PII 则原样返回。"""
    if not text:
        return text
    out = text
    out = _IDCARD.sub(mask_idcard, out)   # 先身份证(18位), 避免被银行卡规则截断
    out = _BANKCARD.sub(mask_bankcard, out)
    out = _PHONE.sub(mask_phone, out)
    out = _EMAIL.sub(mask_email, out)
    return out
