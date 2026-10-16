"""Offline unit tests for TikTok OAuth / token handling (no network).

Run: python3 tests/test_tiktok_auth.py
"""

import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.parse
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from monitoring import auth  # noqa: E402


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


TOKEN_PAYLOAD = {
    "access_token": "act.new", "expires_in": 86400, "open_id": "oid.1",
    "refresh_token": "rft.new", "refresh_expires_in": 31536000,
    "scope": "user.info.basic,video.list", "token_type": "Bearer",
}


class AuthorizeUrlTest(unittest.TestCase):
    def test_params(self):
        url = auth.build_authorize_url("ck", "http://localhost:1/cb",
                                       "user.info.basic,video.list", "st")
        parsed = urllib.parse.urlparse(url)
        q = dict(urllib.parse.parse_qsl(parsed.query))
        self.assertEqual(parsed.netloc, "www.tiktok.com")
        self.assertEqual(q["client_key"], "ck")
        self.assertEqual(q["response_type"], "code")
        self.assertEqual(q["redirect_uri"], "http://localhost:1/cb")
        self.assertEqual(q["scope"], "user.info.basic,video.list")
        self.assertEqual(q["state"], "st")

    def test_pkce_params(self):
        import base64
        import hashlib
        verifier, challenge = auth._pkce_pair()
        url = auth.build_authorize_url("ck", code_challenge=challenge)
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        self.assertEqual(q["code_challenge"], challenge)
        self.assertEqual(q["code_challenge_method"], "S256")
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        self.assertEqual(challenge, expected)


class TokenStoreTest(unittest.TestCase):
    def test_roundtrip_and_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "tok.json"
            store = auth.TokenStore(path)
            self.assertIsNone(store.load())
            store.save({"access_token": "a", "expires_at": 1})
            self.assertEqual(store.load()["access_token"], "a")
            store.clear()
            self.assertIsNone(store.load())


class ExchangeRefreshTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "tok.json"

    def tearDown(self):
        self.tmp.cleanup()

    def _auth(self):
        return auth.TikTokAuth(client_key="ck", client_secret="cs",
                               token_path=self.path)

    def test_exchange_code_stores(self):
        with mock.patch.object(auth, "_post_form", return_value=TOKEN_PAYLOAD):
            self._auth().exchange_code("thecode")
        data = auth.TokenStore(self.path).load()
        self.assertEqual(data["refresh_token"], "rft.new")
        self.assertEqual(data["open_id"], "oid.1")
        self.assertAlmostEqual(data["expires_at"] - data["obtained_at"], 86400, delta=5)

    def test_exchange_code_passes_verifier(self):
        with mock.patch.object(auth, "_post_form", return_value=TOKEN_PAYLOAD) as post:
            self._auth().exchange_code("c", "VER123")
        self.assertEqual(post.call_args[0][1]["code_verifier"], "VER123")

    def test_access_token_uses_fresh_token(self):
        store = auth.TokenStore(self.path)
        store.save({"access_token": "fresh", "expires_at": int(time.time()) + 3600,
                    "refresh_token": "r"})
        with mock.patch.object(auth, "_post_form") as post:
            tok = self._auth().access_token()
        self.assertEqual(tok, "fresh")
        post.assert_not_called()

    def test_access_token_refreshes_when_stale(self):
        store = auth.TokenStore(self.path)
        store.save({"access_token": "old", "expires_at": int(time.time()) - 10,
                    "refresh_token": "rft.old", "open_id": "oid.1"})
        with mock.patch.object(auth, "_post_form", return_value=TOKEN_PAYLOAD) as post:
            tok = self._auth().access_token()
        self.assertEqual(tok, "act.new")
        self.assertEqual(post.call_args[0][1]["grant_type"], "refresh_token")
        self.assertEqual(auth.TokenStore(self.path).load()["refresh_token"], "rft.new")

    def test_status_anonymous(self):
        status = self._auth().status()
        self.assertFalse(status["logged_in"])


class LoginFlowTest(unittest.TestCase):
    def test_login_captures_code_and_exchanges(self):
        port = _free_port()
        redirect = f"http://localhost:{port}/callback"
        with tempfile.TemporaryDirectory() as tmp:
            a = auth.TikTokAuth(client_key="ck", client_secret="cs",
                                token_path=Path(tmp) / "tok.json",
                                redirect_uri=redirect)

            def fake_open(url):
                state = dict(urllib.parse.parse_qsl(
                    urllib.parse.urlparse(url).query))["state"]
                cb = f"{redirect}?code=THECODE&state={state}"
                threading.Thread(
                    target=lambda: urllib.request.urlopen(cb, timeout=5)).start()
                return True

            with mock.patch.object(auth.webbrowser, "open", fake_open), \
                 mock.patch.object(auth, "_post_form", return_value=TOKEN_PAYLOAD) as post:
                data = a.login(port=port, timeout=10)

        self.assertEqual(post.call_args[0][1]["code"], "THECODE")
        self.assertIn("code_verifier", post.call_args[0][1])
        self.assertEqual(data["access_token"], "act.new")

    def test_login_manual_paste_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = auth.TikTokAuth(client_key="ck", client_secret="cs",
                                token_path=Path(tmp) / "tok.json")
            with mock.patch.object(auth.webbrowser, "open"), \
                 mock.patch.object(auth, "_post_form", return_value=TOKEN_PAYLOAD) as post:
                data = a.login(manual=True, prompt=lambda _: (
                    "http://localhost:8080/callback?code=ABC123&state=zz"))
        self.assertEqual(post.call_args[0][1]["code"], "ABC123")
        self.assertEqual(data["access_token"], "act.new")

    def test_login_manual_paste_raw_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = auth.TikTokAuth(client_key="ck", client_secret="cs",
                                token_path=Path(tmp) / "tok.json")
            with mock.patch.object(auth.webbrowser, "open"), \
                 mock.patch.object(auth, "_post_form", return_value=TOKEN_PAYLOAD) as post:
                a.login(manual=True, prompt=lambda _: "RAWCODE")
        self.assertEqual(post.call_args[0][1]["code"], "RAWCODE")

class HeadlessFlowTest(unittest.TestCase):
    def test_begin_and_finish(self):
        with tempfile.TemporaryDirectory() as tmp:
            pending_path = Path(tmp) / "tiktok_auth_pending.json"
            a = auth.TikTokAuth(client_key="ck", client_secret="cs",
                                token_path=Path(tmp) / "tok.json")
            url = a.begin_login()
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
            self.assertEqual(q["code_challenge_method"], "S256")
            pending = auth.TokenStore(pending_path).load()
            self.assertEqual(pending["state"], q["state"])

            with mock.patch.object(auth, "_post_form", return_value=TOKEN_PAYLOAD) as post:
                a.finish_login(f"https://me.github.io/cb?code=CCC&state={q['state']}")
            self.assertEqual(post.call_args[0][1]["code"], "CCC")
            self.assertEqual(post.call_args[0][1]["code_verifier"],
                             pending["code_verifier"])
            self.assertIsNone(auth.TokenStore(pending_path).load())  # cleared

    def test_finish_accepts_bare_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = auth.TikTokAuth(client_key="ck", client_secret="cs",
                                token_path=Path(tmp) / "tok.json")
            a.begin_login()
            with mock.patch.object(auth, "_post_form", return_value=TOKEN_PAYLOAD) as post:
                a.finish_login("BARE_CODE")
            self.assertEqual(post.call_args[0][1]["code"], "BARE_CODE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
