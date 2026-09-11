"""B 模式输入后端：禁止静默空 stub、FAILSAFE、键名规范化。"""
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from harmonica.config import AppConfig, InputConfig
from harmonica.input_backend import (
    BackendUnavailable,
    KEYEVENTF_SCANCODE,
    InputBackend,
    NullBackend,
    PyDirectInputBackend,
    SendInputBackend,
    create_backend,
    key_to_scancode,
    resolve_backend,
)


class _FakeReal(InputBackend):
    def __init__(self, name: str) -> None:
        self.name = name

    def key_down(self, key: str) -> None:
        pass

    def key_up(self, key: str) -> None:
        pass

    def press_key(self, key: str, hold_ms: int) -> None:
        pass

    def click_left(self, hold_ms: int = 40) -> None:
        pass

    def click_right(self, hold_ms: int = 40) -> None:
        pass

    def left_down(self) -> None:
        pass

    def left_up(self) -> None:
        pass

    def right_down(self) -> None:
        pass

    def right_up(self) -> None:
        pass

    def middle_down(self) -> None:
        pass

    def middle_up(self) -> None:
        pass


class ResolveBackendTests(unittest.TestCase):
    def test_null_without_require_real(self) -> None:
        be, note = resolve_backend(InputConfig(backend="null"), require_real=False)
        self.assertEqual(be.name, "null")
        self.assertIsInstance(be, NullBackend)
        self.assertIn("null", (note or "").lower())

    def test_null_require_real_raises(self) -> None:
        with self.assertRaises(BackendUnavailable) as ctx:
            resolve_backend(InputConfig(backend="null"), require_real=True)
        self.assertIn("null", str(ctx.exception).lower())

    def test_create_backend_null_sets_last_error(self) -> None:
        be = create_backend(InputConfig(backend="null"))
        self.assertEqual(be.name, "null")
        self.assertIsInstance(be, NullBackend)
        from harmonica import input_backend as m
        self.assertIsNotNone(m.LAST_BACKEND_ERROR)
        self.assertIn("null", (m.LAST_BACKEND_ERROR or "").lower())

    def test_unknown_require_real_raises(self) -> None:
        def boom(_name: str):
            raise ImportError("missing")

        with patch("harmonica.input_backend._try_construct", side_effect=boom):
            with self.assertRaises(BackendUnavailable):
                resolve_backend(InputConfig(backend="not-a-backend"), require_real=True)

    def test_create_backend_both_fail_returns_null_and_error(self) -> None:
        def boom(_name: str):
            raise ImportError("missing lib")

        with patch("harmonica.input_backend._try_construct", side_effect=boom):
            be = create_backend(InputConfig(backend="pydirectinput"))
        self.assertEqual(be.name, "null")
        from harmonica import input_backend as m
        self.assertIn("pydirectinput", m.LAST_BACKEND_ERROR or "")

    def test_require_real_does_not_play_null_when_both_fail(self) -> None:
        def boom(_name: str):
            raise ImportError("missing lib")

        with patch("harmonica.input_backend._try_construct", side_effect=boom):
            with self.assertRaises(BackendUnavailable) as ctx:
                resolve_backend(InputConfig(backend="pydirectinput"), require_real=True)
        self.assertIn("pydirectinput", str(ctx.exception))
        self.assertIn("无法创建", str(ctx.exception))

    def test_fallback_to_second_real_backend(self) -> None:
        def construct(name: str):
            if name == "pydirectinput":
                raise ImportError("no pydirectinput")
            if name == "sendinput":
                raise ImportError("no sendinput")
            if name == "keyboard_ctypes":
                return _FakeReal("keyboard_ctypes")
            raise AssertionError(name)

        with patch("harmonica.input_backend._try_construct", side_effect=construct):
            be = create_backend(InputConfig(backend="pydirectinput"))
        self.assertEqual(be.name, "keyboard_ctypes")
        self.assertNotEqual(be.name, "null")
        self.assertIsNotNone(be.warning)
        self.assertIn("keyboard_ctypes", be.warning or "")
        from harmonica import input_backend as m
        self.assertIsNone(m.LAST_BACKEND_ERROR)

    def test_prefers_sendinput_when_available(self) -> None:
        def construct(name: str):
            if name == "sendinput":
                return _FakeReal("sendinput")
            raise ImportError(name)

        with patch("harmonica.input_backend._try_construct", side_effect=construct):
            be = create_backend(InputConfig(backend="sendinput"))
        self.assertEqual(be.name, "sendinput")
        from harmonica import input_backend as m
        self.assertIsNone(m.LAST_BACKEND_ERROR)

    def test_keyboard_alias(self) -> None:
        def construct(name: str):
            if name == "keyboard_ctypes":
                return _FakeReal("keyboard_ctypes")
            raise ImportError(name)

        with patch("harmonica.input_backend._try_construct", side_effect=construct):
            be, _note = resolve_backend(InputConfig(backend="keyboard"), require_real=True)
        self.assertEqual(be.name, "keyboard_ctypes")


class ConfigBackendAliasTests(unittest.TestCase):
    def test_legacy_keyboard_name(self) -> None:
        cfg = AppConfig.from_dict({"input": {"backend": "keyboard"}})
        self.assertEqual(cfg.input.backend, "keyboard_ctypes")

    def test_garbage_backend_defaults(self) -> None:
        cfg = AppConfig.from_dict({"input": {"backend": "???"}})
        self.assertEqual(cfg.input.backend, "sendinput")


class PyDirectInputBackendTests(unittest.TestCase):
    def test_failsafe_off_and_keys_lowercased(self) -> None:
        calls = []
        mod = types.ModuleType("pydirectinput")
        mod.PAUSE = 0.1
        mod.FAILSAFE = True

        def keyDown(key, _pause=True):
            calls.append(("down", key, _pause))
            return True

        def keyUp(key, _pause=True):
            calls.append(("up", key, _pause))
            return True

        def mouseDown(button="left", _pause=True):
            calls.append(("mdown", button))

        def mouseUp(button="left", _pause=True):
            calls.append(("mup", button))

        mod.keyDown = keyDown
        mod.keyUp = keyUp
        mod.mouseDown = mouseDown
        mod.mouseUp = mouseUp
        sys.modules["pydirectinput"] = mod
        try:
            be = PyDirectInputBackend()
            self.assertIs(mod.FAILSAFE, False)
            self.assertEqual(mod.PAUSE, 0)
            be.press_key("Z", 0)
            be.middle_down()
            be.middle_up()
        finally:
            sys.modules.pop("pydirectinput", None)
        self.assertEqual(calls[0], ("down", "z", False))
        self.assertEqual(calls[1], ("up", "z", False))
        self.assertIn(("mdown", "middle"), calls)
        self.assertIn(("mup", "middle"), calls)

    def test_keyDown_false_raises(self) -> None:
        mod = types.ModuleType("pydirectinput")
        mod.PAUSE = 0
        mod.FAILSAFE = True
        mod.keyDown = lambda key, _pause=True: False
        mod.keyUp = lambda key, _pause=True: True
        sys.modules["pydirectinput"] = mod
        try:
            be = PyDirectInputBackend()
            with self.assertRaises(RuntimeError) as ctx:
                be.press_key("z", 0)
            self.assertIn("未成功发送", str(ctx.exception))
        finally:
            sys.modules.pop("pydirectinput", None)


class SendInputBackendTests(unittest.TestCase):
    def test_scancodes_for_harmonica_keys(self) -> None:
        self.assertEqual(key_to_scancode("z"), 0x2C)
        self.assertEqual(key_to_scancode("m"), 0x32)
        self.assertEqual(key_to_scancode(","), 0x33)
        self.assertEqual(key_to_scancode("Z"), 0x2C)
        self.assertEqual(key_to_scancode("comma"), 0x33)

    def test_construct_without_user32_fails_off_windows(self) -> None:
        if sys.platform == "win32":
            self.skipTest("Windows 上 SendInput 可用")
        with self.assertRaises(BackendUnavailable):
            SendInputBackend()

    def test_mocked_sendinput_uses_scancode_and_mouse_flags(self) -> None:
        sent = []

        class FakeUser32:
            def SendInput(self, n, arr, size):
                item = arr[0]
                if int(item.type) == 1:  # INPUT_KEYBOARD
                    sent.append(("key", int(item.union.ki.wScan), int(item.union.ki.dwFlags)))
                else:
                    sent.append(("mouse", int(item.union.mi.dwFlags)))
                return n

        be = SendInputBackend(_user32=FakeUser32())
        be.key_down("z")
        be.left_down()
        be.right_down()
        be.middle_down()
        be.key_up(",")
        be.middle_up()
        be.left_up()
        be.right_up()
        self.assertEqual(sent[0][0], "key")
        self.assertEqual(sent[0][1], 0x2C)
        self.assertTrue(sent[0][2] & KEYEVENTF_SCANCODE)
        self.assertEqual(sent[1], ("mouse", 0x0002))  # left down
        self.assertEqual(sent[2], ("mouse", 0x0008))  # right down
        self.assertEqual(sent[3], ("mouse", 0x0020))  # middle down
        self.assertEqual(sent[4][1], 0x33)
        self.assertTrue(sent[4][2] & KEYEVENTF_SCANCODE)
        self.assertTrue(sent[4][2] & 0x0002)  # key up
        self.assertEqual(sent[5], ("mouse", 0x0040))  # middle up

    def test_sendinput_incomplete_raises(self) -> None:
        class FakeUser32:
            def SendInput(self, n, arr, size):
                return 0

        be = SendInputBackend(_user32=FakeUser32())
        with self.assertRaises(RuntimeError) as ctx:
            be.key_down("z")
        self.assertIn("SendInput", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
