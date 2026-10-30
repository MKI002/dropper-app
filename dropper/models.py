"""Data model for drop campaigns, drops and channels, parsed from Twitch GQL responses."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .constants import CLAIM_GRACE_HOURS, SPECIAL_GAME_IDS

JsonType = dict[str, Any]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(value: str | None) -> datetime:
    if not value:
        return datetime.max.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fold_accents(text: str) -> str:
    """"Pokémon" -> "Pokemon"."""
    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


def slugify(name: str) -> str:
    """The directory slug Twitch most likely uses for a game name ("Tom Clancy's The Division 2" ->
    "tom-clancys-the-division-2")."""
    slug = re.sub(r"['’]", "", fold_accents(name).lower())
    slug = re.sub(r"\W+", "-", slug)
    return re.sub(r"-{2,}", "-", slug.strip("-"))


def norm_game(name: str) -> str:
    """The form game names are compared in. Case, accents, spaces and punctuation do not count, so a
    typed "counter strike" matches Twitch's "Counter-Strike" and "pokemon go" matches "Pokémon GO"."""
    text = fold_accents(str(name or "")).casefold()
    return re.sub(r"[\W_]+", "", text) or text.strip()


@dataclass(frozen=True)
class Game:
    id: int
    name: str
    slug: str
    box_art: str = ""

    @classmethod
    def from_gql(cls, data: JsonType) -> Game:
        name = data.get("displayName") or data.get("name") or "?"
        return cls(
            id=int(data["id"]),
            name=name,
            slug=data.get("slug") or slugify(name),
            box_art=re.sub(r"-\{width\}x\{height\}|-\d+x\d+(?=\.\w+$)", "", data.get("boxArtURL") or ""),
        )

    @property
    def special(self) -> bool:
        return self.id in SPECIAL_GAME_IDS

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Game) and other.id == self.id

    def __hash__(self) -> int:
        return self.id


@dataclass
class Benefit:
    id: str
    name: str
    type: str
    image: str

    @classmethod
    def from_gql(cls, edge: JsonType) -> Benefit:
        data = edge["benefit"]
        return cls(
            id=data["id"],
            name=data.get("name") or "?",
            type=data.get("distributionType") or "UNKNOWN",
            image=data.get("imageAssetURL") or "",
        )

    @property
    def is_badge_or_emote(self) -> bool:
        return self.type in ("BADGE", "EMOTE")


@dataclass
class Drop:
    id: str
    name: str
    campaign: Campaign = field(repr=False)
    benefits: list[Benefit]
    starts_at: datetime
    ends_at: datetime
    required_minutes: int
    current_minutes: int = 0
    claim_id: str | None = None
    is_claimed: bool = False
    precondition_ids: list[str] = field(default_factory=list)
    # bookkeeping of our own claim attempts (kept across refreshes by the miner)
    claim_attempts: int = 0
    claim_error: str = ""
    claim_retry_at: datetime | None = None

    @classmethod
    def from_gql(cls, campaign: Campaign, data: JsonType, claimed_benefits: dict[str, datetime]) -> Drop:
        drop = cls(
            id=data["id"],
            name=data.get("name") or "",
            campaign=campaign,
            benefits=[Benefit.from_gql(b) for b in (data.get("benefitEdges") or [])],
            starts_at=parse_ts(data.get("startAt")),
            ends_at=parse_ts(data.get("endAt")),
            required_minutes=int(data.get("requiredMinutesWatched") or 0),
            precondition_ids=[d["id"] for d in (data.get("preconditionDrops") or [])],
        )
        self_edge = data.get("self")
        if self_edge:
            drop.claim_id = self_edge.get("dropInstanceID")
            drop.is_claimed = bool(self_edge.get("isClaimed"))
            drop.current_minutes = int(self_edge.get("currentMinutesWatched") or 0)
        else:
            # Without a self edge we infer the claim from the inventory's awarded benefits:
            # if every benefit was awarded while this drop was running, it was claimed.
            stamps = [claimed_benefits[b.id] for b in drop.benefits if b.id in claimed_benefits]
            if stamps and all(drop.starts_at <= s < drop.ends_at for s in stamps):
                drop.is_claimed = True
        if drop.is_claimed:
            drop.current_minutes = drop.required_minutes
        return drop

    @property
    def rewards(self) -> str:
        return ", ".join(b.name for b in self.benefits) or self.name

    @property
    def preconditions_met(self) -> bool:
        drops = self.campaign.drops
        return all(drops[pid].is_claimed for pid in self.precondition_ids if pid in drops)

    @property
    def remaining_minutes(self) -> int:
        return max(self.required_minutes - self.current_minutes, 0)

    @property
    def total_remaining_minutes(self) -> int:
        drops = self.campaign.drops
        return self.remaining_minutes + max(
            (drops[p].total_remaining_minutes for p in self.precondition_ids if p in drops), default=0
        )

    @property
    def progress(self) -> float:
        if self.required_minutes <= 0:
            return 1.0 if self.is_claimed else 0.0
        return min(self.current_minutes / self.required_minutes, 1.0)

    @property
    def is_complete(self) -> bool:
        return self.required_minutes > 0 and self.current_minutes >= self.required_minutes

    def can_earn(self, now: datetime | None = None) -> bool:
        now = now or utcnow()
        return (
            not self.is_claimed
            and self.required_minutes > 0
            and not self.is_complete  # watch time done: needs a claim, not more watching
            and self.preconditions_met
            and (bool(self.benefits) or self.id in self.campaign.precondition_chain)
            and self.starts_at <= now < self.ends_at
        )

    def claimable(self, now: datetime | None = None) -> bool:
        """Watch time is done but the reward has not been claimed yet."""
        now = now or utcnow()
        return (
            not self.is_claimed
            and self.is_complete
            and self.preconditions_met
            and now < self.campaign.ends_at + timedelta(hours=CLAIM_GRACE_HOURS)
        )

    @property
    def needs_link(self) -> bool:
        """The reward is an in-game item and the game account is not linked."""
        campaign = self.campaign
        return not campaign.linked and bool(campaign.link_url) and any(
            not b.is_badge_or_emote for b in self.benefits
        )

    def status(self, now: datetime | None = None) -> str:
        """One word for the UI: claimed, ready, failed, missed, progress, pending, locked, upcoming,
        expired or other (not a watch-time drop, e.g. gifted subs)."""
        now = now or utcnow()
        campaign = self.campaign
        if self.is_claimed:
            return "claimed"
        if self.required_minutes <= 0:
            return "other"
        if self.is_complete:
            if now >= campaign.ends_at + timedelta(hours=CLAIM_GRACE_HOURS):
                return "missed"
            if not self.preconditions_met:
                return "locked"
            return "failed" if self.claim_error else "ready"
        if now >= min(self.ends_at, campaign.ends_at):
            return "expired"
        if now < max(self.starts_at, campaign.starts_at):
            return "upcoming"
        if not self.preconditions_met:
            return "locked"
        return "progress" if self.current_minutes > 0 else "pending"

    def to_dict(self) -> JsonType:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status(),
            "claim_error": self.claim_error,
            "claim_attempts": self.claim_attempts,
            "claim_retry_at": self.claim_retry_at.isoformat() if self.claim_retry_at else None,
            "needs_link": self.needs_link,
            "rewards": self.rewards,
            "benefits": [b.__dict__ for b in self.benefits],
            "starts_at": self.starts_at.isoformat(),
            "ends_at": self.ends_at.isoformat(),
            "required_minutes": self.required_minutes,
            "current_minutes": self.current_minutes,
            "progress": round(self.progress, 4),
            "is_claimed": self.is_claimed,
            "claimable": self.claimable(),
            "can_earn": self.can_earn(),
        }


@dataclass
class Campaign:
    id: str
    name: str
    game: Game
    status: str
    starts_at: datetime
    ends_at: datetime
    linked: bool
    link_url: str
    image: str
    allowed_channels: dict[str, str] = field(default_factory=dict)  # channel id -> login
    drops: dict[str, Drop] = field(default_factory=dict)
    # False when Twitch did not tell the link status and it was assumed (see Miner._guess_links)
    link_known: bool = True

    @classmethod
    def from_gql(cls, data: JsonType, claimed_benefits: dict[str, datetime] | None = None) -> Campaign:
        claimed_benefits = claimed_benefits or {}
        allow = data.get("allow") or {}
        channels = allow.get("channels") if allow.get("isEnabled", True) else None
        self_edge = data.get("self") or {}
        campaign = cls(
            id=data["id"],
            name=data.get("name") or "",
            game=Game.from_gql(data["game"]),
            status=data.get("status") or "ACTIVE",
            starts_at=parse_ts(data.get("startAt")),
            ends_at=parse_ts(data.get("endAt")),
            linked=bool(self_edge.get("isAccountConnected")),
            link_url=data.get("accountLinkURL") or "",
            image=data.get("imageURL") or "",
            allowed_channels={str(c["id"]): (c.get("name") or c.get("login") or "").lower() for c in (channels or [])},
            link_known=not data.get("linkGuessed"),
        )
        for drop_data in data.get("timeBasedDrops") or []:
            drop = Drop.from_gql(campaign, drop_data, claimed_benefits)
            campaign.drops[drop.id] = drop
        return campaign

    @property
    def precondition_chain(self) -> set[str]:
        return {p for d in self.drops.values() if not d.is_claimed for p in d.precondition_ids}

    @property
    def active(self) -> bool:
        return self.status != "EXPIRED" and self.starts_at <= utcnow() < self.ends_at

    @property
    def upcoming(self) -> bool:
        return self.status != "EXPIRED" and utcnow() < self.starts_at

    @property
    def has_badge_or_emote(self) -> bool:
        return any(b.is_badge_or_emote for d in self.drops.values() for b in d.benefits)

    @property
    def only_badges_emotes(self) -> bool:
        benefits = [b for d in self.drops.values() for b in d.benefits]
        return bool(benefits) and all(b.is_badge_or_emote for b in benefits)

    @property
    def reward_types(self) -> set[str]:
        return {b.type for d in self.drops.values() for b in d.benefits}

    @property
    def finished(self) -> bool:
        # no drops means Twitch sent no details for it, which says nothing about being done
        return bool(self.drops) and all(d.is_claimed or d.required_minutes <= 0 for d in self.drops.values())

    @property
    def claimed_count(self) -> int:
        return sum(d.is_claimed for d in self.drops.values())

    @property
    def remaining_minutes(self) -> int:
        return max((d.total_remaining_minutes for d in self.drops.values() if not d.is_claimed), default=0)

    @property
    def availability(self) -> float:
        """Minutes left in the campaign divided by minutes still to watch. Lower = more urgent."""
        remaining = self.remaining_minutes
        if remaining <= 0:
            return math.inf
        return ((self.ends_at - utcnow()).total_seconds() / 60) / remaining

    def can_earn(self, now: datetime | None = None) -> bool:
        return self.active and any(d.can_earn(now) for d in self.drops.values())

    def channel_allowed(self, channel_id: str) -> bool:
        return not self.allowed_channels or str(channel_id) in self.allowed_channels

    def next_drop(self) -> Drop | None:
        drops = sorted((d for d in self.drops.values() if d.can_earn()), key=lambda d: d.remaining_minutes)
        return drops[0] if drops else None

    def to_dict(self) -> JsonType:
        return {
            "id": self.id,
            "name": self.name,
            "game": {"id": self.game.id, "name": self.game.name, "slug": self.game.slug, "box_art": self.game.box_art},
            "status": "active" if self.active else "upcoming" if self.upcoming else "expired",
            "starts_at": self.starts_at.isoformat(),
            "ends_at": self.ends_at.isoformat(),
            "linked": self.linked,
            "link_known": self.link_known,
            "link_url": self.link_url,
            "image": self.image,
            "acl_channels": len(self.allowed_channels),
            "reward_types": sorted(self.reward_types),
            "finished": self.finished,
            "claimed": self.claimed_count,
            "total": len(self.drops),
            "remaining_minutes": self.remaining_minutes,
            "drops": [d.to_dict() for d in sorted(self.drops.values(), key=lambda d: d.required_minutes)],
        }


@dataclass
class Channel:
    id: str
    login: str
    display_name: str
    online: bool = False
    game: Game | None = None
    viewers: int = 0
    title: str = ""
    broadcast_id: str = ""
    drops_enabled: bool = False
    # campaign ids Twitch says this channel currently offers (None = not checked)
    campaign_ids: set[str] | None = None
    campaign_names: dict[str, str] = field(default_factory=dict)
    source: str = "directory"  # directory | acl | preferred
    last_checked: datetime | None = None

    @property
    def name(self) -> str:
        return self.display_name or self.login

    def to_dict(self) -> JsonType:
        return {
            "id": self.id,
            "login": self.login,
            "name": self.name,
            "online": self.online,
            "game": self.game.name if self.game else None,
            "viewers": self.viewers,
            "title": self.title,
            "drops_enabled": self.drops_enabled,
            "campaign_ids": sorted(self.campaign_ids or []),
            "source": self.source,
            "url": f"https://www.twitch.tv/{self.login}",
        }
