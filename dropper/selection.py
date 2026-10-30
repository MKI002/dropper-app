"""Pure decision logic: which campaigns are wanted and which channel to watch.

Kept free of I/O so it can be unit tested.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from .models import Campaign, Channel, norm_game, utcnow
from .settings import GameMode, PriorityMode, Settings


def on_priority_list(campaign: Campaign, settings: Settings) -> bool:
    """Games on the priority list are watched: a new campaign for them is announced right away."""
    return norm_game(campaign.game.name) in {norm_game(g) for g in settings.games_priority}


def campaign_eligible(campaign: Campaign, settings: Settings) -> bool:
    """Can the reward actually reach the account?"""
    if campaign.linked or not settings.require_linked_account:
        return True
    # badges and emotes land on the Twitch account itself, no game link needed
    return settings.mine_badges_emotes and campaign.has_badge_or_emote


SKIP_REASONS = {
    "disabled": "campaign switched off",
    "game_excluded": "game excluded",
    "not_whitelisted": "game not on the whitelist",
    "not_prioritized": "game not on the priority list",
    "badges_off": "only badges/emotes, which are switched off",
    "not_linked": "game account not linked",
    "upcoming": "starts later",
    "expired": "ended",
    "finished": "all drops claimed",
    "not_watchable": "the drops left are not earned by watching",
    "unavailable": "no drop available right now (precondition or time window)",
}


def skip_reason(campaign: Campaign, settings: Settings, now: datetime | None = None) -> str | None:
    """Returns why a campaign is not mined as a code from SKIP_REASONS, or None if it is wanted.

    The web UI translates the code; SKIP_REASONS holds the English text for logs and the API docs.
    """
    game = norm_game(campaign.game.name)
    if campaign.id in settings.campaigns_exclude:
        return "disabled"
    if game in {norm_game(g) for g in settings.games_exclude}:
        return "game_excluded"
    if settings.game_mode is GameMode.WHITELIST and game not in {norm_game(g) for g in settings.games_whitelist}:
        return "not_whitelisted"
    if settings.priority_mode is PriorityMode.PRIORITY_ONLY and game not in {norm_game(g) for g in settings.games_priority}:
        return "not_prioritized"
    if not settings.mine_badges_emotes and campaign.only_badges_emotes:
        return "badges_off"
    if not campaign_eligible(campaign, settings):
        return "not_linked"
    if campaign.upcoming:
        return "upcoming"
    if not campaign.active:
        return "expired"
    if campaign.finished:
        return "finished" if all(d.is_claimed for d in campaign.drops.values()) else "not_watchable"
    if not campaign.can_earn(now):
        return "unavailable"
    return None


def wanted_campaigns(campaigns: Iterable[Campaign], settings: Settings, now: datetime | None = None) -> list[Campaign]:
    now = now or utcnow()
    wanted = [c for c in campaigns if skip_reason(c, settings, now) is None]
    priority = [norm_game(g) for g in settings.games_priority]

    def prio(c: Campaign) -> int:
        name = norm_game(c.game.name)
        return priority.index(name) if name in priority else len(priority)

    if settings.priority_mode is PriorityMode.LOW_AVAILABILITY:
        wanted.sort(key=lambda c: c.availability)
    else:
        wanted.sort(key=lambda c: c.ends_at)
    wanted.sort(key=prio)  # stable: priority list first, mode decides within
    return wanted


def channel_serves(channel: Channel, campaign: Campaign, verified: bool) -> bool:
    """Does watching this channel progress the campaign?"""
    if not channel.online:
        return False
    if not campaign.channel_allowed(channel.id):
        return False
    if not campaign.game.special and (channel.game is None or channel.game.id != campaign.game.id):
        return False
    if verified and channel.campaign_ids is not None:
        return campaign.id in channel.campaign_ids
    return channel.drops_enabled or bool(campaign.allowed_channels)


def rank_channel(channel: Channel, settings: Settings) -> tuple:
    preferred = channel.login in settings.channels_preferred
    return (
        0 if preferred else 1,
        0 if channel.source == "acl" else 1,
        -channel.viewers,
    )


def pick_channel(
    wanted: list[Campaign],
    channels: Iterable[Channel],
    settings: Settings,
    *,
    current: Channel | None = None,
    cooldown: set[str] | frozenset = frozenset(),
) -> tuple[Campaign | None, Channel | None]:
    pool = [
        ch for ch in channels
        if ch.online and ch.login not in settings.channels_blacklist and ch.id not in cooldown
    ]
    verified = settings.verify_channel_drops
    for campaign in wanted:
        candidates = [ch for ch in pool if channel_serves(ch, campaign, verified)]
        if not candidates:
            continue
        # stay on the current channel when it serves the best campaign: no needless switching
        if current is not None and any(ch.id == current.id for ch in candidates):
            return campaign, next(ch for ch in candidates if ch.id == current.id)
        candidates.sort(key=lambda ch: rank_channel(ch, settings))
        return campaign, candidates[0]
    return None, None
