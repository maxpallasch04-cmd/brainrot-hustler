"""Smoke tests for the video editing toolkit.

Run: python3 tests/test_video_generation.py
Uses tiny, throwaway clips so the whole suite stays fast.
"""

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from moviepy import AudioArrayClip, ColorClip, VideoFileClip
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from video_generation import edit  # noqa: E402


def _write_video(path, size=(160, 120), duration=1.0, fps=10, color=(200, 30, 30)):
    clip = ColorClip(size=size, color=color, duration=duration)
    clip.write_videofile(str(path), fps=fps, codec="libx264", audio=False, logger=None)
    clip.close()


def _write_image(path, size=(40, 40), color=(0, 200, 0)):
    Image.new("RGB", size, color).save(path)


def _audio_clip(duration=1.0, fps=8000):
    return AudioArrayClip(np.zeros((int(duration * fps), 1), dtype="float32"), fps=fps)


class VideoGenerationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    # ---- pure helpers ---

    def test_parse_size(self):
        self.assertEqual(edit.parse_size("1080x1920"), (1080, 1920))
        self.assertEqual(edit.parse_size("1080,1920"), (1080, 1920))
        self.assertEqual(edit.parse_size([720, 1280]), (720, 1280))

    def test_parse_color(self):
        self.assertEqual(edit.parse_color("#000000"), (0, 0, 0))
        self.assertEqual(edit.parse_color("white"), (255, 255, 255))
        self.assertEqual(edit.parse_color([1, 2, 3]), (1, 2, 3))

    def test_contain_and_cover(self):
        src = str(self.tmp / "in.mp4")
        _write_video(src, size=(160, 120), duration=0.5)
        clip = edit.load(src)
        try:
            self.assertEqual(edit.contain(clip, (100, 200)).size, (100, 76))
            self.assertEqual(edit.cover(clip, (100, 200)).size, (100, 200))
        finally:
            clip.close()

    # ---- operations ---

    def test_cut_sets_duration(self):
        src = str(self.tmp / "in.mp4")
        _write_video(src, duration=3.0)
        clip = edit.load(src)
        try:
            self.assertAlmostEqual(edit.cut(clip, 1.0, 2.5).duration, 1.5, places=1)
        finally:
            clip.close()

    def test_background_render(self):
        src = str(self.tmp / "in.mp4")
        _write_video(src, size=(160, 90), duration=0.5)
        out = str(self.tmp / "bg.mp4")
        clip = edit.load(src)
        res = edit.on_background(clip, (180, 320), "#101010")
        edit.render(res, out, fps=10)
        clip.close()
        with VideoFileClip(out) as check:
            self.assertEqual(check.size, [180, 320])

    def test_overlay_render(self):
        src = str(self.tmp / "in.mp4")
        img = str(self.tmp / "logo.png")
        _write_video(src, duration=0.5)
        _write_image(img)
        out = str(self.tmp / "ov.mp4")
        clip = edit.load(src)
        res = edit.overlay(clip, img, x="center", y=10, start=0.1, duration=0.3, size=(20, 20))
        edit.render(res, out, fps=10)
        clip.close()
        self.assertTrue(Path(out).exists())

    def test_concat_render(self):
        a, b = str(self.tmp / "a.mp4"), str(self.tmp / "b.mp4")
        _write_video(a, duration=0.4)
        _write_video(b, duration=0.6)
        out = str(self.tmp / "cc.mp4")
        clips = [edit.load(a), edit.load(b)]
        edit.render(edit.concat(clips), out, fps=10)
        for c in clips:
            c.close()
        with VideoFileClip(out) as check:
            self.assertAlmostEqual(check.duration, 1.0, places=1)

    def test_noise_render(self):
        src = str(self.tmp / "in.mp4")
        _write_video(src, duration=0.5)
        out = str(self.tmp / "noise.mp4")
        clip = edit.load(src)
        res = edit.noise(clip, amount=0.1, mode="vhs", seed=1)
        edit.render(res, out, fps=10)
        clip.close()
        self.assertTrue(Path(out).exists())
        with VideoFileClip(out) as check:
            self.assertEqual(check.size, [160, 120])

    def test_noise_invalid_mode_raises(self):
        clip = ColorClip(size=(16, 16), color=(0, 0, 0), duration=0.2)
        try:
            with self.assertRaises(ValueError):
                edit.noise(clip, mode="nope")
        finally:
            clip.close()

    def test_add_audio_in_memory(self):
        src = str(self.tmp / "in.mp4")
        _write_video(src, duration=0.5)
        out = str(self.tmp / "au.mp4")
        clip = edit.load(src)
        res = edit.add_audio(clip, _audio_clip(0.5), start=0.0, volume=0.5)
        edit.render(res, out, fps=10)
        clip.close()
        with VideoFileClip(out) as check:
            self.assertTrue(check.audio is not None)

    # ---- full pipeline ---

    def test_render_recipe(self):
        a, b = str(self.tmp / "a.mp4"), str(self.tmp / "b.mp4")
        img = str(self.tmp / "logo.png")
        out = str(self.tmp / "final.mp4")
        _write_video(a, size=(160, 90), duration=0.5)
        _write_video(b, size=(160, 90), duration=0.5)
        _write_image(img)
        recipe = {
            "size": "180x320",
            "fps": 10,
            "background": "#000000",
            "noise": {"amount": 0.05},
            "out": out,
            "clips": [
                {"source": a, "start": 0.0, "end": 0.5,
                 "overlays": [{"image": img, "x": 5, "y": 5, "start": 0.0,
                               "duration": 0.2, "size": [16, 16]}]},
                {"source": b, "background": "#222222"},
            ],
        }
        result = edit.render_recipe(recipe)
        self.assertEqual(result["out"], out)
        self.assertTrue(Path(out).exists())
        with VideoFileClip(out) as check:
            self.assertEqual(check.size, [180, 320])
            self.assertAlmostEqual(check.duration, 1.0, places=1)

    # ---- frames ---

    def test_frames_even_spread(self):
        src = str(self.tmp / "in.mp4")
        _write_video(src, size=(160, 120), duration=1.0)
        got = edit.frames(src, count=3, out_dir=str(self.tmp / "f"))
        self.assertEqual(len(got), 3)
        for f in got:
            self.assertTrue(Path(f["path"]).is_file())
        self.assertLess(got[0]["t"], got[1]["t"])
        self.assertLess(got[1]["t"], got[2]["t"])

    def test_frames_explicit_and_width(self):
        src = str(self.tmp / "in.mp4")
        _write_video(src, size=(160, 120), duration=1.0)
        got = edit.frames(src, [0.0, 0.5], out_dir=str(self.tmp / "f2"), width=80)
        self.assertEqual([f["t"] for f in got], [0.0, 0.5])
        self.assertEqual(got[0]["size"], [80, 60])

    # ---- crop / layout ---

    def test_parse_box(self):
        self.assertEqual(edit.parse_box("10,20,30,40"), (10, 20, 30, 40))
        self.assertEqual(edit.parse_box([10, 20, 30, 40]), (10, 20, 30, 40))
        self.assertEqual(edit.parse_box({"x": 1, "y": 2, "w": 3, "h": 4}), (1, 2, 3, 4))
        self.assertEqual(edit.parse_box({"left": 1, "top": 2, "width": 3, "height": 4}),
                         (1, 2, 3, 4))
        with self.assertRaises(ValueError):
            edit.parse_box("1,2,3")

    def test_crop_size_and_clamp(self):
        src = str(self.tmp / "in.mp4")
        _write_video(src, size=(160, 90), duration=0.5)
        clip = edit.load(src)
        try:
            self.assertEqual(edit.crop(clip, (10, 10, 50, 40)).size, (50, 40))
            self.assertEqual(edit.crop(clip, (0, 0, 160, 90), size=(324, 288)).size, (324, 288))
            # out-of-bounds box is clamped to the frame
            self.assertEqual(edit.crop(clip, (150, 80, 100, 100)).size, (10, 10))
        finally:
            clip.close()

    def test_layout_render(self):
        src = str(self.tmp / "in.mp4")
        out = str(self.tmp / "layout.mp4")
        _write_video(src, size=(160, 90), duration=0.5)
        clip = edit.load(src)
        regions = [
            {"box": [0, 0, 160, 20], "size": [180, 40], "position": [0, 0]},
            {"box": [0, 20, 160, 70], "size": [180, 280], "position": [0, 40]},
        ]
        edit.render(edit.layout(clip, regions, "180x320", "#101010"), out, fps=10)
        clip.close()
        with VideoFileClip(out) as check:
            self.assertEqual(check.size, [180, 320])
            self.assertAlmostEqual(check.duration, 0.5, places=1)

    def test_compose_centers_layer(self):
        src = str(self.tmp / "in.mp4")
        _write_video(src, size=(160, 90), duration=0.4)
        clip = edit.load(src)
        try:
            canvas = edit.compose("200x400", [{"clip": clip, "size": [100, 56]}],
                                  background="#000000", duration=clip.duration)
            self.assertEqual(canvas.size, (200, 400))
        finally:
            clip.close()

    def test_compose_needs_duration(self):
        with self.assertRaises(ValueError):
            edit.compose("100x200", [])

    def test_recipe_with_regions(self):
        src = str(self.tmp / "in.mp4")
        out = str(self.tmp / "regions.mp4")
        _write_video(src, size=(160, 90), duration=0.4)
        recipe = {
            "size": "180x320", "fps": 10, "out": out,
            "clips": [{
                "source": src, "start": 0.0, "end": 0.4,
                "regions": [
                    {"box": [0, 0, 160, 20], "size": [180, 40], "position": [0, 0]},
                    {"box": [0, 20, 160, 70], "size": [180, 280], "position": [0, 40]},
                ],
            }],
        }
        result = edit.render_recipe(recipe)
        self.assertEqual(result["out"], out)
        with VideoFileClip(out) as check:
            self.assertEqual(check.size, [180, 320])

    def test_probe(self):
        src = str(self.tmp / "in.mp4")
        _write_video(src, size=(160, 90), duration=0.5)
        info = edit.probe(src)
        self.assertEqual(info["size"], [160, 90])
        self.assertFalse(info["has_audio"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
