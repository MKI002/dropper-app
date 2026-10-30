import asyncio

from dropper.models import Campaign
from dropper.twitch import TwitchError

from .conftest import benefit, campaign, drop


def setup_twitch(miner, campaigns, inventory=None, awarded=None):
    client = miner.client
    details = {c["id"]: c for c in campaigns}
    listed = [{"id": c["id"], "status": c["status"], "game": c["game"], "self": c["self"]} for c in campaigns]
    client.handlers["Campaigns"] = {"data": {"currentUser": {"dropCampaigns": listed}}}
    client.handlers["CampaignDetails"] = lambda v: {"data": {"user": {"dropCampaign": details[v["dropID"]]}}}
    client.handlers["Inventory"] = lambda v: {"data": {"currentUser": {"inventory": {
        "dropCampaignsInProgress": inventory or [], "gameEventDrops": awarded or []}}}}


async def test_fetch_campaigns_merges_inventory_progress(miner):
    base = campaign("c1", 1, "Rust", [drop("d1", 60, [benefit("b1", "Skin")])])
    progress = {"id": "c1", "timeBasedDrops": [drop("d1", 60, [benefit("b1", "Skin")], current=45, instance="42#c1#d1")]}
    setup_twitch(miner, [base], inventory=[progress])
    await miner.fetch_campaigns()
    d = miner.campaigns["c1"].drops["d1"]
    assert d.current_minutes == 45 and d.claim_id == "42#c1#d1"
    assert miner.campaigns["c1"].allowed_channels == {}


async def test_claim_falls_back_to_generated_id(miner):
    fast(miner)
    c = Campaign.from_gql(campaign("c1", 1, "Rust", [drop("d1", 30, [benefit("b", "Hat")], current=30, instance="bad")]))
    miner.campaigns = {"c1": c}
    tried = []

    def claim(v):
        cid = v["input"]["dropInstanceID"]
        tried.append(cid)
        if cid == "42#c1#d1":
            return {"data": {"claimDropRewards": {"status": "ELIGIBLE_FOR_ALL"}}}
        return {"data": {"claimDropRewards": {"status": "DROP_INSTANCE_NOT_FOUND"}}}

    miner.client.handlers["ClaimDrop"] = claim
    assert await miner.claim_all_ready("sweep") == 1
    assert tried == ["bad", "42#c1#d1"]
    assert c.drops["d1"].is_claimed
    claims = miner.stats.recent_claims()
    assert claims[0]["success"] == 1 and claims[0]["method"] == "sweep"


async def test_claim_retries_transient_failures(miner, monkeypatch):
    fast(miner)
    c = Campaign.from_gql(campaign("c1", 1, "Rust", [drop("d1", 30, [benefit("b", "Hat")], current=30, instance="42#c1#d1")]))
    miner.campaigns = {"c1": c}
    calls = []

    def claim(v):
        calls.append(v)
        if len(calls) < 3:
            raise TwitchError("connection reset")
        return {"data": {"claimDropRewards": {"status": "DROP_INSTANCE_ALREADY_CLAIMED"}}}

    miner.client.handlers["ClaimDrop"] = claim
    assert await miner.claim_drop(c.drops["d1"]) is True
    assert len(calls) == 3 and c.drops["d1"].is_claimed


async def test_failed_claim_is_recorded_and_retried_later(miner, monkeypatch):
    fast(miner)
    c = Campaign.from_gql(campaign("c1", 1, "Rust", [drop("d1", 30, [benefit("b", "Hat")], current=30)]))
    miner.campaigns = {"c1": c}
    miner.client.handlers["ClaimDrop"] = {"data": {"claimDropRewards": {"status": "UNKNOWN_X"}}}
    assert await miner.claim_drop(c.drops["d1"]) is False
    assert c.drops["d1"].claimable()  # still pending -> next sweep tries again
    assert miner.stats.recent_claims()[0]["success"] == 0


async def test_discover_and_select_verified_channel(miner):
    camp = campaign("c1", 1, "Rust", [drop("d1", 60, [benefit("b", "Skin")], current=0)])
    miner.campaigns = {"c1": Campaign.from_gql(camp)}

    def directory(v):
        assert v["options"]["systemFilters"] == ["DROPS_ENABLED"]
        edges = []
        for i, (login, viewers) in enumerate([("fake", 5000), ("real", 300)]):
            edges.append({"node": {"id": f"s{i}", "viewersCount": viewers, "title": "t",
                                   "game": {"id": "1", "displayName": "Rust"},
                                   "broadcaster": {"id": str(i + 10), "login": login, "displayName": login}}})
        return {"data": {"game": {"streams": {"edges": edges}}}}

    miner.client.handlers["GameDirectory"] = directory
    miner.client.handlers["AvailableDrops"] = lambda v: {"data": {"channel": {
        "id": v["channelID"], "viewerDropCampaigns": [{"id": "c1"}] if v["channelID"] == "11" else []}}}
    await miner.discover_channels()
    await miner.select_channel()
    assert miner.watching.login == "real"
    assert miner.target_campaign.id == "c1"
    assert miner.state == "watching"


async def test_watch_sends_spade_event_and_tracks_progress(miner, monkeypatch):
    camp = campaign("c1", 1, "Rust", [drop("d1", 60, [benefit("b", "Skin")], current=0)])
    miner.campaigns = {"c1": Campaign.from_gql(camp)}
    from dropper.models import Channel, Game
    ch = Channel(id="11", login="real", display_name="Real", online=True, game=Game(1, "Rust", "rust"),
                 broadcast_id="b1", campaign_ids={"c1"})
    miner.channels = {"11": ch}
    miner.target_campaign = miner.campaigns["c1"]
    miner.watching = ch
    assert await miner.send_watch(ch)
    method, url, kwargs = miner.client.requests[-1]
    assert (method, url) == ("POST", "https://spade.example/track") and "data" in kwargs["data"]
    miner.client.handlers["CurrentDrop"] = {"data": {"currentUser": {"dropCurrentSession": {"dropID": "d1", "currentMinutesWatched": 17}}}}
    await miner._check_progress(ch)
    assert miner.campaigns["c1"].drops["d1"].current_minutes == 17
    assert miner.current_drop_id == "d1"


async def test_watch_requests_stream_segments(miner):
    from dropper.models import Channel, Game
    ch = Channel(id="11", login="real", display_name="Real", online=True, game=Game(1, "Rust", "rust"),
                 broadcast_id="b1", campaign_ids=set())
    miner.client.handlers["PlaybackAccessToken"] = {"data": {"streamPlaybackAccessToken": {"value": "v", "signature": "s"}}}
    playlists = {
        "usher": '#EXTM3U\nhttps://cdn.example/best.m3u8\nhttps://cdn.example/low.m3u8\n',
        "low": "#EXTM3U\nhttps://cdn.example/seg1.ts\nhttps://cdn.example/seg2.ts\n",
    }

    async def request(method, url, **kwargs):
        miner.client.requests.append((method, url, kwargs))
        if "usher" in url:
            return 200, playlists["usher"]
        if url.endswith("low.m3u8"):
            return 200, playlists["low"]
        if method == "HEAD":
            return 200, ""
        return 204, ""

    miner.client.request = request
    assert await miner.send_watch(ch)
    heads = [u for m, u, _ in miner.client.requests if m == "HEAD"]
    assert heads == ["https://cdn.example/seg1.ts", "https://cdn.example/seg2.ts"]
    miner.client.requests.clear()
    assert await miner.send_watch(ch)  # same segments again: nothing new to request
    assert not [1 for m, *_ in miner.client.requests if m == "HEAD"]


async def test_pubsub_drop_claim_event_claims(miner, monkeypatch):
    fast(miner)
    c = Campaign.from_gql(campaign("c1", 1, "Rust", [drop("d1", 30, [benefit("b", "Hat")], current=29)]))
    miner.campaigns = {"c1": c}
    seen = []
    miner.client.handlers["ClaimDrop"] = lambda v: seen.append(v) or {"data": {"claimDropRewards": {"status": "ELIGIBLE_FOR_ALL"}}}
    await miner._on_pubsub("user-drop-events.42", {"type": "drop-claim", "data": {"drop_id": "d1", "drop_instance_id": "inst-1"}})
    assert seen[0]["input"]["dropInstanceID"] == "inst-1"
    assert c.drops["d1"].is_claimed


async def test_settings_change_requests_refresh(miner):
    miner._wake.clear()
    miner.store.update({"games_exclude": ["Rust"]})
    assert miner._wake.is_set()
    miner._wake.clear()
    miner.store.update({"webhook_url": "https://example.com/hook"})
    assert not miner._wake.is_set()


def fast(miner):
    miner.retry_delay = 0
    miner.claim_settle_seconds = 0


async def test_failed_claim_backs_off_and_survives_refresh(miner):
    fast(miner)
    base = campaign("c1", 1, "Rust", [drop("d1", 30, [benefit("b", "Hat")])], linked=False)
    progress = {"id": "c1", "timeBasedDrops": [drop("d1", 30, [benefit("b", "Hat")], current=30)]}
    setup_twitch(miner, [base], inventory=[progress])
    await miner.fetch_campaigns()
    attempts = []
    miner.client.handlers["ClaimDrop"] = lambda v: attempts.append(v) or {
        "data": {"claimDropRewards": {"status": "INELIGIBLE"}}}
    assert await miner.claim_all_ready("refresh") == 0
    d = miner.campaigns["c1"].drops["d1"]
    assert d.status() == "failed" and d.claim_error == "INELIGIBLE" and d.claim_attempts == 1
    assert d.needs_link and d.claim_retry_at is not None
    tried = len(attempts)
    assert await miner.claim_all_ready("sweep") == 0
    assert len(attempts) == tried  # backing off, no new request
    assert miner.snapshot()["counts"]["claim_failed"] == 1

    await miner.fetch_campaigns()  # re-read from Twitch: bookkeeping stays
    d = miner.campaigns["c1"].drops["d1"]
    assert d.claim_attempts == 1 and d.claim_retry_at is not None

    base["self"]["isAccountConnected"] = True  # user linked the account in the meantime
    await miner.fetch_campaigns()
    miner.client.handlers["ClaimDrop"] = {"data": {"claimDropRewards": {"status": "ELIGIBLE_FOR_ALL"}}}
    assert await miner.claim_all_ready("refresh") == 1
    d = miner.campaigns["c1"].drops["d1"]
    assert d.is_claimed and d.claim_error == "" and d.status() == "claimed"


async def test_auto_claim_off_leaves_drops_for_the_button(miner):
    fast(miner)
    miner.store.update({"auto_claim": False})
    c = Campaign.from_gql(campaign("c1", 1, "Rust", [drop("d1", 30, [benefit("b", "Hat")], current=29)]))
    miner.campaigns = {"c1": c}
    seen = []
    miner.client.handlers["ClaimDrop"] = lambda v: seen.append(v) or {"data": {"claimDropRewards": {"status": "ELIGIBLE_FOR_ALL"}}}
    await miner._on_pubsub("user-drop-events.42", {"type": "drop-claim", "data": {"drop_id": "d1", "drop_instance_id": "inst-1"}})
    miner._apply_progress("d1", 30)
    assert await miner.claim_all_ready("sweep") == 0
    d = c.drops["d1"]
    assert not seen and d.status() == "ready" and d.claim_id == "inst-1"
    assert await miner.claim_drop(d, method="manual") is True
    assert seen[0]["input"]["dropInstanceID"] == "inst-1"


async def test_selection_reason_explains_the_pick(miner):
    from dropper.models import Channel, Game
    rust = Game(1, "Rust", "rust")
    miner.campaigns = {
        "c1": Campaign.from_gql(campaign("c1", 1, "Rust", [drop("d1", 60, [benefit("b", "Skin")], current=0)], end=5)),
        "c2": Campaign.from_gql(campaign("c2", 2, "Dota", [drop("d2", 60, [benefit("b2", "Hat")], current=0)], end=2)),
    }
    miner.channels = {
        "1": Channel(id="1", login="big", display_name="Big", online=True, game=rust, viewers=900, campaign_ids={"c1"}),
        "2": Channel(id="2", login="small", display_name="Small", online=True, game=rust, viewers=50, campaign_ids={"c1"}),
    }
    await miner.select_channel()
    assert miner.watching.login == "big"
    assert miner.snapshot()["selection"] == {
        "campaign_id": "c1", "campaign": "Rust Kampagne c1", "game": "Rust", "position": 2, "queue": 2,
        "candidates": 2, "rule": "viewers"}
    assert miner.snapshot()["activity"] == {"code": "watching", "params": {"channel": "Big", "game": "Rust"}}
    miner.channels["2"].viewers = 5000
    await miner.select_channel()
    assert miner.watching.login == "big" and miner.selection["rule"] == "stay"
    miner.channels = {}
    await miner.select_channel()
    assert miner.selection is None and miner.activity["code"] == "no_channels"


async def test_new_priority_switches_right_away(miner):
    from dropper.models import Channel, Game
    miner.campaigns = {
        "c1": Campaign.from_gql(campaign("c1", 1, "Rust", [drop("d1", 60, [benefit("b", "Skin")], current=0)], end=2)),
        "c2": Campaign.from_gql(campaign("c2", 2, "Dota", [drop("d2", 60, [benefit("b2", "Hat")], current=0)], end=9)),
    }
    miner.channels = {
        "1": Channel(id="1", login="rusty", display_name="Rusty", online=True, game=Game(1, "Rust", "rust"),
                     viewers=900, campaign_ids={"c1"}),
        "2": Channel(id="2", login="dotty", display_name="Dotty", online=True, game=Game(2, "Dota", "dota"),
                     viewers=50, campaign_ids={"c2"}),
    }
    await miner.select_channel()
    miner.current_drop_id = "d1"  # what Twitch reported while watching Rust
    assert miner.watching.login == "rusty" and miner.snapshot()["drop"]["id"] == "d1"
    miner._wake.clear()
    miner.store.update({"games_priority": ["Dota"]})
    # no waiting for the full refresh: the next state the UI reads already shows the new pick
    assert miner.watching.login == "dotty" and miner.target_campaign.id == "c2"
    assert miner.snapshot()["drop"]["id"] == "d2"
    assert miner._wake.is_set()  # the refresh still runs to pick up new channels


async def test_refresh_requested_during_a_refresh_is_not_lost(miner, monkeypatch):
    import asyncio
    calls = []

    async def refresh():
        calls.append(1)
        if len(calls) == 1:
            miner.request_refresh()  # a settings change while the first refresh runs

    async def noop(*_):
        pass

    monkeypatch.setattr(miner, "refresh", refresh)
    monkeypatch.setattr(miner, "_update_pubsub_topics", noop)
    monkeypatch.setattr(miner.pubsub, "start", lambda: None)
    monkeypatch.setattr(miner, "_seconds_until_next_refresh", lambda: 3600)
    task = asyncio.create_task(miner._main_loop())
    for _ in range(50):
        await asyncio.sleep(0.01)
        if len(calls) >= 2:
            break
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert len(calls) == 2


async def test_watch_time_follows_real_time_not_wakeups(miner, monkeypatch):
    """Early wake-ups (channel switches, settings changes) used to count an extra minute each time."""
    import dropper.miner as miner_mod
    from dropper.models import Channel, Game
    a = Channel(id="11", login="a", display_name="A", online=True, game=Game(1, "Rust", "rust"), broadcast_id="b1")
    b = Channel(id="12", login="b", display_name="B", online=True, game=Game(1, "Rust", "rust"), broadcast_id="b2")
    clock = [1000.0]
    loops = [0]
    monkeypatch.setattr(miner_mod.time, "monotonic", lambda: clock[0])

    async def send_watch(channel):
        return True

    async def nothing(*args):
        return None

    async def sleep(seconds):
        loops[0] += 1
        if loops[0] >= 600:
            raise asyncio.CancelledError
        clock[0] += 5  # woken early every 5 s
        miner.watching = b if miner.watching is a else a  # and switching channel each time

    monkeypatch.setattr(miner, "send_watch", send_watch)
    monkeypatch.setattr(miner, "_check_progress", nothing)
    monkeypatch.setattr(miner, "_sleep_or_reselect", sleep)
    miner.client.logged_in.set()
    miner.watching = a
    try:
        await miner._watch_loop()
    except asyncio.CancelledError:
        pass
    elapsed = clock[0] - 1000.0
    assert miner.session_watch_minutes <= elapsed // 60
    assert miner.session_watch_minutes >= elapsed // 60 - 1
