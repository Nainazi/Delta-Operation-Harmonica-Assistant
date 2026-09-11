"""按键保持应跟踪音符时值，而不是固定脉冲。"""
from __future__ import annotations

import random
import unittest

from harmonica.config import HumanizeConfig
from harmonica.humanizer import (
    HOLD_RATIO_MAX,
    HOLD_RATIO_MIN,
    KEYUP_PAD_MS,
    humanize_event,
    humanize_hold,
)


class HumanizeHoldTests(unittest.TestCase):
    def test_hold_is_about_87_percent_when_jitter_off(self) -> None:
        cfg = HumanizeConfig(enabled=False, press_hold_ms=45)
        rng = random.Random(0)
        duration_s = 0.400
        hold = humanize_hold(cfg, rng, duration_s=duration_s)
        expected = int(round(400 * (HOLD_RATIO_MIN + HOLD_RATIO_MAX) / 2.0))
        self.assertEqual(hold, expected)
        self.assertGreaterEqual(hold, int(400 * HOLD_RATIO_MIN) - 1)
        self.assertLessEqual(hold, int(400 * HOLD_RATIO_MAX) + 1)
        self.assertLessEqual(hold, 400 - KEYUP_PAD_MS)

    def test_hold_respects_press_hold_floor_on_long_notes(self) -> None:
        cfg = HumanizeConfig(enabled=False, press_hold_ms=200)
        hold = humanize_hold(cfg, random.Random(0), duration_s=0.250)
        # 250ms * 0.875 = 219，且不低于 200，并留 8ms 抬键
        self.assertGreaterEqual(hold, 200)
        self.assertLessEqual(hold, 250 - KEYUP_PAD_MS)

    def test_short_note_caps_below_duration_for_keyup(self) -> None:
        cfg = HumanizeConfig(enabled=False, press_hold_ms=45)
        hold = humanize_hold(cfg, random.Random(0), duration_s=0.020)
        self.assertGreaterEqual(hold, 1)
        self.assertLessEqual(hold, max(1, 20 - KEYUP_PAD_MS))

    def test_humanize_event_passes_duration_into_hold(self) -> None:
        cfg = HumanizeConfig(enabled=False, press_hold_ms=20)
        rng = random.Random(1)
        timing = humanize_event(1.0, 0.5, cfg, rng, first=True)
        self.assertAlmostEqual(timing.duration_s, 0.5)
        mid = int(round(500 * (HOLD_RATIO_MIN + HOLD_RATIO_MAX) / 2.0))
        self.assertEqual(timing.hold_ms, mid)
        self.assertLess(timing.hold_ms, int(timing.duration_s * 1000))

    def test_enabled_hold_stays_in_ratio_band(self) -> None:
        cfg = HumanizeConfig(enabled=True, press_hold_ms=20, seed=7)
        rng = random.Random(7)
        duration_s = 0.8
        holds = [humanize_hold(cfg, rng, duration_s=duration_s) for _ in range(40)]
        lo = int(800 * HOLD_RATIO_MIN) - 2
        hi = int(800 * HOLD_RATIO_MAX) + 2
        for h in holds:
            self.assertGreaterEqual(h, lo)
            self.assertLessEqual(h, hi)
            self.assertLessEqual(h, 800 - KEYUP_PAD_MS)

    def test_legacy_pulse_without_duration(self) -> None:
        cfg = HumanizeConfig(enabled=False, press_hold_ms=45)
        self.assertEqual(humanize_hold(cfg, random.Random(0)), 45)


if __name__ == "__main__":
    unittest.main()
