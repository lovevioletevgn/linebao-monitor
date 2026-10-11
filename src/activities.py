"""羊毛活动提醒（按时提醒，不是抓线报）。

核心认知：真正的「1 分钱 / 免费」来自平台官方活动，
有固定入口 + 固定开抢时间，靠抢或靠任务，不靠爬虫。
所以这个模块做的事是：到点了提醒你。

状态记录在 data/reminded.json，同一天同一活动只提醒一次。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from .config import BASE_DIR, resolve_path
from .notifiers import build_notifiers
from .sources import Item

log = logging.getLogger("linebao.activities")

ACTIVITIES_FILE = BASE_DIR / "activities.yaml"
STATE_FILE = "data/reminded.json"


def load_activities() -> dict:
    if not ACTIVITIES_FILE.exists():
        raise FileNotFoundError(f"找不到活动清单: {ACTIVITIES_FILE}")
    with open(ACTIVITIES_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_state() -> dict:
    p = resolve_path(STATE_FILE)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    p = resolve_path(STATE_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def pick_due(now: datetime | None = None) -> tuple[list[dict], dict, str]:
    """挑出当前该提醒的活动（进入时间窗口且今天没提醒过）。"""
    now = now or datetime.now()
    data = load_activities()
    default_before = int((data.get("settings") or {}).get("default_remind_before", 10))

    today = now.strftime("%Y-%m-%d")
    state = _load_state()
    done = set(state.get(today) or [])

    due: list[dict] = []
    for a in data.get("activities") or []:
        name = a.get("name")
        if not name or name in done:
            continue
        raw_time = (a.get("time") or "").strip()
        try:
            hh, mm = raw_time.split(":")
            target = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
        except Exception:
            log.warning("活动时间格式不对，已跳过: %s -> %r", name, raw_time)
            continue

        before = int(a.get("remind_before", default_before))
        start = target - timedelta(minutes=before)
        if start <= now <= target:
            due.append(a)

    return due, state, today


def run_reminders(cfg: dict, now: datetime | None = None) -> int:
    due, state, today = pick_due(now)
    now = now or datetime.now()

    if not due:
        log.info("当前无到点活动（%s）", now.strftime("%Y-%m-%d %H:%M"))
        return 0

    items = [
        Item(
            title=f"⏰ {a['name']} · {a.get('time', '')} 开抢",
            url="",
            summary=f"{a.get('where', '')}　{a.get('note', '')}".strip(),
            source="羊毛开抢提醒",
        )
        for a in due
    ]

    notifiers = build_notifiers(cfg.get("notify", {}).get("channels", []))
    pushed = False
    for n in notifiers:
        try:
            if n.send(items):
                pushed = True
        except Exception as exc:
            log.error("提醒推送失败 [%s]: %s", getattr(n, "name", "?"), exc)

    if pushed or not notifiers:
        state.setdefault(today, [])
        state[today].extend(a["name"] for a in due)
        _save_state(state)
        log.info("已提醒 %d 个活动: %s", len(due), " / ".join(a["name"] for a in due))
    else:
        log.error("全部通道失败，本次不记录，下轮会重试")

    return len(due)
