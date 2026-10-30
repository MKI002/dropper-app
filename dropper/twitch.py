"""Low level Twitch access: HTTP session, device code login, GQL with retries and rate limit."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import aiohttp

from .constants import (
    CLIENT_ID, CLIENT_URL, DEVICE_SCOPES, DEVICE_URL, GQL_OPERATIONS, GQL_URL, TOKEN_URL, USER_AGENT, VALIDATE_URL,
)

logger = logging.getLogger("dropper.twitch")
JsonType = dict[str, Any]


class TwitchError(Exception):
    pass


class GQLError(TwitchError):
    def __init__(self, operation: str, errors: Any):
        super().__init__(f"{operation}: {errors}")
        self.operation = operation
        self.errors = errors


class AuthError(TwitchError):
    pass


@dataclass
class LoginPrompt:
    user_code: str
    verification_uri: str
    expires_at: float


class RateLimiter:
    """At most `capacity` operations per `window` seconds. GQL breaks badly when hammered."""

    def __init__(self, capacity: int = 5, window: float = 1.0):
        self.capacity = capacity
        self.window = window
        self._stamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                self._stamps = [s for s in self._stamps if now - s < self.window]
                if len(self._stamps) < self.capacity:
                    self._stamps.append(now)
                    return
                await asyncio.sleep(self.window - (now - self._stamps[0]))


class TwitchClient:
    RETRYABLE_GQL_ERRORS = {
        "service error", "service timeout", "service unavailable", "request cancelled",
        "context deadline exceeded",
    }

    def __init__(self, data_dir: Path, get_settings: Callable[[], Any]):
        self.auth_path = data_dir / "auth.json"
        self._get_settings = get_settings
        self._session: aiohttp.ClientSession | None = None
        self._limiter = RateLimiter()
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.user_id: str | None = None
        self.login: str | None = None
        self.device_id: str = secrets.token_hex(16)
        self.session_id: str = secrets.token_hex(8)
        self.login_prompt: LoginPrompt | None = None
        self.logged_in = asyncio.Event()
        # index into GQLOperation.hashes currently used per operation key
        self._hash_index: dict[str, int] = {}
        self._load_auth()

    # ---------------------------------------------------------------- persistence
    def _load_auth(self) -> None:
        if not self.auth_path.exists():
            return
        try:
            data = json.loads(self.auth_path.read_text("utf8"))
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            self.device_id = data.get("device_id") or self.device_id
        except Exception:
            logger.warning("auth.json unreadable, a new login will be required")

    def _save_auth(self) -> None:
        self.auth_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.auth_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({
            "access_token": self.access_token, "refresh_token": self.refresh_token, "device_id": self.device_id,
        }), "utf8")
        tmp.chmod(0o600)
        tmp.replace(self.auth_path)

    def logout(self) -> None:
        self.access_token = None
        self.refresh_token = None
        self.user_id = None
        self.login = None
        self.logged_in.clear()
        self.auth_path.unlink(missing_ok=True)

    # ---------------------------------------------------------------- http
    async def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30, sock_connect=10),
                headers={"User-Agent": USER_AGENT},
            )
        return self._session

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()

    def _headers(self, gql: bool = False) -> dict[str, str]:
        headers = {
            "Accept": "*/*",
            "Accept-Language": "en-US",
            "Client-Id": CLIENT_ID,
            "Client-Session-Id": self.session_id,
            "X-Device-Id": self.device_id,
            "User-Agent": USER_AGENT,
        }
        if gql:
            headers["Origin"] = CLIENT_URL
            headers["Referer"] = CLIENT_URL
            if self.access_token:
                headers["Authorization"] = f"OAuth {self.access_token}"
        return headers

    async def request(self, method: str, url: str, *, retries: int = 5, **kwargs) -> tuple[int, str]:
        """Performs a request, retrying connection problems and 5xx with exponential backoff."""
        session = await self.session()
        proxy = self._get_settings().proxy or None
        delay = 1.0
        for attempt in range(retries):
            try:
                async with session.request(method, url, proxy=proxy, **kwargs) as response:
                    body = await response.text()
                    if response.status < 500:
                        return response.status, body
                    logger.warning("%s %s -> %s, retrying in %.0fs", method, url, response.status, delay)
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.warning("%s %s failed (%s), retrying in %.0fs", method, url, exc, delay)
            if attempt < retries - 1:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
        raise TwitchError(f"{method} {url} failed after {retries} attempts")

    # ---------------------------------------------------------------- auth
    async def refresh(self) -> bool:
        """Renews the access token with the stored refresh token. Returns success."""
        if not self.refresh_token:
            return False
        status, body = await self.request("POST", TOKEN_URL, headers=self._headers(), data={
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        })
        if status != 200:
            logger.info("Token refresh failed (%s)", status)
            return False
        data = json.loads(body)
        self.access_token = data["access_token"]
        self.refresh_token = data.get("refresh_token") or self.refresh_token
        self._save_auth()
        logger.info("Twitch login renewed automatically")
        return True

    async def validate(self, _refreshed: bool = False) -> bool:
        """Checks the stored token. Returns True when logged in."""
        if not self.access_token:
            return False
        status, body = await self.request(
            "GET", VALIDATE_URL, headers={"Authorization": f"OAuth {self.access_token}"}
        )
        if status == 401:
            if not _refreshed and await self.refresh():
                return await self.validate(_refreshed=True)
            logger.info("Stored Twitch token is no longer valid")
            self.logout()
            return False
        if status != 200:
            raise TwitchError(f"token validation returned {status}")
        data = json.loads(body)
        if data.get("client_id") != CLIENT_ID:
            logger.info("Stored token belongs to another client, re-login required")
            self.logout()
            return False
        self.user_id = str(data["user_id"])
        self.login = data.get("login")
        self.logged_in.set()
        return True

    async def device_login(self) -> None:
        """Runs the device code flow until the user entered the code on twitch.tv/activate."""
        headers = self._headers()
        headers.update({"Accept": "application/json", "Origin": CLIENT_URL, "Referer": f"{CLIENT_URL}/"})
        while not self.logged_in.is_set():
            status, body = await self.request(
                "POST", DEVICE_URL, headers=headers, data={"client_id": CLIENT_ID, "scopes": DEVICE_SCOPES}
            )
            if status != 200:
                raise AuthError(f"device code request failed: {status} {body[:200]}")
            data = json.loads(body)
            expires_at = time.time() + int(data["expires_in"])
            self.login_prompt = LoginPrompt(data["user_code"], data["verification_uri"], expires_at)
            logger.info("Login: open %s and enter code %s", data["verification_uri"], data["user_code"])
            payload = {
                "client_id": CLIENT_ID,
                "device_code": data["device_code"],
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            }
            while time.time() < expires_at:
                await asyncio.sleep(int(data.get("interval", 5)))
                status, body = await self.request("POST", TOKEN_URL, headers=headers, data=payload)
                if status == 200:
                    tokens = json.loads(body)
                    self.access_token = tokens["access_token"]
                    self.refresh_token = tokens.get("refresh_token")
                    self._save_auth()
                    self.login_prompt = None
                    if await self.validate():
                        logger.info("Logged in as %s", self.login)
                        return
                    break
            # code expired or token invalid: request a new code

    # ---------------------------------------------------------------- gql
    def operation(self, key: str, variables: JsonType | None = None) -> JsonType:
        op = GQL_OPERATIONS[key]
        override = self._get_settings().gql_hash_overrides.get(key)
        return op.build(variables, override or op.hashes[self._hash_index.get(key, 0) % len(op.hashes)])

    def _rotate_hash(self, operation_name: str, ops: list[JsonType]) -> bool:
        """Switches an operation to its next known hash after PersistedQueryNotFound."""
        key = next((k for k, op in GQL_OPERATIONS.items() if op.name == operation_name), None)
        if key is None or self._get_settings().gql_hash_overrides.get(key):
            return False
        op = GQL_OPERATIONS[key]
        index = self._hash_index.get(key, 0) + 1
        if index >= len(op.hashes):
            return False
        self._hash_index[key] = index
        logger.warning("GQL %s: hash outdated, switching to alternative %d", operation_name, index)
        for item in ops:
            if item.get("operationName") == operation_name:
                item["extensions"]["persistedQuery"]["sha256Hash"] = op.hashes[index]
        return True

    async def gql(self, ops: JsonType | list[JsonType]) -> Any:
        """Sends one or a batch of GQL operations. Retries transient errors, raises GQLError."""
        name = ops["operationName"] if isinstance(ops, dict) else f"batch[{len(ops)}]"
        delay = 2.0
        for attempt in range(5):
            await self._limiter.acquire()
            status, body = await self.request("POST", GQL_URL, json=ops, headers=self._headers(gql=True))
            if status == 401:
                if attempt < 4 and await self.refresh():
                    continue
                self.logout()
                raise AuthError("Twitch rejected the token (401)")
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                raise GQLError(name, f"HTTP {status}: {body[:200]}")
            responses = data if isinstance(data, list) else [data]
            retry = False
            for response in responses:
                if isinstance(response, dict) and "error" in response and "errors" not in response:
                    raise GQLError(name, f"{response.get('error')}: {response.get('message')}")
                errors = response.get("errors") if isinstance(response, dict) else None
                if not errors:
                    continue
                messages = {e.get("message") for e in errors}
                if "PersistedQueryNotFound" in messages:
                    op_name = response.get("extensions", {}).get("operationName") or name
                    if self._rotate_hash(op_name, ops if isinstance(ops, list) else [ops]):
                        retry = True
                        break
                if messages & self.RETRYABLE_GQL_ERRORS and attempt < 4:
                    retry = True
                    break
                if messages <= {"server error"} and response.get("data") is not None:
                    # partial data: Twitch nulls the failing field, the rest is usable
                    continue
                raise GQLError(response.get("extensions", {}).get("operationName", name), errors)
            if not retry:
                return data
            logger.info("GQL %s transient error, retry in %.0fs", name, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)
        raise GQLError(name, "retries exhausted")

    async def gql_batch(self, ops: list[JsonType], chunk: int = 20, tolerant: bool = False) -> list[JsonType]:
        """Sends operations in chunks, results in the same order. With tolerant=True a chunk that fails is
        sent again one operation at a time, and an operation that still fails comes back as {}."""
        results: list[JsonType] = []
        for i in range(0, len(ops), chunk):
            part = ops[i:i + chunk]
            try:
                results.extend(await self.gql(part))
            except GQLError as exc:
                if not tolerant:
                    raise
                logger.debug("GQL batch failed (%s), sending one by one", exc)
                for op in part:
                    try:
                        results.append(await self.gql(op))
                    except GQLError as single:
                        logger.warning("GQL %s failed: %s", op.get("operationName"), single)
                        results.append({})
        return results
