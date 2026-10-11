"""线报监测助手 · 启动入口。

直接用项目内的隔离 Python 运行：
    <venv>/Scripts/python.exe run.py --dry-run
"""
from __future__ import annotations

import sys
from pathlib import Path

# 保证无论从哪个目录调用都能 import src
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Windows 控制台默认 GBK，中文会乱码/报错，强制 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from src.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
