"""Persistent settings, edited from the web UI and stored as JSON in the data directory."""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from .catalog import DEFAULT_CATALOG_URL

logger = logging.getLogger("dropper.settings")

AVATAR_MAX = 700_000  # characters of an uploaded picture (the web UI shrinks it to 256x256 first)


def clean_sender_name(value: str) -> str:
    """The Discord sender name as typed, with spaces tidied; Discord takes at most 80 characters."""
    return " ".join(str(value or "").split())[:80]


def clean_avatar(value: str) -> str:
    """An uploaded picture (a data URL) or a public image URL. Anything else means the Dropper icon."""
    value = str(value or "").strip()
    if len(value) <= AVATAR_MAX and re.fullmatch(r"data:image/(png|jpeg|gif);base64,[A-Za-z0-9+/]+=*", value):
        return value
    return value if re.fullmatch(r"https?://\S+", value) else ""


class PriorityMode(str, Enum):
    # campaigns that end first are mined first
    ENDING_SOONEST = "ending_soonest"
    # campaigns with the least spare time (time left / minutes still needed) first
    LOW_AVAILABILITY = "low_availability"
    # only games on the priority list are mined, in list order
    PRIORITY_ONLY = "priority_only"


class GameMode(str, Enum):
    # mine every campaign that is not excluded
    ALL = "all"
    # mine only games on the whitelist
    WHITELIST = "whitelist"


class Settings(BaseModel):
    # what to mine
    game_mode: GameMode = GameMode.ALL
    games_whitelist: list[str] = Field(default_factory=list)
    games_exclude: list[str] = Field(default_factory=list)
    games_priority: list[str] = Field(default_factory=list)
    # individual campaigns switched off in the UI (campaign ids)
    campaigns_exclude: list[str] = Field(default_factory=list)
    priority_mode: PriorityMode = PriorityMode.ENDING_SOONEST
    # badges and emotes need no linked game account, so they are always deliverable
    mine_badges_emotes: bool = True
    # skip campaigns whose game account is not linked (the reward could not be delivered)
    require_linked_account: bool = True

    # channels
    channels_preferred: list[str] = Field(default_factory=list)
    channels_blacklist: list[str] = Field(default_factory=list)
    stream_languages: list[str] = Field(default_factory=list)
    channels_per_game: int = Field(default=25, ge=1, le=100)
    # double check each candidate with Twitch's per-channel "available drops" endpoint
    verify_channel_drops: bool = True

    # behaviour
    # claim finished drops on our own; when off, drops wait for the "claim" button in the UI
    auto_claim: bool = True
    claim_channel_points: bool = True
    refresh_interval_minutes: int = Field(default=30, ge=5, le=240)
    claim_sweep_interval_minutes: int = Field(default=5, ge=1, le=60)
    paused: bool = False

    # notifications: a Discord webhook, or any URL that takes JSON, and the events to send
    webhook_url: str = ""
    notify_claimed: bool = True
    notify_failed: bool = True
    notify_campaign_done: bool = True
    # a game on the priority list got a campaign (also one that starts later)
    notify_watched: bool = True
    notify_new_campaign: bool = False
    notify_login: bool = True
    # how the messages show up in Discord: the sender name (empty = Dropper) and its picture, uploaded
    # in the web UI (empty = the Dropper icon)
    webhook_username: str = ""
    webhook_avatar: str = ""

    # web UI language (en, de, ...); the UI falls back to English for unknown codes
    ui_language: str = Field(default="en", pattern=r"^[a-z]{2}(-[A-Za-z]{2,4})?$")

    # advanced
    # public list of running campaigns, used because Twitch hides the full list from apps (empty = off)
    campaign_catalog_url: str = DEFAULT_CATALOG_URL
    proxy: str = ""
    gql_hash_overrides: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "games_whitelist", "games_exclude", "games_priority", "campaigns_exclude",
        "channels_preferred", "channels_blacklist", "stream_languages",
    )
    @classmethod
    def _clean_list(cls, value: list[str]) -> list[str]:
        seen: list[str] = []
        for item in value:
            item = item.strip()
            if item and item not in seen:
                seen.append(item)
        return seen

    @field_validator("webhook_url")
    @classmethod
    def _webhook_scheme(cls, value: str) -> str:
        value = value.strip()
        # "discord.com/api/webhooks/..." pasted without the scheme
        return f"https://{value}" if value and "://" not in value else value

    @field_validator("channels_preferred", "channels_blacklist")
    @classmethod
    def _lower_logins(cls, value: list[str]) -> list[str]:
        return [v.lower().lstrip("@") for v in value]

    # these clean up instead of refusing: a hand-edited settings.json must still load
    @field_validator("webhook_username")
    @classmethod
    def _sender_name(cls, value: str) -> str:
        return clean_sender_name(value)

    @field_validator("webhook_avatar")
    @classmethod
    def _avatar(cls, value: str) -> str:
        return clean_avatar(value)


class SettingsStore:
    """Loads and saves settings atomically; notifies listeners on change."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._listeners: list = []
        self.settings = self._load()

    def _load(self) -> Settings:
        if self.path.exists():
            try:
                return Settings.model_validate(json.loads(self.path.read_text("utf8")))
            except Exception:
                logger.exception("settings.json is invalid, falling back to defaults")
                backup = self.path.with_suffix(".invalid.json")
                self.path.replace(backup)
        settings = Settings()
        # optional first-start seeding from the environment
        if proxy := os.environ.get("DROPPER_PROXY") or os.environ.get("PURPLERAIN_PROXY"):
            settings.proxy = proxy
        self._write(settings)
        return settings

    def _write(self, settings: Settings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(settings.model_dump_json(indent=2), "utf8")
        tmp.replace(self.path)

    def on_change(self, callback) -> None:
        self._listeners.append(callback)

    def update(self, data: dict) -> Settings:
        with self._lock:
            merged = self.settings.model_dump()
            merged.update(data)
            new = Settings.model_validate(merged)
            self._write(new)
            old, self.settings = self.settings, new
        for callback in self._listeners:
            try:
                callback(old, new)
            except Exception:
                logger.exception("settings listener failed")
        return new
