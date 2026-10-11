"""企业微信群机器人推送（备用通道）。

建法：企业微信群 -> 右上角 -> 群机器人 -> 添加 -> 复制 Webhook 地址。

青龙面板场景可用环境变量：LINEBAO_WECOM_WEBHOOK
"""
from __future__ import annotations

import logging
import os
import time

import requests

from ..sources import Item

log = logging.getLogger("linebao.notify.wecom")


class WecomNotifier:
    name = "wecom"

    def __init__(self, cfg: dict) -> None:
        self.webhook = (cfg.get("webhook") or os.getenv("LINEBAO_WECOM_WEBHOOK") or "").strip()
        if not self.webhook:
            raise ValueError(
                "缺少 webhook：请填 config.yaml 的 wecom.webhook，"
                "或设环境变量 LINEBAO_WECOM_WEBHOOK"
            )

    def _build_md(self, items: list[Item]) -> str:
        lines = [f"## 🛒 线报速递 · {len(items)} 条"]
        for i, it in enumerate(items, 1):
            price = f" ¥{it.price}" if it.price is not None else ""
            lines.append(f"{i}. [{it.title}{price}]({it.url})")
            lines.append(f'<font color="comment">{it.source}</font>')
        lines.append(f'<font color="comment">⏰ {time.strftime("%Y-%m-%d %H:%M")}</font>')
        return "\n".join(lines)

    def send(self, items: list[Item]) -> bool:
        if not items:
            return True
        payload = {"msgtype": "markdown", "markdown": {"content": self._build_md(items)}}
        try:
            resp = requests.post(self.webhook, json=payload, timeout=15)
            data = resp.json()
        except Exception as exc:
            log.error("企业微信推送失败: %s", exc)
            return False
        if data.get("errcode") == 0:
            log.info("企业微信推送成功: %d 条", len(items))
            return True
        log.error("企业微信推送失败: %s", data)
        return False
