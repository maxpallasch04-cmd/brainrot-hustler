"""Minimal Twitch Helix client (stdlib only, no extra dependencies).

Auth uses an app access token (client_credentials grant), so no user login is
needed. Credentials come from the environment:

    TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET

See README for how to create them.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
API = "https://api.twitch.tv/helix"


def _http_json(url, *, method="GET", headers=None, params=None, data=None, timeout=15):
    """Tiny JSON-over-HTTP helper. Raises RuntimeError with the API body on error."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    headers = dict(headers or {})
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"Twitch {exc.code} for {url}: {detail}") from exc


class Helix:
    """Thin wrapper over the read-only Helix endpoints we need."""

    def __init__(self, client_id=None, client_secret=None, timeout=15):
        self.client_id = client_id or os.environ.get("TWITCH_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("TWITCH_CLIENT_SECRET")
        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "Missing credentials: set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET "
                "(create a Twitch app, see README)."
            )
        self.timeout = timeout
        self._token = None
        self._token_exp = 0.0

    # ---- auth -----------------------------------------------------------

    def token(self) -> str:
        """Return a cached app access token, refreshing it when needed."""
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        resp = _http_json(TOKEN_URL, method="POST", timeout=self.timeout, data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
        })
        self._token = resp["access_token"]
        self._token_exp = time.time() + float(resp.get("expires_in", 0))
        return self._token

    def _get(self, path, params=None):
        url = f"{API}{path}"
        headers = {"Client-Id": self.client_id, "Authorization": f"Bearer {self.token()}"}
        try:
            return _http_json(url, headers=headers, params=params, timeout=self.timeout)
        except RuntimeError:
            self._token = None  # token may have expired -> one retry with a fresh one
            headers["Authorization"] = f"Bearer {self.token()}"
            return _http_json(url, headers=headers, params=params, timeout=self.timeout)

    # ---- lookups --------------------------------------------------------

    def get_game_id(self, name: str) -> str:
        """Category / game name -> game_id."""
        data = self._get("/games", {"name": name}).get("data", [])
        if not data:
            raise ValueError(f"no Twitch category named {name!r}")
        return data[0]["id"]

    def get_user_id(self, login: str) -> str:
        """Broadcaster login name -> user id."""
        data = self._get("/users", {"login": login}).get("data", [])
        if not data:
            raise ValueError(f"no Twitch user named {login!r}")
        return data[0]["id"]

    # ---- clips ----------------------------------------------------------

    def iter_clips(self, *, game_id=None, broadcaster_id=None, started_at=None,
                   ended_at=None, first=100, max_pages=5):
        """Yield clips, paging through the cursor. Helix returns them most-viewed first."""
        after = None
        for _ in range(int(max_pages)):
            params = {"first": min(int(first), 100)}
            if game_id:
                params["game_id"] = game_id
            if broadcaster_id:
                params["broadcaster_id"] = broadcaster_id
            if started_at:
                params["started_at"] = started_at
            if ended_at:
                params["ended_at"] = ended_at
            if after:
                params["after"] = after
            page = self._get("/clips", params)
            for clip in page.get("data", []):
                yield clip
            after = page.get("pagination", {}).get("cursor")
            if not after:
                break
