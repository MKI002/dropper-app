"""Notifications for Discord or any other webhook: claimed drops, failed claims, finished and new
campaigns, campaigns for games on the priority list, and a lost Twitch login. The texts follow the web
UI language (static/locales)."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from .models import Campaign, Drop
    from .settings import Settings

logger = logging.getLogger("dropper.notify")
JsonType = dict[str, Any]

LOCALES = Path(__file__).parent / "static" / "locales"
# event -> setting that switches it on or off
EVENTS = {
    "claimed": "notify_claimed",
    "failed": "notify_failed",
    "campaign_done": "notify_campaign_done",
    "watched": "notify_watched",
    "new_campaign": "notify_new_campaign",
    "login": "notify_login",
}
# event names in the JSON sent to webhooks that are not Discord ("drop_claimed" predates the others)
JSON_EVENTS = {"claimed": "drop_claimed", "failed": "claim_failed", "campaign_done": "campaign_done",
               "watched": "watched_game", "new_campaign": "new_campaign", "login": "login_needed", "test": "test"}
COLORS = {"claimed": 0x30D158, "failed": 0xFF453A, "campaign_done": 0x9A5CFF, "watched": 0x64D2FF,
          "new_campaign": 0x0A84FF, "login": 0xFF9F0A, "test": 0x9A5CFF}
DISCORD_HOSTS = {"discord.com", "discordapp.com", "ptb.discord.com", "canary.discord.com"}
MAX_EMBEDS = 10  # Discord's limit per message
DEFAULT_NAME = "Dropper"
DEFAULT_AVATAR = Path(__file__).parent / "static" / "img" / "avatar.png"


def is_discord(url: str) -> bool:
    parts = urlsplit(url)
    return parts.hostname in DISCORD_HOSTS and parts.path.startswith("/api/webhooks/")


def _webhook_base(url: str) -> str:
    """The webhook itself, without ?thread_id= or a /slack suffix: what GET and PATCH take."""
    parts = urlsplit(url)
    match = re.match(r"/api/webhooks/[^/]+/[^/]+", parts.path)
    return f"{parts.scheme}://{parts.netloc}{match.group(0) if match else parts.path}"


def sender_name(name: str | None) -> str:
    """The name shown next to Discord messages. Discord refuses names that contain "discord" or "clyde"
    or are "everyone" or "here"; those become Dropper instead of losing the message."""
    name = " ".join(str(name or "").split())[:80]
    if not name or re.search(r"discord|clyde", name, re.I) or name.casefold() in {"everyone", "here"}:
        return DEFAULT_NAME
    return name


def _cut(text: str, limit: int) -> str:
    text = str(text or "")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _box_art(url: str) -> str:
    # Twitch serves box art in the size named in the file name
    if "jtvnw.net/ttv-boxart/" in url and not re.search(r"-\d+x\d+\.\w+$", url):
        return re.sub(r"(\.\w+)$", r"-144x192\1", url)
    return url


_locales: dict[str, JsonType] = {}


def _locale(code: str) -> JsonType:
    if code not in _locales:
        path = LOCALES / f"{code}.json"
        try:
            _locales[code] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _locales[code] = {}
    return _locales[code]


def translate(lang: str, key: str, **params: Any) -> str:
    """A UI text in the given language, English when it is missing. Plural entries use "other"."""
    code = re.split(r"[-_]", (lang or "en").lower())[0]
    value = _locale(code).get(key) or _locale("en").get(key) or key
    if isinstance(value, dict):
        value = value.get("other") or next(iter(value.values()))
    return re.sub(r"\{(\w+)\}", lambda m: str(params.get(m.group(1), m.group(0))), str(value))


class Notifier:
    """Collects events for a moment and sends them together, so a sweep that claims five drops
    posts one Discord message with five cards instead of five messages."""

    def __init__(self, client: Any, get_settings: Callable[[], Settings], delay: float = 2.0,
                 state_path: Path | None = None):
        self.client = client
        self._settings = get_settings
        self.delay = delay
        self._pending: list[tuple[str, JsonType, JsonType]] = []  # (event, embed, extra JSON)
        self._task: asyncio.Task | None = None
        # avatar hashes Discord gave the pictures Dropper set, to tell them from one set in Discord
        self._state_path = state_path
        self._avatars_set: list[str] = self._load_state()
        self._picture_of: dict[str, str] = {}  # webhook -> digest of the picture it has, as far as known

    # ---------------------------------------------------------------- events
    def drop_claimed(self, drop: Drop) -> None:
        campaign = drop.campaign
        embed = {
            "title": self._t("notify.claimed"),
            "description": f"**{_cut(drop.rewards, 300)}**",
            "fields": [
                self._field("notify.field.game", campaign.game.name),
                self._field("notify.field.campaign", campaign.name),
                self._field("notify.field.progress", f"{campaign.claimed_count}/{len(campaign.drops)}"),
            ],
        }
        image = next((b.image for b in drop.benefits if b.image), "")
        if image:
            embed["thumbnail"] = {"url": image}
        self._push("claimed", embed, {"drop": drop.to_dict(), "campaign": campaign.name, "game": campaign.game.name})

    def claim_failed(self, drop: Drop) -> None:
        campaign = drop.campaign
        hint = self._t("drops.failed.link" if drop.needs_link else "drops.failed.retry")
        embed = {
            "title": self._t("notify.failed"),
            "description": f"**{_cut(drop.rewards, 300)}**\n{hint}",
            "fields": [
                self._field("notify.field.game", campaign.game.name),
                self._field("notify.field.campaign", campaign.name),
                self._field("notify.field.error", f"`{_cut(drop.claim_error or '?', 900)}`", inline=False),
            ],
        }
        if drop.needs_link and campaign.link_url.startswith("http"):
            embed["url"] = campaign.link_url
        self._push("failed", embed, {"drop": drop.to_dict(), "campaign": campaign.name, "game": campaign.game.name})

    def campaign_done(self, campaign: Campaign) -> None:
        embed = {
            "title": self._t("notify.campaign_done"),
            "description": f"**{_cut(campaign.name, 300)}**\n{self._t('notify.campaign_done.text')}",
            "fields": [self._field("notify.field.game", campaign.game.name), self._rewards(campaign)],
        }
        self._art(embed, campaign)
        self._push("campaign_done", embed, {"campaign": campaign.name, "game": campaign.game.name})

    def new_campaign(self, campaign: Campaign) -> None:
        ends = f"<t:{int(campaign.ends_at.timestamp())}:R>"
        embed = {
            "title": self._t("notify.new_campaign"),
            "description": f"**{_cut(campaign.name, 300)}**",
            "fields": [self._field("notify.field.game", campaign.game.name), self._field("notify.field.ends", ends)],
        }
        if campaign.drops:
            embed["fields"].append(self._rewards(campaign))
        self._art(embed, campaign)
        self._push("new_campaign", embed, {"campaign": campaign.name, "game": campaign.game.name,
                                           "ends_at": campaign.ends_at.isoformat()})

    def watched_campaign(self, campaign: Campaign, reason: str | None) -> None:
        """A game on the priority list got a campaign. reason is why it is not farmed right now, a code
        from selection.SKIP_REASONS ("upcoming", "not_linked", ...), or None when it is."""
        if campaign.upcoming:
            text, when_key, when = "notify.watched.upcoming", "notify.field.starts", campaign.starts_at
        else:
            text = "notify.watched.link" if reason == "not_linked" else "notify.watched.active"
            when_key, when = "notify.field.ends", campaign.ends_at
        embed = {
            "title": self._t("notify.watched", game=campaign.game.name),
            "description": f"**{_cut(campaign.name, 300)}**\n{self._t(text)}",
            "fields": [self._field(when_key, f"<t:{int(when.timestamp())}:R>")],
        }
        if campaign.drops:
            embed["fields"].append(self._rewards(campaign))
        if campaign.link_url.startswith("http") and not (campaign.linked and campaign.link_known):
            # catalog campaigns do not tell whether the account is linked: offer the link either way
            embed["fields"].append(self._field("notify.field.account", f"[{self._t('camp.unlinked')}]({campaign.link_url})"))
            if not campaign.linked:
                embed["url"] = campaign.link_url
        self._art(embed, campaign)
        self._push("watched", embed, {
            "campaign": campaign.name, "game": campaign.game.name, "status": "upcoming" if campaign.upcoming else "active",
            "starts_at": campaign.starts_at.isoformat(), "ends_at": campaign.ends_at.isoformat(),
            "link_url": campaign.link_url,
        })

    def login_needed(self) -> None:
        embed = {"title": self._t("notify.login"), "description": self._t("notify.login.text")}
        self._push("login", embed, {})

    async def test(self, url: str, username: str | None = None, avatar: str | None = None) -> tuple[bool, str]:
        """Sends a test message right away, with the name and picture given (those from the settings form,
        so they can be tried before saving) or the saved ones. Returns success and what the server said."""
        settings = self._settings()
        embed = self._finish("test", {"title": self._t("notify.test"), "description": self._t("notify.test.text")})
        if is_discord(url):
            avatar = settings.webhook_avatar if avatar is None else avatar
            await self._set_picture(url, avatar)
            name = settings.webhook_username if username is None else username
            return await self._send(url, self._discord_payload([embed], name, avatar))
        return await self._send(url, self._json_payload("test", embed, {}))

    # ---------------------------------------------------------------- building blocks
    def _t(self, key: str, **params: Any) -> str:
        return translate(self._settings().ui_language, key, **params)

    def _field(self, key: str, value: str, inline: bool = True) -> JsonType:
        return {"name": self._t(key), "value": _cut(value or "–", 1024), "inline": inline}

    def _rewards(self, campaign: Campaign) -> JsonType:
        names = [d.rewards for d in sorted(campaign.drops.values(), key=lambda d: d.required_minutes)]
        text = ", ".join(names[:8]) + (f" (+{len(names) - 8})" if len(names) > 8 else "")
        return self._field("notify.field.rewards", text, inline=False)

    @staticmethod
    def _art(embed: JsonType, campaign: Campaign) -> None:
        image = _box_art(campaign.game.box_art) or campaign.image
        if image.startswith("http"):
            embed["thumbnail"] = {"url": image}

    def _finish(self, event: str, embed: JsonType) -> JsonType:
        embed["title"] = _cut(embed["title"], 256)
        embed["color"] = COLORS[event]
        embed["footer"] = {"text": "Dropper"}
        embed["timestamp"] = datetime.now(timezone.utc).isoformat()
        return embed

    @staticmethod
    def _discord_payload(embeds: list[JsonType], name: str | None = None, avatar: str = "") -> JsonType:
        # names come from Twitch and the catalog: never let them ping anyone
        payload = {"username": sender_name(name), "embeds": embeds, "allowed_mentions": {"parse": []}}
        if avatar.startswith(("https://", "http://")):
            payload["avatar_url"] = avatar
        return payload

    @staticmethod
    def _json_payload(event: str, embed: JsonType, extra: JsonType) -> JsonType:
        parts = [embed["title"], re.sub(r"\*\*|`", "", embed.get("description") or "")]
        parts += [f"{f['name']}: {re.sub(r'`', '', f['value'])}" for f in embed.get("fields") or []
                  if not f["value"].startswith("<t:")]
        return {"event": JSON_EVENTS[event], "text": " · ".join(p.replace("\n", " ") for p in parts if p), **extra}

    # ---------------------------------------------------------------- sending
    def enabled(self, event: str) -> bool:
        settings = self._settings()
        return bool(settings.webhook_url) and bool(getattr(settings, EVENTS[event]))

    def _push(self, event: str, embed: JsonType, extra: JsonType) -> None:
        if not self.enabled(event):
            return
        self._pending.append((event, self._finish(event, embed), extra))
        if self._task is None or self._task.done():
            try:
                self._task = asyncio.get_running_loop().create_task(self._flush_later())
            except RuntimeError:  # no event loop: nothing can be sent anyway
                self._pending.clear()

    async def _flush_later(self) -> None:
        await asyncio.sleep(self.delay)
        await self.flush()

    async def flush(self) -> None:
        pending, self._pending = self._pending, []
        settings = self._settings()
        url = settings.webhook_url
        if not pending or not url:
            return
        if is_discord(url):
            await self._set_picture(url, settings.webhook_avatar)
            for i in range(0, len(pending), MAX_EMBEDS):
                payload = self._discord_payload([e for _, e, _ in pending[i:i + MAX_EMBEDS]],
                                                settings.webhook_username, settings.webhook_avatar)
                ok, detail = await self._send(url, payload)
                if not ok and detail.startswith("HTTP 400") and "username" in detail and payload["username"] != DEFAULT_NAME:
                    # a name Discord does not take must not cost the message
                    logger.warning("Discord refused the name %r: %s", payload["username"], detail)
                    ok, detail = await self._send(url, {**payload, "username": DEFAULT_NAME})
                if not ok:
                    logger.warning("Discord notification failed: %s", detail)
        else:
            for event, embed, extra in pending:
                ok, detail = await self._send(url, self._json_payload(event, embed, extra))
                if not ok:
                    logger.warning("Webhook notification failed: %s", detail)

    async def _send(self, url: str, payload: JsonType) -> tuple[bool, str]:
        for _ in range(2):
            try:
                status, body = await self.client.request("POST", url, json=payload, retries=2)
            except Exception as exc:
                return False, str(exc)
            if status == 429:  # Discord rate limit: wait as told, once
                try:
                    wait = float(json.loads(body).get("retry_after", 1))
                except (ValueError, AttributeError):
                    wait = 1.0
                await asyncio.sleep(min(wait, 10))
                continue
            if 200 <= status < 300:
                return True, f"HTTP {status}"
            return False, f"HTTP {status}: {_cut(_error(body), 200)}"
        return False, "HTTP 429: rate limited"

    # ---------------------------------------------------------------- Discord picture
    async def _set_picture(self, url: str, avatar: str) -> None:
        """Discord loads avatar_url from the internet, where Dropper usually can not be reached. So an
        uploaded picture, or else the Dropper icon, becomes the webhook's own picture. The icon never
        replaces a picture set in Discord itself; a picture uploaded in Dropper does."""
        if avatar.startswith(("https://", "http://")):
            return  # goes with every message as avatar_url
        uploaded = avatar.startswith("data:image/")
        image = avatar if uploaded else _default_avatar()
        base = _webhook_base(url)
        digest = hashlib.sha1(image.encode()).hexdigest()
        if self._picture_of.get(base) == digest:
            return
        try:
            if not uploaded:
                status, body = await self.client.request("GET", base, retries=1)
                current = _json(body).get("avatar") if status == 200 else None
                if status != 200:
                    logger.info("Could not read the Discord webhook: HTTP %s %s", status, _cut(_error(body), 200))
                    return  # asked again with the next message
                if current and current not in self._avatars_set:
                    self._picture_of[base] = digest  # chosen in Discord: keep it
                    return
            status, body = await self.client.request("PATCH", base, json={"avatar": image}, retries=1)
        except Exception as exc:
            logger.info("Could not set the Discord picture: %s", exc)
            return
        if not 200 <= status < 300:
            logger.warning("Could not set the Discord picture: HTTP %s %s", status, _cut(_error(body), 200))
            return
        self._picture_of[base] = digest
        avatar_hash = _json(body).get("avatar")
        if avatar_hash and avatar_hash not in self._avatars_set:
            self._avatars_set = (self._avatars_set + [avatar_hash])[-20:]
            self._save_state()

    def _load_state(self) -> list[str]:
        if self._state_path is None or not self._state_path.exists():
            return []
        try:
            return [str(h) for h in json.loads(self._state_path.read_text("utf8")).get("avatars", [])]
        except (OSError, ValueError, AttributeError):
            return []

    def _save_state(self) -> None:
        if self._state_path is None:
            return
        try:
            tmp = self._state_path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"avatars": self._avatars_set}), "utf8")
            tmp.replace(self._state_path)
        except OSError as exc:
            logger.warning("Could not save %s: %s", self._state_path, exc)


def _default_avatar() -> str:
    return "data:image/png;base64," + base64.b64encode(DEFAULT_AVATAR.read_bytes()).decode()


def _json(body: str) -> JsonType:
    try:
        data = json.loads(body)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _error(body: str) -> str:
    """What went wrong, from a Discord error answer: the message and the fields it is about."""
    data = _json(body)
    detail = str(data.get("message") or body)
    if isinstance(data.get("errors"), dict):
        detail += f" ({', '.join(data['errors'])})"
    return detail
