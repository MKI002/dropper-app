"""Entry point: python -m dropper"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn

from .miner import LogBuffer, Miner
from .settings import SettingsStore
from .stats import Stats
from .web import create_app


def main() -> None:
    # PURPLERAIN_DATA is the name from before the rename, so older setups keep their data
    data_dir = Path(os.environ.get("DROPPER_DATA") or os.environ.get("PURPLERAIN_DATA") or "/data")
    data_dir.mkdir(parents=True, exist_ok=True)
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logs = LogBuffer()
    logging.getLogger("dropper").addHandler(logs)

    store = SettingsStore(data_dir / "settings.json")
    stats = Stats(data_dir / "stats.db")
    miner = Miner(data_dir, store, stats)

    @asynccontextmanager
    async def lifespan(_app):
        miner.start()
        yield
        await miner.stop()
        stats.close()

    app = create_app(miner, logs, lifespan=lifespan)
    uvicorn.run(app, host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "8080")),
                log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
