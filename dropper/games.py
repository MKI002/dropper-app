"""Games by name: the ones seen in campaigns and channels, and lookups on Twitch.

The priority list holds game names, also of games that have no drop campaign right now: Dropper
farms them as soon as one starts. A name typed there is looked up on Twitch to check the spelling and
to learn the game's box art and directory slug. The slug finds the drops-enabled streams of a new
campaign before the public catalog lists it.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .models import Game, norm_game, slugify
from .twitch import GQLError, TwitchError

logger = logging.getLogger("dropper.games")
JsonType = dict[str, Any]

MISS_TTL = 900  # seconds before a name Twitch did not know is asked for again
# box art by game id; the web UI and the notifier add the size
BOX_ART = "https://static-cdn.jtvnw.net/ttv-boxart/{id}_IGDB.jpg"


def _directory_game(response: Any, slug: str, fallback_name: str) -> Game | None:
    """The game in a DirectoryPage_Game answer, None when Twitch has no game with that slug."""
    data = (response.get("data") or {}).get("game") if isinstance(response, dict) else None
    if not isinstance(data, dict) or not data.get("id"):
        return None
    # a live stream carries the game's display name and box art when the game itself does not
    stream_game: JsonType = {}
    for edge in (data.get("streams") or {}).get("edges") or []:
        node = edge.get("node") if isinstance(edge, dict) else None
        if isinstance(node, dict) and isinstance(node.get("game"), dict):
            stream_game = node["game"]
            break
    return Game.from_gql({
        "id": data["id"],
        "displayName": (data.get("displayName") or stream_game.get("displayName") or data.get("name")
                        or stream_game.get("name") or fallback_name),
        "slug": data.get("slug") or stream_game.get("slug") or slug,
        "boxArtURL": data.get("boxArtURL") or stream_game.get("boxArtURL") or BOX_ART.format(id=data["id"]),
    })


class GameIndex:
    """Remembers games under their compared name (see norm_game) and looks names up on Twitch."""

    def __init__(self, client: Any):
        self.client = client
        self._games: dict[str, Game] = {}
        self._misses: dict[str, float] = {}

    def remember(self, game: Game | None) -> None:
        if game is None:
            return
        key = norm_game(game.name)
        known = self._games.get(key)
        # campaigns and lookups carry box art, channels often do not: keep the richer entry
        if known is None or (game.box_art and not known.box_art):
            self._games[key] = game
        self._misses.pop(key, None)

    def get(self, name: str) -> Game | None:
        return self._games.get(norm_game(name))

    def known(self) -> list[Game]:
        return list(self._games.values())

    async def lookup(self, name: str) -> Game | None:
        """The Twitch game with this name (case, accents and punctuation do not matter), None when
        Twitch has none. Raises TwitchError when Twitch could not be asked."""
        name = " ".join(name.split())
        key = norm_game(name)
        if not key:
            return None
        if key in self._games:
            return self._games[key]
        missed = self._misses.get(key)
        if missed is not None and time.monotonic() - missed < MISS_TTL:
            return None
        game = await self._ask_twitch(name)
        if game is None:
            self._misses[key] = time.monotonic()
            return None
        self.remember(game)
        self._games.setdefault(key, game)  # also under the typed name, if Twitch spells it differently
        return game

    async def _ask_twitch(self, name: str) -> Game | None:
        # 1. Twitch's own name -> slug lookup
        redirect: JsonType = {}
        redirect_failed = False
        try:
            response = await self.client.gql(self.client.operation("SlugRedirect", {"name": name}))
            redirect = ((response.get("data") or {}).get("game") or {}) if isinstance(response, dict) else {}
        except GQLError as exc:
            redirect_failed = True
            logger.debug("Game slug lookup for %r failed: %s", name, exc)
        # 2. the game directory under that slug, or the slug Twitch most likely uses for the name
        slug = redirect.get("slug") or slugify(name)
        shown = redirect.get("displayName") or redirect.get("name") or name
        game = None
        directory_failed: GQLError | None = None
        if slug:
            try:
                response = await self.client.gql(self.client.operation("GameDirectory", {
                    "slug": slug, "limit": 1, "options": {"systemFilters": [], "broadcasterLanguages": []},
                }))
                game = _directory_game(response, slug, shown)
            except GQLError as exc:
                directory_failed = exc
        if game is None and redirect.get("id"):
            # Twitch knows the name, the directory did not answer: what the redirect said is enough
            game = Game.from_gql({
                "id": redirect["id"], "displayName": shown, "slug": redirect.get("slug") or slug,
                "boxArtURL": redirect.get("boxArtURL") or BOX_ART.format(id=redirect["id"]),
            })
        if game is not None:
            return game
        if directory_failed is not None:
            raise directory_failed
        if redirect_failed:
            # a guessed slug that finds nothing does not prove that the game does not exist
            raise TwitchError(f"could not look up {name!r}")
        return None
