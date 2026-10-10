"""Offline unit tests for Twitch clip discovery (no network).

Run: python3 tests/test_twitch_clips.py
"""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from twitch_clips import discovery, download, helix  # noqa: E402

NOW = 1_700_000_000


def _clip(cid, views, created_ts, duration=20.0, language="en"):
    return {
        "id": cid,
        "url": f"https://clips.twitch.tv/{cid}",
        "title": cid,
        "view_count": views,
        "duration": duration,
        "language": language,
        "broadcaster_name": "someone",
        "game_id": "1",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(created_ts)),
    }


class FakeClient:
    def __init__(self, clips):
        self._clips = clips

    def get_game_id(self, name):
        return "1"

    def iter_clips(self, **kwargs):
        return iter(self._clips)


class DiscoveryTest(unittest.TestCase):
    def test_decorate_age_and_velocity(self):
        clip = _clip("a", 1200, NOW - 2 * 3600)
        out = discovery.decorate(clip, now=NOW)
        self.assertEqual(out["view_count"], 1200)
        self.assertAlmostEqual(out["age_hours"], 2.0, places=2)
        self.assertAlmostEqual(out["views_per_hour"], 600.0, places=1)

    def test_iso_roundtrip(self):
        self.assertEqual(discovery._parse_iso(discovery._iso(NOW)), NOW)

    def test_rank_by_views(self):
        clips = [_clip("a", 100, NOW - 3600), _clip("b", 900, NOW - 7200)]
        out = discovery.find_clips(FakeClient(clips), game="x", hours=100, top=10, now=NOW)
        self.assertEqual([c["id"] for c in out], ["b", "a"])

    def test_rank_by_velocity(self):
        # a: few views but very fresh -> higher velocity than b
        clips = [_clip("a", 300, NOW - 1800), _clip("b", 1000, NOW - 50 * 3600)]
        out = discovery.find_clips(FakeClient(clips), game="x", hours=1000,
                                   sort="velocity", now=NOW)
        self.assertEqual(out[0]["id"], "a")

    def test_filters(self):
        clips = [
            _clip("low", 10, NOW - 3600),
            _clip("long", 5000, NOW - 3600, duration=90.0),
            _clip("de", 5000, NOW - 3600, language="de"),
            _clip("ok", 5000, NOW - 3600),
        ]
        out = discovery.find_clips(FakeClient(clips), game="x", hours=100,
                                   min_views=1000, max_duration=60, language="en",
                                   top=10, now=NOW)
        self.assertEqual([c["id"] for c in out], ["ok"])

    def test_exclude_and_dedupe(self):
        clips = [_clip("a", 100, NOW - 3600), _clip("a", 100, NOW - 3600),
                 _clip("b", 90, NOW - 3600)]
        out = discovery.find_clips(FakeClient(clips), game="x", hours=100,
                                   exclude_ids={"b"}, top=10, now=NOW)
        self.assertEqual([c["id"] for c in out], ["a"])

    def test_needs_game_or_id(self):
        with self.assertRaises(ValueError):
            discovery.find_clips(FakeClient([]), now=NOW)


class HelixTest(unittest.TestCase):
    def test_missing_credentials(self):
        with mock.patch.dict(os.environ, {"TWITCH_CLIENT_ID": "", "TWITCH_CLIENT_SECRET": ""}):
            with self.assertRaises(RuntimeError):
                helix.Helix()

    def test_token_cached_and_headers(self):
        calls = []

        def fake(url, *, method="GET", headers=None, params=None, data=None, timeout=15):
            calls.append({"url": url, "method": method, "headers": headers, "params": params})
            if url == helix.TOKEN_URL:
                return {"access_token": "TOK", "expires_in": 3600}
            return {"data": [_clip("a", 5, NOW - 3600)], "pagination": {}}

        with mock.patch.object(helix, "_http_json", fake):
            client = helix.Helix("cid", "secret")
            clips = list(client.iter_clips(game_id="1"))
            list(client.iter_clips(game_id="1"))  # second call reuses the token

        self.assertEqual(len(clips), 1)
        tokens = [c for c in calls if c["url"] == helix.TOKEN_URL]
        self.assertEqual(len(tokens), 1)  # cached
        clip_calls = [c for c in calls if c["url"].endswith("/clips")]
        self.assertEqual(clip_calls[0]["headers"]["Authorization"], "Bearer TOK")
        self.assertEqual(clip_calls[0]["headers"]["Client-Id"], "cid")
        self.assertEqual(clip_calls[0]["params"]["game_id"], "1")


class DownloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_clip_url(self):
        self.assertEqual(download.clip_url({"id": "abc"}), "https://clips.twitch.tv/abc")
        self.assertEqual(download.clip_url({"url": "https://www.twitch.tv/x/clip/y"}),
                         "https://www.twitch.tv/x/clip/y")
        self.assertEqual(download.clip_url("abc"), "https://clips.twitch.tv/abc")
        self.assertEqual(download.clip_url("https://clips.twitch.tv/abc"),
                         "https://clips.twitch.tv/abc")

    def test_clip_id(self):
        self.assertEqual(download.clip_id({"id": "abc"}), "abc")
        self.assertEqual(download.clip_id("https://www.twitch.tv/oatley/clip/Slug-123"),
                         "Slug-123")

    def test_missing_reference(self):
        with self.assertRaises(ValueError):
            download.clip_url({})

    def test_skip_existing_file(self):
        out = self.tmp / "clips"
        out.mkdir()
        (out / "abc.mp4").write_bytes(b"x")
        path, skipped = download._download({"id": "abc"}, str(out))
        self.assertTrue(skipped)
        self.assertEqual(Path(path).name, "abc.mp4")

    def test_safe_filename(self):
        self.assertEqual(download._safe("Slug-123_ok"), "Slug-123_ok")
        self.assertEqual(download._safe("a/b c"), "a_b_c")

    def test_download_clips_aggregates(self):
        def fake(clip, out_dir, *, overwrite=False, quiet=True):
            cid = download.clip_id(clip)
            if cid == "bad":
                raise RuntimeError("boom")
            if cid == "old":
                return f"{out_dir}/old.mp4", True
            return f"{out_dir}/{cid}.mp4", False

        with mock.patch.object(download, "_download", fake):
            res = download.download_clips([{"id": "a"}, {"id": "old"}, {"id": "bad"}],
                                          "clips", top=3)
        self.assertEqual(res["downloaded"], ["clips/a.mp4"])
        self.assertEqual(res["skipped"], ["clips/old.mp4"])
        self.assertEqual([f["clip"] for f in res["failed"]], ["bad"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
