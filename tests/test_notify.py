import asyncio
import json

from dropper.models import Campaign
from dropper.notify import DEFAULT_AVATAR, Notifier, _default_avatar, _webhook_base, is_discord, sender_name, translate
from dropper.settings import Settings

from .conftest import benefit, campaign, drop
from .test_miner import fast, setup_twitch
from .test_web import client_for

DISCORD = "https://discord.com/api/webhooks/123/token"


def posts(miner):
    return [kwargs["json"] for method, url, kwargs in miner.client.requests if method == "POST"]


async def settle(miner):
    await asyncio.sleep(0.05)  # lets the notifier's short collection pause run out


def notifying(miner, url=DISCORD, **settings):
    miner.notifier.delay = 0
    miner.store.update({"webhook_url": url, **settings})


def test_discord_urls_are_recognized():
    assert is_discord(DISCORD)
    assert is_discord("https://canary.discord.com/api/webhooks/1/x")
    assert not is_discord("https://example.com/api/webhooks/1/x")
    assert not is_discord("https://discord.com.evil.example/api/webhooks/1/x")


def test_texts_follow_the_ui_language():
    assert translate("de", "notify.claimed") == "Drop abgeholt"
    assert translate("pt-BR", "notify.field.game") == "Jogo"
    assert translate("xx", "notify.claimed") == "Drop claimed"


def test_webhook_url_without_scheme_gets_https(miner):
    miner.store.update({"webhook_url": "  discord.com/api/webhooks/1/x "})
    assert miner.settings.webhook_url == "https://discord.com/api/webhooks/1/x"


async def test_claims_are_batched_into_one_discord_message(miner):
    notifying(miner, ui_language="de")
    c = Campaign.from_gql(campaign("c1", 1, "Rust", [drop("d1", 30, [benefit("b1", "Hat")]),
                                                     drop("d2", 60, [benefit("b2", "Shirt")])]))
    for d in c.drops.values():
        d.is_claimed = True
        miner._record_claim(d, "auto", True, "")
    await settle(miner)
    sent = posts(miner)
    assert len(sent) == 1
    payload = sent[0]
    assert payload["username"] == "Dropper" and payload["allowed_mentions"] == {"parse": []}
    # both drops, and the campaign is complete after the second one
    titles = [e["title"] for e in payload["embeds"]]
    assert titles == ["Drop abgeholt", "Drop abgeholt", "Kampagne abgeschlossen"]
    first = payload["embeds"][0]
    assert first["description"] == "**Hat**" and first["thumbnail"]["url"] == "https://img/b1.png"
    assert {"name": "Spiel", "value": "Rust", "inline": True} in first["fields"]


async def test_switched_off_events_send_nothing(miner):
    notifying(miner, notify_claimed=False, notify_campaign_done=False)
    c = Campaign.from_gql(campaign("c1", 1, "Rust", [drop("d1", 30, [benefit("b1", "Hat")])]))
    d = c.drops["d1"]
    d.is_claimed = True
    miner._record_claim(d, "auto", True, "")
    await settle(miner)
    assert posts(miner) == []


async def test_other_webhooks_get_json(miner):
    notifying(miner, url="https://example.com/hook", notify_campaign_done=False)
    c = Campaign.from_gql(campaign("c1", 1, "Rust", [drop("d1", 30, [benefit("b1", "Hat")])]))
    d = c.drops["d1"]
    d.is_claimed = True
    miner._record_claim(d, "auto", True, "")
    await settle(miner)
    (payload,) = posts(miner)
    assert payload["event"] == "drop_claimed" and payload["game"] == "Rust"
    assert "Hat" in payload["text"] and "**" not in payload["text"]


async def test_only_the_first_failed_claim_is_announced(miner):
    fast(miner)
    notifying(miner)
    c = Campaign.from_gql(campaign("c1", 1, "Rust", [drop("d1", 30, [benefit("b", "Hat")], current=30)], linked=False))
    miner.campaigns = {"c1": c}
    miner.client.handlers["ClaimDrop"] = {"data": {"claimDropRewards": {"status": "INELIGIBLE"}}}
    d = c.drops["d1"]
    assert not await miner.claim_drop(d)
    d.claim_retry_at = None
    assert not await miner.claim_drop(d)
    await settle(miner)
    (payload,) = posts(miner)
    (embed,) = payload["embeds"]
    assert embed["title"] == "Claim failed" and embed["url"] == "https://link"
    assert {"name": "Reason", "value": "`INELIGIBLE`", "inline": False} in embed["fields"]


async def test_new_campaigns_are_announced_after_the_first_load(miner):
    notifying(miner, notify_new_campaign=True)
    old = campaign("c1", 1, "Rust", [drop("d1", 30, [benefit("b1", "Hat")])])
    setup_twitch(miner, [old])
    await miner.fetch_campaigns()  # first load: only takes note
    fresh = campaign("c2", 2, "Dota", [drop("d2", 30, [benefit("b2", "Cape")])], start=-1)
    returning = campaign("c3", 3, "Apex", [drop("d3", 30, [benefit("b3", "Skin")])], start=-72)
    setup_twitch(miner, [old, fresh, returning])
    await miner.fetch_campaigns()
    await miner.fetch_campaigns()  # nothing twice
    await settle(miner)
    (payload,) = posts(miner)
    (embed,) = payload["embeds"]
    assert embed["title"] == "New campaign" and embed["description"] == "**Dota Kampagne c2**"
    assert embed["fields"][1]["value"].startswith("<t:")


async def test_lost_login_is_announced_once_but_a_logout_is_not(miner, monkeypatch):
    notifying(miner)
    client = miner.client

    async def invalid():
        return False

    async def device_login():
        client.logged_in.set()

    monkeypatch.setattr(client, "validate", invalid)
    monkeypatch.setattr(client, "device_login", device_login, raising=False)
    await miner.ensure_login()  # logged in from the start
    client.logout()  # Twitch rejected the token
    await miner.ensure_login()
    await settle(miner)
    (payload,) = posts(miner)
    assert payload["embeds"][0]["title"] == "Login needed"

    miner.logout()  # asked for in the UI
    await miner.ensure_login()
    await settle(miner)
    assert len(posts(miner)) == 1


async def test_test_message_reports_what_discord_said(miner):
    async def request(method, url, **kwargs):
        miner.client.requests.append((method, url, kwargs))
        return (204, "") if url == DISCORD else (404, '{"message": "Unknown Webhook", "code": 10015}')

    miner.client.request = request
    assert await miner.notifier.test(DISCORD) == (True, "HTTP 204")
    assert await miner.notifier.test("https://discord.com/api/webhooks/9/gone") == (False, "HTTP 404: Unknown Webhook")
    assert posts(miner)[0]["embeds"][0]["title"] == "Test message"


def test_test_endpoint_needs_a_url(miner):
    api = client_for(miner)
    assert api.post("/api/notify/test", json={}).status_code == 400
    r = api.post("/api/notify/test", json={"url": DISCORD})
    assert r.json() == {"ok": True, "detail": "HTTP 204"}


PICTURE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg=="


def fake_discord(miner, avatar=None, refuse_names=False):
    """Answers like Discord: GET shows the webhook's picture hash, PATCH sets a new picture."""
    hook = {"avatar": avatar, "patches": 0}

    async def request(method, url, **kwargs):
        miner.client.requests.append((method, url, kwargs))
        if method == "GET":
            return 200, json.dumps({"id": "123", "name": "Captain Hook", "avatar": hook["avatar"]})
        if method == "PATCH":
            hook["patches"] += 1
            hook["avatar"] = f"hash{hook['patches']}"
            return 200, json.dumps({"id": "123", "avatar": hook["avatar"]})
        if refuse_names and kwargs["json"].get("username") != "Dropper":
            return 400, json.dumps({"code": 50035, "message": "Invalid Form Body",
                                    "errors": {"username": {"_errors": [{"code": "USERNAME_INVALID"}]}}})
        return 204, ""

    miner.client.request = request
    return hook


def calls(miner, method):
    return [(url, kwargs.get("json")) for m, url, kwargs in miner.client.requests if m == method]


def test_sender_names_discord_refuses_become_dropper():
    assert sender_name("  Drop   Bot ") == "Drop Bot"
    assert sender_name("") == sender_name(None) == "Dropper"
    assert sender_name("My Discord bot") == sender_name("clydeling") == sender_name("Everyone") == "Dropper"
    assert sender_name("x" * 100) == "x" * 80
    assert _webhook_base("https://discord.com/api/webhooks/1/tok/slack?thread_id=5") == "https://discord.com/api/webhooks/1/tok"


def test_picture_setting_takes_uploads_and_image_urls_only():
    assert Settings(webhook_avatar=PICTURE).webhook_avatar == PICTURE
    assert Settings(webhook_avatar="https://example.com/a.png").webhook_avatar == "https://example.com/a.png"
    for bad in ("javascript:alert(1)", "data:image/svg+xml;base64,PHN2Zz4=", "data:image/png;base64,<b>", "x" * 10):
        assert Settings(webhook_avatar=bad).webhook_avatar == ""
    assert Settings(webhook_username="  Drop \n Bot ").webhook_username == "Drop Bot"


async def test_uploaded_picture_becomes_the_webhook_picture_and_the_name_goes_with_each_message(miner):
    hook = fake_discord(miner, avatar="chosen-in-discord")
    notifying(miner, webhook_username="Drop Bot", webhook_avatar=PICTURE)
    miner.notifier.login_needed()
    await settle(miner)
    # an upload replaces even a picture set in Discord, it was chosen in Dropper after all
    assert calls(miner, "PATCH") == [("https://discord.com/api/webhooks/123/token", {"avatar": PICTURE})]
    assert calls(miner, "GET") == []
    payload = posts(miner)[0]
    assert payload["username"] == "Drop Bot" and "avatar_url" not in payload
    # set once, not with every message
    miner.notifier.login_needed()
    await settle(miner)
    assert hook["patches"] == 1 and len(posts(miner)) == 2


async def test_dropper_icon_is_the_default_but_never_replaces_a_picture_from_discord(miner, tmp_data):
    hook = fake_discord(miner, avatar=None)
    notifying(miner)
    miner.notifier.login_needed()
    await settle(miner)
    icon = _default_avatar()
    assert icon == "data:image/png;base64," + __import__("base64").b64encode(DEFAULT_AVATAR.read_bytes()).decode()
    assert calls(miner, "PATCH") == [("https://discord.com/api/webhooks/123/token", {"avatar": icon})]
    assert posts(miner)[0]["username"] == "Dropper"
    assert json.loads((tmp_data / "notify.json").read_text()) == {"avatars": ["hash1"]}

    # a fresh start with a webhook whose picture was picked in Discord: left alone
    miner.client.requests.clear()
    miner.notifier = Notifier(miner.client, lambda: miner.store.settings, delay=0, state_path=tmp_data / "notify.json")
    hook["avatar"] = "chosen-in-discord"
    miner.notifier.login_needed()
    await settle(miner)
    assert calls(miner, "PATCH") == [] and len(posts(miner)) == 1


async def test_reset_puts_the_icon_back_over_an_uploaded_picture(miner, tmp_data):
    hook = fake_discord(miner, avatar=None)
    notifying(miner, webhook_avatar=PICTURE)
    miner.notifier.login_needed()
    await settle(miner)
    assert hook["avatar"] == "hash1"
    # after a restart Dropper still knows the uploaded picture is its own
    miner.notifier = Notifier(miner.client, lambda: miner.store.settings, delay=0, state_path=tmp_data / "notify.json")
    miner.store.update({"webhook_avatar": ""})
    miner.notifier.login_needed()
    await settle(miner)
    assert [body["avatar"] for _, body in calls(miner, "PATCH")] == [PICTURE, _default_avatar()]


async def test_a_name_discord_refuses_does_not_cost_the_message(miner):
    fake_discord(miner, avatar="chosen-in-discord", refuse_names=True)
    notifying(miner, webhook_username="Drop Bot")
    miner.notifier.login_needed()
    await settle(miner)
    assert [p["username"] for p in posts(miner)] == ["Drop Bot", "Dropper"]
    # the test message tells what Discord said instead
    assert await miner.notifier.test(DISCORD) == (False, "HTTP 400: Invalid Form Body (username)")


def test_test_message_takes_name_and_picture_from_the_form(miner):
    fake_discord(miner, avatar=None)
    miner.store.update({"webhook_username": "Saved Name"})
    api = client_for(miner)
    r = api.post("/api/notify/test", json={"url": DISCORD, "username": " Farm  Bot ", "avatar": PICTURE})
    assert r.json() == {"ok": True, "detail": "HTTP 204"}
    assert calls(miner, "PATCH") == [("https://discord.com/api/webhooks/123/token", {"avatar": PICTURE})]
    assert posts(miner)[-1]["username"] == "Farm Bot"
    # without them the saved ones count
    api.post("/api/notify/test", json={"url": DISCORD})
    assert posts(miner)[-1]["username"] == "Saved Name"


async def test_image_url_goes_with_each_message_instead(miner):
    fake_discord(miner, avatar=None)
    notifying(miner, webhook_avatar="https://example.com/me.png")
    miner.notifier.login_needed()
    await settle(miner)
    assert calls(miner, "PATCH") == [] and calls(miner, "GET") == []
    assert posts(miner)[0]["avatar_url"] == "https://example.com/me.png"


async def test_saved_picture_comes_back_after_testing_one_that_was_not_saved(miner):
    fake_discord(miner, avatar=None)
    notifying(miner)
    miner.notifier.login_needed()
    await settle(miner)
    assert await miner.notifier.test(DISCORD, avatar=PICTURE) == (True, "HTTP 204")
    miner.notifier.login_needed()  # the form was discarded: the icon is still the saved picture
    await settle(miner)
    assert [body["avatar"] for _, body in calls(miner, "PATCH")] == [_default_avatar(), PICTURE, _default_avatar()]


async def test_names_discord_never_takes_are_not_even_tried(miner):
    fake_discord(miner, avatar="chosen-in-discord", refuse_names=True)
    notifying(miner, webhook_username="My Discord Bot")
    miner.notifier.login_needed()
    await settle(miner)
    assert [p["username"] for p in posts(miner)] == ["Dropper"]


async def test_another_webhook_gets_the_picture_too(miner):
    fake_discord(miner, avatar=None)
    notifying(miner, webhook_avatar=PICTURE)
    miner.notifier.login_needed()
    await settle(miner)
    miner.store.update({"webhook_url": "https://discord.com/api/webhooks/456/other"})
    miner.notifier.login_needed()
    await settle(miner)
    assert [url for url, _ in calls(miner, "PATCH")] == ["https://discord.com/api/webhooks/123/token",
                                                         "https://discord.com/api/webhooks/456/other"]
