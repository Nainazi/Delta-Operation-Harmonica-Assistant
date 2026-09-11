"""音级 / 八度 / 半音 → 按键与鼠标修饰。"""
from __future__ import annotations

import unittest

from harmonica.note_map import format_play_hint, map_event, map_note
from harmonica.score_parser import NoteEvent, parse


class NoteMapTests(unittest.TestCase):
    def test_base_degree_is_letter_without_mouse(self) -> None:
        m = map_note(1, 0, 0)
        self.assertEqual(m.key, "z")
        self.assertFalse(m.left)
        self.assertFalse(m.right)
        self.assertFalse(m.middle)
        self.assertEqual(format_play_hint(m), "z")
        self.assertEqual(tuple(m.mouse_buttons), ())

    def test_accidental_holds_middle(self) -> None:
        sharp = map_note(1, 1, 0)
        flat = map_note(3, -1, 0)
        self.assertTrue(sharp.middle)
        self.assertTrue(flat.middle)
        self.assertFalse(sharp.left)
        self.assertFalse(sharp.right)
        self.assertEqual(sharp.key, "z")
        self.assertEqual(flat.key, "c")
        self.assertEqual(format_play_hint(sharp), "中键+z")
        self.assertEqual(tuple(sharp.mouse_buttons), ("middle",))

    def test_octave_minus_one_holds_left(self) -> None:
        m = map_note(5, 0, -1)
        self.assertTrue(m.left)
        self.assertFalse(m.right)
        self.assertEqual(m.key, "b")
        self.assertEqual(format_play_hint(m), "左键+b")

    def test_octave_plus_one_holds_right(self) -> None:
        m = map_note(2, 0, 1)
        self.assertTrue(m.right)
        self.assertFalse(m.left)
        self.assertEqual(m.key, "x")
        self.assertEqual(format_play_hint(m), "右键+x")

    def test_top_high_do_is_comma_with_right(self) -> None:
        m = map_note(1, 0, 2)
        self.assertEqual(m.key, ",")
        self.assertTrue(m.right)
        self.assertFalse(m.left)
        self.assertFalse(m.middle)
        self.assertEqual(m.display_key, "，")
        self.assertEqual(format_play_hint(m), "右键+，")

    def test_top_sharp_do_combines_right_middle_comma(self) -> None:
        m = map_note(1, 1, 2)
        self.assertEqual(m.key, ",")
        self.assertTrue(m.right)
        self.assertTrue(m.middle)
        self.assertFalse(m.left)
        self.assertEqual(format_play_hint(m), "右键+中键+，")
        self.assertEqual(tuple(m.mouse_buttons), ("right", "middle"))

    def test_low_sharp_combines_left_and_middle(self) -> None:
        m = map_note(1, 1, -1)
        self.assertEqual(m.key, "z")
        self.assertTrue(m.left)
        self.assertTrue(m.middle)
        self.assertEqual(format_play_hint(m), "左键+中键+z")

    def test_parse_tokens_round_trip_to_mapping(self) -> None:
        cases = {
            "1": ("z", False, False, False),
            "#1": ("z", False, False, True),
            "1^": ("z", False, True, False),
            "1,": ("z", True, False, False),
            "1^^": (",", False, True, False),
            "#1^^": (",", False, True, True),
        }
        for tok, expected in cases.items():
            with self.subTest(tok=tok):
                ev = parse(tok).events[0]
                m = map_event(ev)
                self.assertEqual(
                    (m.key, m.left, m.right, m.middle), expected, tok
                )

    def test_uppercase_keymap(self) -> None:
        ev = NoteEvent(degree=1, accidental=0, beats=1.0, octave=0)
        m = map_event(ev, {1: "Z"})
        self.assertEqual(m.key, "z")


if __name__ == "__main__":
    unittest.main()
