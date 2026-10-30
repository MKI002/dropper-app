"""The miner: keeps campaigns up to date, finds drop-enabled channels, watches and claims."""

from __future__ import annotations

import asyncio
import base64
import collections
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .catalog import fetch_catalog
from .games import GameIndex
from .models import Campaign, Channel, Drop, Game, norm_game, parse_ts, utcnow
from .notify import Notifier
from .pubsub import PubSub
from .constants import BROWSER_USER_AGENT, PUBSUB_TOPICS, SPADE_FALLBACK_URL, USHER_URL
from .selection import channel_serves, on_priority_list, pick_channel, skip_reason, wanted_campaigns
from .settings import Settings, SettingsStore
from .stats import Stats
from .twitch import AuthError, GQLError, TwitchClient, TwitchError

logger = logging.getLogger("dropper.miner")
JsonType = dict[str, Any]

WATCH_INTERVAL = 20  # seconds between stream segment requests (what Twitch counts as watching)
MINUTE_INTERVAL = 59  # seconds between "minute-watched" events and drop progress checks
SEEN_SEGMENTS = 120  # segment URLs remembered so each one is requested only once
STALL_MINUTES = 12  # no progress for this long -> try another channel
COOLDOWN_MINUTES = 30  # how long a stalled channel is skipped
CLAIM_ATTEMPTS = 3
CLAIM_BACKOFF_MINUTES = (5, 10, 20, 40, 60)  # wait between sweeps after failed claims
CATALOG_MAX_AGE = 600  # seconds the public campaign catalog is reused before it is read again
SCOUT_CHANNELS_PER_GAME = 10  # live channels asked for the drops of campaigns we only know by name
LOOKUP_TIMEOUT = 8  # seconds a game lookup from the web UI may take
# why a campaign of a game on the priority list is not farmed, for which it is still announced
WATCHED_REASONS = {None, "upcoming", "not_linked", "unavailable"}

# what the miner is doing; the web UI translates the code, the text is for the API and logs
ACTIVITIES = {
    "starting": "Starting",
    "checking_login": "Checking login",
    "login_required": "Waiting for the Twitch login (code in the web UI)",
    "paused": "Paused",
    "loading_campaigns": "Loading campaigns",
    "claiming": "Claiming finished drops",
    "searching_channels": "Searching channels with drops",
    "watching": "Watching {channel} ({game})",
    "no_campaigns": "No wanted campaign is active",
    "no_channels": "No live channel with matching drops",
}
SPADE_PATTERN = re.compile(r'"spade_?url": ?"(https://[.\w\-/]+)"', re.I)
SETTINGS_JS_PATTERN = re.compile(r'src="(https://[\w.]+/config/settings\.[0-9a-f]{32}\.js)"', re.I)


def deep_merge(base: JsonType, extra: JsonType) -> JsonType:
    """Merges `extra` on top of `base`; dicts merge recursively, other values from `extra` win."""
    out = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        elif value is not None or key not in out:
            out[key] = value
    return out


class LogBuffer(logging.Handler):
    """Keeps the latest log lines for the web UI."""

    def __init__(self, size: int = 500):
        super().__init__(logging.INFO)
        self.lines: collections.deque[dict] = collections.deque(maxlen=size)
        self.counter = 0

    def emit(self, record: logging.LogRecord) -> None:
        self.counter += 1
        self.lines.append({
            "id": self.counter,
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "msg": record.getMessage(),
        })


class Miner:
    def __init__(self, data_dir: Path, store: SettingsStore, stats: Stats, client: TwitchClient | None = None):
        self.data_dir = data_dir
        self.store = store
        self.stats = stats
        self.client = client or TwitchClient(data_dir, lambda: self.store.settings)
        self.pubsub = PubSub(self.client, self._on_pubsub)
        self.notifier = Notifier(self.client, lambda: self.store.settings, state_path=data_dir / "notify.json")
        self.games = GameIndex(self.client)

        self.state = "starting"
        self.status_text = ""
        self.activity: JsonType = {}
        self._set_activity("starting")
        self.last_error: str | None = None
        self.last_refresh: datetime | None = None
        self.next_refresh: datetime | None = None
        self.started_at = utcnow()

        self.campaigns: dict[str, Campaign] = {}
        self.channels: dict[str, Channel] = {}
        self.watching: Channel | None = None
        self.target_campaign: Campaign | None = None
        self.manual_channel: str | None = None  # login forced from the UI
        self.selection: JsonType | None = None  # why the current channel was picked, shown in the UI
        self.rewards: list[JsonType] = []  # every reward the account ever received (inventory)
        self.awarded: dict[str, datetime] = {}  # benefit id -> last awarded
        # where the campaign list came from: "twitch", "catalog" or "inventory" (see fetch_campaigns)
        self.campaign_source = "twitch"
        self._sources: JsonType = {"listed": {}, "details": {}, "in_progress": {}, "claimed": {}}
        self._discovered: dict[str, JsonType] = {}  # campaigns read from live channels, by id
        self._catalog: tuple[float, list[JsonType]] | None = None
        self._gate_logged = False
        self.current_drop_id: str | None = None
        self._progress_mark: tuple[int, float] = (-1, time.monotonic())
        self._cooldown: dict[str, float] = {}
        self._claiming: set[str] = set()
        self._spade_url: str | None = None
        self._stream_urls: dict[str, str] = {}  # channel login -> lowest quality media playlist
        self._seen_segments: collections.deque[str] = collections.deque(maxlen=SEEN_SEGMENTS)
        self._last_spade = float("-inf")
        self._hls_warned = False
        self._wake = asyncio.Event()
        self._reselect = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self.session_watch_minutes = 0
        self.session_claims = 0
        self.retry_delay = 2.0  # base delay between claim retries (seconds)
        self.claim_settle_seconds = 5.0  # wait after a claim before the next drop is picked
        # campaigns seen active and wanted, for "new campaign" notifications (None until the first load)
        self._announced: set[str] | None = None
        # every campaign id seen, for "a game on the priority list got a campaign" (None until the first load)
        self._seen: set[str] | None = None
        self._refreshes = 0  # completed refreshes
        self._in_refresh = False
        self._was_logged_in = False
        self._login_notified = False

        store.on_change(self._on_settings_change)

    @property
    def settings(self) -> Settings:
        return self.store.settings

    @property
    def drops(self) -> dict[str, Drop]:
        return {d.id: d for c in self.campaigns.values() for d in c.drops.values()}

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        self._tasks = [
            asyncio.create_task(self._supervise(self._main_loop), name="main"),
            asyncio.create_task(self._supervise(self._watch_loop), name="watch"),
            asyncio.create_task(self._supervise(self._sweep_loop), name="sweep"),
        ]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.pubsub.stop()
        await self.client.close()

    async def _supervise(self, func) -> None:
        """Restarts a loop after unexpected errors so one bad response never kills the miner."""
        while True:
            try:
                await func()
            except asyncio.CancelledError:
                raise
            except AuthError as exc:
                self.last_error = str(exc)
                logger.warning("Login invalid: %s", exc)
                self._wake.set()
                await asyncio.sleep(15)
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.exception("Error in %s, restarting in 30s", func.__name__)
                await asyncio.sleep(30)

    # settings that change which campaign or channel comes first; the data at hand is enough to re-pick
    SELECTION_KEYS = {
        "game_mode", "games_whitelist", "games_exclude", "games_priority", "priority_mode",
        "mine_badges_emotes", "require_linked_account", "campaigns_exclude", "channels_preferred",
        "channels_blacklist",
    }

    def _on_settings_change(self, old: Settings, new: Settings) -> None:
        refresh_keys = self.SELECTION_KEYS | {"stream_languages", "channels_per_game", "verify_channel_drops", "paused"}
        changed = {k for k in refresh_keys if getattr(old, k) != getattr(new, k)}
        if not changed:
            return
        if changed & self.SELECTION_KEYS and self.channels and not new.paused:
            # switch right away instead of after the full refresh, which can take a while
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                pass
            else:
                self._select()
        self.request_refresh()

    def request_refresh(self) -> None:
        self._wake.set()

    # ------------------------------------------------------------------ login
    async def ensure_login(self) -> None:
        if self.client.logged_in.is_set():
            self._was_logged_in = True
            return
        self.state = "login"
        self._set_activity("checking_login")
        # a stored or earlier login that stopped working, not a first start or a logout from the UI
        lost = self._was_logged_in or bool(self.client.access_token)
        if await self.client.validate():
            logger.info("Logged in as %s", self.client.login)
            self._was_logged_in, self._login_notified = True, False
            return
        self._set_activity("login_required")
        if lost and not self._login_notified:
            self._login_notified = True
            self.notifier.login_needed()
        await self.client.device_login()
        self._was_logged_in, self._login_notified = True, False

    def logout(self) -> None:
        """Logout asked for in the web UI: a new login is needed, but no notification about it."""
        self._login_notified = True  # until the next login
        self.client.logout()
        self.request_refresh()

    # ------------------------------------------------------------------ main loop
    async def _main_loop(self) -> None:
        while True:
            # cleared before the refresh: a request made while it runs triggers another one
            self._wake.clear()
            await self.ensure_login()
            self.pubsub.start()
            await self._update_pubsub_topics()
            if self.settings.paused:
                self.state = "paused"
                self._set_activity("paused")
                self._set_watching(None)
            else:
                await self.refresh()
            wait = self._seconds_until_next_refresh()
            self.next_refresh = utcnow() + timedelta(seconds=wait)
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=wait)
            except asyncio.TimeoutError:
                pass

    def _seconds_until_next_refresh(self) -> float:
        wait = self.settings.refresh_interval_minutes * 60
        now = utcnow()
        # refresh right when a campaign or drop starts/ends
        for campaign in self.campaigns.values():
            stamps = [campaign.starts_at, campaign.ends_at]
            stamps += [d.starts_at for d in campaign.drops.values()] + [d.ends_at for d in campaign.drops.values()]
            for stamp in stamps:
                delta = (stamp - now).total_seconds()
                if 0 < delta < wait:
                    wait = delta + 5
        return max(wait, 30)

    async def refresh(self) -> None:
        self.state = "refreshing"
        self._in_refresh = True
        try:
            self._set_activity("loading_campaigns")
            await self.fetch_campaigns()
            await self.resolve_watched()
            self._set_activity("claiming")
            await self.claim_all_ready("refresh")
            self._set_activity("searching_channels")
            await self.discover_channels()
            self._refreshes += 1
        finally:
            self._in_refresh = False
        self.last_refresh = utcnow()
        self.last_error = None
        await self.select_channel()

    # ------------------------------------------------------------------ campaigns
    async def fetch_inventory(self) -> tuple[dict[str, JsonType], dict[str, datetime]]:
        response = await self.client.gql(self.client.operation("Inventory"))
        inventory = (response.get("data", {}).get("currentUser") or {}).get("inventory") or {}
        in_progress = {c["id"]: c for c in (inventory.get("dropCampaignsInProgress") or [])}
        claimed = {}
        rewards = []
        for benefit in inventory.get("gameEventDrops") or []:
            if not isinstance(benefit, dict) or not benefit.get("id"):
                continue
            game = benefit.get("game") or {}
            rewards.append({
                "id": benefit["id"], "name": benefit.get("name") or "", "image": benefit.get("imageURL") or "",
                "game": game.get("displayName") or game.get("name") or "",
                "last_awarded_at": benefit.get("lastAwardedAt"), "count": int(benefit.get("totalCount") or 1),
                "link_url": benefit.get("requiredAccountLink") or "", "connected": bool(benefit.get("isConnected")),
            })
            try:
                claimed[benefit["id"]] = datetime.fromisoformat(benefit["lastAwardedAt"].replace("Z", "+00:00"))
            except (KeyError, AttributeError, ValueError):
                continue
        rewards.sort(key=lambda r: r["last_awarded_at"] or "", reverse=True)
        self.rewards, self.awarded = rewards, claimed
        return in_progress, claimed

    async def fetch_campaigns(self) -> None:
        in_progress, claimed = await self.fetch_inventory()
        listed = await self._dashboard_campaigns()
        details: dict[str, JsonType] = {}
        if listed:
            self.campaign_source = "twitch"
            ops = [
                self.client.operation("CampaignDetails", {"channelLogin": self.client.user_id, "dropID": c["id"]})
                for c in listed
            ]
            for result in await self.client.gql_batch(ops, tolerant=True):
                campaign = ((result.get("data") or {}).get("user") or {}).get("dropCampaign")
                if campaign:
                    details[campaign["id"]] = campaign
        else:
            # Since September 2026 Twitch answers the campaign list and details with null for app
            # clients. The public catalog names the running campaigns, the live channels that offer
            # them tell their drops (verify_channels) and the inventory still has our progress.
            if not self._gate_logged:
                logger.warning("Twitch sent no campaign list (blocked for apps since September 2026), "
                               "using the public campaign catalog and live channels instead")
                self._gate_logged = True
            listed = await self._catalog_campaigns()
            self.campaign_source = "catalog" if listed else "inventory"
        self._sources = {
            "listed": {c["id"]: c for c in listed}, "details": details,
            "in_progress": in_progress, "claimed": claimed,
        }
        self._build_campaigns()
        self._announce_new_campaigns()
        active = sum(c.active for c in self.campaigns.values())
        logger.info("%d campaigns loaded (%d active, %d wanted, list from %s)", len(self.campaigns), active,
                    len(wanted_campaigns(self.campaigns.values(), self.settings)), self.campaign_source)

    def _announce_new_campaigns(self) -> None:
        """Notifies about new campaigns. A game on the priority list gets a message as soon as a campaign
        for it shows up, also one that starts later; any other wanted campaign gets one when it starts.
        The first load after a start only takes note of what is there, so a restart never announces
        every campaign again."""
        now = utcnow()
        settings = self.settings
        # campaigns that live channels reveal during the first refresh were running before the start too
        first = self._announced is None or (self._in_refresh and not self._refreshes)
        known, seen = self._announced or set(), self._seen or set()
        new = [c for c in self.campaigns.values() if c.id not in seen]
        fresh = [c for c in wanted_campaigns(self.campaigns.values(), settings, now) if c.active and c.id not in known]
        self._seen = seen | {c.id for c in new}
        self._announced = known | {c.id for c in fresh}
        if first:
            return
        watched = set()
        if self.notifier.enabled("watched"):
            for campaign in new:
                reason = skip_reason(campaign, settings, now)
                if on_priority_list(campaign, settings) and (campaign.active or campaign.upcoming) \
                        and reason in WATCHED_REASONS:
                    self.notifier.watched_campaign(campaign, reason)
                    watched.add(campaign.id)
        # one announced while upcoming is not announced again when it starts
        self._announced |= watched
        for campaign in fresh:
            # one that started long ago only showed up again (catalog back, a setting changed)
            if campaign.id not in watched and now - campaign.starts_at < timedelta(hours=24):
                self.notifier.new_campaign(campaign)

    async def _dashboard_campaigns(self) -> list[JsonType]:
        try:
            response = await self.client.gql(self.client.operation("Campaigns"))
        except GQLError as exc:
            logger.warning("Campaign list request failed: %s", exc)
            return []
        listed = (response.get("data", {}).get("currentUser") or {}).get("dropCampaigns") or []
        return [c for c in listed if c.get("id") and c.get("status") in ("ACTIVE", "UPCOMING")]

    async def _catalog_campaigns(self) -> list[JsonType]:
        url = self.settings.campaign_catalog_url.strip()
        if not url:
            return []
        if self._catalog and time.monotonic() - self._catalog[0] < CATALOG_MAX_AGE:
            return self._catalog[1]
        try:
            campaigns = await fetch_catalog(self.client, url)
        except Exception as exc:
            logger.warning("Campaign catalog %s unavailable: %s", url, exc)
            return self._catalog[1] if self._catalog else []
        self._catalog = (time.monotonic(), campaigns)
        return campaigns

    def _build_campaigns(self) -> None:
        """Merges every source into Campaign objects: list, details, drops seen on channels, inventory."""
        src = self._sources
        listed, details, in_progress = src["listed"], src["details"], src["in_progress"]
        now = utcnow()
        self._discovered = {k: v for k, v in self._discovered.items() if parse_ts(v.get("endAt")) > now}
        merged: dict[str, JsonType] = {}
        for cid in set(listed) | set(in_progress) | set(self._discovered):
            data = deep_merge(self._discovered.get(cid, {}), listed.get(cid, {}))
            data = deep_merge(data, details.get(cid, {}))
            data = deep_merge(data, in_progress.get(cid, {}))  # inventory has the real progress
            if data.get("game"):
                merged[cid] = data
        self._guess_links(merged)

        campaigns: dict[str, Campaign] = {}
        for cid, data in merged.items():
            try:
                campaigns[cid] = Campaign.from_gql(data, src["claimed"])
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Could not parse campaign %s: %s", cid, exc)
        self._carry_over_claims(campaigns)
        self.campaigns = campaigns
        for campaign in campaigns.values():
            self.games.remember(campaign.game)

    def _guess_links(self, merged: dict[str, JsonType]) -> None:
        """Campaigns from the catalog or from channels carry no account link status. Take it from
        inventory campaigns or rewards of the same game; when nothing is known, assume linked."""
        by_game: dict[str, bool] = {}
        by_name: dict[str, bool] = {}
        for reward in self.rewards:
            if reward.get("link_url") and reward.get("game"):
                by_name[reward["game"].lower()] = bool(reward.get("connected"))
        for data in self._sources["in_progress"].values():
            linked = (data.get("self") or {}).get("isAccountConnected")
            if linked is not None and data.get("game"):
                by_game[str(data["game"].get("id"))] = bool(linked)
        for data in merged.values():
            if (data.get("self") or {}).get("isAccountConnected") is not None:
                continue
            game = data["game"]
            name = str(game.get("displayName") or game.get("name") or "").lower()
            guessed = False
            if str(game.get("id")) in by_game:
                linked = by_game[str(game.get("id"))]
            elif name in by_name:
                linked = by_name[name]
            else:
                # no link needed without a link URL; otherwise unknown, and assumed linked
                linked, guessed = True, bool(data.get("accountLinkURL"))
            data["self"] = {**(data.get("self") or {}), "isAccountConnected": linked}
            data["linkGuessed"] = guessed

    def _carry_over_claims(self, campaigns: dict[str, Campaign]) -> None:
        """Keeps our claim bookkeeping when campaigns are re-read from Twitch."""
        old = self.drops
        for campaign in campaigns.values():
            for drop in campaign.drops.values():
                previous = old.get(drop.id)
                if previous is None or drop.is_claimed or not previous.claim_attempts:
                    continue
                drop.claim_attempts = previous.claim_attempts
                drop.claim_error = previous.claim_error
                drop.claim_retry_at = previous.claim_retry_at
                if drop.campaign.linked != previous.campaign.linked or drop.claim_id != previous.claim_id:
                    drop.claim_retry_at = None  # account linked or new claim id: try again right away

    # ------------------------------------------------------------------ games
    async def resolve_watched(self) -> None:
        """Looks up the games on the priority list that no campaign or channel told us about yet, for the
        directory slug that finds their drops-enabled streams (and the box art in the web UI)."""
        for name in self.settings.games_priority:
            if self.games.get(name) is not None:
                continue
            try:
                await self.games.lookup(name)
            except TwitchError as exc:
                logger.debug("Looking up %r on Twitch failed: %s", name, exc)
                return  # Twitch can not be asked right now; the next refresh tries again

    def watched_without_campaign(self) -> list[Game]:
        """Games on the priority list that Twitch knows and that have no running campaign."""
        running = {norm_game(c.game.name) for c in self.campaigns.values() if c.active}
        out: list[Game] = []
        for name in self.settings.games_priority:
            game = self.games.get(name)
            if game is not None and norm_game(name) not in running and game not in out:
                out.append(game)
        return out

    def _campaign_states(self) -> dict[str, str]:
        """Compared game name -> "active" or "upcoming", for games with a campaign."""
        states: dict[str, str] = {}
        for campaign in self.campaigns.values():
            key = norm_game(campaign.game.name)
            if campaign.active:
                states[key] = "active"
            elif campaign.upcoming:
                states.setdefault(key, "upcoming")
        return states

    @staticmethod
    def _game_dict(game: Game, states: dict[str, str]) -> JsonType:
        return {"name": game.name, "id": game.id, "box_art": game.box_art, "campaign": states.get(norm_game(game.name))}

    def game_suggestions(self, query: str, limit: int = 8) -> list[JsonType]:
        """Games whose name contains the query, for the priority list: from campaigns, channels and
        lookups, the reward history and what was watched before. Closest names and games with a
        campaign come first."""
        q = norm_game(query) if query.strip() else ""
        states = self._campaign_states()
        found: dict[str, JsonType] = {}
        for game in self._games_at_hand():
            found.setdefault(norm_game(game.name), self._game_dict(game, states))
        for name in [r["game"] for r in self.rewards if r.get("game")] + self.stats.games():
            key = norm_game(name)
            found.setdefault(key, {"name": name, "id": None, "box_art": "", "campaign": states.get(key)})
        order = {"active": 0, "upcoming": 1}
        matches = [
            ((0 if key == q else 1 if key.startswith(q) else 2), order.get(item["campaign"], 2), item["name"].casefold(), item)
            for key, item in found.items() if q in key
        ]
        matches.sort(key=lambda m: m[:3])
        return [m[3] for m in matches[:limit]]

    def _games_at_hand(self) -> list[Game]:
        """Games of the campaigns, the channels and earlier lookups."""
        games = [c.game for c in self.campaigns.values()]
        games += [ch.game for ch in self.channels.values() if ch.game is not None]
        return games + self.games.known()

    async def check_game(self, name: str) -> JsonType:
        """Whether Twitch knows a game name: status "found" (with the game), "missing" or "unavailable"."""
        name = " ".join(name.split())
        key = norm_game(name)
        game = next((g for g in self._games_at_hand() if norm_game(g.name) == key), None)
        if game is not None:
            return {"query": name, "status": "found", "game": self._game_dict(game, self._campaign_states())}
        try:
            game = await asyncio.wait_for(self.games.lookup(name), LOOKUP_TIMEOUT)
        except (TwitchError, asyncio.TimeoutError) as exc:
            logger.debug("Looking up %r on Twitch failed: %s", name, exc)
            return {"query": name, "status": "unavailable", "game": None}
        if game is None:
            return {"query": name, "status": "missing", "game": None}
        return {"query": name, "status": "found", "game": self._game_dict(game, self._campaign_states())}

    def campaign_overview(self) -> list[JsonType]:
        out = []
        wanted_ids = [c.id for c in wanted_campaigns(self.campaigns.values(), self.settings)]
        for campaign in self.campaigns.values():
            data = campaign.to_dict()
            data["skip_reason"] = skip_reason(campaign, self.settings)
            data["wanted"] = campaign.id in wanted_ids
            data["queue_position"] = wanted_ids.index(campaign.id) + 1 if campaign.id in wanted_ids else None
            data["mining"] = self.target_campaign is not None and self.target_campaign.id == campaign.id
            data["live_channels"] = sum(
                1 for ch in self.channels.values()
                if ch.online and ch.campaign_ids is not None and campaign.id in ch.campaign_ids
            )
            out.append(data)
        out.sort(key=lambda c: (not c["mining"], c["queue_position"] or 10_000, c["status"] != "active", c["ends_at"]))
        return out

    def drops_overview(self) -> JsonType:
        """Every drop of every known campaign with its status, plus the account's reward history."""
        claimed_at = self.stats.claim_times()
        wanted_ids = {c.id for c in wanted_campaigns(self.campaigns.values(), self.settings)}
        drops = []
        for campaign in self.campaigns.values():
            for drop in campaign.drops.values():
                data = drop.to_dict()
                stamp = claimed_at.get(drop.id)
                if stamp is None and drop.is_claimed:
                    awarded = [self.awarded[b.id] for b in drop.benefits if b.id in self.awarded]
                    stamp = max(awarded).isoformat() if awarded else None
                data["claimed_at"] = stamp
                data["mining"] = drop.id == self.current_drop_id
                data["campaign"] = {
                    "id": campaign.id, "name": campaign.name, "image": campaign.image, "linked": campaign.linked,
                    "link_known": campaign.link_known,
                    "link_url": campaign.link_url, "starts_at": campaign.starts_at.isoformat(),
                    "ends_at": campaign.ends_at.isoformat(),
                    "wanted": campaign.id in wanted_ids,
                }
                data["game"] = {"id": campaign.game.id, "name": campaign.game.name, "box_art": campaign.game.box_art}
                drops.append(data)
        counts = collections.Counter(d["status"] for d in drops)
        return {
            "drops": drops, "counts": dict(counts), "rewards": self.rewards,
            "claims": self.stats.recent_claims(200), "auto_claim": self.settings.auto_claim,
        }

    # ------------------------------------------------------------------ claiming
    async def claim_all_ready(self, method: str) -> int:
        if not self.settings.auto_claim:
            return 0
        claimed = 0
        now = utcnow()
        for drop in list(self.drops.values()):
            if drop.claimable() and not (drop.claim_retry_at and drop.claim_retry_at > now):
                if claimed:
                    await asyncio.sleep(self.retry_delay)  # space out bulk claims like the site does
                if await self.claim_drop(drop, method=method):
                    claimed += 1
        return claimed

    async def claim_drop(self, drop: Drop, *, instance_id: str | None = None, method: str = "auto") -> bool:
        """Claims a drop, trying every claim id we know, with retries. Returns success."""
        if drop.is_claimed:
            return True
        if drop.id in self._claiming:
            return False
        self._claiming.add(drop.id)
        try:
            candidates: list[str] = []
            generated = f"{self.client.user_id}#{drop.campaign.id}#{drop.id}"
            for cid in (instance_id, drop.claim_id, generated):
                if cid and cid not in candidates:
                    candidates.append(cid)
            detail = ""
            for claim_id in candidates:
                for attempt in range(CLAIM_ATTEMPTS):
                    ok, detail = await self._claim_request(claim_id)
                    if ok:
                        drop.is_claimed = True
                        drop.claim_id = claim_id
                        drop.current_minutes = drop.required_minutes
                        drop.claim_attempts, drop.claim_error, drop.claim_retry_at = 0, "", None
                        self._record_claim(drop, method, True, detail)
                        return True
                    if detail.startswith("fatal"):
                        break  # this claim id is invalid, try the next one
                    await asyncio.sleep(self.retry_delay * (attempt + 1) ** 2)
            drop.claim_attempts += 1
            drop.claim_error = detail.removeprefix("fatal: ") or "unknown error"
            backoff = CLAIM_BACKOFF_MINUTES[min(drop.claim_attempts, len(CLAIM_BACKOFF_MINUTES)) - 1]
            drop.claim_retry_at = utcnow() + timedelta(minutes=backoff)
            self._record_claim(drop, method, False, detail)
            logger.error("Claim failed: %s (%s)%s, next attempt in %d minutes", drop.rewards, detail,
                         ", game account not linked" if drop.needs_link else "", backoff)
            return False
        finally:
            self._claiming.discard(drop.id)

    async def _claim_request(self, claim_id: str) -> tuple[bool, str]:
        try:
            response = await self.client.gql(
                self.client.operation("ClaimDrop", {"input": {"dropInstanceID": claim_id}})
            )
        except GQLError as exc:
            text = str(exc.errors)
            return False, ("fatal: " if "not found" in text.lower() or "invalid" in text.lower() else "") + text
        except TwitchError as exc:
            return False, str(exc)
        result = (response.get("data") or {}).get("claimDropRewards")
        if not result:
            return False, "fatal: empty response"
        status = result.get("status", "")
        if status in ("ELIGIBLE_FOR_ALL", "DROP_INSTANCE_ALREADY_CLAIMED"):
            return True, status
        return False, f"fatal: {status}" if status else "unknown status"

    def _record_claim(self, drop: Drop, method: str, success: bool, detail: str) -> None:
        campaign = drop.campaign
        self.stats.add_claim(
            drop_id=drop.id, drop_name=drop.name, rewards=drop.rewards, campaign_id=campaign.id,
            campaign_name=campaign.name, game=campaign.game.name, method=method, success=success, detail=detail,
        )
        if success:
            self.session_claims += 1
            logger.info("Drop claimed: %s (%s, %d/%d)", drop.rewards, campaign.game.name,
                        campaign.claimed_count, len(campaign.drops))
            self.notifier.drop_claimed(drop)
            if campaign.finished:
                self.notifier.campaign_done(campaign)
        elif drop.claim_attempts == 1:
            # retries follow with growing pauses; only the first failure is news
            self.notifier.claim_failed(drop)

    async def _sweep_loop(self) -> None:
        """Re-reads the inventory regularly and claims whatever is finished but unclaimed.

        This is what makes claiming reliable: even if a PubSub event or a claim call got lost,
        the next sweep picks the drop up again (up to 24h after the campaign ended).
        """
        await self.client.logged_in.wait()
        while True:
            await asyncio.sleep(self.settings.claim_sweep_interval_minutes * 60)
            if not self.client.logged_in.is_set() or not self.campaigns:
                continue
            in_progress, claimed = await self.fetch_inventory()
            for cid, data in in_progress.items():
                campaign = self.campaigns.get(cid)
                if campaign is None:
                    continue
                fresh = Campaign.from_gql(deep_merge(self._campaign_skeleton(campaign), data), claimed)
                for drop_id, fresh_drop in fresh.drops.items():
                    drop = campaign.drops.get(drop_id)
                    if drop is None:
                        continue
                    if fresh_drop.is_claimed and not drop.is_claimed:
                        drop.is_claimed = True
                        drop.current_minutes = drop.required_minutes
                    elif not drop.is_claimed:
                        drop.current_minutes = max(drop.current_minutes, fresh_drop.current_minutes)
                        drop.claim_id = fresh_drop.claim_id or drop.claim_id
            if await self.claim_all_ready("sweep"):
                self._reselect.set()

    @staticmethod
    def _campaign_skeleton(campaign: Campaign) -> JsonType:
        return {
            "id": campaign.id, "name": campaign.name, "status": campaign.status,
            "game": {"id": campaign.game.id, "displayName": campaign.game.name, "slug": campaign.game.slug},
            "startAt": campaign.starts_at.isoformat(), "endAt": campaign.ends_at.isoformat(),
        }

    # ------------------------------------------------------------------ channels
    async def discover_channels(self) -> None:
        settings = self.settings
        wanted = wanted_campaigns(self.campaigns.values(), settings)
        found: dict[str, Channel] = {}

        # 1. channels named in campaign ACLs and preferred channels: check their live status
        acl_logins: dict[str, str] = {}
        for campaign in wanted:
            for cid, login in list(campaign.allowed_channels.items())[:100]:
                if login:
                    acl_logins[login] = "acl"
        for login in settings.channels_preferred:
            acl_logins[login] = "preferred"
        if self.manual_channel:
            acl_logins[self.manual_channel] = "preferred"
        if self.watching:
            # keep tracking the watched channel even if it dropped out of the directory's top list
            acl_logins.setdefault(self.watching.login, self.watching.source)
        for channel in await self.fetch_streams(list(acl_logins)):
            channel.source = acl_logins.get(channel.login, "acl")
            found[channel.id] = channel

        # 2. game directories filtered to drops-enabled streams
        games: dict[int, Game] = {}
        for campaign in wanted:
            if not campaign.allowed_channels:
                games[campaign.game.id] = campaign.game
        for channels in (await self.fetch_directories(list(games.values()))).values():
            for channel in channels:
                found.setdefault(channel.id, channel)
        # campaigns known only by name (catalog): the channels that offer them tell their drops
        scout: dict[int, Game] = {}
        for campaign in self.campaigns.values():
            if not campaign.drops and campaign.game.id not in games and skip_reason(campaign, settings) == "unavailable":
                scout[campaign.game.id] = campaign.game
        # games on the priority list without a running campaign: drops-enabled streams show a new campaign
        # as soon as it starts, also before the catalog lists it
        for game in self.watched_without_campaign():
            if game.id not in games:
                scout.setdefault(game.id, game)
        scouted: set[str] = set()
        limit = min(SCOUT_CHANNELS_PER_GAME, settings.channels_per_game)
        for channels in (await self.fetch_directories(list(scout.values()), limit=limit)).values():
            for channel in channels:
                if channel.id not in found:
                    found[channel.id] = channel
                    scouted.add(channel.id)

        found = {k: ch for k, ch in found.items() if ch.login not in settings.channels_blacklist}

        # 3. ask Twitch which campaigns each live channel really offers right now
        online = [ch for ch in found.values() if ch.online]
        await self.verify_channels(online if settings.verify_channel_drops else [ch for ch in online if ch.id in scouted])
        # scouting channels are only kept when they offer a campaign
        found = {k: ch for k, ch in found.items() if k not in scouted or ch.campaign_ids}

        # keep the watched channel's object identity so the watch loop is not disturbed
        if self.watching and self.watching.id in found:
            fresh = found[self.watching.id]
            self.watching.__dict__.update({k: v for k, v in fresh.__dict__.items() if k != "source"})
            found[self.watching.id] = self.watching
        self.channels = found
        for channel in found.values():
            self.games.remember(channel.game)
        live = sum(ch.online for ch in found.values())
        logger.info("%d channels found, %d live with drops", len(found), live)

    async def fetch_streams(self, logins: list[str]) -> list[Channel]:
        if not logins:
            return []
        ops = [self.client.operation("GetStreamInfo", {"channel": login}) for login in logins]
        channels = []
        for login, result in zip(logins, await self.client.gql_batch(ops)):
            user = (result.get("data") or {}).get("user")
            if not user:
                continue
            channel = Channel(id=str(user["id"]), login=(user.get("login") or login).lower(),
                              display_name=user.get("displayName") or login)
            self._apply_stream(channel, user)
            channels.append(channel)
        return channels

    @staticmethod
    def _apply_stream(channel: Channel, user: JsonType) -> None:
        stream = user.get("stream")
        settings = user.get("broadcastSettings") or {}
        channel.online = bool(stream)
        channel.last_checked = utcnow()
        if stream:
            channel.broadcast_id = str(stream.get("id") or "")
            channel.viewers = int(stream.get("viewersCount") or 0)
            game = settings.get("game")
            channel.game = Game.from_gql(game) if game else None
            channel.title = settings.get("title") or ""
        else:
            channel.game = None
            channel.viewers = 0

    async def fetch_directories(self, games: list[Game], limit: int | None = None) -> dict[int, list[Channel]]:
        """Drops-enabled live streams per game id. All games go out in batched requests (with a catalog
        that is around a hundred games); a game whose directory fails just comes back empty."""
        settings = self.settings
        options = {
            "systemFilters": ["DROPS_ENABLED"],
            "broadcasterLanguages": [lang.upper() for lang in settings.stream_languages],
        }
        ops = [self.client.operation("GameDirectory", {
            "slug": game.slug, "limit": limit or settings.channels_per_game, "options": options,
        }) for game in games]
        if not ops:
            return {}
        try:
            results = await self.client.gql_batch(ops, tolerant=True)
        except GQLError as exc:
            logger.warning("Could not load the game directories: %s", exc)
            return {}
        return {game.id: self._directory_channels(game, result) for game, result in zip(games, results)}

    @staticmethod
    def _directory_channels(game: Game, response: JsonType) -> list[Channel]:
        if not isinstance(response, dict):
            return []
        edges = (((response.get("data") or {}).get("game") or {}).get("streams") or {}).get("edges") or []
        channels = []
        for edge in edges:
            node = edge.get("node") or {}
            broadcaster = node.get("broadcaster")
            if not broadcaster:
                continue
            channel = Channel(
                id=str(broadcaster["id"]), login=broadcaster["login"].lower(),
                display_name=broadcaster.get("displayName") or broadcaster["login"],
                online=True, viewers=int(node.get("viewersCount") or 0), title=node.get("title") or "",
                broadcast_id=str(node.get("id") or ""), drops_enabled=True, source="directory",
                game=Game.from_gql(node["game"]) if node.get("game") else game, last_checked=utcnow(),
            )
            channels.append(channel)
        return channels

    async def verify_channels(self, channels: list[Channel]) -> None:
        if not channels:
            return
        ops = [self.client.operation("AvailableDrops", {"channelID": ch.id}) for ch in channels]
        try:
            results = await self.client.gql_batch(ops, tolerant=True)
        except GQLError as exc:
            logger.warning("Checking channels for drops failed: %s", exc)
            return
        by_id = {ch.id: ch for ch in channels}
        news = False
        for result in results:
            info = (result.get("data") or {}).get("channel")
            if not info:
                continue
            channel = by_id.get(str(info.get("id")))
            if channel is None:
                continue
            offered = [c for c in (info.get("viewerDropCampaigns") or []) if c.get("id")]
            ids = {c["id"] for c in offered}
            channel.campaign_names = {c["id"]: c.get("name") or "" for c in offered}
            channel.campaign_ids = ids
            channel.drops_enabled = bool(ids)
            for data in offered:
                news |= self._remember_campaign(data)
        if news:
            self._build_campaigns()
            self._announce_new_campaigns()

    def _remember_campaign(self, data: JsonType) -> bool:
        """Keeps the drops a live channel reports for a campaign (Twitch no longer hands out campaign
        details to apps). Returns True when this is new information."""
        game = data.get("game") or {}
        drops = [d for d in (data.get("timeBasedDrops") or []) if d.get("id")]
        if not game.get("id") or not drops:
            return False
        name = game.get("displayName") or game.get("name") or "?"
        entry = {
            "id": data["id"],
            "name": data.get("name") or "",
            "status": "ACTIVE",
            "startAt": min((d["startAt"] for d in drops if d.get("startAt")), default=None),
            "endAt": data.get("endAt"),
            "accountLinkURL": "",
            "game": {
                "id": str(game["id"]), "name": name, "displayName": name, "slug": game.get("slug") or "",
                "boxArtURL": game.get("boxArtURL") or f"https://static-cdn.jtvnw.net/ttv-boxart/{game['id']}_IGDB.jpg",
            },
            "timeBasedDrops": [{
                "id": d["id"], "name": d.get("name") or "", "startAt": d.get("startAt"), "endAt": d.get("endAt"),
                "requiredMinutesWatched": d.get("requiredMinutesWatched"),
                "preconditionDrops": d.get("preconditionDrops"),
                "benefitEdges": [
                    {**edge, "benefit": {"distributionType": "UNKNOWN", **(edge.get("benefit") or {})}}
                    for edge in (d.get("benefitEdges") or []) if (edge.get("benefit") or {}).get("id")
                ],
            } for d in drops],
        }
        if self._discovered.get(entry["id"]) == entry:
            return False
        self._discovered[entry["id"]] = entry
        return True

    # ------------------------------------------------------------------ selection
    async def select_channel(self) -> None:
        self._select()

    def _select(self) -> None:
        settings = self.settings
        if settings.paused:
            return
        now = time.monotonic()
        self._cooldown = {k: v for k, v in self._cooldown.items() if v > now}
        wanted = wanted_campaigns(self.campaigns.values(), settings)

        if self.manual_channel:
            manual = next((ch for ch in self.channels.values() if ch.login == self.manual_channel), None)
            if manual and manual.online:
                campaign = next((c for c in wanted if manual.game and c.game.id == manual.game.id), None)
                self.target_campaign = campaign
                self._set_watching(manual)
                return
            logger.info("Manually picked channel %s is offline, back to automatic", self.manual_channel)
            self.manual_channel = None

        campaign, channel = pick_channel(
            wanted, self.channels.values(), settings, current=self.watching, cooldown=set(self._cooldown)
        )
        previous = self.watching
        self.target_campaign = campaign
        current = self.drops.get(self.current_drop_id or "")
        if current is not None and (campaign is None or current.campaign.id != campaign.id):
            self.current_drop_id = None  # Twitch reports the drop of the new campaign on the next poll
        self.selection = self._explain(wanted, campaign, channel, previous)
        if channel is None:
            self._set_watching(None)
            self.state = "idle"
            self._set_activity("no_channels" if wanted else "no_campaigns")
            return
        self._set_watching(channel)

    def _explain(self, wanted: list[Campaign], campaign: Campaign | None, channel: Channel | None,
                 previous: Channel | None) -> JsonType | None:
        """Why this channel: the campaign's place in the queue, how many live channels offer it and
        which rule picked this one (single, stay, preferred, acl or viewers)."""
        if campaign is None or channel is None:
            return None
        settings = self.settings
        candidates = [
            ch for ch in self.channels.values()
            if ch.online and ch.login not in settings.channels_blacklist and ch.id not in self._cooldown
            and channel_serves(ch, campaign, settings.verify_channel_drops)
        ]
        if len(candidates) <= 1:
            rule = "single"
        elif previous is not None and previous.id == channel.id:
            rule = "stay"
        elif channel.login in settings.channels_preferred:
            rule = "preferred"
        elif channel.source == "acl":
            rule = "acl"
        else:
            rule = "viewers"
        return {
            "campaign_id": campaign.id, "campaign": campaign.name, "game": campaign.game.name,
            "position": wanted.index(campaign) + 1, "queue": len(wanted), "candidates": len(candidates),
            "rule": rule,
        }

    def _set_activity(self, code: str, **params: Any) -> None:
        self.activity = {"code": code, "params": params}
        self.status_text = ACTIVITIES[code].format(**params)

    def _set_watching(self, channel: Channel | None) -> None:
        previous = self.watching
        self.watching = channel
        if channel is None:
            self.current_drop_id = None
            return
        self.state = "watching"
        game = channel.game.name if channel.game else "?"
        self._set_activity("watching", channel=channel.name, game=game)
        if previous is None or previous.id != channel.id:
            logger.info("Switching to %s (%s, %d viewers)", channel.name, game, channel.viewers)
            self._progress_mark = (-1, time.monotonic())
            self.current_drop_id = None
            self._reselect.set()
            asyncio.create_task(self._update_pubsub_topics())
            if self.settings.claim_channel_points:
                asyncio.create_task(self._claim_points_bonus(channel))

    async def switch_to(self, login: str | None) -> None:
        self.manual_channel = login.lower() if login else None
        if self.manual_channel and not any(ch.login == self.manual_channel for ch in self.channels.values()):
            for channel in await self.fetch_streams([self.manual_channel]):
                channel.source = "preferred"
                self.channels[channel.id] = channel
                if self.settings.verify_channel_drops and channel.online:
                    await self.verify_channels([channel])
        await self.select_channel()

    # ------------------------------------------------------------------ watching
    async def _watch_loop(self) -> None:
        last_check = float("-inf")
        last_channel: Channel | None = None
        # Watch time is credited from the real time between successful watch requests, not per request:
        # an early wake-up (channel switch, settings change) must not count an extra minute.
        last_ok: float | None = None
        credit = 0.0
        while True:
            channel = self.watching
            if channel is None or self.settings.paused or not self.client.logged_in.is_set():
                last_ok = None
                self._reselect.clear()
                try:
                    await asyncio.wait_for(self._reselect.wait(), timeout=10)
                except asyncio.TimeoutError:
                    pass
                continue
            if channel is not last_channel:
                last_channel, last_check = channel, float("-inf")
            started = time.monotonic()
            ok = await self.send_watch(channel)
            if ok:
                if last_ok is not None:
                    credit += min(started - last_ok, WATCH_INTERVAL * 2)
                last_ok = started
                while credit >= 60:
                    credit -= 60
                    self.session_watch_minutes += 1
                    self.stats.add_watch_minute(channel.game.name if channel.game else "?", channel.login)
            else:
                last_ok = None
                logger.info("Watch event for %s failed, checking the stream", channel.name)
                await self._recheck_watched()
                await self._sleep_or_reselect(30)
                continue
            if started - last_check >= MINUTE_INTERVAL - 1:
                await self._sleep_or_reselect(15)
                if self.watching is channel:
                    last_check = started
                    await self._check_progress(channel)
            await self._sleep_or_reselect(WATCH_INTERVAL - (time.monotonic() - started))

    async def _sleep_or_reselect(self, seconds: float) -> None:
        if seconds <= 0:
            return
        self._reselect.clear()
        try:
            await asyncio.wait_for(self._reselect.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    async def send_watch(self, channel: Channel) -> bool:
        """Watches the stream the way the player does: fetches its HLS segments (what Twitch counts since
        2026-10-07) and, once a minute, sends the minute-watched event. True when the channel is still live."""
        if not channel.broadcast_id:
            await self._recheck_watched()
            channel = self.watching
            if channel is None or not channel.broadcast_id:
                return False
        hls = await self._watch_stream(channel)
        spade = True
        if time.monotonic() - self._last_spade >= MINUTE_INTERVAL - 1:
            spade = await self._send_spade(channel)
            if spade:
                self._last_spade = time.monotonic()
        return hls is not False and spade

    async def _watch_stream(self, channel: Channel) -> bool | None:
        """Requests the new segments of the stream. None when the playlist could not be set up (the
        minute-watched event still goes out), False when the stream is gone, True on success."""
        try:
            url = self._stream_urls.get(channel.login) or await self._get_stream_url(channel.login)
            if url is None:
                return None
            self._stream_urls[channel.login] = url
            status, body = await self.client.request("GET", url, headers={"Connection": "close"}, retries=2)
            if status >= 400:
                self._stream_urls.pop(channel.login, None)
                return False if status == 404 else None
            segments = [line for line in body.splitlines() if line.startswith("http")]
            fresh = [seg for seg in segments if seg not in self._seen_segments]
            for seg in fresh:
                status, _ = await self.client.request("HEAD", seg, retries=1)
                if status != 200:
                    self._stream_urls.pop(channel.login, None)
                    return None
                self._seen_segments.append(seg)
            self._hls_warned = False
            return True
        except (TwitchError, GQLError, KeyError, TypeError, ValueError) as exc:
            self._stream_urls.pop(channel.login, None)
            if not self._hls_warned:
                logger.warning("Could not read the stream of %s (%s), drop progress may not count", channel.name, exc)
                self._hls_warned = True
            return None

    async def _get_stream_url(self, login: str) -> str | None:
        response = await self.client.gql(self.client.operation("PlaybackAccessToken", {"login": login}))
        token = (response.get("data") or {}).get("streamPlaybackAccessToken")
        if not token:
            return None
        status, body = await self.client.request(
            "GET", USHER_URL.format(login=login), params={"sig": token["signature"], "token": token["value"]},
            retries=2,
        )
        if status != 200 or body.lstrip().startswith(("{", "[")):
            return None  # offline, or the token was refused
        urls = [line.strip() for line in body.splitlines() if line.startswith("http")]
        return urls[-1] if urls else None  # the last variant is the lowest quality

    async def _send_spade(self, channel: Channel) -> bool:
        if self._spade_url is None:
            try:
                self._spade_url = await self._get_spade_url(channel.login)
            except TwitchError as exc:
                logger.info("Could not read the watch URL (%s), using the default one", exc)
                self._spade_url = SPADE_FALLBACK_URL
        payload = [{
            "event": "minute-watched",
            "properties": {
                "broadcast_id": str(channel.broadcast_id),
                "channel_id": str(channel.id),
                "channel": channel.login,
                "client_time": utcnow().isoformat(),
                "game": channel.game.name if channel.game else "",
                "game_id": str(channel.game.id) if channel.game else "",
                "hidden": False,
                "is_live": True,
                "live": True,
                "logged_in": True,
                "minutes_logged": 1,
                "muted": False,
                "user_id": int(self.client.user_id or 0),
            },
        }]
        data = base64.b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
        try:
            status, _ = await self.client.request("POST", self._spade_url, data={"data": data}, retries=3)
        except TwitchError:
            self._spade_url = None
            return False
        if status != 204:
            self._spade_url = None
        return status == 204

    async def _get_spade_url(self, login: str) -> str:
        browser = {"User-Agent": BROWSER_USER_AGENT}
        status, html = await self.client.request("GET", f"https://www.twitch.tv/{login}", headers=browser)
        match = SPADE_PATTERN.search(html)
        if not match:
            settings_js = SETTINGS_JS_PATTERN.search(html)
            if not settings_js:
                raise TwitchError("spade URL not found (step 1)")
            _, js = await self.client.request("GET", settings_js.group(1), headers=browser)
            match = SPADE_PATTERN.search(js)
            if not match:
                raise TwitchError("spade URL not found (step 2)")
        return match.group(1)

    async def _recheck_watched(self) -> None:
        channel = self.watching
        if channel is None:
            return
        fresh = await self.fetch_streams([channel.login])
        if fresh:
            for key in ("online", "broadcast_id", "viewers", "game", "title", "last_checked"):
                setattr(channel, key, getattr(fresh[0], key))
        else:
            channel.online = False
        target = self.target_campaign
        wrong_game = (
            target is not None and not target.game.special
            and (channel.game is None or channel.game.id != target.game.id)
        )
        if not channel.online or wrong_game:
            logger.info("%s went offline or switched games, looking for another channel", channel.name)
            if wrong_game:
                self._cooldown[channel.id] = time.monotonic() + COOLDOWN_MINUTES * 60
            self._set_watching(None)
            await self.select_channel()
            if self.watching is None:
                self.request_refresh()

    async def _check_progress(self, channel: Channel) -> None:
        """Polls the current drop session; claims finished drops; detects stalled channels."""
        try:
            response = await self.client.gql(
                self.client.operation("CurrentDrop", {"channelID": channel.id, "channelLogin": ""})
            )
            session = ((response.get("data") or {}).get("currentUser") or {}).get("dropCurrentSession")
        except GQLError as exc:
            logger.debug("CurrentDrop failed: %s", exc)
            session = None
        if session and session.get("dropID"):
            self._apply_progress(session["dropID"], int(session.get("currentMinutesWatched") or 0))
        await self._check_stall(channel)

    def _apply_progress(self, drop_id: str, minutes: int) -> None:
        drop = self.drops.get(drop_id)
        if drop is None:
            return
        self.current_drop_id = drop_id
        if minutes > drop.current_minutes or drop.current_minutes > drop.required_minutes:
            drop.current_minutes = min(minutes, drop.required_minutes)
        mark_minutes, _ = self._progress_mark
        total = sum(d.current_minutes for d in drop.campaign.drops.values())
        if total != mark_minutes:
            self._progress_mark = (total, time.monotonic())
        if drop.claimable() and self.settings.auto_claim:
            asyncio.create_task(self._claim_and_continue(drop, None, "progress"))

    async def _check_stall(self, channel: Channel) -> None:
        _, since = self._progress_mark
        if time.monotonic() - since < STALL_MINUTES * 60 or self.target_campaign is None:
            return
        logger.warning("No progress on %s for %d minutes, trying another channel",
                       channel.name, STALL_MINUTES)
        self._cooldown[channel.id] = time.monotonic() + COOLDOWN_MINUTES * 60
        self._progress_mark = (-1, time.monotonic())
        self.manual_channel = None
        await self.select_channel()

    async def _claim_and_continue(self, drop: Drop, instance_id: str | None, method: str) -> None:
        if await self.claim_drop(drop, instance_id=instance_id, method=method):
            # the next drop starts once Twitch registers the claim; reselect in case the campaign is done
            await asyncio.sleep(self.claim_settle_seconds)
            await self.select_channel()
            self._reselect.set()

    # ------------------------------------------------------------------ pubsub
    async def _update_pubsub_topics(self) -> None:
        uid = self.client.user_id
        if not uid:
            return
        topics = {f"{PUBSUB_TOPICS['user_drops']}.{uid}", f"{PUBSUB_TOPICS['user_notifications']}.{uid}"}
        if self.settings.claim_channel_points:
            topics.add(f"{PUBSUB_TOPICS['user_points']}.{uid}")
        if self.watching:
            topics.add(f"{PUBSUB_TOPICS['stream_state']}.{self.watching.id}")
        try:
            await self.pubsub.set_topics(topics)
        except Exception as exc:
            logger.debug("PubSub topics not updated: %s", exc)

    async def _on_pubsub(self, topic: str, message: JsonType) -> None:
        kind = message.get("type")
        data = message.get("data") or {}
        if topic.startswith(PUBSUB_TOPICS["user_drops"]):
            drop = self.drops.get(data.get("drop_id", ""))
            if kind == "drop-progress" and drop is not None:
                self._apply_progress(drop.id, int(data.get("current_progress_min") or 0))
            elif kind == "drop-claim" and drop is not None:
                drop.current_minutes = max(drop.current_minutes, drop.required_minutes)
                drop.claim_id = data.get("drop_instance_id") or drop.claim_id
                drop.claim_retry_at = None
                if self.settings.auto_claim:
                    await self._claim_and_continue(drop, data.get("drop_instance_id"), "pubsub")
                else:
                    self._reselect.set()
        elif topic.startswith(PUBSUB_TOPICS["user_notifications"]):
            notification = (data.get("notification") or {}) if kind == "create-notification" else {}
            if notification.get("type") == "user_drop_reward_reminder_notification":
                self.request_refresh()
        elif topic.startswith(PUBSUB_TOPICS["user_points"]):
            if kind == "claim-available":
                claim = data.get("claim") or {}
                await self._claim_points(claim.get("id"), claim.get("channel_id"))
            elif kind == "points-earned":
                gain = (data.get("point_gain") or {})
                channel = self.channels.get(str(data.get("channel_id")))
                self.stats.add_points(channel.login if channel else str(data.get("channel_id")),
                                      int(gain.get("total_points") or 0))
        elif topic.startswith(PUBSUB_TOPICS["stream_state"]):
            if kind == "stream-down" and self.watching and topic.endswith(f".{self.watching.id}"):
                logger.info("%s went offline", self.watching.name)
                self.watching.online = False
                self._set_watching(None)
                await self.select_channel()
            elif kind == "viewcount" and self.watching and topic.endswith(f".{self.watching.id}"):
                self.watching.viewers = int(message.get("viewers") or self.watching.viewers)

    async def _claim_points_bonus(self, channel: Channel) -> None:
        try:
            response = await self.client.gql(self.client.operation("ChannelPointsContext", {"channelLogin": channel.login}))
            community = ((response.get("data") or {}).get("community") or {})
            points = (((community.get("channel") or {}).get("self") or {}).get("communityPoints") or {})
            claim = points.get("availableClaim")
            if claim:
                await self._claim_points(claim.get("id"), channel.id)
        except Exception as exc:
            logger.debug("Channel points context failed: %s", exc)

    async def _claim_points(self, claim_id: str | None, channel_id: str | None) -> None:
        if not claim_id or not channel_id or not self.settings.claim_channel_points:
            return
        try:
            await self.client.gql(self.client.operation(
                "ClaimCommunityPoints", {"input": {"claimID": claim_id, "channelID": str(channel_id)}}
            ))
            logger.info("Channel points bonus claimed")
        except Exception as exc:
            logger.debug("Channel points claim failed: %s", exc)

    # ------------------------------------------------------------------ ui state
    def snapshot(self) -> JsonType:
        drop = self.drops.get(self.current_drop_id or "")
        target = self.target_campaign
        if target is not None and (drop is None or drop.campaign.id != target.id):
            drop = target.next_drop() or drop
        prompt = self.client.login_prompt
        return {
            "state": self.state,
            "status": self.status_text,
            "activity": self.activity,
            "error": self.last_error,
            "user": {"login": self.client.login, "id": self.client.user_id} if self.client.logged_in.is_set() else None,
            "login_prompt": {
                "code": prompt.user_code, "url": prompt.verification_uri,
                "expires_in": max(0, int(prompt.expires_at - time.time())),
            } if prompt and not self.client.logged_in.is_set() else None,
            "paused": self.settings.paused,
            "pubsub": self.pubsub.connected,
            "watching": self.watching.to_dict() if self.watching else None,
            "manual": self.manual_channel,
            "selection": {"rule": "manual"} if self.manual_channel and self.watching else self.selection,
            "auto_claim": self.settings.auto_claim,
            "campaign_source": self.campaign_source,
            "campaign": {
                "id": self.target_campaign.id, "name": self.target_campaign.name,
                "game": self.target_campaign.game.name, "box_art": self.target_campaign.game.box_art,
                "claimed": self.target_campaign.claimed_count, "total": len(self.target_campaign.drops),
                "ends_at": self.target_campaign.ends_at.isoformat(),
                "remaining_minutes": self.target_campaign.remaining_minutes,
            } if self.target_campaign else None,
            "drop": drop.to_dict() if drop else None,
            "last_refresh": self.last_refresh.isoformat() if self.last_refresh else None,
            "next_refresh": self.next_refresh.isoformat() if self.next_refresh else None,
            "started_at": self.started_at.isoformat(),
            "session": {"minutes": self.session_watch_minutes, "claims": self.session_claims},
            "counts": {
                "campaigns": len(self.campaigns),
                "active": sum(c.active for c in self.campaigns.values()),
                "wanted": len(wanted_campaigns(self.campaigns.values(), self.settings)),
                "channels_live": sum(ch.online for ch in self.channels.values()),
                "claimable": sum(d.claimable() for d in self.drops.values()),
                "claim_ready": sum(d.status() == "ready" for d in self.drops.values()),
                "claim_failed": sum(d.status() == "failed" for d in self.drops.values()),
            },
        }
