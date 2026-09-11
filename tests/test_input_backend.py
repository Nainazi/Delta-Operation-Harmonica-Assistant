"""B 模式输入后端：禁止静默空 stub、FAILSAFE、键名规范化。"""
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from harmonica.config import AppConfig, InputConfig
from harmonica.input_backend import (
    BackendUnavailable,
    InputBackend,
    NullBackend,
    PyDirectInputBackend,
    create_backend,
    resolve_backend,
)


class _FakeReal(InputBackend):
    def __init__(self, name: str) -> None:
        self.name = name

    def press_key(self, key: str, hold_ms: int) -> None:
        pass

    def click_left(self, hold_ms: int = 40) -> None:
        pass

    def click_right(self, hold_ms: int = 40) -> None:
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
        self.assertIsNone(note)

    def test_null_require_real_raises(self) -> None:
        with self.assertRaises(BackendUnavailable) as ctx:
            resolve_backend(InputConfig(backend="null"), require_real=True)
        self.assertIn("null", str(ctx.exception).lower())

    def test_create_backend_require_real_null_raises(self) -> None:
        with self.assertRaises(BackendUnavailable):
            create_backend(InputConfig(backend="null"), require_real=True)

    def test_unknown_require_real_raises(self) -> None:
        with self.assertRaises(BackendUnavailable):
            resolve_backend(InputConfig(backend="not-a-backend"), require_real=True)

    def test_require_real_does_not_return_null_when_both_fail(self) -> None:
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
            if name == "keyboard_ctypes":
                return _FakeReal("keyboard_ctypes")
            raise AssertionError(name)

        with patch("harmonica.input_backend._try_construct", side_effect=construct):
            be, note = resolve_backend(
                InputConfig(backend="pydirectinput"), require_real=True)
        self.assertEqual(be.name, "keyboard_ctypes")
        self.assertNotEqual(be.name, "null")
        self.assertIsNotNone(note)
        self.assertIn("keyboard_ctypes", note or "")

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
        self.assertEqual(cfg.input.backend, "pydirectinput")


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


if __name__ == "__main__":
    unittest.main()
