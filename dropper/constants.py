"""Twitch endpoints, client identity and persisted GQL operations.

The persisted query hashes are the ones the official clients use. Twitch rotates them from
time to time; every hash can be overridden from the web UI (Einstellungen -> Erweitert)
without rebuilding the container.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

JsonType = dict[str, Any]

# Android TV ("Smart Box") identity: this client is allowed to use the device code login
# flow (the Android phone app id answers "invalid client") and needs no integrity token.
CLIENT_ID = "ue6666qo983tsx6so1t0vnawi233wa"
CLIENT_URL = "https://android.tv.twitch.tv"
USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 7.1; Smart Box C1) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"
)
# scopes requested by the TV app during device login
DEVICE_SCOPES = "channel_read chat:read user_blocks_edit user_blocks_read user_follows_edit user_read"
# desktop browser identity, only used to load channel pages (spade URL lookup)
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"
)

GQL_URL = "https://gql.twitch.tv/gql"
DEVICE_URL = "https://id.twitch.tv/oauth2/device"
TOKEN_URL = "https://id.twitch.tv/oauth2/token"
VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"
USHER_URL = "https://usher.ttvnw.net/api/channel/hls/{login}.m3u8"
PUBSUB_URL = "wss://pubsub-edge.twitch.tv/v1"
# used when the spade URL can not be scraped from the channel page
SPADE_FALLBACK_URL = "https://spade.twitch.tv/track"

# games that let you earn drops on any channel, regardless of the category streamed
SPECIAL_GAME_IDS = {509663, 509672}

# Drops can still be claimed up to 24h after the campaign ended
CLAIM_GRACE_HOURS = 24


@dataclass
class GQLOperation:
    name: str
    sha256: str
    variables: JsonType = field(default_factory=dict)
    # other known hashes for the same operation (other client builds); tried automatically
    # when Twitch answers PersistedQueryNotFound
    fallbacks: tuple[str, ...] = ()

    @property
    def hashes(self) -> tuple[str, ...]:
        return (self.sha256, *self.fallbacks)

    def build(self, variables: JsonType | None = None, sha256: str | None = None) -> JsonType:
        merged = copy.deepcopy(self.variables)
        if variables:
            _merge(merged, variables)
        return {
            "operationName": self.name,
            "extensions": {
                "persistedQuery": {"version": 1, "sha256Hash": sha256 or self.sha256}
            },
            "variables": merged,
        }


def _merge(base: JsonType, extra: JsonType) -> None:
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value


GQL_OPERATIONS: dict[str, GQLOperation] = {
    "GetStreamInfo": GQLOperation(
        "VideoPlayerStreamInfoOverlayChannel",
        "198492e0857f6aedead9665c81c5a06d67b25b58034649687124083ff288597d",
        {"channel": ""},
        ("e785b65ff71ad7b363b34878335f27dd9372869ad0c5740a130b9268bcdbe7e7",),
    ),
    "ClaimDrop": GQLOperation(
        "DropsPage_ClaimDropRewards",
        "a455deea71bdc9015b78eb49f4acfbce8baa7ccbedd28e549bb025bd0f751930",
        {"input": {"dropInstanceID": ""}},
    ),
    "ChannelPointsContext": GQLOperation(
        "ChannelPointsContext",
        "374314de591e69925fce3ddc2bcf085796f56ebb8cad67a0daa3165c03adc345",
        {"channelLogin": ""},
    ),
    "ClaimCommunityPoints": GQLOperation(
        "ClaimCommunityPoints",
        "46aaeebe02c99afdf4fc97c7c0cba964124bf6b0af229395f1f6d1feed05b3d0",
        {"input": {"claimID": "", "channelID": ""}},
    ),
    "Inventory": GQLOperation(
        "Inventory",
        "8337eb8541b314040b0edde0c09c5c7a2783ba1960aa9edfbf3bac16d0fec404",
        {"fetchRewardCampaigns": False},
        ("d86775d0ef16a63a33ad52e80eaff963b2d5b72fada7c991504a57496e1d8e4b",),
    ),
    "CurrentDrop": GQLOperation(
        "DropCurrentSessionContext",
        "4d06b702d25d652afb9ef835d2a550031f1cf762b193523a92166f40ea3d142b",
        {"channelID": "", "channelLogin": ""},
    ),
    "Campaigns": GQLOperation(
        "ViewerDropsDashboard",
        "c16bb890cc8ce7647a96ee69cd313d423a378a3dedadf630a1017cde18975feb",
        {"fetchRewardCampaigns": False},
        ("5a4da2ab3d5b47c9f9ce864e727b2cb346af1e3ea8b897fe8f704a97ff017619",),
    ),
    "CampaignDetails": GQLOperation(
        "DropCampaignDetails",
        "039277bf98f3130929262cc7c6efd9c141ca3749cb6dca442fc8ead9a53f77c1",
        {"channelLogin": "", "dropID": ""},
        ("f6396f5ffdde867a8f6f6da18286e4baf02e5b98d14689a69b5af320a4c7b7b8",),
    ),
    "AvailableDrops": GQLOperation(
        "DropsHighlightService_AvailableDrops",
        "782dad0f032942260171d2d80a654f88bdd0c5a9dddc392e9bc92218a0f42d20",
        {"channelID": ""},
    ),
    "GameDirectory": GQLOperation(
        "DirectoryPage_Game",
        "86bcceb4e8b1a51256ff8eed8bd8aae4acacf80d737efe904f84f3aeadf8cafd",
        {
            "limit": 30,
            "slug": "",
            "imageWidth": 50,
            "includeCostreaming": False,
            "options": {
                "broadcasterLanguages": [],
                "freeformTags": None,
                "includeRestricted": ["SUB_ONLY_LIVE"],
                "recommendationsContext": {"platform": "web"},
                "sort": "VIEWER_COUNT",
                "systemFilters": [],
                "tags": [],
                "requestID": "JIRA-VXP-2397",
            },
            "sortTypeIsRecency": False,
        },
    ),
    # stream access token; since 2026-10-07 Twitch only counts watch time for clients that fetch the HLS segments
    "PlaybackAccessToken": GQLOperation(
        "PlaybackAccessToken",
        "ed230aa1e33e07eebb8928504583da78a5173989fadfb1ac94be06a04f3cdbe9",
        {"isLive": True, "isVod": False, "login": "", "platform": "web", "playerType": "site", "vodID": ""},
    ),
    # game name -> slug, what twitch.tv/directory/game/<name> uses; checks names typed into the priority list
    "SlugRedirect": GQLOperation(
        "DirectoryGameRedirect",
        "1f0300090caceec51f33c5e20647aceff9017f740f223c3c532ba6fa59f6b6cc",
        {"name": ""},
    ),
}

PUBSUB_TOPICS = {
    "user_drops": "user-drop-events",
    "user_notifications": "onsite-notifications",
    "user_points": "community-points-user-v1",
    "stream_state": "video-playback-by-id",
}
