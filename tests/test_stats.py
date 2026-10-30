from __future__ import annotations

import sqlite3

from dropper.stats import DAY_MINUTES, Stats, _now


def test_day_never_exceeds_24_hours(tmp_path):
    stats = Stats(tmp_path / "stats.db")
    stats.add_watch_minute("Rust", "a", DAY_MINUTES - 2)
    stats.add_watch_minute("Rust", "b", 5)
    stats.add_watch_minute("Rust", "b")
    today = stats.summary(1)["timeline"][-1]
    assert today["minutes"] == DAY_MINUTES


def test_repairs_days_over_24_hours(tmp_path):
    path = tmp_path / "stats.db"
    Stats(path).close()
    db = sqlite3.connect(path)
    db.executemany("INSERT INTO watch(day, game, channel, minutes) VALUES (?, ?, ?, ?)", [
        ("2026-10-23", "Rust", "a", 1000), ("2026-10-23", "Rust", "b", 500),
        ("2026-10-22", "Rust", "a", 600),
    ])
    db.commit()
    db.close()
    stats = Stats(path)
    rows = {(r["day"], r["channel"]): r["minutes"] for r in stats._query("SELECT * FROM watch")}
    assert rows[("2026-10-23", "a")] == 960 and rows[("2026-10-23", "b")] == 480
    assert rows[("2026-10-22", "a")] == 600


def test_today_uses_utc_day(tmp_path):
    stats = Stats(tmp_path / "stats.db")
    stats.add_watch_minute("Rust", "a", 3)
    assert stats._query("SELECT day FROM watch")[0]["day"] == _now().date().isoformat()
