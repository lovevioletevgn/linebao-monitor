"""PushPlus 微信推送（最省事的通道）。

微信扫码登录 https://www.pushplus.plus/ 即可拿到 token，
不用建群、不用加机器人，直接把消息推到你微信。

免费版每天 200 条，个人用完全够（需实名认证）。

token 来源优先级：config.yaml 的 pushplus.token > 环境变量 PUSHPLUS_TOKEN
"""
from __future__ import annotations

import logging
import os
import time

import requests

from ..sources import Item

log = logging.getLogger("linebao.notify.pushplus")

_API = "https://www.pushplus.plus/send"


class PushPlusNotifier:
    name = "pushplus"

    def __init__(self, cfg: dict) -> None:
        self.token = (cfg.get("token") or os.getenv("PUSHPLUS_TOKEN") or "").strip()
        if not self.token:
            raise ValueError(
                "缺少 token：请设环境变量 PUSHPLUS_TOKEN，或填 config.yaml 的 pushplus.token"
            )

    def _build_md(self, items: list[Item]) -> str:
        lines = [f"## 🛒 线报速递 · {len(items)} 条", ""]
        for i, it in enumerate(items, 1):
            price = f" **¥{it.price}**" if it.price is not None else ""
            lines.append(f"{i}. [{it.title}{price}]({it.url})")
        lines.append("")
        lines.append(f"<span style=\"color:#999\">⏰ {time.strftime('%Y-%m-%d %H:%M')}</span>")
        return "\n".join(lines)

    def send(self, items: list[Item]) -> bool:
        if not items:
            return True

        payload = {
            "token": self.token,
            "title": f"线报速递 · {len(items)} 条",
            "content": self._build_md(items),
            "template": "markdown",
        }
        try:
            resp = requests.post(_API, json=payload, timeout=15)
            data = resp.json()
        except Exception as exc:
            log.error("PushPlus 推送失败: %s", exc)
            return False

        if data.get("code") == 200:
            log.info("PushPlus 推送成功: %d 条", len(items))
            return True
        log.error("PushPlus 推送失败: %s", data)
        return False
