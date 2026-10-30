from datetime import datetime, timezone

from dropper.models import Campaign, Channel, Game
from dropper.selection import pick_channel, skip_reason, wanted_campaigns
from dropper.settings import GameMode, PriorityMode, Settings

from .conftest import benefit, campaign, drop, iso


def make(cid="c1", game_id=1, game="Rust", drops=None, **kw) -> Campaign:
    drops = drops if drops is not None else [drop(f"{cid}-d1", 60, [benefit(f"{cid}-b1", "Skin")], current=10)]
    return Campaign.from_gql(campaign(cid, game_id, game, drops, **kw))


def live(cid: str, login: str, game_id: int, game: str, viewers=100, campaigns=None, source="directory") -> Channel:
    return Channel(id=cid, login=login, display_name=login, online=True, game=Game(game_id, game, game.lower()),
                   viewers=viewers, drops_enabled=True, campaign_ids=campaigns, source=source)


def test_parse_campaign_and_progress():
    c = make()
    d = c.drops["c1-d1"]
    assert c.game.name == "Rust" and c.active and c.linked
    assert d.current_minutes == 10 and d.remaining_minutes == 50
    assert d.can_earn() and not d.claimable()
    assert c.game.box_art == "https://img/box.jpg"


def test_claimable_when_minutes_done_and_not_claimed():
    c = make(drops=[drop("d", 30, [benefit("b", "Hat")], current=30, instance="inst")])
    d = c.drops["d"]
    assert d.claimable() and d.claim_id == "inst"
    assert not d.can_earn()


def test_claim_inferred_from_awarded_benefits():
    data = campaign("c", 1, "Rust", [drop("d", 30, [benefit("b", "Hat")])])
    awarded = {"b": datetime.fromisoformat(iso(-1).replace("Z", "+00:00"))}
    c = Campaign.from_gql(data, awarded)
    assert c.drops["d"].is_claimed and c.finished


def test_preconditions_block_later_drops():
    c = make(drops=[
        drop("first", 60, [benefit("b1", "A")], current=5),
        drop("second", 120, [benefit("b2", "B")], current=0, pre=["first"]),
    ])
    assert c.drops["first"].can_earn()
    assert not c.drops["second"].can_earn()
    assert c.drops["second"].total_remaining_minutes == 175


def test_skip_reasons():
    s = Settings()
    assert skip_reason(make(), s) is None
    assert skip_reason(make(linked=False), s) == "not_linked"
    badge = make(linked=False, drops=[drop("d", 30, [benefit("b", "Badge", "BADGE")], current=0)])
    assert skip_reason(badge, s) is None
    assert skip_reason(badge, Settings(mine_badges_emotes=False)) == "badges_off"
    assert skip_reason(make(), Settings(games_exclude=["rust"])) == "game_excluded"
    assert skip_reason(make(), Settings(game_mode=GameMode.WHITELIST, games_whitelist=["Dota 2"])) == "not_whitelisted"
    assert skip_reason(make(), Settings(campaigns_exclude=["c1"])) == "disabled"
    assert skip_reason(make(start=5, end=50, status="UPCOMING"), s) == "upcoming"
    # details missing: not "all drops claimed", just nothing to earn
    empty = make(drops=[])
    assert not empty.finished and skip_reason(empty, s) == "unavailable"
    # a gift-sub drop needs no watch time: nothing left to farm, but nothing was claimed either
    gift = make(drops=[drop("g", 0, [benefit("gb", "Wrap")], current=0)])
    assert gift.finished and skip_reason(gift, s) == "not_watchable"
    done = make(drops=[drop("d", 30, [benefit("b", "Hat")], current=30, claimed=True)])
    assert skip_reason(done, s) == "finished"


def test_wanted_order_priority_then_ending():
    a = make("a", 1, "Rust", end=10)
    b = make("b", 2, "Dota 2", end=5)
    c = make("c", 3, "Valorant", end=100)
    assert [x.id for x in wanted_campaigns([a, b, c], Settings())] == ["b", "a", "c"]
    assert [x.id for x in wanted_campaigns([a, b, c], Settings(games_priority=["valorant"]))] == ["c", "b", "a"]
    only = Settings(games_priority=["Rust"], priority_mode=PriorityMode.PRIORITY_ONLY)
    assert [x.id for x in wanted_campaigns([a, b, c], only)] == ["a"]


def test_pick_channel_uses_verified_campaigns_and_acl():
    rust = make("rust", 1, "Rust")
    acl = make("acl", 2, "Dota 2", acl=[{"id": "200", "name": "pro"}])
    wanted = [acl, rust]
    channels = [
        live("100", "big", 2, "Dota 2", viewers=9000, campaigns=set()),  # not in ACL
        live("200", "pro", 2, "Dota 2", viewers=10, campaigns={"acl"}, source="acl"),
        live("300", "rusty", 1, "Rust", campaigns={"rust"}),
    ]
    campaign_, channel = pick_channel(wanted, channels, Settings())
    assert campaign_.id == "acl" and channel.login == "pro"
    # blacklisted -> falls through to the next campaign
    campaign_, channel = pick_channel(wanted, channels, Settings(channels_blacklist=["pro"]))
    assert campaign_.id == "rust" and channel.login == "rusty"


def test_pick_channel_respects_verification_and_stickiness():
    rust = make("rust", 1, "Rust")
    no_drops = live("1", "nodrops", 1, "Rust", viewers=5000, campaigns=set())
    a = live("2", "a", 1, "Rust", viewers=100, campaigns={"rust"})
    b = live("3", "b", 1, "Rust", viewers=900, campaigns={"rust"})
    _, ch = pick_channel([rust], [no_drops, a, b], Settings())
    assert ch.login == "b"
    _, ch = pick_channel([rust], [no_drops, a, b], Settings(), current=a)
    assert ch.login == "a"  # no needless switch
    _, ch = pick_channel([rust], [no_drops, a, b], Settings(channels_preferred=["a"]))
    assert ch.login == "a"
    _, ch = pick_channel([rust], [no_drops, a, b], Settings(), cooldown={"3"})
    assert ch.login == "a"
    other_game = live("4", "x", 9, "Other", campaigns={"rust"})
    assert pick_channel([rust], [other_game], Settings()) == (None, None)


def test_drop_status_words():
    c = make(drops=[
        drop("done", 30, [benefit("b1", "A")], current=30, claimed=True),
        drop("ready", 30, [benefit("b2", "B")], current=30),
        drop("run", 60, [benefit("b3", "C")], current=10),
        drop("wait", 60, [benefit("b4", "D")], current=0),
        drop("after", 90, [benefit("b5", "E")], current=0, pre=["run"]),
        drop("subs", 0, [benefit("b6", "F")], current=0),
    ])
    status = {d.id: d.status() for d in c.drops.values()}
    assert status == {"done": "claimed", "ready": "ready", "run": "progress", "wait": "pending",
                      "after": "locked", "subs": "other"}
    c.drops["ready"].claim_error = "INELIGIBLE"
    assert c.drops["ready"].status() == "failed"
    old = make(cid="old", drops=[drop("o1", 30, [benefit("x", "X")], current=30), drop("o2", 60, [benefit("y", "Y")], current=5)],
               start=-100, end=-30)
    assert {d.id: d.status() for d in old.drops.values()} == {"o1": "missed", "o2": "expired"}
