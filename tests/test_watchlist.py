"""Games on the priority list that have no campaign yet: looked up on Twitch, scouted for drops-enabled
streams, picked up and announced as soon as a campaign starts."""

import pytest

from dropper.games import BOX_ART, GameIndex
from dropper.models import Campaign, norm_game, slugify
from dropper.selection import skip_reason, wanted_campaigns
from dropper.settings import PriorityMode, Settings
from dropper.twitch import GQLError, TwitchError

from .conftest import FakeClient, benefit, campaign, drop, iso
from .test_discovery import gated, stream
from .test_miner import setup_twitch
from .test_notify import notifying, posts, settle
from .test_web import client_for

SOT = {"id": "490377", "slug": "sea-of-thieves"}


def test_game_names_compare_loosely():
    assert norm_game("Counter-Strike") == norm_game("counter strike") == "counterstrike"
    assert norm_game("Pokémon GO") == norm_game("pokemon go")
    assert norm_game("Call of Duty: Warzone") == norm_game("call of duty warzone")
    assert norm_game("Minecraft") != norm_game("Minecraft Dungeons")
    assert norm_game("!!!") == "!!!"  # nothing left to compare: keep the text
    assert slugify("Pokémon UNITE") == "pokemon-unite"
    assert slugify("Tom Clancy’s The Division 2") == "tom-clancys-the-division-2"


def test_priority_list_matches_names_typed_loosely():
    cs = Campaign.from_gql(campaign("c1", 1, "Counter-Strike", [drop("d1", 30, [benefit("b1", "Case")])], end=10))
    rust = Campaign.from_gql(campaign("c2", 2, "Rust", [drop("d2", 30, [benefit("b2", "Skin")])], end=5))
    settings = Settings(games_priority=["counter strike"])
    assert [c.id for c in wanted_campaigns([rust, cs], settings)] == ["c1", "c2"]
    only = Settings(games_priority=["counter strike"], priority_mode=PriorityMode.PRIORITY_ONLY)
    assert skip_reason(cs, only) is None and skip_reason(rust, only) == "not_prioritized"


def lookup_client(*, redirect=None, directory=None):
    client = FakeClient()
    if redirect is not None:
        client.handlers["SlugRedirect"] = redirect
    if directory is not None:
        client.handlers["GameDirectory"] = directory
    return client


async def test_lookup_takes_twitch_spelling_and_box_art():
    def directory(v):
        assert v["slug"] == "sea-of-thieves" and v["limit"] == 1 and v["options"]["systemFilters"] == []
        return {"data": {"game": {"id": "490377", "name": "Sea of Thieves", "streams": {"edges": [{"node": {
            "game": {"id": "490377", "displayName": "Sea of Thieves",
                     "boxArtURL": "https://static-cdn.jtvnw.net/ttv-boxart/490377_IGDB-{width}x{height}.jpg"}}}]}}}}

    client = lookup_client(redirect=lambda v: {"data": {"game": SOT}}, directory=directory)
    games = GameIndex(client)
    game = await games.lookup("  sea of   thieves ")
    assert (game.id, game.name, game.slug) == (490377, "Sea of Thieves", "sea-of-thieves")
    assert game.box_art == "https://static-cdn.jtvnw.net/ttv-boxart/490377_IGDB.jpg"
    assert client.calls[0] == ("SlugRedirect", {"name": "sea of thieves"})
    calls = len(client.calls)
    assert await games.lookup("Sea Of Thieves") is game and len(client.calls) == calls  # remembered
    assert games.get("SEA OF THIEVES") is game


async def test_lookup_guesses_the_slug_when_the_name_lookup_fails():
    def broken(v):
        raise GQLError("DirectoryGameRedirect", [{"message": "PersistedQueryNotFound"}])

    def directory(v):
        return {"data": {"game": {"id": "27471", "name": "Minecraft"} if v["slug"] == "minecraft" else None}}

    games = GameIndex(lookup_client(redirect=broken, directory=directory))
    game = await games.lookup("minecraft")
    assert (game.name, game.slug, game.box_art) == ("Minecraft", "minecraft", BOX_ART.format(id=27471))
    # a guessed slug that finds nothing proves nothing: Twitch could not be asked properly
    with pytest.raises(TwitchError):
        await games.lookup("Minecraf")


async def test_unknown_names_are_not_asked_for_again_right_away():
    client = lookup_client(redirect={"data": {"game": None}}, directory={"data": {"game": None}})
    games = GameIndex(client)
    assert await games.lookup("Seas of Theives") is None
    calls = len(client.calls)
    assert await games.lookup("seas of theives") is None and len(client.calls) == calls


def sot_campaign(start=-1, end=48):
    return {
        "id": "sot-1", "name": "Sea of Thieves Season 20", "endAt": iso(end),
        "game": {"id": "490377", "displayName": "Sea of Thieves", "name": "Sea of Thieves"},
        "timeBasedDrops": [{"id": "s1", "name": "Sails", "startAt": iso(start), "endAt": iso(end),
                            "requiredMinutesWatched": 60, "preconditionDrops": None,
                            "benefitEdges": [{"benefit": {"id": "sb1", "name": "Pirate Sails", "imageAssetURL": "x"}}]}],
    }


async def test_watched_game_gets_picked_up_when_its_campaign_starts(miner):
    notifying(miner, games_priority=["sea of thieves"])
    gated(miner, [], [])  # Twitch hides the campaign list and the catalog does not know it yet
    live = []
    scouted = []

    def directory(v):
        if v["options"].get("systemFilters") == ["DROPS_ENABLED"]:
            scouted.append(v["slug"])
            return {"data": {"game": {"streams": {"edges": live}}}}
        return {"data": {"game": {"id": "490377", "name": "Sea of Thieves", "streams": {"edges": []}}}}

    miner.client.handlers["SlugRedirect"] = {"data": {"game": SOT}}
    miner.client.handlers["GameDirectory"] = directory
    miner.client.handlers["AvailableDrops"] = lambda v: {"data": {"channel": {
        "id": v["channelID"], "viewerDropCampaigns": [sot_campaign()] if v["channelID"] == "30" else []}}}

    await miner.refresh()  # no campaign yet: looked up, scouted, nothing to do
    assert miner.games.get("Sea of Thieves").slug == "sea-of-thieves"
    assert scouted == ["sea-of-thieves"] and miner.watching is None
    assert [g.name for g in miner.watched_without_campaign()] == ["Sea of Thieves"]

    live.append(stream(30, "pirate", 490377, "Sea of Thieves", 1200))  # the campaign started
    await miner.refresh()
    assert miner.target_campaign.id == "sot-1" and miner.watching.login == "pirate"
    assert miner.watched_without_campaign() == []
    await settle(miner)
    (payload,) = posts(miner)
    (embed,) = payload["embeds"]
    assert embed["title"] == "Drops for Sea of Thieves"
    assert embed["description"].startswith("**Sea of Thieves Season 20**\nA new campaign is running.")
    assert {"name": "Rewards", "value": "Pirate Sails", "inline": False} in embed["fields"]

    await miner.refresh()  # announced once
    await settle(miner)
    assert len(posts(miner)) == 1


async def test_campaigns_found_during_the_first_refresh_are_not_announced(miner):
    notifying(miner, games_priority=["Sea of Thieves"], notify_new_campaign=True)
    gated(miner, [], [])
    miner.client.handlers["SlugRedirect"] = {"data": {"game": SOT}}
    miner.client.handlers["GameDirectory"] = lambda v: {"data": {"game": {"id": "490377", "name": "Sea of Thieves",
        "streams": {"edges": [stream(30, "pirate", 490377, "Sea of Thieves", 10)]}}}}
    miner.client.handlers["AvailableDrops"] = lambda v: {"data": {"channel": {
        "id": v["channelID"], "viewerDropCampaigns": [sot_campaign(start=-30)]}}}
    await miner.refresh()  # it ran before Dropper started (an update, a restart)
    await settle(miner)
    assert "sot-1" in miner.campaigns and posts(miner) == []


async def test_upcoming_campaign_of_a_watched_game_is_announced_once(miner):
    notifying(miner, games_priority=["Apex Legends"], notify_new_campaign=True, ui_language="de")
    rust = campaign("c1", 1, "Rust", [drop("d1", 30, [benefit("b1", "Hat")])])
    setup_twitch(miner, [rust])
    await miner.fetch_campaigns()  # first load: only takes note
    apex = campaign("c2", 5, "Apex Legends", [drop("a1", 60, [benefit("b2", "Charm")])], status="UPCOMING", start=20, end=200)
    setup_twitch(miner, [rust, apex])
    await miner.fetch_campaigns()
    await settle(miner)
    (payload,) = posts(miner)
    (embed,) = payload["embeds"]
    assert embed["title"] == "Drops für Apex Legends"
    assert embed["description"] == "**Apex Legends Kampagne c2**\nEine neue Kampagne steht an. Dropper farmt sie, sobald sie startet."
    assert embed["fields"][0]["name"] == "Startet" and embed["fields"][0]["value"].startswith("<t:")
    assert "url" not in embed and all(f["name"] != "Spielkonto" for f in embed["fields"])  # linked

    # it starts and is farmed: already announced, so the plain "new campaign" message stays away
    started = dict(apex, status="ACTIVE", startAt=iso(-1))
    setup_twitch(miner, [rust, started])
    await miner.fetch_campaigns()
    assert "c2" in [c.id for c in wanted_campaigns(miner.campaigns.values(), miner.settings)]
    await settle(miner)
    assert len(posts(miner)) == 1


async def test_watched_campaign_that_needs_a_linked_account_says_so(miner):
    notifying(miner, games_priority=["Sea of Thieves"])
    setup_twitch(miner, [])
    await miner.fetch_campaigns()
    setup_twitch(miner, [campaign("c3", 490377, "Sea of Thieves", [drop("s1", 60, [benefit("b3", "Sails")])],
                                  start=-2, linked=False)])
    await miner.fetch_campaigns()
    assert skip_reason(miner.campaigns["c3"], miner.settings) == "not_linked"
    await settle(miner)
    (embed,) = posts(miner)[0]["embeds"]
    assert embed["description"].endswith("Link your game account so Dropper can farm it.")
    assert {"name": "Game account", "value": "[Link account](https://link)", "inline": True} in embed["fields"]
    assert embed["url"] == "https://link"


async def test_watched_announcements_can_be_switched_off(miner):
    notifying(miner, games_priority=["Dota 2"], notify_watched=False, notify_new_campaign=True)
    setup_twitch(miner, [])
    await miner.fetch_campaigns()
    setup_twitch(miner, [campaign("c9", 9, "Dota 2", [drop("d9", 30, [benefit("b9", "Ward")])], start=-1)])
    await miner.fetch_campaigns()
    await settle(miner)
    (payload,) = posts(miner)
    assert payload["embeds"][0]["title"] == "New campaign"  # the plain message still comes


def test_game_search_and_lookup_endpoints(miner):
    miner.campaigns = {"c1": Campaign.from_gql(campaign("c1", 1, "Rust", [drop("d1", 30, [benefit("b1", "Hat")])]))}
    miner.games.remember(miner.campaigns["c1"].game)
    miner.rewards = [{"game": "Sea of Thieves"}]
    miner.client.handlers["SlugRedirect"] = lambda v: {"data": {"game": SOT if norm_game(v["name"]) == "seaofthieves" else None}}
    miner.client.handlers["GameDirectory"] = lambda v: {"data": {"game": (
        {"id": "490377", "name": "Sea of Thieves"} if v["slug"] == "sea-of-thieves" else None)}}
    api = client_for(miner)

    r = api.get("/api/games/search", params={"q": "ru"}).json()
    assert r["results"][0] == {"name": "Rust", "id": 1, "box_art": "https://img/box.jpg", "campaign": "active"}
    assert r["lookup"]["status"] == "missing"

    r = api.get("/api/games/search", params={"q": "sea of thieves"}).json()
    assert r["lookup"]["status"] == "found" and r["lookup"]["game"]["name"] == "Sea of Thieves"
    assert r["results"][0]["name"] == "Sea of Thieves" and r["results"][0]["id"] == 490377

    r = api.post("/api/games/lookup", json={"names": ["Rust", "Seas of Theives", ""]}).json()
    assert [(g["query"], g["status"]) for g in r["games"]] == [("Rust", "found"), ("Seas of Theives", "missing")]


def test_lookup_reports_when_twitch_cannot_be_asked(miner):
    def broken(v):
        raise GQLError("x", [{"message": "service unavailable"}])

    miner.client.handlers["SlugRedirect"] = broken
    miner.client.handlers["GameDirectory"] = broken
    r = client_for(miner).get("/api/games/search", params={"q": "Minecraft"}).json()
    assert r["lookup"] == {"query": "Minecraft", "status": "unavailable", "game": None}
