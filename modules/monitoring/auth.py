"""TikTok OAuth (Login Kit) + token store/refresh.

The Display API needs a **user access token** (scope ``video.list``). This module
runs the interactive browser flow once, persists the tokens to a JSON file, and
then keeps the access token fresh automatically (access token ~24 h, refresh
token ~365 d).

App credentials come from the environment (set by the operator, not the agent):

    TIKTOK_CLIENT_KEY
    TIKTOK_CLIENT_SECRET

Mutable tokens live in a file (default: ``data/tiktok_token.json``), overridable
via ``TIKTOK_TOKEN_FILE``. All timestamps are Unix seconds.

Flow:
    auth = TikTokAuth()
    auth.login()                 # opens browser, captures ?code=, stores tokens
    token = auth.access_token()  # valid token, auto-refreshed when stale
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

AUTHORIZE = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN = "https://open.tiktokapis.com/v2/oauth/token/"
REVOKE = "https://open.tiktokapis.com/v2/oauth/revoke/"

DEFAULT_SCOPE = "user.info.basic,user.info.stats,video.list"
DEFAULT_REDIRECT = "http://localhost:8080/callback"
DEFAULT_TOKEN_FILE = Path(__file__).resolve().parent.parent / "data" / "tiktok_token.json"

# Refresh a little before the access token actually expires.
REFRESH_MARGIN = 300  # seconds


def _post_form(url: str, fields: dict, timeout: int = 15) -> dict:
    """POST application/x-www-form-urlencoded, return decoded JSON."""
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"TikTok OAuth {exc.code}: "
                           f"{exc.read().decode('utf-8', 'replace')}") from exc
    if "error" in payload:
        raise RuntimeError(f"TikTok OAuth error {payload['error']}: "
                           f"{payload.get('error_description')}")
    return payload


def _pkce_pair() -> tuple[str, str]:
    """(code_verifier, code_challenge) for PKCE S256. TikTok requires it."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def build_authorize_url(client_key: str, redirect_uri: str = DEFAULT_REDIRECT,
                        scope: str = DEFAULT_SCOPE, state: str | None = None,
                        code_challenge: str | None = None) -> str:
    """The URL the user opens to grant access."""
    params = {
        "client_key": client_key,
        "scope": scope,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state or secrets.token_urlsafe(16),
    }
    if code_challenge:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"
    return AUTHORIZE + "?" + urllib.parse.urlencode(params)


class TokenStore:
    """JSON file holding the current access/refresh tokens."""

    def __init__(self, path: str | os.PathLike | None = None) -> None:
        self.path = Path(path or os.environ.get("TIKTOK_TOKEN_FILE")
                         or DEFAULT_TOKEN_FILE)

    def load(self) -> dict | None:
        if not self.path.exists():
            return None
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)  # atomic
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


class TikTokAuth:
    """Interactive login + automatic refresh for the user access token."""

    def __init__(self, client_key: str | None = None, client_secret: str | None = None,
                 token_path: str | os.PathLike | None = None,
                 redirect_uri: str | None = None, scope: str | None = None) -> None:
        self.client_key = client_key or os.environ.get("TIKTOK_CLIENT_KEY")
        self.client_secret = client_secret or os.environ.get("TIKTOK_CLIENT_SECRET")
        self.redirect_uri = redirect_uri or os.environ.get("TIKTOK_REDIRECT_URI") \
            or DEFAULT_REDIRECT
        self.scope = scope or os.environ.get("TIKTOK_SCOPE") or DEFAULT_SCOPE
        self.store = TokenStore(token_path)

    @classmethod
    def available(cls) -> bool:
        """True if client credentials are present in the environment."""
        return bool(os.environ.get("TIKTOK_CLIENT_KEY")
                    and os.environ.get("TIKTOK_CLIENT_SECRET"))

    def _require_app(self) -> None:
        if not (self.client_key and self.client_secret):
            raise RuntimeError(
                "Missing TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET (TikTok "
                "Developer App -> Login Kit + Display API).")

    # -- token lifecycle -----------------------------------------------------

    def exchange_code(self, code: str, code_verifier: str | None = None) -> dict:
        """Turn an authorization code into stored tokens."""
        self._require_app()
        fields = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }
        if code_verifier:
            fields["code_verifier"] = code_verifier
        payload = _post_form(TOKEN, fields)
        now = int(time.time())
        data = {
            "open_id": payload.get("open_id"),
            "scope": payload.get("scope", self.scope),
            "token_type": payload.get("token_type", "Bearer"),
            "access_token": payload["access_token"],
            "refresh_token": payload.get("refresh_token"),
            "expires_at": now + int(payload.get("expires_in", 0)),
            "refresh_expires_at": now + int(payload.get("refresh_expires_in", 0)),
            "obtained_at": now,
        }
        self.store.save(data)
        return data

    def refresh(self) -> str:
        """Use the refresh token to get a new access token. Returns it."""
        self._require_app()
        data = self.store.load() or {}
        refresh_token = data.get("refresh_token")
        if not refresh_token:
            raise RuntimeError("No refresh token stored. Run `login` first.")
        payload = _post_form(TOKEN, {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        })
        now = int(time.time())
        data.update({
            "open_id": payload.get("open_id", data.get("open_id")),
            "scope": payload.get("scope", data.get("scope", self.scope)),
            "access_token": payload["access_token"],
            # TikTok may rotate the refresh token -> always keep the newest.
            "refresh_token": payload.get("refresh_token") or refresh_token,
            "expires_at": now + int(payload.get("expires_in", 0)),
            "refresh_expires_at": now + int(payload.get("refresh_expires_in", 0)),
            "refreshed_at": now,
        })
        self.store.save(data)
        return data["access_token"]

    def access_token(self, margin: int = REFRESH_MARGIN) -> str:
        """A currently valid access token, refreshing when close to expiry."""
        data = self.store.load()
        if not data:
            raise RuntimeError("No TikTok token stored. Run "
                               "`python3 -m monitoring.cli login` first.")
        if int(data.get("expires_at", 0)) - time.time() > margin:
            return data["access_token"]
        return self.refresh()

    def status(self) -> dict:
        """Non-secret summary of the stored token."""
        data = self.store.load()
        if not data:
            return {"logged_in": False, "token_file": str(self.store.path)}
        now = int(time.time())
        return {
            "logged_in": True,
            "open_id": data.get("open_id"),
            "scope": data.get("scope"),
            "token_file": str(self.store.path),
            "access_expires_in": max(0, int(data.get("expires_at", 0)) - now),
            "refresh_expires_in": max(0, int(data.get("refresh_expires_at", 0)) - now),
        }

    def revoke(self) -> None:
        """Revoke the current access token and drop it locally."""
        self._require_app()
        data = self.store.load() or {}
        if data.get("access_token"):
            _post_form(REVOKE, {"client_key": self.client_key,
                                "client_secret": self.client_secret,
                                "token": data["access_token"]})
        self.store.clear()

    # -- interactive login ---------------------------------------------------

    def _pending_store(self) -> "TokenStore":
        return TokenStore(self.store.path.parent / "tiktok_auth_pending.json")

    def begin_login(self) -> str:
        """Headless step 1: persist PKCE state, return the authorize URL.

        Pairs with ``finish_login`` for flows where the redirect can't reach a
        local server (e.g. a hosted redirect URI)."""
        self._require_app()
        state = secrets.token_urlsafe(16)
        verifier, challenge = _pkce_pair()
        self._pending_store().save({
            "state": state,
            "code_verifier": verifier,
            "redirect_uri": self.redirect_uri,
            "created_at": int(time.time()),
        })
        return build_authorize_url(self.client_key, self.redirect_uri,
                                   self.scope, state, challenge)

    def finish_login(self, raw: str) -> dict:
        """Headless step 2: exchange the pasted redirect URL (or bare code)."""
        pending = self._pending_store().load() or {}
        query = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(raw).query))
        code = query.get("code") or raw.strip()
        if not code:
            raise RuntimeError("Kein Authorization-Code gefunden.")
        data = self.exchange_code(urllib.parse.unquote(code),
                                  pending.get("code_verifier"))
        self._pending_store().clear()
        return data

    def login(self, port: int | None = None, open_browser: bool = True,
              timeout: int = 300, manual: bool = False, prompt=input) -> dict:
        """Run the browser flow: open authorize URL, capture code, store tokens.

        Default starts a throwaway local server on the redirect URI's port and
        waits for the ``?code=`` callback. With ``manual=True`` it skips the
        server: the user pastes back the full redirect URL (or just the code) —
        a fallback when the redirect can't reach localhost. Returns the stored
        token data.
        """
        self._require_app()
        state = secrets.token_urlsafe(16)
        verifier, challenge = _pkce_pair()
        url = build_authorize_url(self.client_key, self.redirect_uri,
                                  self.scope, state, challenge)

        if manual:
            print("Autorisiere im Browser und füge danach die komplette "
                  "Redirect-URL (oder nur den code) ein:\n\n" + url + "\n")
            if open_browser:
                webbrowser.open(url)
            raw = prompt("code / Redirect-URL: ").strip()
            query = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(raw).query))
            code = query.get("code") or raw
            if not code:
                raise RuntimeError("Kein Authorization-Code eingegeben.")
            return self.exchange_code(urllib.parse.unquote(code), verifier)

        parsed = urllib.parse.urlparse(self.redirect_uri)
        if port is None:
            port = parsed.port or 8080

        result: dict = {}
        done = threading.Event()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                query = dict(urllib.parse.parse_qsl(
                    urllib.parse.urlparse(self.path).query))
                result.update(query)
                ok = "code" in query and query.get("state") == state
                msg = ("Login erfolgreich – Fenster kann geschlossen werden."
                       if ok else
                       f"Login fehlgeschlagen: "
                       f"{query.get('error_description') or query.get('error') or 'state/Code fehlt'}")
                body = f"<!doctype html><meta charset='utf-8'><h2>{msg}</h2>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body.encode("utf-8"))
                done.set()

            def log_message(self, *args):  # silence
                pass

        server = HTTPServer(("localhost", port), Handler)
        threading.Thread(target=server.handle_request, daemon=True).start()
        print(f"Öffne im Browser:\n  {url}\n")
        if open_browser:
            webbrowser.open(url)
        try:
            if not done.wait(timeout):
                raise RuntimeError("Login-Timeout: kein Redirect erhalten.")
        finally:
            server.server_close()

        if result.get("error"):
            raise RuntimeError(f"TikTok Login abgelehnt: {result['error']} "
                               f"{result.get('error_description', '')}")
        if result.get("state") != state:
            raise RuntimeError("OAuth state mismatch (CSRF?).")
        code = result.get("code")
        if not code:
            raise RuntimeError("Kein Authorization-Code im Redirect.")
        return self.exchange_code(urllib.parse.unquote(code), verifier)
