"""飞书群机器人推送。

建法：飞书群 -> 设置 -> 群机器人 -> 添加「自定义机器人」-> 复制 Webhook 地址。
若开启「签名校验」，把密钥填到 config 的 secret 字段。

青龙面板场景：可用环境变量提供，避免密钥随仓库泄露——
    LINEBAO_FEISHU_WEBHOOK / LINEBAO_FEISHU_SECRET
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import time

import requests

from ..sources import Item

log = logging.getLogger("linebao.notify.feishu")


class FeishuNotifier:
    name = "feishu"

    def __init__(self, cfg: dict) -> None:
        # 优先 config.yaml，其次环境变量
        self.webhook = (cfg.get("webhook") or os.getenv("LINEBAO_FEISHU_WEBHOOK") or "").strip()
        self.secret = (cfg.get("secret") or os.getenv("LINEBAO_FEISHU_SECRET") or "").strip()
        if not self.webhook:
            raise ValueError(
                "缺少 webhook：请填 config.yaml 的 feishu.webhook，"
                "或设环境变量 LINEBAO_FEISHU_WEBHOOK"
            )
        if not self.webhook.startswith("https://"):
            raise ValueError(f"webhook 格式可疑: {self.webhook[:40]}")

    def _gen_sign(self, timestamp: int) -> str:
        string_to_sign = f"{timestamp}\n{self.secret}"
        digest = hmac.new(
            string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(digest).decode("utf-8")

    def _build_text(self, items: list[Item]) -> str:
        lines = [f"🛒 线报速递 · {len(items)} 条", "━━━━━━━━━━━━━━"]
        for i, it in enumerate(items, 1):
            price = f" ¥{it.price}" if it.price is not None else ""
            lines.append(f"{i}. {it.title}{price}")
            if it.url:
                lines.append(f"   [{it.source}] {it.url}")
            elif it.summary:
                lines.append(f"   {it.summary}")
        lines.append("━━━━━━━━━━━━━━")
        lines.append("⏰ " + time.strftime("%Y-%m-%d %H:%M"))
        return "\n".join(lines)

    def send(self, items: list[Item]) -> bool:
        if not items:
            return True

        payload = {
            "msg_type": "text",
            "content": {"text": self._build_text(items)},
        }
        if self.secret:
            ts = int(time.time())
            payload["timestamp"] = str(ts)
            payload["sign"] = self._gen_sign(ts)

        try:
            resp = requests.post(self.webhook, json=payload, timeout=15)
        except Exception as exc:
            log.error("飞书推送网络错误: %s", exc)
            return False

        try:
            data = resp.json()
        except Exception:
            log.error("飞书返回非 JSON: HTTP %s %s", resp.status_code, resp.text[:200])
            return False

        if data.get("code") in (0, None) and data.get("StatusCode", 0) == 0:
            log.info("飞书推送成功: %d 条", len(items))
            return True
        log.error("飞书推送失败: %s", data)
        return False
