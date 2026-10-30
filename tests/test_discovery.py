"""Twitch hides the campaign list from app clients: the catalog and live channels fill the gap."""

import json

from dropper.catalog import DEFAULT_CATALOG_URL, fetch_catalog, to_gql
from dropper.selection import skip_reason, wanted_campaigns

from .conftest import benefit, campaign, drop, iso


def catalog_item(cid, game_id, game, slug, *, status="active", link="", end=48):
    return {
        "twitch_id": cid, "name": f"{game} drops", "status": status, "image_url": f"/media/campaigns/{cid}.png",
        "details_url": "https://www.twitch.tv/", "account_link_url": link, "start_at": iso(24 if status == "upcoming" else -24), "end_at": iso(end),
        "allow_is_enabled": False, "is_fully_imported": True,
        "game": {"twitch_id": str(game_id), "slug": slug, "name": game, "display_name": game,
                 "box_art_url": f"/media/games/box_art/{game_id}.jpg"},
    }


def gated(miner, inventory, catalog, *, catalog_status=200):
    """Dashboard answers null (the integrity gate), the catalog lists campaigns."""
    client = miner.client
    client.handlers["Campaigns"] = {"data": {"currentUser": {"dropCampaigns": None}}}
    client.handlers["Inventory"] = {"data": {"currentUser": {"inventory": {
        "dropCampaignsInProgress": inventory, "gameEventDrops": []}}}}
    plain = client.request

    async def request(method, url, **kwargs):
        if url.startswith(DEFAULT_CATALOG_URL):
            client.requests.append((method, url, kwargs))
            if catalog_status != 200:
                return catalog_status, "unavailable"
            items = catalog if "status=active" in url else [i for i in catalog if i["status"] == "upcoming"]
            items = [i for i in items if ("status=" + i["status"]) in url]
            return 200, json.dumps({"total": len(items), "page": 1, "page_size": 100, "items": items})
        return await plain(method, url, **kwargs)

    client.request = request


def stream(sid, login, game_id, game, viewers):
    return {"node": {"id": f"s{sid}", "viewersCount": viewers, "title": "drops",
                     "game": {"id": str(game_id), "displayName": game},
                     "broadcaster": {"id": str(sid), "login": login, "displayName": login}}}


async def test_gated_dashboard_uses_catalog_and_reads_drops_from_live_channels(miner):
    inventory = [campaign("inv", 2, "Marvel Rivals", [drop("m1", 120, [benefit("mb", "Spray")], current=30)])]
    gated(miner, inventory, [
        catalog_item("c-rust", 1, "Rust", "rust", link="https://link/rust", end=24),
        catalog_item("c-halo", 3, "Halo Infinite", "halo-infinite"),
        catalog_item("c-soon", 4, "Apex Legends", "apex-legends", status="upcoming", end=200),
        catalog_item("inv", 2, "Marvel Rivals", "marvel-rivals"),
    ])
    directories = {
        "rust": [stream(10, "rustlive", 1, "Rust", 900), stream(11, "nothing", 1, "Rust", 50)],
        "marvel-rivals": [stream(20, "rivals", 2, "Marvel Rivals", 300)],
        "halo-infinite": [],
    }
    limits = {}

    def directory(v):
        limits[v["slug"]] = v["limit"]
        return {"data": {"game": {"streams": {"edges": directories.get(v["slug"], [])}}}}

    rust_campaign = {
        "id": "c-rust", "name": "Rust drops", "endAt": iso(24), "detailsURL": "https://www.twitch.tv/drops",
        "game": {"id": "1", "displayName": "Rust", "name": "Rust"},
        "timeBasedDrops": [{"id": "rd1", "name": "Skin", "startAt": iso(-24), "endAt": iso(24),
                            "requiredMinutesWatched": 60, "preconditionDrops": None,
                            "benefitEdges": [{"benefit": {"id": "rb1", "name": "Rust Skin", "imageAssetURL": "x"}}]}],
    }
    offers = {"10": [rust_campaign], "11": [], "20": [{"id": "inv"}]}
    miner.client.handlers["GameDirectory"] = directory
    miner.client.handlers["AvailableDrops"] = lambda v: {"data": {"channel": {
        "id": v["channelID"], "viewerDropCampaigns": offers[v["channelID"]]}}}

    await miner.fetch_campaigns()
    assert miner.campaign_source == "catalog"
    assert set(miner.campaigns) == {"c-rust", "c-halo", "c-soon", "inv"}
    assert miner.campaigns["inv"].drops["m1"].current_minutes == 30  # inventory wins over the catalog
    assert not miner.campaigns["c-rust"].drops and skip_reason(miner.campaigns["c-rust"], miner.settings) == "unavailable"
    assert miner.campaigns["c-rust"].game.box_art == "https://ttvdrops.lovinator.space/media/games/box_art/1.jpg"

    await miner.discover_channels()
    rust = miner.campaigns["c-rust"]
    assert rust.drops["rd1"].required_minutes == 60 and rust.drops["rd1"].benefits[0].name == "Rust Skin"
    # the link status is unknown for catalog campaigns that need a link: assumed linked, but flagged
    assert rust.linked and not rust.link_known
    assert miner.campaigns["c-halo"].link_known  # no link URL: nothing to link
    assert limits == {"marvel-rivals": 25, "rust": 10, "halo-infinite": 10}
    assert {ch.login for ch in miner.channels.values()} == {"rustlive", "rivals"}  # "nothing" offers nothing

    await miner.select_channel()
    assert [c.id for c in wanted_campaigns(miner.campaigns.values(), miner.settings)] == ["c-rust", "inv"]
    assert miner.watching.login == "rustlive" and miner.target_campaign.id == "c-rust"
    assert miner.snapshot()["campaign_source"] == "catalog"


async def test_unreachable_catalog_leaves_the_inventory(miner):
    inventory = [campaign("inv", 2, "Marvel Rivals", [drop("m1", 120, [benefit("mb", "Spray")], current=30)])]
    gated(miner, inventory, [catalog_item("c-rust", 1, "Rust", "rust")], catalog_status=503)
    await miner.fetch_campaigns()
    assert miner.campaign_source == "inventory"
    assert set(miner.campaigns) == {"inv"}


async def test_catalog_can_be_switched_off(miner):
    gated(miner, [], [catalog_item("c-rust", 1, "Rust", "rust")])
    miner.store.update({"campaign_catalog_url": ""})
    await miner.fetch_campaigns()
    assert miner.campaign_source == "inventory" and not miner.campaigns
    assert not [r for r in miner.client.requests if r[1].startswith(DEFAULT_CATALOG_URL)]


async def test_fetch_catalog_reads_every_page():
    pages = {1: [catalog_item(f"a{i}", i + 1, f"Game {i}", f"game-{i}") for i in range(100)],
             2: [catalog_item("a100", 500, "Last", "last")]}
    seen = []

    class Client:
        async def request(self, method, url, **kwargs):
            seen.append(url)
            page = int(url.split("page=")[1].split("&")[0])
            items = pages.get(page, []) if "status=active" in url else []
            return 200, json.dumps({"total": 101 if "status=active" in url else 0, "items": items})

    campaigns = await fetch_catalog(Client(), DEFAULT_CATALOG_URL)
    assert len(campaigns) == 101
    assert sum("status=active" in u for u in seen) == 2 and sum("status=upcoming" in u for u in seen) == 1


def test_catalog_entry_shape():
    entry = to_gql(catalog_item("c1", 7, "Rust", "rust", link="https://link"), DEFAULT_CATALOG_URL)
    assert entry["id"] == "c1" and entry["status"] == "ACTIVE" and entry["accountLinkURL"] == "https://link"
    assert entry["game"] == {"id": "7", "name": "Rust", "displayName": "Rust", "slug": "rust",
                             "boxArtURL": "https://ttvdrops.lovinator.space/media/games/box_art/7.jpg"}
    assert to_gql(catalog_item("c2", 7, "Rust", "rust", status="expired"), DEFAULT_CATALOG_URL) is None
