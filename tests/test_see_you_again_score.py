"""内置曲谱 See You Again 练习片段。"""
from __future__ import annotations

import os
import unittest

from harmonica.config import builtin_scores_dir
from harmonica.score_parser import parse


class SeeYouAgainScoreTests(unittest.TestCase):
    def test_file_exists_and_parses(self) -> None:
        path = os.path.join(builtin_scores_dir(), "see_you_again_1p5x.txt")
        self.assertTrue(os.path.isfile(path), path)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        self.assertIn("See You Again（1.5倍速梗）", text)
        self.assertIn("@bpm 150", text)
        self.assertNotIn("琵琶", text)
        result = parse(text)
        self.assertGreater(len(result.events), 0)
        self.assertEqual(result.bpm_override, 150.0)
