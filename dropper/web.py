"""REST API and static web UI."""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from . import __version__
from .miner import LogBuffer, Miner
from .selection import skip_reason, wanted_campaigns
from .settings import clean_avatar, clean_sender_name

STATIC_DIR = Path(__file__).parent / "static"


def _asset_version() -> str:
    digest = hashlib.sha1(__version__.encode())
    for path in sorted(STATIC_DIR.rglob("*")):
        if path.is_file():
            stat = path.stat()
            digest.update(f"{path.name}:{stat.st_size}:{int(stat.st_mtime)}".encode())
    return digest.hexdigest()[:10]


def create_app(miner: Miner, logs: LogBuffer, *, lifespan=None) -> FastAPI:
    asset_version = _asset_version()
    app = FastAPI(title="Dropper", version=__version__, lifespan=lifespan, docs_url="/api/docs", redoc_url=None)
    user = os.environ.get("WEBUI_USER", "admin")
    password = os.environ.get("WEBUI_PASSWORD", "")

    @app.middleware("http")
    async def basic_auth(request: Request, call_next):
        if password and request.url.path != "/api/health":
            header = request.headers.get("authorization", "")
            ok = False
            if header.lower().startswith("basic "):
                try:
                    name, _, pw = base64.b64decode(header[6:]).decode().partition(":")
                    ok = secrets.compare_digest(name, user) and secrets.compare_digest(pw, password)
                except Exception:
                    ok = False
            if not ok:
                return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Dropper"'})
        return await call_next(request)

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "version": __version__, "state": miner.state}

    @app.get("/api/state")
    async def state() -> dict[str, Any]:
        data = miner.snapshot()
        data["version"] = __version__
        return data

    @app.get("/api/campaigns")
    async def campaigns() -> list[dict[str, Any]]:
        return miner.campaign_overview()

    @app.get("/api/channels")
    async def channels() -> list[dict[str, Any]]:
        watching_id = miner.watching.id if miner.watching else None
        wanted_ids = {c.id for c in wanted_campaigns(miner.campaigns.values(), miner.settings)}
        out = []
        for ch in miner.channels.values():
            data = ch.to_dict()
            data["watching"] = ch.id == watching_id
            data["campaigns"] = []
            for cid in data["campaign_ids"]:
                campaign = miner.campaigns.get(cid)
                wanted = cid in wanted_ids
                if campaign is not None:
                    # reason codes: see selection.SKIP_REASONS, plus "unknown_campaign"
                    reason = "" if wanted else (skip_reason(campaign, miner.settings) or "not_wanted")
                    name, game = campaign.name, campaign.game.name
                else:
                    # Twitch reports it for the channel, but it is not in the account's drop list
                    reason, name, game = "unknown_campaign", ch.campaign_names.get(cid, ""), ""
                data["campaigns"].append({"id": cid, "name": name, "game": game, "wanted": wanted, "reason": reason})
            data["campaigns"].sort(key=lambda c: (not c["wanted"], c["name"]))
            data["blacklisted"] = ch.login in miner.settings.channels_blacklist
            data["preferred"] = ch.login in miner.settings.channels_preferred
            out.append(data)
        out.sort(key=lambda c: (not c["watching"], not c["online"], not c["drops_enabled"], -c["viewers"]))
        return out

    @app.get("/api/drops")
    async def drops() -> dict[str, Any]:
        return miner.drops_overview()

    @app.get("/api/stats")
    async def stats(days: int = 30) -> dict[str, Any]:
        days = max(1, min(days, 365))
        data = miner.stats.summary(days)
        data["recent_claims"] = miner.stats.recent_claims(100)
        return data

    @app.get("/api/logs")
    async def get_logs(after: int = 0) -> list[dict[str, Any]]:
        return [line for line in logs.lines if line["id"] > after]

    @app.get("/api/settings")
    async def get_settings() -> dict[str, Any]:
        return miner.settings.model_dump(mode="json")

    @app.put("/api/settings")
    async def put_settings(data: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            return miner.store.update(data).model_dump(mode="json")
        except ValidationError as exc:
            raise HTTPException(422, detail=exc.errors(include_url=False, include_context=False))

    @app.get("/api/games/search")
    async def games_search(q: str = "") -> dict[str, Any]:
        """Games for the priority list: known ones whose name contains q, and q itself looked up on Twitch."""
        query = " ".join(q.split())[:100]
        lookup = await miner.check_game(query) if len(query) >= 2 else None
        return {"query": query, "results": miner.game_suggestions(query), "lookup": lookup}

    @app.post("/api/games/lookup")
    async def games_lookup(data: dict[str, Any] = Body(default={})) -> dict[str, Any]:
        """Spelling check and box art for game names, such as those on the priority list."""
        names = [" ".join(str(n).split())[:100] for n in (data.get("names") or [])][:30]
        return {"games": [await miner.check_game(n) for n in names if n]}

    @app.post("/api/refresh")
    async def refresh() -> dict[str, Any]:
        miner.request_refresh()
        return {"ok": True}

    @app.post("/api/switch")
    async def switch(data: dict[str, Any] = Body(default={})) -> dict[str, Any]:
        await miner.switch_to(data.get("login") or None)
        return {"ok": True, "watching": miner.watching.to_dict() if miner.watching else None}

    @app.post("/api/claim/{drop_id}")
    async def claim(drop_id: str) -> dict[str, Any]:
        drop = miner.drops.get(drop_id)
        if drop is None:
            raise HTTPException(404, "drop not found")
        if not drop.claimable() and not drop.is_claimed:
            raise HTTPException(409, "drop is not finished yet")
        return {"ok": await miner.claim_drop(drop, method="manual")}

    @app.post("/api/campaigns/{campaign_id}/toggle")
    async def toggle_campaign(campaign_id: str) -> dict[str, Any]:
        excluded = list(miner.settings.campaigns_exclude)
        if campaign_id in excluded:
            excluded.remove(campaign_id)
        else:
            excluded.append(campaign_id)
        miner.store.update({"campaigns_exclude": excluded})
        return {"ok": True, "excluded": campaign_id in excluded}

    @app.post("/api/pause")
    async def pause(data: dict[str, Any] = Body(default={})) -> dict[str, Any]:
        miner.store.update({"paused": bool(data.get("paused", not miner.settings.paused))})
        return {"paused": miner.settings.paused}

    @app.post("/api/logout")
    async def logout() -> dict[str, Any]:
        miner.logout()
        return {"ok": True}

    @app.post("/api/notify/test")
    async def notify_test(data: dict[str, Any] = Body(default={})) -> dict[str, Any]:
        # URL, name and picture from the settings form, so they can be tried before saving
        url = str(data.get("url") or miner.settings.webhook_url).strip()
        if not url:
            raise HTTPException(400, "no webhook URL")
        if not url.startswith(("https://", "http://")):
            url = f"https://{url}"
        username = clean_sender_name(data["username"]) if "username" in data else None
        avatar = clean_avatar(data["avatar"]) if "avatar" in data else None
        ok, detail = await miner.notifier.test(url, username=username, avatar=avatar)
        return {"ok": ok, "detail": detail}

    @app.exception_handler(Exception)
    async def errors(_: Request, exc: Exception):
        return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})

    @app.get("/")
    async def index() -> HTMLResponse:
        # asset URLs carry a version so browsers pick up new files right after an image update
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8").replace("__ASSET_VERSION__", asset_version)
        return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
