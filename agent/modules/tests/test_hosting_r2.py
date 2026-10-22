"""Offline unit tests for the R2 backend (no network, no boto3 required).

Run: python3 tests/test_hosting_r2.py
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import importlib  # noqa: E402

r2 = importlib.import_module("hosting.r2")  # noqa: E402

ENV = {
    "R2_ACCOUNT_ID": "abc123",
    "R2_ACCESS_KEY_ID": "KEY",
    "R2_SECRET_ACCESS_KEY": "SECRET",
    "R2_BUCKET": "brainrot",
    "R2_PUBLIC_BASE_URL": "https://pub-x.r2.dev/",
    # Standalone-Betrieb ohne Kanal braucht einen expliziten Prefix.
    "R2_PREFIX": "videos",
}
MANAGED = list(ENV) + ["R2_PREFIX", "R2_ENDPOINT", "R2_KEEP", "R2_QUOTA_GB",
                       "BRAINROT_CHANNEL", "BRAINROT_DB"]
T0 = datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc)


def _objs(*specs):
    """specs: (key, size, seconds_after_T0)."""
    return [{"key": k, "size": s, "last_modified": T0 + timedelta(seconds=t)}
            for k, s, t in specs]


class _FakeClient:
    def __init__(self, objects):
        self._objects = objects
        self.deleted = []
        self.put = []

    def list_objects_v2(self, **kwargs):
        return {"Contents": [{"Key": o["key"], "Size": o["size"],
                              "LastModified": o["last_modified"]} for o in self._objects],
                "IsTruncated": False}

    def delete_objects(self, Bucket, Delete):
        keys = [o["Key"] for o in Delete["Objects"]]
        self.deleted.extend(keys)
        return {"Deleted": [{"Key": k} for k in keys]}

    def put_object(self, **kwargs):
        self.put.append(kwargs)
        return {}


class _Base(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in MANAGED}
        for k in MANAGED:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class ConfigTest(_Base):
    def test_missing_config_raises(self):
        with self.assertRaises(r2.R2Error):
            r2.config()

    def test_is_configured_false_when_empty(self):
        self.assertFalse(r2.is_configured())

    def test_defaults(self):
        os.environ.update(ENV)
        cfg = r2.config()
        self.assertEqual(cfg["endpoint"], "https://abc123.r2.cloudflarestorage.com")
        self.assertEqual(cfg["public_base_url"], "https://pub-x.r2.dev")
        self.assertEqual(cfg["prefix"], "videos/")
        self.assertTrue(r2.is_configured())

    def test_without_channel_and_prefix_raises(self):
        os.environ.update(ENV)
        os.environ.pop("R2_PREFIX", None)
        with self.assertRaises(r2.R2Error):
            r2.config()

    def test_channel_prefix_from_profile(self):
        from longterm_memory import db as ltm

        tmp = Path(tempfile.mkdtemp()) / "t.db"
        conn = ltm.init_db(tmp)
        ltm.upsert_channel(conn, "sls")
        conn.close()
        os.environ.update(ENV, BRAINROT_DB=str(tmp), BRAINROT_CHANNEL="sls")
        self.assertEqual(r2.config()["prefix"], "brainrot/sls/")

    def test_channel_beats_prefix_override(self):
        from longterm_memory import db as ltm

        tmp = Path(tempfile.mkdtemp()) / "t.db"
        conn = ltm.init_db(tmp)
        ltm.upsert_channel(conn, "sls")
        conn.close()
        os.environ.update(ENV, BRAINROT_DB=str(tmp), BRAINROT_CHANNEL="sls",
                          R2_PREFIX="stale/")
        self.assertEqual(r2.config()["prefix"], "brainrot/sls/")

    def test_unknown_channel_raises(self):
        from longterm_memory import db as ltm

        tmp = Path(tempfile.mkdtemp()) / "t.db"
        conn = ltm.init_db(tmp)
        ltm.upsert_channel(conn, "sls")
        conn.close()
        os.environ.update(ENV, BRAINROT_DB=str(tmp), BRAINROT_CHANNEL="nope")
        with self.assertRaises(r2.R2Error):
            r2.config()

    def test_endpoint_and_prefix_override(self):
        os.environ.update(ENV, R2_ENDPOINT="https://custom.example", R2_PREFIX="clips")
        cfg = r2.config()
        self.assertEqual(cfg["endpoint"], "https://custom.example")
        self.assertEqual(cfg["prefix"], "clips/")

    def test_keep_and_quota_defaults(self):
        self.assertEqual(r2.keep_count(), 1)
        self.assertEqual(r2.quota_bytes(), 10 * 1024 ** 3)

    def test_keep_and_quota_override(self):
        os.environ.update(R2_KEEP="3", R2_QUOTA_GB="2.5")
        self.assertEqual(r2.keep_count(), 3)
        self.assertEqual(r2.quota_bytes(), int(2.5 * 1024 ** 3))

    def test_object_key(self):
        self.assertEqual(r2.object_key("My Clip!.mp4", when=T0),
                         "videos/2026-10-12/20261012-100000-My-Clip-.mp4")

    def test_public_url(self):
        os.environ.update(ENV)
        self.assertEqual(r2.public_url("videos/a.mp4"),
                         "https://pub-x.r2.dev/videos/a.mp4")


class UploadTest(_Base):
    def test_upload_bytes_puts_object(self):
        os.environ.update(ENV)
        fake = _FakeClient([])
        with mock.patch.object(r2, "_client", return_value=fake):
            url = r2.upload_bytes(b"data", "clip.mp4", key="videos/k.mp4")
        self.assertEqual(url, "https://pub-x.r2.dev/videos/k.mp4")
        self.assertEqual(fake.put[0]["Bucket"], "brainrot")
        self.assertEqual(fake.put[0]["Key"], "videos/k.mp4")
        self.assertEqual(fake.put[0]["ContentType"], "video/mp4")

    def test_upload_does_not_prune(self):
        os.environ.update(ENV)
        fake = _FakeClient(_objs(("videos/old.mp4", 1, 0)))
        with mock.patch.object(r2, "_client", return_value=fake):
            r2.upload_bytes(b"d", "a.mp4", key="videos/new.mp4")
        self.assertEqual(fake.deleted, [])

    def test_upload_file_roundtrip(self):
        os.environ.update(ENV)
        fake = _FakeClient([])
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "clip.mp4"
            f.write_bytes(b"1234")
            with mock.patch.object(r2, "_client", return_value=fake):
                url = r2.upload_file(f, key="videos/z.mp4")
        self.assertEqual(url, "https://pub-x.r2.dev/videos/z.mp4")
        self.assertEqual(fake.put[0]["Key"], "videos/z.mp4")

    def test_upload_file_stream_uses_a_handle(self):
        os.environ.update(ENV)
        fake = _FakeClient([])
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "big.mp4"
            f.write_bytes(b"1234")
            with mock.patch.object(r2, "_client", return_value=fake):
                url = r2.upload_file(f, key="videos/big.mp4", stream=True)
        self.assertEqual(url, "https://pub-x.r2.dev/videos/big.mp4")
        body = fake.put[0]["Body"]
        self.assertTrue(hasattr(body, "read"), "stream must pass a file handle")
        self.assertEqual(fake.put[0]["ContentType"], "video/mp4")

    def test_upload_error_wrapped(self):
        os.environ.update(ENV)
        fake = mock.Mock()
        fake.put_object.side_effect = RuntimeError("boom")
        with mock.patch.object(r2, "_client", return_value=fake):
            with self.assertRaises(r2.R2Error):
                r2.upload_bytes(b"d", "a.mp4", key="k")

    def test_upload_file_missing(self):
        with self.assertRaises(r2.R2Error):
            r2.upload_file(Path(tempfile.gettempdir()) / "no-such-r2-file.mp4")


class PruneTest(_Base):
    def setUp(self):
        super().setUp()
        os.environ.update(ENV)

    def test_keeps_newest_and_deletes_rest(self):
        fake = _FakeClient(_objs(("videos/a.mp4", 10, 0),
                                 ("videos/b.mp4", 10, 10),
                                 ("videos/c.mp4", 10, 20)))
        with mock.patch.object(r2, "_client", return_value=fake):
            out = r2.prune(keep=1, quota=10 ** 12)
        self.assertEqual(out["kept"], ["videos/c.mp4"])
        self.assertCountEqual(out["deleted"], ["videos/a.mp4", "videos/b.mp4"])
        self.assertEqual(fake.deleted, out["deleted"])
        self.assertEqual(out["bytes"], 10)

    def test_protected_key_survives(self):
        fake = _FakeClient(_objs(("videos/a.mp4", 10, 0), ("videos/b.mp4", 10, 10)))
        with mock.patch.object(r2, "_client", return_value=fake):
            out = r2.prune(keep=0, quota=10 ** 12, protect={"videos/a.mp4"})
        self.assertEqual(out["kept"], ["videos/a.mp4"])
        self.assertEqual(out["deleted"], ["videos/b.mp4"])

    def test_quota_drops_oldest_survivors(self):
        fake = _FakeClient(_objs(("videos/a.mp4", 100, 0),
                                 ("videos/b.mp4", 100, 10),
                                 ("videos/c.mp4", 100, 20)))
        with mock.patch.object(r2, "_client", return_value=fake):
            out = r2.prune(keep=3, quota=150)
        self.assertEqual(out["kept"], ["videos/c.mp4"])
        self.assertCountEqual(out["deleted"], ["videos/a.mp4", "videos/b.mp4"])
        self.assertEqual(out["bytes"], 100)

    def test_protected_ignored_by_quota(self):
        fake = _FakeClient(_objs(("videos/a.mp4", 100, 0), ("videos/b.mp4", 100, 10)))
        with mock.patch.object(r2, "_client", return_value=fake):
            out = r2.prune(keep=2, quota=50, protect={"videos/a.mp4"})
        self.assertEqual(out["kept"], ["videos/a.mp4"])
        self.assertEqual(out["deleted"], ["videos/b.mp4"])

    def test_empty_bucket_deletes_nothing(self):
        fake = _FakeClient([])
        with mock.patch.object(r2, "_client", return_value=fake):
            out = r2.prune(keep=1)
        self.assertEqual(out["deleted"], [])
        self.assertEqual(fake.deleted, [])


class UsageTest(_Base):
    def test_usage(self):
        os.environ.update(ENV, R2_QUOTA_GB="1")
        fake = _FakeClient(_objs(("videos/a.mp4", 100, 0), ("videos/b.mp4", 50, 10)))
        with mock.patch.object(r2, "_client", return_value=fake):
            out = r2.usage()
        self.assertEqual(out["objects"], 2)
        self.assertEqual(out["bytes"], 150)
        self.assertEqual(out["free_bytes"], 1024 ** 3 - 150)
        self.assertEqual(out["keys"], ["videos/a.mp4", "videos/b.mp4"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
