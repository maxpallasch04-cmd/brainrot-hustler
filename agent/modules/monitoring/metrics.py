"""TikTok Display API client (official, no scraping).

Reads the channel's own public videos and account stats. Requires a **user
access token** with the `video.list` scope, from the environment:

    TIKTOK_ACCESS_TOKEN

See README for how to obtain it (TikTok Developer App + OAuth). Timestamps are
Unix seconds.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

API = "https://open.tiktokapis.com/v2"

VIDEO_FIELDS = ("id,title,video_description,duration,create_time,view_count,"
                "like_count,comment_count,share_count,is_aigc,share_url")
USER_FIELDS = "follower_count,likes_count,video_count"

MAX_PAGE = 20  # Display API caps /video/list at 20 per page


def _request(url, *, method="GET", headers=None, body=None, timeout=15) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=dict(headers or {}),
                                 method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"TikTok {exc.code}: "
                           f"{exc.read().decode('utf-8', 'replace')}") from exc
    error = payload.get("error") or {}
    if error.get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok error {error.get('code')}: {error.get('message')}")
    return payload


class TikTokMetrics:
    """Thin read-only wrapper over the Display API endpoints we need."""

    def __init__(self, access_token=None, timeout=15, token_provider=None) -> None:
        """access_token: static token. token_provider: callable returning a
        fresh token (e.g. from TikTokAuth.access_token, which auto-refreshes)."""
        self.token = access_token or os.environ.get("TIKTOK_ACCESS_TOKEN")
        self._provider = token_provider
        if not self.token and token_provider is None:
            raise RuntimeError(
                "Missing TIKTOK_ACCESS_TOKEN (create a TikTok Developer App and "
                "complete OAuth; see README)."
            )
        self.timeout = timeout

    def _auth_token(self) -> str:
        return self._provider() if self._provider is not None else self.token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._auth_token()}",
                "Content-Type": "application/json"}

    def list_videos(self, max_count: int = MAX_PAGE, cursor: str | None = None):
        """One page of own public videos -> (videos, cursor, has_more)."""
        body = {"max_count": min(int(max_count), MAX_PAGE)}
        if cursor:
            body["cursor"] = cursor
        resp = _request(f"{API}/video/list/?fields={VIDEO_FIELDS}", method="POST",
                        headers=self._headers(), body=body, timeout=self.timeout)
        data = resp.get("data", {})
        return data.get("videos", []), data.get("cursor"), bool(data.get("has_more"))

    def list_recent(self, n: int = 50) -> list[dict]:
        """Page through the cursor up to `n` videos (no unbounded auto-loop)."""
        videos: list[dict] = []
        cursor = None
        while len(videos) < n:
            page, cursor, has_more = self.list_videos(MAX_PAGE, cursor)
            videos.extend(page)
            if not cursor or not has_more:
                break
        return videos[:n]

    def user_stats(self) -> dict:
        """Account-level stats: follower_count, likes_count, video_count."""
        resp = _request(f"{API}/user/info/?fields={USER_FIELDS}",
                        headers=self._headers(), timeout=self.timeout)
        return resp.get("data", {}).get("user", {})
