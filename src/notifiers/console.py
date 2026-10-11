"""控制台推送器：本机调试用，直接打到 stdout。"""
from __future__ import annotations

from ..sources import Item


class ConsoleNotifier:
    name = "console"

    def __init__(self, cfg: dict | None = None) -> None:
        self.cfg = cfg or {}

    def send(self, items: list[Item]) -> bool:
        if not items:
            print("[console] 无线报")
            return True
        print("=" * 60)
        print(f"[console] 本轮 {len(items)} 条线报")
        print("=" * 60)
        for i, it in enumerate(items, 1):
            price = f" ¥{it.price}" if it.price is not None else ""
            print(f"{i:>2}. {it.title}{price}")
            print(f"    来源: {it.source}")
            if it.url:
                print(f"    链接: {it.url}")
            if it.summary:
                print(f"    摘要: {it.summary[:120]}")
            print("-" * 60)
        return True
