"""过滤规则：关键词筛选 + 价格上限。

关键词两种写法：
    普通词   -> 子串匹配，如 "免费"
    /正则/   -> 正则匹配，如 "/0\\.01|1分/"（精确，避免 "31元" 被 "1元" 误命中）

来源级旁路：
    某些源（如 Telegram 线报频道）内容本身就是线报，用关键词再筛会误杀。
    在 Item.meta 里设 no_keyword_filter=True 即可跳过关键词检查。
"""
from __future__ import annotations

import re

from .sources import Item

# 常见价格写法：￥12.9 / ¥12 / 12.9元 / 12元
_PRICE_PATTERNS = [
    re.compile(r"[¥￥]\s*(\d+(?:\.\d+)?)"),
    re.compile(r"(\d+(?:\.\d+)?)\s*元"),
]

_REGEX_CACHE: dict[str, re.Pattern | None] = {}


def is_regex(pattern: str) -> bool:
    return len(pattern) >= 2 and pattern.startswith("/") and pattern.endswith("/")


def _compile(pattern: str) -> re.Pattern | None:
    if pattern not in _REGEX_CACHE:
        try:
            _REGEX_CACHE[pattern] = re.compile(pattern[1:-1])
        except re.error:
            _REGEX_CACHE[pattern] = None
    return _REGEX_CACHE[pattern]


def match_keyword(text: str, pattern: str) -> bool:
    """普通词走子串，/.../ 走正则；正则写错时退化为子串，不让它崩。"""
    if is_regex(pattern):
        rx = _compile(pattern)
        if rx is None:
            return pattern[1:-1] in text
        return rx.search(text) is not None
    return pattern in text


def extract_price(text: str) -> float | None:
    """抠出文本里的第一个价格（¥/￥ 优先于 "xx元"）。"""
    if not text:
        return None
    for pat in _PRICE_PATTERNS:
        m = pat.search(text)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
    return None


def judge(item: Item, filters_cfg: dict) -> tuple[bool, str]:
    """返回 (是否通过, 原因)。"""
    text = f"{item.title} {item.summary}"

    includes = [k for k in (filters_cfg.get("include_keywords") or []) if k]
    excludes = [k for k in (filters_cfg.get("exclude_keywords") or []) if k]
    max_price = float(filters_cfg.get("max_price") or 0)

    # 1) 排除词
    for kw in excludes:
        if match_keyword(text, kw):
            return False, f"排除词:{kw}"

    # 2) 价格：抓取阶段已解析就直接用，否则从文本里抠
    price = item.price if item.price is not None else extract_price(text)
    if price is not None:
        item.price = price
        if max_price > 0 and price > max_price:
            return False, f"价格{price}超上限{max_price}"

    # 3) 线报源旁路：频道内容本身就是线报，不做关键词二次筛选
    if item.meta.get("no_keyword_filter"):
        return True, "线报源直通"

    # 4) 包含词
    if includes:
        hits = [kw for kw in includes if match_keyword(text, kw)]
        if not hits:
            return False, "无包含词"
        return True, "命中:" + "/".join(h.strip("/") for h in hits[:3])

    return True, "无包含词限制"


def apply_filters(items: list[Item], filters_cfg: dict) -> list[Item]:
    passed: list[Item] = []
    for it in items:
        ok, reason = judge(it, filters_cfg)
        it.meta["filter_reason"] = reason
        if ok:
            passed.append(it)
    return passed
