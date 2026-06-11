"""发布失败信息归类（风控 / 技术 / 其他）。"""

from __future__ import annotations

RISK_KEYWORDS = (
    "频繁",
    "违规",
    "限制",
    "风控",
    "封禁",
    "风险管控",
    "操作过频",
    "涉嫌",
    "违禁",
)

TECHNICAL_KEYWORDS = (
    "cookie",
    "timeout",
    "playwright",
    "chromium",
    "element",
    "selector",
    "登录",
    "过期",
    "expired",
    "网络",
    "连接",
    "未找到",
    "dom",
    "超时",
    "浏览器",
    "biliup",
)


def classify_failure_message(message: str | None) -> str:
    if not message:
        return "other"
    lowered = message.lower()
    if any(keyword in message for keyword in RISK_KEYWORDS):
        return "risk"
    if any(keyword in lowered or keyword in message for keyword in TECHNICAL_KEYWORDS):
        return "technical"
    return "other"


def failure_category_label(category: str) -> str:
    return {
        "risk": "疑似风控",
        "technical": "技术问题",
        "other": "其他",
    }.get(category, category)
