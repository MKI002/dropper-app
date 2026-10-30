"""Public catalog of running drop campaigns.

Since September 2026 Twitch answers the campaign list and campaign details queries with null for app
clients (an integrity check). The catalog names the campaigns that are running; the drops themselves
are read from the live channels that offer them (DropsHighlightService_AvailableDrops), and our own
progress still comes from the inventory. The default source is ttvdrops (open data, CC0).
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlencode, urljoin

logger = logging.getLogger("dropper.catalog")

DEFAULT_CATALOG_URL = "https://ttvdrops.lovinator.space/api/v1/twitch/campaigns/"
PAGE_SIZE = 100
MAX_PAGES = 10
STATUSES = {"active": "ACTIVE", "upcoming": "UPCOMING"}


def _absolute(base: str, url: str | None) -> str:
    return urljoin(base, url) if url else ""


def to_gql(item: dict[str, Any], base: str) -> dict[str, Any] | None:
    """Turns one catalog entry into the shape of Twitch's ViewerDropsDashboard campaigns."""
    game = item.get("game") or {}
    status = STATUSES.get(str(item.get("status") or "").lower())
    if not item.get("twitch_id") or not game.get("twitch_id") or status is None:
        return None
    try:
        game_id = int(game["twitch_id"])
    except (TypeError, ValueError):
        return None
    name = game.get("display_name") or game.get("name") or "?"
    return {
        "id": str(item["twitch_id"]),
        "name": item.get("name") or "",
        "status": status,
        "startAt": item.get("start_at"),
        "endAt": item.get("end_at"),
        "accountLinkURL": item.get("account_link_url") or "",
        "imageURL": _absolute(base, item.get("image_url")),
        "game": {
            "id": str(game_id),
            "name": name,
            "displayName": name,
            "slug": game.get("slug") or "",
            "boxArtURL": _absolute(base, game.get("box_art_url")),
        },
    }


async def fetch_catalog(client: Any, url: str) -> list[dict[str, Any]]:
    """Reads every active and upcoming campaign from the catalog. Raises on network or format errors."""
    campaigns: dict[str, dict[str, Any]] = {}
    for status in STATUSES:
        for page in range(1, MAX_PAGES + 1):
            query = urlencode({"status": status, "page": page, "page_size": PAGE_SIZE})
            code, body = await client.request(
                "GET", f"{url}{'&' if '?' in url else '?'}{query}", retries=2,
                headers={"Accept": "application/json"},
            )
            if code != 200:
                raise ValueError(f"HTTP {code}")
            data = json.loads(body)
            items = data.get("items")
            if not isinstance(items, list):
                raise ValueError("unexpected response")
            for item in items:
                campaign = to_gql(item, url) if isinstance(item, dict) else None
                if campaign is not None:
                    campaigns.setdefault(campaign["id"], campaign)
            if len(items) < PAGE_SIZE or page * PAGE_SIZE >= int(data.get("total") or 0):
                break
    return list(campaigns.values())
