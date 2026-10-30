from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from dropper.miner import Miner
from dropper.settings import SettingsStore
from dropper.stats import Stats

NOW = datetime.now(timezone.utc)


def iso(delta_hours: float) -> str:
    return (NOW + timedelta(hours=delta_hours)).isoformat().replace("+00:00", "Z")


def benefit(bid: str, name: str, kind: str = "DIRECT_ENTITLEMENT") -> dict:
    return {"benefit": {"id": bid, "name": name, "distributionType": kind, "imageAssetURL": f"https://img/{bid}.png"}}


def drop(did: str, minutes: int, benefits: list, *, current: int | None = None, claimed: bool = False,
         instance: str | None = None, pre: list[str] | None = None) -> dict:
    data = {
        "id": did, "name": did, "requiredMinutesWatched": minutes, "benefitEdges": benefits,
        "startAt": iso(-24), "endAt": iso(48), "preconditionDrops": [{"id": p} for p in (pre or [])],
    }
    if current is not None:
        data["self"] = {"currentMinutesWatched": current, "isClaimed": claimed, "dropInstanceID": instance}
    return data


def campaign(cid: str, game_id: int, game: str, drops: list, *, linked: bool = True, acl: list | None = None,
             status: str = "ACTIVE", start: float = -24, end: float = 48) -> dict:
    return {
        "id": cid, "name": f"{game} Kampagne {cid}", "status": status,
        "game": {"id": str(game_id), "displayName": game, "slug": game.lower().replace(" ", "-"), "boxArtURL": "https://img/box-{width}x{height}.jpg"},
        "self": {"isAccountConnected": linked}, "accountLinkURL": "https://link",
        "startAt": iso(start), "endAt": iso(end),
        "allow": {"channels": acl, "isEnabled": True} if acl else {"channels": None},
        "timeBasedDrops": drops,
    }


class FakeClient:
    """Stands in for TwitchClient: answers GQL operations from a handler table."""

    def __init__(self):
        self.user_id = "42"
        self.login = "tester"
        self.access_token = "tok"
        self.login_prompt = None
        self.logged_in = asyncio.Event()
        self.logged_in.set()
        self.handlers: dict[str, Any] = {}
        self.calls: list[tuple[str, dict]] = []
        self.requests: list[tuple[str, str, dict]] = []

    def _get_settings(self):
        return None

    def operation(self, key: str, variables: dict | None = None) -> dict:
        return {"operationName": key, "variables": variables or {}}

    async def gql(self, ops):
        if isinstance(ops, list):
            return [await self.gql(op) for op in ops]
        self.calls.append((ops["operationName"], ops["variables"]))
        handler = self.handlers.get(ops["operationName"])
        if handler is None:
            return {"data": {}}
        return handler(ops["variables"]) if callable(handler) else handler

    async def gql_batch(self, ops, chunk=20, tolerant=False):
        return await self.gql(list(ops))

    async def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        if "twitch.tv/" in url and method == "GET":
            return 200, '<script>window.__x={"spade_url": "https://spade.example/track"}</script>'
        return 204, ""

    async def validate(self):
        return True

    async def close(self):
        pass

    def logout(self):
        self.logged_in.clear()


@pytest.fixture
def tmp_data(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def miner(tmp_data: Path):
    store = SettingsStore(tmp_data / "settings.json")
    stats = Stats(tmp_data / "stats.db")
    client = FakeClient()
    m = Miner(tmp_data, store, stats, client=client)
    yield m
    stats.close()
