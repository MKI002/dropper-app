"""SQLite backed statistics: watch time, claimed drops and channel points."""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    drop_id TEXT NOT NULL,
    drop_name TEXT,
    rewards TEXT,
    campaign_id TEXT,
    campaign_name TEXT,
    game TEXT,
    method TEXT,
    success INTEGER NOT NULL,
    detail TEXT
);
CREATE INDEX IF NOT EXISTS claims_drop ON claims(drop_id);
CREATE TABLE IF NOT EXISTS watch (
    day TEXT NOT NULL,
    game TEXT NOT NULL,
    channel TEXT NOT NULL,
    minutes INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, game, channel)
);
CREATE TABLE IF NOT EXISTS points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    channel TEXT NOT NULL,
    amount INTEGER NOT NULL
);
"""

DAY_MINUTES = 24 * 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Stats:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(SCHEMA)
            self._repair_watch_days()

    def _repair_watch_days(self) -> None:
        """Older versions could count more than 24 h on one day (an extra minute on every channel switch and
        a minute per ~59 s). Scales such days down to 24 h, keeping the split between games and channels."""
        days = self._db.execute(
            "SELECT day, SUM(minutes) AS total FROM watch GROUP BY day HAVING total > ?", (DAY_MINUTES,)
        ).fetchall()
        for day, total in days:
            rows = self._db.execute("SELECT game, channel, minutes FROM watch WHERE day = ?", (day,)).fetchall()
            for game, channel, minutes in rows:
                self._db.execute(
                    "UPDATE watch SET minutes = ? WHERE day = ? AND game = ? AND channel = ?",
                    (minutes * DAY_MINUTES // total, day, game, channel),
                )
        if days:
            self._db.commit()

    def close(self) -> None:
        self._db.close()

    def _exec(self, sql: str, params: tuple = ()) -> None:
        with self._lock:
            self._db.execute(sql, params)
            self._db.commit()

    def _query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._db.execute(sql, params).fetchall()]

    def add_watch_minute(self, game: str, channel: str, minutes: int = 1) -> None:
        day = _now().date().isoformat()
        with self._lock:
            # One stream at a time: a day never holds more than 24 h of watch time.
            (total,) = self._db.execute("SELECT COALESCE(SUM(minutes), 0) FROM watch WHERE day = ?", (day,)).fetchone()
            minutes = min(minutes, DAY_MINUTES - total)
            if minutes <= 0:
                return
            self._db.execute(
                "INSERT INTO watch(day, game, channel, minutes) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(day, game, channel) DO UPDATE SET minutes = minutes + excluded.minutes",
                (day, game, channel, minutes),
            )
            self._db.commit()

    def add_claim(self, *, drop_id: str, drop_name: str, rewards: str, campaign_id: str,
                  campaign_name: str, game: str, method: str, success: bool, detail: str = "") -> None:
        self._exec(
            "INSERT INTO claims(ts, drop_id, drop_name, rewards, campaign_id, campaign_name, game, method, success, detail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (_now().isoformat(), drop_id, drop_name, rewards, campaign_id, campaign_name, game, method, int(success), detail),
        )

    def add_points(self, channel: str, amount: int) -> None:
        self._exec("INSERT INTO points(ts, channel, amount) VALUES (?, ?, ?)", (_now().isoformat(), channel, amount))

    def claim_times(self) -> dict[str, str]:
        """Time of the latest successful claim per drop id."""
        rows = self._query("SELECT drop_id, MAX(ts) AS ts FROM claims WHERE success = 1 GROUP BY drop_id")
        return {r["drop_id"]: r["ts"] for r in rows}

    def games(self) -> list[str]:
        """Every game that was ever watched or had a drop claimed."""
        rows = self._query("SELECT game FROM watch UNION SELECT game FROM claims")
        return [r["game"] for r in rows if r["game"]]

    def recent_claims(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._query("SELECT * FROM claims ORDER BY id DESC LIMIT ?", (limit,))

    def summary(self, days: int = 30) -> dict[str, Any]:
        since = (_now() - timedelta(days=days - 1)).date().isoformat()
        per_day = self._query(
            "SELECT day, SUM(minutes) AS minutes FROM watch WHERE day >= ? GROUP BY day ORDER BY day", (since,)
        )
        claims_per_day = self._query(
            "SELECT substr(ts, 1, 10) AS day, COUNT(*) AS claims FROM claims "
            "WHERE success = 1 AND substr(ts, 1, 10) >= ? GROUP BY day ORDER BY day", (since,)
        )
        per_game = self._query(
            "SELECT w.game, SUM(w.minutes) AS minutes, "
            "(SELECT COUNT(*) FROM claims c WHERE c.game = w.game AND c.success = 1) AS claims "
            "FROM watch w GROUP BY w.game ORDER BY minutes DESC LIMIT 25"
        )
        per_channel = self._query(
            "SELECT channel, game, SUM(minutes) AS minutes FROM watch GROUP BY channel, game "
            "ORDER BY minutes DESC LIMIT 25"
        )
        totals = self._query(
            "SELECT (SELECT COALESCE(SUM(minutes), 0) FROM watch) AS minutes, "
            "(SELECT COUNT(*) FROM claims WHERE success = 1) AS claims, "
            "(SELECT COUNT(*) FROM claims WHERE success = 0) AS failed_claims, "
            "(SELECT COALESCE(SUM(amount), 0) FROM points) AS points, "
            "(SELECT COALESCE(SUM(minutes), 0) FROM watch WHERE day = ?) AS minutes_today, "
            "(SELECT COUNT(*) FROM claims WHERE success = 1 AND substr(ts, 1, 10) = ?) AS claims_today",
            (_now().date().isoformat(), _now().date().isoformat()),
        )[0]
        claims_map = {r["day"]: r["claims"] for r in claims_per_day}
        minutes_map = {r["day"]: r["minutes"] for r in per_day}
        timeline = []
        for i in range(days):
            day = (_now() - timedelta(days=days - 1 - i)).date().isoformat()
            timeline.append({"day": day, "minutes": minutes_map.get(day, 0), "claims": claims_map.get(day, 0)})
        return {"totals": totals, "timeline": timeline, "per_game": per_game, "per_channel": per_channel}
