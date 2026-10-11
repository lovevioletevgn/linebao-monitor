"""去重存储：用 SQLite 记录已推送过的条目指纹，避免重复刷屏。"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path


class SeenStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen (
                fp         TEXT PRIMARY KEY,
                title      TEXT,
                url        TEXT,
                source     TEXT,
                first_seen TEXT DEFAULT (datetime('now', 'localtime'))
            )
            """
        )
        self._conn.commit()

    @staticmethod
    def fingerprint(title: str, url: str) -> str:
        raw = f"{(title or '').strip()}|{(url or '').strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def is_seen(self, fp: str) -> bool:
        cur = self._conn.execute("SELECT 1 FROM seen WHERE fp = ? LIMIT 1", (fp,))
        return cur.fetchone() is not None

    def mark_seen(self, fp: str, title: str, url: str, source: str = "") -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO seen (fp, title, url, source) VALUES (?, ?, ?, ?)",
            (fp, title, url, source),
        )
        self._conn.commit()

    def count(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM seen")
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
