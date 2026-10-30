from fastapi.testclient import TestClient

from dropper.miner import LogBuffer
from dropper.models import Campaign
from dropper.web import create_app

from .conftest import benefit, campaign, drop


def client_for(miner, monkeypatch=None):
    return TestClient(create_app(miner, LogBuffer()))


def test_state_and_health(miner):
    api = client_for(miner)
    assert api.get("/api/health").json()["ok"] is True
    state = api.get("/api/state").json()
    assert state["user"]["login"] == "tester"
    assert state["counts"]["campaigns"] == 0
    assert "Dropper" in api.get("/").text


def test_settings_roundtrip_and_validation(miner, tmp_data):
    api = client_for(miner)
    r = api.put("/api/settings", json={"games_priority": ["Rust", " rust ", "Rust", "Dota 2"], "channels_preferred": ["@SomeOne"]})
    assert r.status_code == 200
    assert r.json()["games_priority"] == ["Rust", "rust", "Dota 2"]
    assert r.json()["channels_preferred"] == ["someone"]
    assert api.put("/api/settings", json={"refresh_interval_minutes": 1}).status_code == 422
    assert '"Dota 2"' in (tmp_data / "settings.json").read_text()


def test_campaigns_toggle_and_claim(miner):
    miner.campaigns = {"c1": Campaign.from_gql(campaign("c1", 1, "Rust", [drop("d1", 30, [benefit("b", "Hat")], current=10)]))}
    api = client_for(miner)
    data = api.get("/api/campaigns").json()
    assert data[0]["wanted"] is True and data[0]["queue_position"] == 1
    assert api.post("/api/campaigns/c1/toggle").json()["excluded"] is True
    assert api.get("/api/campaigns").json()[0]["skip_reason"] == "disabled"
    assert api.post("/api/claim/d1").status_code == 409
    assert api.post("/api/claim/nope").status_code == 404


def test_stats_endpoint(miner):
    miner.stats.add_watch_minute("Rust", "real", 30)
    miner.stats.add_claim(drop_id="d", drop_name="d", rewards="Hat", campaign_id="c", campaign_name="C",
                          game="Rust", method="sweep", success=True)
    data = client_for(miner).get("/api/stats?days=7").json()
    assert data["totals"]["minutes"] == 30 and data["totals"]["claims"] == 1
    assert len(data["timeline"]) == 7 and data["timeline"][-1]["minutes"] == 30
    assert data["per_game"][0] == {"game": "Rust", "minutes": 30, "claims": 1}


def test_basic_auth(miner, monkeypatch):
    monkeypatch.setenv("WEBUI_PASSWORD", "pw")
    api = client_for(miner)
    assert api.get("/api/state").status_code == 401
    assert api.get("/api/health").status_code == 200
    assert api.get("/api/state", auth=("admin", "pw")).status_code == 200


def test_channels_list_offered_campaigns_with_reasons(miner):
    from dropper.models import Channel, Game
    miner.campaigns = {
        "c1": Campaign.from_gql(campaign("c1", 1, "Rust", [drop("d1", 30, [benefit("b", "Hat")], current=0)])),
        "c2": Campaign.from_gql(campaign("c2", 1, "Rust", [drop("d2", 30, [benefit("b2", "Cap")], current=0)])),
    }
    miner.store.update({"campaigns_exclude": ["c2"]})
    miner.channels = {"7": Channel(id="7", login="x", display_name="X", online=True, game=Game(1, "Rust", "rust"),
                                   drops_enabled=True, campaign_ids={"c1", "c2", "c9"},
                                   campaign_names={"c1": "C1", "c2": "C2", "c9": "Esports Ignite"})}
    offered = {c["id"]: c for c in client_for(miner).get("/api/channels").json()[0]["campaigns"]}
    assert offered["c1"]["wanted"] is True and offered["c1"]["reason"] == ""
    assert offered["c2"]["wanted"] is False and offered["c2"]["reason"] == "disabled"
    assert offered["c9"]["name"] == "Esports Ignite" and offered["c9"]["reason"] == "unknown_campaign"


def test_drops_overview_lists_every_drop_with_history(miner):
    miner.campaigns = {"c1": Campaign.from_gql(campaign("c1", 1, "Rust", [
        drop("d1", 30, [benefit("b1", "Hat")], current=30, claimed=True),
        drop("d2", 60, [benefit("b2", "Cap")], current=60),
        drop("d3", 90, [benefit("b3", "Coat")], current=12),
    ]))}
    miner.stats.add_claim(drop_id="d1", drop_name="d1", rewards="Hat", campaign_id="c1", campaign_name="C",
                          game="Rust", method="pubsub", success=True)
    miner.rewards = [{"id": "b0", "name": "Old badge", "image": "", "game": "Rust", "last_awarded_at": None,
                      "count": 1, "link_url": "", "connected": True}]
    data = client_for(miner).get("/api/drops").json()
    by_id = {d["id"]: d for d in data["drops"]}
    assert by_id["d1"]["status"] == "claimed" and by_id["d1"]["claimed_at"]
    assert by_id["d2"]["status"] == "ready" and by_id["d3"]["status"] == "progress"
    assert by_id["d3"]["game"]["name"] == "Rust" and by_id["d3"]["campaign"]["wanted"] is True
    assert data["counts"] == {"claimed": 1, "ready": 1, "progress": 1}
    assert data["rewards"][0]["name"] == "Old badge" and data["claims"][0]["method"] == "pubsub"


def test_index_carries_asset_version(miner):
    html = client_for(miner).get("/").text
    assert "__ASSET_VERSION__" not in html
