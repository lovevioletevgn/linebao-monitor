"""推送通道集合。"""
from __future__ import annotations

import logging
import os

from .console import ConsoleNotifier
from .feishu import FeishuNotifier
from .html import HtmlNotifier
from .pushplus import PushPlusNotifier
from .wecom import WecomNotifier

log = logging.getLogger("linebao.notify")

_REGISTRY = {
    "console": ConsoleNotifier,
    "feishu": FeishuNotifier,
    "html": HtmlNotifier,
    "pushplus": PushPlusNotifier,
    "wecom": WecomNotifier,
}

# 这些通道支持用环境变量提供凭证（青龙面板场景）
_ENV_HINTS = {
    "feishu": "LINEBAO_FEISHU_WEBHOOK",
    "wecom": "LINEBAO_WECOM_WEBHOOK",
    "pushplus": "PUSHPLUS_TOKEN",
}


def build_notifiers(channels: list[dict]):
    """按配置构造推送器列表；配置缺失/无 webhook 的自动跳过并警告。"""
    result = []
    for ch in channels or []:
        kind = (ch.get("type") or "").strip().lower()
        enabled = bool(ch.get("enabled", False))
        # 只要设了环境变量就自动启用，省得忘记改 config.yaml
        env_key = _ENV_HINTS.get(kind)
        if not enabled and env_key and os.getenv(env_key):
            log.info("[%s] 检测到环境变量 %s，自动启用", kind, env_key)
            enabled = True
        if not enabled:
            continue
        cls = _REGISTRY.get(kind)
        if cls is None:
            log.warning("未知推送类型: %s，已跳过", kind)
            continue
        try:
            notifier = cls(ch)
        except ValueError as exc:
            log.warning("[%s] %s，已跳过", kind, exc)
            continue
        result.append(notifier)
    if not result:
        log.warning("没有任何可用的推送通道，本轮只写库不推送")
    return result
