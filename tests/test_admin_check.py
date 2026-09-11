"""管理员提权检测：不循环 UAC，未提权才警告。"""
from __future__ import annotations

import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from harmonica import admin_check
from harmonica.admin_check import (
    UNELEVATED_HINT,
    is_elevated,
    relaunch_command,
    relaunch_elevated,
    should_warn_unelevated,
)


class ElevationDetectTests(unittest.TestCase):
    def test_hint_text(self) -> None:
        self.assertIn("管理员", UNELEVATED_HINT)
        self.assertIn("游戏若也是管理员", UNELEVATED_HINT)

    def test_non_windows_unknown(self) -> None:
        with patch.object(sys, "platform", "linux"):
            self.assertIsNone(is_elevated())
            self.assertFalse(should_warn_unelevated())

    def test_windows_not_admin_warns(self) -> None:
        shell32 = MagicMock()
        shell32.IsUserAnAdmin.return_value = 0
        fake_ctypes = types.SimpleNamespace(windll=types.SimpleNamespace(shell32=shell32))
        with patch.object(sys, "platform", "win32"), \
             patch.dict(sys.modules, {"ctypes": fake_ctypes}):
            self.assertIs(is_elevated(), False)
            self.assertTrue(should_warn_unelevated())

    def test_windows_admin_no_warn(self) -> None:
        shell32 = MagicMock()
        shell32.IsUserAnAdmin.return_value = 1
        fake_ctypes = types.SimpleNamespace(windll=types.SimpleNamespace(shell32=shell32))
        with patch.object(sys, "platform", "win32"), \
             patch.dict(sys.modules, {"ctypes": fake_ctypes}):
            self.assertIs(is_elevated(), True)
            self.assertFalse(should_warn_unelevated())

    def test_detect_failure_does_not_warn(self) -> None:
        shell32 = MagicMock()
        shell32.IsUserAnAdmin.side_effect = OSError("nope")
        fake_ctypes = types.SimpleNamespace(windll=types.SimpleNamespace(shell32=shell32))
        with patch.object(sys, "platform", "win32"), \
             patch.dict(sys.modules, {"ctypes": fake_ctypes}):
            self.assertIsNone(is_elevated())
            self.assertFalse(should_warn_unelevated())


class RelaunchTests(unittest.TestCase):
    def test_frozen_uses_exe_and_extra_args(self) -> None:
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", r"C:\app\harmonica.exe"), \
             patch.object(sys, "argv", [r"C:\app\harmonica.exe", "--mode", "B"]):
            exe, params = relaunch_command()
        self.assertEqual(exe, r"C:\app\harmonica.exe")
        self.assertIn("--mode", params)
        self.assertIn("B", params)

    def test_module_launch_uses_dash_m(self) -> None:
        with patch.object(sys, "frozen", False, create=True), \
             patch.object(sys, "executable", sys.executable), \
             patch.object(sys, "argv", [os.path.join("pkg", "__main__.py")]):
            exe, params = relaunch_command()
        self.assertEqual(exe, sys.executable)
        self.assertTrue(params.startswith("-m harmonica") or params.startswith('"-m"'))
        self.assertIn("harmonica", params)

    def test_relaunch_skipped_when_already_elevated(self) -> None:
        with patch.object(sys, "platform", "win32"), \
             patch.object(admin_check, "is_elevated", return_value=True):
            ok, msg = relaunch_elevated()
        self.assertFalse(ok)
        self.assertIn("已是管理员", msg)

    def test_relaunch_non_windows(self) -> None:
        with patch.object(sys, "platform", "linux"):
            ok, msg = relaunch_elevated()
        self.assertFalse(ok)
        self.assertIn("Windows", msg)

    def test_uac_cancel_does_not_retry(self) -> None:
        shell32 = MagicMock()
        shell32.ShellExecuteW.return_value = 5  # ERROR_ACCESS_DENIED / cancelled-ish
        fake_ctypes = types.SimpleNamespace(windll=types.SimpleNamespace(shell32=shell32))
        with patch.object(sys, "platform", "win32"), \
             patch.object(admin_check, "is_elevated", return_value=False), \
             patch.object(admin_check, "relaunch_command", return_value=("python", "-m harmonica")), \
             patch.dict(sys.modules, {"ctypes": fake_ctypes}):
            ok, msg = relaunch_elevated()
        self.assertFalse(ok)
        self.assertIn("保持不变", msg)
        shell32.ShellExecuteW.assert_called_once()


if __name__ == "__main__":
    unittest.main()
