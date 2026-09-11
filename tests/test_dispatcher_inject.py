"""Dispatcher B 模式必须调用真实后端 press/release，而不是空跑。"""
from __future__ import annotations

import unittest

from harmonica.config import AppConfig
from harmonica.dispatcher import Dispatcher
from harmonica.input_backend import InputBackend, NullBackend
from harmonica.score_parser import NoteEvent, parse


class RecordingBackend(InputBackend):
    name = "recording"

    def __init__(self) -> None:
        self.events = []

    def press_key(self, key: str, hold_ms: int) -> None:
        self.events.append(("press", key, hold_ms))

    def click_left(self, hold_ms: int = 40) -> None:
        self.events.append(("left", hold_ms))

    def click_right(self, hold_ms: int = 40) -> None:
        self.events.append(("right", hold_ms))

    def middle_down(self) -> None:
        self.events.append(("middle_down",))

    def middle_up(self) -> None:
        self.events.append(("middle_up",))


def _fast_cfg() -> AppConfig:
    cfg = AppConfig()
    cfg.timing.bpm = 600
    cfg.timing.beat_seconds = 0.01
    cfg.humanize.enabled = False
    cfg.humanize.press_hold_ms = 1
    cfg.humanize.inter_note_gap_ms = 0
    cfg.timing.key_before_click = False
    return cfg


class DispatcherInjectTests(unittest.TestCase):
    def test_play_b_sends_letter_keys(self) -> None:
        rec = RecordingBackend()
        result = parse("1 2")
        d = Dispatcher(_fast_cfg(), backend=rec)
        d.play_b(result.events)
        d.wait(2.0)
        presses = [e for e in rec.events if e[0] == "press"]
        self.assertEqual([p[1] for p in presses], ["z", "x"])
        self.assertNotEqual(rec.name, "null")

    def test_play_b_accidental_holds_middle(self) -> None:
        rec = RecordingBackend()
        result = parse("#1")
        d = Dispatcher(_fast_cfg(), backend=rec)
        d.play_b(result.events)
        d.wait(2.0)
        kinds = [e[0] for e in rec.events]
        self.assertIn("middle_down", kinds)
        self.assertIn("press", kinds)
        self.assertIn("middle_up", kinds)
        # 推荐顺序：先中键再字母
        down_i = kinds.index("middle_down")
        press_i = kinds.index("press")
        up_i = kinds.index("middle_up")
        self.assertLess(down_i, press_i)
        self.assertLess(press_i, up_i)
        self.assertEqual(rec.events[press_i][1], "z")

    def test_play_c_does_not_press(self) -> None:
        rec = RecordingBackend()
        result = parse("1 #2")
        d = Dispatcher(_fast_cfg(), backend=rec)
        d.play_c(result.events)
        d.wait(2.0)
        presses = [e for e in rec.events if e[0] == "press"]
        mids = [e for e in rec.events if e[0] in ("middle_down",)]
        self.assertEqual(presses, [])
        self.assertEqual(mids, [])

    def test_default_backend_is_null_not_inject(self) -> None:
        d = Dispatcher(_fast_cfg())
        self.assertIsInstance(d.backend, NullBackend)

    def test_on_error_when_backend_raises(self) -> None:
        class Boom(RecordingBackend):
            def press_key(self, key: str, hold_ms: int) -> None:
                raise RuntimeError("send failed")

        seen = []
        result = parse("1")
        d = Dispatcher(_fast_cfg(), backend=Boom(), on_error=seen.append)
        d.play_b(result.events)
        d.wait(2.0)
        self.assertTrue(seen)
        self.assertIsInstance(d.last_error, RuntimeError)

    def test_uppercase_keymap_still_sends_letter(self) -> None:
        rec = RecordingBackend()
        cfg = _fast_cfg()
        cfg.input.key_map = {1: "Z", 2: "X", 3: "C", 4: "V", 5: "B", 6: "N", 7: "M"}
        ev = NoteEvent(degree=1, accidental=0, beats=1.0, octave=0)
        d = Dispatcher(cfg, backend=rec)
        d.play_b([ev])
        d.wait(2.0)
        presses = [e for e in rec.events if e[0] == "press"]
        self.assertEqual(presses[0][1], "z")


if __name__ == "__main__":
    unittest.main()
