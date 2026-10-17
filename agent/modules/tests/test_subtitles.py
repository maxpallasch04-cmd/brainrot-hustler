"""Offline tests for the subtitle layer (no network).

Run: python3 tests/test_subtitles.py
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from moviepy import ColorClip, VideoFileClip  # noqa: E402

from subtitles import subs  # noqa: E402

SRT = """1
00:00:01,000 --> 00:00:03,500
Hello <i>world</i>

2
00:00:04,000 --> 00:00:06,000
what a line!
"""

VTT = """WEBVTT

NOTE auto-generated

00:00:01.000 --> 00:00:03.000 align:start position:10%
hi there

00:00:03.000 --> 00:00:05.000
hi there

00:01:00.000 --> 00:01:02.000
second half
"""

WORD_VTT = """WEBVTT

00:00:01.000 --> 00:00:04.000 align:start position:10%
hello<00:00:01.500><c> world</c><00:00:02.200><c> again.</c>

00:00:04.500 --> 00:00:06.000
new<00:00:04.600><c> sentence</c>
"""


class ParseTest(unittest.TestCase):
    def test_parse_srt_strips_tags(self):
        cues = subs.parse(SRT)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0]["text"], "Hello world")
        self.assertAlmostEqual(cues[0]["start"], 1.0, places=3)
        self.assertAlmostEqual(cues[1]["end"], 6.0, places=3)

    def test_parse_vtt_cue_settings_and_dedupe(self):
        cues = subs.parse(VTT)
        self.assertEqual(len(cues), 3)  # NOTE block ignored
        self.assertEqual(cues[0]["text"], "hi there")
        cleaned = subs.dedupe(cues)
        self.assertEqual(len(cleaned), 2)
        self.assertAlmostEqual(cleaned[0]["end"], 5.0, places=3)

    def test_parse_ts_with_hours(self):
        self.assertAlmostEqual(subs._parse_ts("01:02:03.500"), 3723.5, places=3)
        self.assertAlmostEqual(subs._parse_ts("02:03.500"), 123.5, places=3)


class WindowTest(unittest.TestCase):
    def test_window_offsets_and_clamps(self):
        cues = subs.parse(SRT)
        got = subs.window(cues, 2.0, 5.0)
        self.assertEqual(len(got), 2)
        self.assertAlmostEqual(got[0]["start"], 0.0, places=3)   # clamped at 2.0
        self.assertAlmostEqual(got[0]["end"], 1.5, places=3)
        self.assertAlmostEqual(got[1]["start"], 2.0, places=3)
        self.assertAlmostEqual(got[1]["end"], 3.0, places=3)     # clamped at 5.0

    def test_window_absolute_keeps_timestamps(self):
        got = subs.window(subs.parse(SRT), 2.0, 5.0, offset=False)
        self.assertAlmostEqual(got[0]["start"], 2.0, places=3)

    def test_window_empty_outside(self):
        self.assertEqual(subs.window(subs.parse(SRT), 100.0, 101.0), [])

    def test_to_srt_format(self):
        text = subs.to_srt([{"start": 0.0, "end": 1.5, "text": "a"}])
        self.assertIn("00:00:00,000 --> 00:00:01,500", text)
        self.assertTrue(text.startswith("1\n"))


class WordsTest(unittest.TestCase):
    def test_words_from_inline_tags(self):
        got = subs.words(subs.parse(WORD_VTT))
        self.assertEqual([w["word"] for w in got],
                         ["hello", "world", "again.", "new", "sentence"])
        self.assertAlmostEqual(got[0]["start"], 1.0, places=3)
        self.assertAlmostEqual(got[1]["start"], 1.5, places=3)
        self.assertAlmostEqual(got[2]["start"], 2.2, places=3)
        self.assertNotIn("approx", got[0])

    def test_words_fallback_is_approx(self):
        got = subs.words(subs.parse(VTT))
        self.assertTrue(got)
        self.assertTrue(all(w.get("approx") for w in got))

    def test_sentences_split_on_punctuation(self):
        got = subs.sentences(subs.words(subs.parse(WORD_VTT)))
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0]["text"], "hello world again.")
        self.assertAlmostEqual(got[0]["start"], 1.0, places=3)
        self.assertAlmostEqual(got[0]["end"], 4.0, places=3)

    def test_snap_before_after_and_word(self):
        words = subs.words(subs.parse(WORD_VTT))
        before = subs.snap(2.3, words, mode="sentence", direction="before")
        self.assertEqual(before["snapped"], 1.0)
        self.assertEqual(before["text"], "hello world again.")
        after = subs.snap(2.3, words, mode="sentence", direction="after")
        self.assertEqual(after["snapped"], 4.0)
        word = subs.snap(2.3, words, mode="word", direction="before")
        self.assertEqual(word["snapped"], 2.2)

    def test_window_words_is_small(self):
        words = subs.words(subs.parse(WORD_VTT))
        got = subs.window_words(words, 2.0, seconds=0.3)
        self.assertEqual([w["word"] for w in got], ["world", "again."])
        self.assertLessEqual(len(subs.window_words(words, 2.0, seconds=100,
                                                   limit=2)), 2)


class NumbersTest(unittest.TestCase):
    def test_digits_and_range(self):
        cues = subs.parse("1\n00:00:01,000 --> 00:00:02,000\nthat is a 8.25\n\n"
                          "2\n00:00:03,000 --> 00:00:04,000\ngets a 3.5 from the judges\n")
        hits = subs.find_numbers(cues)
        self.assertEqual([h["value"] for h in hits], [8.25, 3.5])
        self.assertEqual([h["value"] for h in subs.find_numbers(cues, lo=8)], [8.25])
        self.assertEqual([h["value"] for h in subs.find_numbers(cues, hi=5)], [3.5])

    def test_spelled_out(self):
        cues = [{"start": 5.0, "end": 6.0, "text": "nine point five!"}]
        hits = subs.find_numbers(cues)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["value"], 9.5)
        self.assertEqual(hits[0]["kind"], "words")

    def test_no_numbers(self):
        cues = [{"start": 0.0, "end": 1.0, "text": "what a line"}]
        self.assertEqual(subs.find_numbers(cues), [])


class StyleTest(unittest.TestCase):
    def test_build_style(self):
        self.assertEqual(
            subs.build_style(font_size=64, outline=3, alignment=2, margin_v=220),
            "FontSize=64,Outline=3,Alignment=2,MarginV=220")
        self.assertIsNone(subs.build_style())


class BurnTest(unittest.TestCase):
    def test_burn_hardsubs_and_keeps_size(self):
        tmp = Path(tempfile.mkdtemp())
        video = tmp / "clip.mp4"
        clip = ColorClip(size=(160, 90), color=(30, 30, 30), duration=1.0)
        clip.write_videofile(str(video), fps=10, codec="libx264", audio=False, logger=None)
        clip.close()

        srt = tmp / "clip.srt"
        subs.write_srt([{"start": 0.1, "end": 0.9, "text": "what a line!"}], srt)

        out = tmp / "out.mp4"
        got = subs.burn(video, srt, out, force_style=subs.build_style(font_size=24, outline=2))
        self.assertTrue(Path(got).exists())
        with VideoFileClip(str(out)) as check:
            self.assertEqual(check.size, [160, 90])
            self.assertAlmostEqual(check.duration, 1.0, places=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
