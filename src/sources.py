"""信息源抓取：RSS + 通用网页 + Telegram 频道。

设计原则：
  1. 单个源失败绝不拖垮整轮，全部捕获异常并记录。
  2. 代理按域名分流 —— 国内站直连（走代理会被反爬拦），境外站走代理。
"""
from __future__ import annotations

import html as _html
import logging
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

log = logging.getLogger("linebao.sources")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

_WS_RE = re.compile(r"\s+")
_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)")

TITLE_MAX = 200
SUMMARY_MAX = 400


@dataclass
class Item:
    title: str
    url: str
    summary: str = ""
    source: str = ""
    published: str = ""
    price: float | None = None
    meta: dict = field(default_factory=dict)


def clean_text(text: str) -> str:
    """反转义 HTML 实体、去 &nbsp;、压缩空白、归一化特殊字符。

    NFKC 归一化很关键：TG 线报爱用特殊字符醒目/规避审查，
    例如 `𝟬.𝟬𝟭`（数学粗体数字），不归一化就永远匹配不到 "0.01"。
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _html.unescape(text)
    text = text.replace("\xa0", " ")
    text = _WS_RE.sub(" ", text)
    return text.strip()


def _first_number(text: str) -> float | None:
    """从「1元」「9.9元（需用券）」这类文本里取出第一个数字。"""
    m = _NUM_RE.search(text or "")
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _clean_html(html_text: str) -> str:
    if not html_text:
        return ""
    try:
        raw = BeautifulSoup(html_text, "lxml").get_text(" ", strip=True)
    except Exception:
        raw = html_text
    return clean_text(raw)


def resolve_proxy(cfg: dict | None = None) -> str:
    """代理地址：环境变量优先，其次 config.runtime.proxy。"""
    env = os.getenv("LINEBAO_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    if env:
        return env.strip()
    if cfg:
        return str((cfg.get("runtime") or {}).get("proxy") or "").strip()
    return ""


# 这些是国内站，走境外代理会被反爬拦（实测什么值得买走代理后返回反爬页，
# 条目直接变 0）。命中则强制直连，其余域名走代理。
DOMESTIC_HOSTS = (
    "meidebi.com", "smzdm.com", "jd.com", "taobao.com", "tmall.com",
    "qq.com", "weibo.com", "163.com", "sina.com.cn", "baidu.com",
    "zhihu.com", "bilibili.com", "pinduoduo.com", "yangkeduo.com",
)


def _proxies_for(url: str, session: requests.Session) -> dict | None:
    """按域名决定走不走代理。"""
    proxy = session.proxies.get("https") or session.proxies.get("http") or ""
    if not proxy:
        return None
    host = urlparse(url).netloc.lower().split(":")[0]
    for d in DOMESTIC_HOSTS:
        if host == d or host.endswith("." + d):
            return {"http": None, "https": None}  # 国内站直连
    return {"http": proxy, "https": proxy}


def build_session(cfg: dict | None = None) -> requests.Session:
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    proxy = resolve_proxy(cfg)
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}
        log.info("使用代理: %s（国内站自动直连）", proxy)
    return s


def fetch_rss(source: dict, session: requests.Session, timeout: int = 15) -> list[Item]:
    """抓 RSS。"""
    url = (source.get("url") or "").strip()
    name = source.get("name", url)
    if not url:
        return []

    resp = session.get(url, timeout=timeout, proxies=_proxies_for(url, session))
    resp.raise_for_status()

    feed = feedparser.parse(resp.content)
    if getattr(feed, "bozo", 0) and not feed.entries:
        raise ValueError(f"RSS 解析失败: {getattr(feed, 'bozo_exception', 'unknown')}")

    items: list[Item] = []
    for entry in feed.entries[:80]:
        title = clean_text(entry.get("title") or "")[:TITLE_MAX]
        link = (entry.get("link") or "").strip()
        summary = _clean_html(entry.get("summary") or entry.get("description") or "")[:SUMMARY_MAX]
        published = entry.get("published") or entry.get("updated") or ""
        if not title and not link:
            continue
        items.append(
            Item(title=title, url=link, summary=summary, source=name, published=published)
        )
    return items


def fetch_web(source: dict, session: requests.Session, timeout: int = 15) -> list[Item]:
    """抓通用网页，用 CSS 选择器提取列表。"""
    url = (source.get("url") or "").strip()
    name = source.get("name", url)
    item_sel = source.get("item_selector")
    if not url or not item_sel:
        raise ValueError("网页源必须配置 url 和 item_selector")

    resp = session.get(url, timeout=timeout, proxies=_proxies_for(url, session))
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() in ("iso-8859-1", "ascii"):
        resp.encoding = resp.apparent_encoding or "utf-8"

    soup = BeautifulSoup(resp.text, "lxml")
    nodes = soup.select(item_sel)
    if not nodes:
        log.warning("[%s] 选择器未匹配到任何条目，页面结构可能变了: %s", name, item_sel)

    title_sel = source.get("title_selector")
    link_sel = source.get("link_selector") or title_sel
    time_sel = source.get("time_selector")
    price_sel = source.get("price_selector")

    items: list[Item] = []
    for node in nodes[:80]:
        t_node = node.select_one(title_sel) if title_sel else node
        l_node = node.select_one(link_sel) if link_sel else node
        title = clean_text(t_node.get_text(" ", strip=True))[:TITLE_MAX] if t_node else ""
        href = l_node.get("href", "") if l_node else ""
        published = ""
        if time_sel:
            tm = node.select_one(time_sel)
            if tm:
                published = clean_text(tm.get_text(" ", strip=True))

        price = None
        if price_sel:
            pm = node.select_one(price_sel)
            if pm:
                price = _first_number(clean_text(pm.get_text(" ", strip=True)))

        if not title and not href:
            continue
        items.append(
            Item(
                title=title,
                url=urljoin(url, href),
                summary="",
                source=name,
                published=published,
                price=price,
            )
        )
    return items


def fetch_telegram(source: dict, session: requests.Session, timeout: int = 20) -> list[Item]:
    """抓 Telegram 公开频道预览页 (t.me/s/<channel>)。

    这是真·线报群的形态：不需要账号，公开频道可直接读。
    ⚠️ 必须配好代理（境外站点）。
    """
    channel = (source.get("channel") or "").strip().lstrip("@")
    name = source.get("name") or ("@" + channel)
    if not channel:
        raise ValueError("Telegram 源必须配置 channel（频道用户名，不带 @）")

    url = f"https://t.me/s/{channel}"
    resp = session.get(url, timeout=timeout, proxies=_proxies_for(url, session))
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")

    if not soup.select("div.tgme_widget_message"):
        warn = soup.select_one(".tgme_page_description")
        detail = clean_text(warn.get_text(" ", strip=True)) if warn else "无消息"
        raise ValueError(f"频道无可读消息（私密频道或不存在）: {detail[:60]}")

    items: list[Item] = []
    for node in soup.select("div.tgme_widget_message"):
        text_el = node.select_one(".tgme_widget_message_text")
        if not text_el:
            continue
        text = clean_text(text_el.get_text(" ", strip=True))
        if not text:
            continue

        # 优先取消息里的外链（线报一般指向商品页），否则退回消息永久链接
        ext = ""
        for a in text_el.find_all("a", href=True):
            h = a["href"]
            if h.startswith("http") and "t.me" not in h:
                ext = h
                break
        if not ext:
            date_el = node.select_one("a.tgme_widget_message_date")
            ext = date_el.get("href", "") if date_el else ""

        price = _first_number(text) if re.search(r"[¥￥]|元", text) else None

        items.append(
            Item(
                title=text[:TITLE_MAX],
                url=ext,
                summary=text[:SUMMARY_MAX],
                source=name,
                price=price,
            )
        )
    return items


_FETCHERS = {
    "rss": fetch_rss,
    "web": fetch_web,
    "telegram": fetch_telegram,
}


def collect_all(cfg: dict, session: requests.Session) -> tuple[list[Item], list[str]]:
    """遍历所有启用的源，返回 (条目列表, 错误列表)。"""
    runtime = cfg.get("runtime", {})
    timeout = int(runtime.get("timeout", 15))
    delay = float(runtime.get("request_delay", 1.0))

    sources = cfg.get("sources", {})
    jobs: list[tuple[str, dict]] = []
    for kind in ("rss", "web", "telegram"):
        for s in sources.get(kind) or []:
            if s.get("enabled", True):
                jobs.append((kind, s))

    all_items: list[Item] = []
    errors: list[str] = []

    for idx, (kind, src) in enumerate(jobs):
        name = src.get("name") or src.get("url") or src.get("channel") or "?"
        fetch = _FETCHERS.get(kind)
        if fetch is None:
            continue
        try:
            got = fetch(src, session, timeout)
            # Telegram 频道本身就是线报流，不做关键词二次筛选（否则会被误杀）
            if kind == "telegram":
                for it in got:
                    it.meta["no_keyword_filter"] = True
            log.info("[%s] %s -> %d 条", kind, name, len(got))
            all_items.extend(got)
        except Exception as exc:  # 单源失败不影响其他源
            msg = f"{kind}:{name} -> {type(exc).__name__}: {exc}"
            log.warning("源抓取失败 %s", msg)
            errors.append(msg)

        if idx < len(jobs) - 1 and delay > 0:
            time.sleep(delay)

    return all_items, errors
