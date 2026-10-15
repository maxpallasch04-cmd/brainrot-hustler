"""Turn raw Helix clips into a ranked shortlist of 'viral' candidates.

Helix returns clips most-viewed first, but there is no full-text search: you
scope by category (game_id) or broadcaster, then rank client-side. Here we
rank by view_count ('proven') or views_per_hour ('newly viral').
"""

from __future__ import annotations

import calendar
import time


def _parse_iso(value: str) -> int:
    """Twitch '2020-08-10T17:04:10Z' -> unix seconds (UTC)."""
    return calendar.timegm(time.strptime(value.replace("Z", ""), "%Y-%m-%dT%H:%M:%S"))


def _iso(ts: float) -> str:
    """unix seconds -> Twitch-style UTC timestamp."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def decorate(clip: dict, now: float | None = None) -> dict:
    """Add age_hours and views_per_hour to a raw clip."""
    now = time.time() if now is None else now
    age_h = max((now - _parse_iso(clip["created_at"])) / 3600.0, 1 / 60)
    views = int(clip.get("view_count", 0))
    return {
        "id": clip["id"],
        "url": clip.get("url"),
        "title": clip.get("title", ""),
        "view_count": views,
        "duration": float(clip.get("duration", 0)),
        "language": clip.get("language"),
        "broadcaster_name": clip.get("broadcaster_name"),
        "game_id": clip.get("game_id"),
        "created_at": clip.get("created_at"),
        "age_hours": round(age_h, 2),
        "views_per_hour": round(views / age_h, 1),
    }


def find_clips(client, *, game=None, game_id=None, hours=24, min_views=0,
               max_duration=None, language=None, top=10, sort="views",
               max_pages=5, now=None, exclude_ids=()) -> list[dict]:
    """Return up to `top` ranked clips for a category within the last `hours`.

    client: a Helix instance (or anything with get_game_id + iter_clips).
    sort:   'views' (proven) or 'velocity' (views_per_hour).
    """
    now = time.time() if now is None else now
    if game_id is None:
        if not game:
            raise ValueError("need `game` or `game_id`")
        game_id = client.get_game_id(game)

    raw = client.iter_clips(game_id=game_id, started_at=_iso(now - hours * 3600),
                            max_pages=max_pages)

    exclude = set(exclude_ids)
    seen: set[str] = set()
    out: list[dict] = []
    for clip in raw:
        if clip["id"] in exclude or clip["id"] in seen:
            continue
        seen.add(clip["id"])
        if int(clip.get("view_count", 0)) < min_views:
            continue
        if max_duration is not None and float(clip.get("duration", 0)) > max_duration:
            continue
        if language and clip.get("language") != language:
            continue
        out.append(decorate(clip, now))

    key = "views_per_hour" if sort == "velocity" else "view_count"
    out.sort(key=lambda c: c[key], reverse=True)
    return out[:top]
