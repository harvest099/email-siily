"""正则关键词降级：LLM 未配置或调用失败时兜底, 保证流程永不崩。

规则可加——每个 CATEGORY 是 (关键词列表, 默认是否需处理) 的映射, 按优先级从上到下命中即停。
"""
from __future__ import annotations

from typing import Any, Optional

# 优先级从上到下: 命中即归类 (需要我处理 > 重要通知 > 资讯速览)
_RULES: list[tuple[str, list[str], bool]] = [
    ("需要我处理", [
        "续费", "缴费", "账单", "扣款", "到期", "即将失效", "验证码", "密码重置",
        "verify", "renew", "invoice", "payment", "due", "deadline", "confirm",
    ], True),
    ("重要通知", [
        "服务条款", "隐私政策", "安全", "风险提示", "登录异常", "异常登录", "更新",
        "terms", "privacy", "security", "alert", "notice",
    ], False),
    ("资讯速览", [
        "新闻", "资讯", "周报", "月报", "推荐", "促销", "优惠", "活动", "newsletter",
        "promo", "digest",
    ], False),
]


def _match(subject: str, body: str) -> Optional[tuple[str, bool]]:
    text = (subject + " " + body).lower()
    for cat, kws, needs in _RULES:
        for kw in kws:
            if kw.lower() in text:
                return cat, needs
    return None


def classify(mails: list[dict]) -> dict[str, Any]:
    """对邮件列表做正则粗分, 返回与 LLM 相同结构的结果。全兜底为「资讯速览」。"""
    buckets: dict[str, list[dict]] = {"需要我处理": [], "重要通知": [], "资讯速览": []}
    todo: list[str] = []

    for m in mails:
        subject = m.get("subject", "")
        body = m.get("body_preview", "") or m.get("body", "")
        hit = _match(subject, body)
        cat, needs = hit or ("资讯速览", False)

        entry = {
            "uid": m.get("uid", ""),
            "subject": subject,
            "from": m.get("from", ""),
            "reason": "关键词规则: " + ("命中" if hit else "默认兜底"),
            "deadline": None,
            "needs_action": needs,
        }
        buckets[cat].append(entry)
        if needs and subject:
            todo.append(f"处理「{subject}」")

    return {
        "categories": buckets,
        "todo": todo,
        "summary": f"正则降级共 {len(mails)} 封: "
                   + "/".join(f"{k}{len(v)}" for k, v in buckets.items() if v),
        "fallback": True,
    }
