"""配置加载与路径解析。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# 项目根目录（src 的上一级）
BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_CONFIG = BASE_DIR / "config.yaml"


def load_dotenv(path: Path | None = None) -> None:
    """加载项目根目录的 .env（KEY=VALUE 格式），不覆盖已有环境变量。

    密钥（飞书 webhook 等）建议放这里，而不是写进 config.yaml——
    这样 config 可以随便传，.env 被 .gitignore 挡住。
    """
    env_path = path or (BASE_DIR / ".env")
    if not env_path.exists():
        return
    try:
        content = env_path.read_text(encoding="utf-8")
    except Exception:
        return
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, val)


def load_config(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """读取 YAML 配置，补齐缺省结构。

    注意：YAML 里只有注释的键会被解析成 None（不是空列表），
    所以这里统一用 `if not x: x = 默认值`，不能用 setdefault。
    """
    load_dotenv()
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    if not cfg_path.exists():
        raise FileNotFoundError(f"找不到配置文件: {cfg_path}")

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    sources = cfg.get("sources") or {}
    if not sources.get("rss"):
        sources["rss"] = []
    if not sources.get("web"):
        sources["web"] = []
    cfg["sources"] = sources

    filters = cfg.get("filters") or {}
    cfg["filters"] = filters

    notify = cfg.get("notify") or {}
    if not notify.get("channels"):
        notify["channels"] = []
    cfg["notify"] = notify

    runtime = cfg.get("runtime") or {}
    runtime.setdefault("max_push_per_run", 20)
    runtime.setdefault("timeout", 15)
    runtime.setdefault("request_delay", 1.0)
    runtime.setdefault("db_path", "data/seen.db")
    runtime.setdefault("log_level", "INFO")
    cfg["runtime"] = runtime

    return cfg


def resolve_path(path_str: str) -> Path:
    """相对路径按项目根目录解析，保证在哪运行都找得到。"""
    p = Path(path_str)
    return p if p.is_absolute() else (BASE_DIR / p)
