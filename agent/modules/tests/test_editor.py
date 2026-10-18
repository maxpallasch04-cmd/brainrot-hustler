"""Tests für `editor` (kein ffmpeg nötig, außer beim Rauchtest am Ende)."""

from __future__ import annotations

import unittest
from pathlib import Path

from editor import SpecError, validate
from editor.graph import build
from editor.spec import Spec

SRC = 1920, 1080


def fake_probe(path):
    return {
        "path": str(path),
        "width": SRC[0],
        "height": SRC[1],
        "size": SRC,
        "duration": 60.0,
        "has_audio": True,
        "rotation": 0,
    }


def spec(**extra):
    base = {
        "size": [1080, 1920],
        "fps": 30,
        "clips": [
            {
                "source": "in.mp4",
                "start": 0,
                "end": 30,
                "regions": [
                    {"box": [0, 0, 1920, 120], "size": [1080, 68],
                     "position": [0, 0], "fit": "contain"},
                ],
            }
        ],
    }
    base.update(extra)
    return Spec(base)


def check(rec, **kw):
    kw.setdefault("check_fs", False)
    kw.setdefault("probe_fn", fake_probe)
    return validate(rec, **kw)


def codes(report, kind="errors"):
    return [e["code"] for e in report[kind]]


class ValidateTests(unittest.TestCase):
    def test_valid_spec(self):
        report = check(spec())
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["stats"]["clips"], 1)
        self.assertEqual(report["stats"]["size"], [1080, 1920])

    def test_region_outside_canvas(self):
        rec = spec()
        rec.data["clips"][0]["regions"].append(
            {"box": [0, 0, 100, 100], "size": [2000, 200], "position": [0, 0]}
        )
        report = check(rec)
        self.assertFalse(report["ok"])
        self.assertIn("region.outside_canvas", codes(report))

    def test_box_outside_source(self):
        rec = spec()
        rec.data["clips"][0]["regions"][0]["box"] = [1800, 0, 400, 120]
        report = check(rec)
        self.assertIn("region.box.outside_source", codes(report))

    def test_overlap_forbidden(self):
        rec = spec(expect={"overlap": "forbid"})
        rec.data["clips"][0]["regions"] = [
            {"box": [0, 0, 960, 1080], "size": [1080, 960], "position": [0, 0]},
            {"box": [960, 0, 960, 1080], "size": [1080, 960], "position": [0, 500]},
        ]
        report = check(rec)
        self.assertIn("region.overlap", codes(report))

    def test_overlap_allowed_by_default(self):
        rec = spec()
        rec.data["clips"][0]["regions"] = [
            {"box": [0, 0, 960, 1080], "size": [1080, 960], "position": [0, 0]},
            {"box": [960, 0, 960, 1080], "size": [1080, 960], "position": [0, 500]},
        ]
        report = check(rec)
        self.assertTrue(report["ok"], report)

    def test_fill_exact_ok(self):
        rec = spec(expect={"fill": "exact"})
        rec.data["clips"][0]["regions"] = [
            {"box": [0, 0, 1920, 540], "size": [1080, 960], "position": [0, 0]},
            {"box": [0, 540, 1920, 540], "size": [1080, 960], "position": [0, 960]},
        ]
        report = check(rec)
        self.assertTrue(report["ok"], report)

    def test_fill_exact_reports_gap(self):
        rec = spec(expect={"fill": "exact"})
        report = check(rec)
        self.assertFalse(report["ok"])
        self.assertIn("canvas.gap", codes(report))

    def test_fill_exact_allows_overlap_if_covered(self):
        rec = spec(expect={"fill": "exact"})
        rec.data["clips"][0]["regions"] = [
            {"box": [0, 0, 1920, 1080], "size": [1080, 1920], "position": [0, 0]},
            {"box": [0, 0, 400, 130], "size": [400, 130], "position": [30, 30]},
        ]
        report = check(rec)
        self.assertTrue(report["ok"], report)

    def test_uncovered_warns_by_default(self):
        report = check(spec())
        self.assertIn("canvas.uncovered", codes(report, "warnings"))
        self.assertEqual(report["stats"]["coverage"], 3.5)

    def test_full_bleed_has_no_coverage_warning(self):
        rec = spec()
        rec.data["clips"][0]["regions"] = [
            {"box": [656, 0, 607, 1080], "size": [1080, 1920], "position": [0, 0]},
            {"box": [0, 0, 400, 130], "size": [400, 130], "position": [30, 30]},
        ]
        report = check(rec)
        self.assertNotIn("canvas.uncovered", codes(report, "warnings"))
        self.assertEqual(report["stats"]["coverage"], 100.0)

    def test_ratio_warning(self):
        rec = spec(expect={"ratio": "warn"})
        report = check(rec)
        self.assertTrue(report["ok"], report)
        self.assertIn("region.ratio", codes(report, "warnings"))

    def test_ratio_off_by_default(self):
        report = check(spec())
        self.assertNotIn("region.ratio", codes(report, "warnings"))

    def test_ratio_reports_the_loss(self):
        rec = spec(expect={"ratio": "warn"})
        report = check(rec)
        msg = report["warnings"][0]["message"]
        self.assertIn("contain leaves", msg)
        self.assertIn("%", msg)

    def test_stretch_warns_by_default(self):
        rec = spec()
        rec.data["clips"][0]["regions"][0].update(
            {"box": [0, 0, 1920, 1080], "size": [1080, 800], "fit": "stretch"}
        )
        report = check(rec)
        self.assertIn("region.stretch", codes(report, "warnings"))
        self.assertIn("distorts", report["warnings"][0]["message"])

    def test_no_stretch_warning_when_ratio_matches(self):
        rec = spec()
        rec.data["clips"][0]["regions"][0].update(
            {"box": [0, 0, 1920, 1080], "size": [1080, 608], "fit": "stretch"}
        )
        report = check(rec)
        self.assertNotIn("region.stretch", codes(report, "warnings"))

    def test_ratio_as_error(self):
        rec = spec(expect={"ratio": "error"})
        report = check(rec)
        self.assertIn("region.ratio", codes(report))

    def test_odd_size_warns(self):
        rec = spec(size=[1081, 1921])
        report = check(rec)
        self.assertIn("size.odd", codes(report, "warnings"))

    def test_expect_invalid(self):
        rec = spec(expect={"overlap": "maybe"})
        report = check(rec)
        self.assertIn("expect.invalid", codes(report))

    def test_bad_time(self):
        rec = spec()
        rec.data["clips"][0]["end"] = 0
        report = check(rec)
        self.assertIn("clip.time.invalid", codes(report))

    def test_start_past_source(self):
        rec = spec()
        rec.data["clips"][0].update({"start": 120, "end": 130})
        report = check(rec)
        self.assertIn("clip.time.out_of_range", codes(report))

    def test_missing_clips(self):
        report = check(Spec({"size": [1080, 1920]}))
        self.assertIn("clips.empty", codes(report))

    def test_missing_source(self):
        report = validate(spec(), check_fs=True, probe_fn=fake_probe)
        self.assertIn("clip.source.not_found", codes(report))

    def test_audio_partial_warns(self):
        rec = spec()
        rec.data["clips"][0]["source"] = "a.mp4"
        rec.data["clips"].append({"source": "b.mp4", "start": 0, "end": 5})

        def probe_two(path):
            info = fake_probe(path)
            info["has_audio"] = str(path).endswith("a.mp4")
            return info

        report = validate(rec, check_fs=False, probe_fn=probe_two)
        self.assertIn("audio.partial", codes(report, "warnings"))


class GraphTests(unittest.TestCase):
    def probes(self, rec):
        return {str(rec.resolve("in.mp4")): fake_probe("in.mp4")}

    def test_single_clip_two_regions(self):
        rec = spec()
        rec.data["clips"][0]["regions"].append(
            {"box": [440, 160, 1040, 620], "size": [1080, 800], "position": [0, 80]}
        )
        built = build(rec, self.probes(rec))
        graph = built["filter_complex"]
        self.assertIn("split=2", graph)
        self.assertIn("overlay=x=0:y=80", graph)
        self.assertEqual(built["vout"], "v0")
        self.assertEqual(built["size"], [1080, 1920])
        self.assertIn("[a0]", graph)

    def test_cover_and_contain(self):
        rec = spec()
        rec.data["clips"][0]["regions"] = [
            {"box": [0, 0, 1920, 120], "size": [1080, 68], "fit": "contain"},
            {"box": [440, 160, 1040, 620], "size": [1080, 800], "fit": "cover"},
        ]
        graph = build(rec, self.probes(rec))["filter_complex"]
        self.assertIn("force_original_aspect_ratio=decrease", graph)
        self.assertIn("pad=1080:68", graph)
        self.assertIn("force_original_aspect_ratio=increase", graph)

    def test_concat_two_clips(self):
        rec = spec()
        rec.data["clips"].append({"source": "in.mp4", "start": 0, "end": 5,
                                  "regions": []})
        built = build(rec, self.probes(rec))
        self.assertIn("concat=n=2:v=1:a=1[vout][aout]", built["filter_complex"])
        self.assertEqual(built["duration"], 35.0)

    def test_transition_uses_xfade(self):
        rec = spec(transition=0.5)
        rec.data["clips"].append({"source": "in.mp4", "start": 0, "end": 10,
                                  "regions": []})
        built = build(rec, self.probes(rec), transition=0.5)
        graph = built["filter_complex"]
        self.assertIn("xfade=transition=fade:duration=0.500:offset=29.500", graph)
        self.assertIn("acrossfade", graph)
        self.assertEqual(built["duration"], 39.5)

    def test_no_audio_if_one_clip_is_silent(self):
        rec = spec()
        rec.data["clips"].append({"source": "in.mp4", "start": 0, "end": 5})

        def probe_one(path):
            info = fake_probe(path)
            info["has_audio"] = False
            return info

        built = build(rec, {str(rec.resolve("in.mp4")): probe_one("in.mp4")})
        self.assertIsNone(built["aout"])
        self.assertIn("concat=n=2:v=1:a=0[vout]", built["filter_complex"])

    def test_clip_without_regions_is_background(self):
        rec = spec()
        rec.data["clips"][0]["regions"] = []
        built = build(rec, self.probes(rec))
        self.assertNotIn("split", built["filter_complex"])
        self.assertIn("format=yuv420p,setsar=1[v0]", built["filter_complex"])

    def test_duplicate_region_names_warn(self):
        rec = spec()
        rec.data["clips"][0]["regions"] = [
            {"name": "action", "box": [0, 0, 1920, 1080], "size": [1080, 1920]},
            {"name": "action", "box": [0, 0, 400, 130], "size": [400, 130],
             "position": [30, 30]},
        ]
        report = check(rec)
        self.assertIn("region.name.duplicate", codes(report, "warnings"))

    def test_empty_region_name_warns(self):
        rec = spec()
        rec.data["clips"][0]["regions"][0]["name"] = "  "
        report = check(rec)
        self.assertIn("region.name.empty", codes(report, "warnings"))


class FramesTest(unittest.TestCase):
    def setUp(self):
        import subprocess
        import tempfile
        from editor.probe import ffmpeg_exe

        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.src = f"{self.dir}/in.mp4"
        cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
               "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=10:duration=1",
               "-pix_fmt", "yuv420p", self.src]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            self.tmp.cleanup()
            self.skipTest(f"ffmpeg unavailable: {exc}")

    def tearDown(self):
        self.tmp.cleanup()

    def test_even_spread(self):
        from editor import frames

        got = frames(self.src, count=3, out_dir=f"{self.dir}/f")
        self.assertEqual(len(got), 3)
        self.assertEqual([f["t"] for f in got], [0.167, 0.5, 0.833])
        for item in got:
            self.assertTrue(Path(item["path"]).is_file())

    def test_explicit_times_and_width(self):
        from editor import frames

        got = frames(self.src, [0.0, 0.5], out_dir=f"{self.dir}/f2", width=80)
        self.assertEqual([f["t"] for f in got], [0.0, 0.5])
        self.assertEqual(got[0]["size"], [80, 60])

    def test_bad_count(self):
        from editor import frames

        with self.assertRaises(ValueError):
            frames(self.src, count=0, out_dir=f"{self.dir}/f3")


if __name__ == "__main__":
    unittest.main()
