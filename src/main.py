"""线报监测助手 · 主流程。

用法（在项目根目录）:
    python run.py                 # 跑一轮
    python run.py --dry-run       # 只打印，不推送、不写库
    python run.py --loop 300      # 常驻，每 300 秒一轮
    python run.py --config x.yaml # 指定配置
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime

from .config import load_config, resolve_path
from .filters import apply_filters
from .notifiers import build_notifiers
from .sources import Item, build_session, collect_all
from .store import SeenStore

log = logging.getLogger("linebao")


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, str(level).upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def run_once(cfg: dict, dry_run: bool = False) -> dict:
    """跑一轮：抓取 -> 过滤 -> 去重 -> 推送。返回统计。"""
    stats: dict = {"fetched": 0, "passed": 0, "fresh": 0, "pushed": 0, "errors": []}

    session = build_session(cfg)
    items, errors = collect_all(cfg, session)
    stats["fetched"] = len(items)
    stats["errors"] = errors

    passed = apply_filters(items, cfg.get("filters", {}))
    stats["passed"] = len(passed)

    db_path = resolve_path(cfg["runtime"]["db_path"])
    store = SeenStore(db_path)
    try:
        fresh: list[tuple[str, Item]] = []
        for it in passed:
            fp = store.fingerprint(it.title, it.url)
            if store.is_seen(fp):
                continue
            fresh.append((fp, it))
        stats["fresh"] = len(fresh)

        # 线报源（Telegram 频道）优先推送 —— 那才是真羊毛，别被折扣商品挤掉
        fresh.sort(key=lambda pair: 0 if pair[1].meta.get("no_keyword_filter") else 1)

        max_push = int(cfg["runtime"].get("max_push_per_run", 20))
        if max_push > 0:
            fresh = fresh[:max_push]

        if dry_run:
            log.info("[dry-run] 新增 %d 条（不推送、不写库）", len(fresh))
            for n in build_notifiers([{"type": "console", "enabled": True}]):
                n.send([it for _, it in fresh])
            return stats

        if not fresh:
            log.info("没有新线报")
            return stats

        notifiers = build_notifiers(cfg.get("notify", {}).get("channels", []))
        payload = [it for _, it in fresh]

        any_ok = False
        for n in notifiers:
            try:
                if n.send(payload):
                    any_ok = True
            except Exception as exc:
                log.error("推送器 %s 异常: %s", getattr(n, "name", "?"), exc)

        if any_ok or not notifiers:
            # 推送成功（或压根没配通道）才标记已读，避免刷屏
            for fp, it in fresh:
                store.mark_seen(fp, it.title, it.url, it.source)
            stats["pushed"] = len(fresh)
        else:
            log.error("全部推送通道失败，本轮不写库，下轮会重试")

        return stats
    finally:
        store.close()


def _run_one_round(cfg: dict, dry_run: bool) -> dict:
    log.info("-" * 52)
    log.info("开始一轮监测 · %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    stats = run_once(cfg, dry_run=dry_run)
    log.info(
        "本轮: 抓取 %d | 过滤通过 %d | 新增 %d | 已推送 %d",
        stats["fetched"], stats["passed"], stats["fresh"], stats["pushed"],
    )
    if stats["errors"]:
        log.warning("失败源 %d 个:", len(stats["errors"]))
        for e in stats["errors"]:
            log.warning("  - %s", e)
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="线报监测助手")
    parser.add_argument("--config", default=None, help="配置文件路径（默认 config.yaml）")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不推送不写库")
    parser.add_argument("--loop", type=int, default=0, help="常驻模式，每 N 秒跑一轮")
    parser.add_argument("--remind", action="store_true", help="活动开抢提醒模式（不抓取，只按时提醒）")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    setup_logging(cfg["runtime"].get("log_level", "INFO"))

    if args.remind:
        from .activities import run_reminders

        run_reminders(cfg)
        return 0

    if args.loop and args.loop > 0:
        log.info("常驻模式，间隔 %d 秒（Ctrl+C 退出）", args.loop)
        while True:
            try:
                _run_one_round(cfg, args.dry_run)
            except KeyboardInterrupt:
                log.info("收到中断，退出")
                return 0
            except Exception as exc:
                log.exception("本轮异常，已跳过: %s", exc)
            try:
                time.sleep(args.loop)
            except KeyboardInterrupt:
                log.info("收到中断，退出")
                return 0
    else:
        _run_one_round(cfg, args.dry_run)
    return 0
