import json

import pytest

from dropper.constants import GQL_OPERATIONS
from dropper.settings import Settings
from dropper.twitch import GQLError, TwitchClient


async def test_persisted_query_not_found_switches_to_fallback_hash(tmp_path, monkeypatch):
    settings = Settings()
    client = TwitchClient(tmp_path, lambda: settings)
    primary, fallback = GQL_OPERATIONS["Inventory"].hashes
    seen = []

    async def fake_request(method, url, **kwargs):
        sha = kwargs["json"]["extensions"]["persistedQuery"]["sha256Hash"]
        seen.append(sha)
        if sha == primary:
            return 200, json.dumps({"errors": [{"message": "PersistedQueryNotFound"}],
                                    "extensions": {"operationName": "Inventory"}})
        return 200, json.dumps({"data": {"currentUser": {"inventory": {}}}})

    async def no_sleep(*_):
        pass

    monkeypatch.setattr(client, "request", fake_request)
    monkeypatch.setattr("dropper.twitch.asyncio.sleep", no_sleep)
    result = await client.gql(client.operation("Inventory"))
    assert result["data"]["currentUser"]["inventory"] == {}
    assert seen == [primary, fallback]
    # the working hash is remembered for later calls
    assert client.operation("Inventory")["extensions"]["persistedQuery"]["sha256Hash"] == fallback


async def test_tolerant_batch_isolates_a_failing_operation(tmp_path, monkeypatch):
    settings = Settings()
    client = TwitchClient(tmp_path, lambda: settings)
    sent = []

    def answer(op):
        channel = op["variables"]["channelID"]
        if channel == "bad":
            return {"errors": [{"message": "forbidden"}], "data": None,
                    "extensions": {"operationName": "DropsHighlightService_AvailableDrops"}}
        return {"data": {"channel": {"id": channel, "viewerDropCampaigns": []}}}

    async def fake_request(method, url, **kwargs):
        body = kwargs["json"]
        sent.append(len(body) if isinstance(body, list) else 1)
        return 200, json.dumps([answer(op) for op in body] if isinstance(body, list) else answer(body))

    monkeypatch.setattr(client, "request", fake_request)
    ops = [client.operation("AvailableDrops", {"channelID": c}) for c in ["a", "bad", "c"]]
    results = await client.gql_batch(ops, tolerant=True)
    # one bad channel costs only its own answer, the order stays intact
    assert [((r.get("data") or {}).get("channel") or {}).get("id") for r in results] == ["a", None, "c"]
    assert sent == [3, 1, 1, 1]
    with pytest.raises(GQLError):
        await client.gql_batch(ops)


def test_manual_override_wins(tmp_path):
    settings = Settings(gql_hash_overrides={"Inventory": "abc"})
    client = TwitchClient(tmp_path, lambda: settings)
    assert client.operation("Inventory")["extensions"]["persistedQuery"]["sha256Hash"] == "abc"


async def test_device_login_uses_tv_client(tmp_path, monkeypatch):
    from dropper.constants import CLIENT_ID, DEVICE_URL

    settings = Settings()
    client = TwitchClient(tmp_path, lambda: settings)
    sent = {}

    async def fake_request(method, url, **kwargs):
        if url == DEVICE_URL:
            sent.update(kwargs)
            return 400, '{"status":400,"message":"stop"}'
        raise AssertionError(url)

    monkeypatch.setattr(client, "request", fake_request)
    try:
        await client.device_login()
    except Exception as exc:
        assert "stop" in str(exc)
    assert CLIENT_ID == "ue6666qo983tsx6so1t0vnawi233wa"
    assert sent["data"]["client_id"] == CLIENT_ID
    assert sent["headers"]["Client-Id"] == CLIENT_ID
    assert sent["headers"]["Origin"] == "https://android.tv.twitch.tv"


async def test_expired_token_is_renewed_with_refresh_token(tmp_path, monkeypatch):
    from dropper.constants import CLIENT_ID, TOKEN_URL, VALIDATE_URL

    (tmp_path / "auth.json").write_text(json.dumps({"access_token": "old", "refresh_token": "r1", "device_id": "d"}))
    settings = Settings()
    client = TwitchClient(tmp_path, lambda: settings)

    async def fake_request(method, url, **kwargs):
        if url == VALIDATE_URL:
            if kwargs["headers"]["Authorization"] == "OAuth old":
                return 401, "{}"
            return 200, json.dumps({"client_id": CLIENT_ID, "user_id": "42", "login": "viewer"})
        if url == TOKEN_URL:
            assert kwargs["data"]["grant_type"] == "refresh_token" and kwargs["data"]["refresh_token"] == "r1"
            return 200, json.dumps({"access_token": "new", "refresh_token": "r2"})
        raise AssertionError(url)

    monkeypatch.setattr(client, "request", fake_request)
    assert await client.validate() is True
    assert client.login == "viewer"
    saved = json.loads((tmp_path / "auth.json").read_text())
    assert saved["access_token"] == "new" and saved["refresh_token"] == "r2"
