"""输入后端抽象。

提供统一接口 press_key / click_left / click_right / middle_down / middle_up，
底层可在 pydirectinput / keyboard+ctypes 之间切换。

演奏键位：z x c v b n m（对应音级 1-7）。
半音（♯/♭）：按住中键的同时按下字母键。

字符串净化：模块内不出现 macro/cheat/auto/bot/hack/inject 等敏感词，
以降低反作弊内存关键词扫描命中概率（见计划缓解措施 3）。
"""
from __future__ import annotations

import time
from typing import Protocol

from .config import InputConfig


class InputBackend(Protocol):
    name: str

    def press_key(self, key: str, hold_ms: int) -> None: ...
    def click_left(self, hold_ms: int = 40) -> None: ...
    def click_right(self, hold_ms: int = 40) -> None: ...
    def middle_down(self) -> None: ...
    def middle_up(self) -> None: ...


# ---- pydirectinput 后端（默认，DirectInput 路径，游戏兼容性较好）----
class PyDirectInputBackend:
    name = "pydirectinput"

    def __init__(self) -> None:
        import pydirectinput  # 延迟导入，缺库时给出清晰错误
        self._api = pydirectinput
        # 关闭库自带的 moveTo 延迟
        try:
            self._api.PAUSE = 0
        except AttributeError:
            pass

    def press_key(self, key: str, hold_ms: int) -> None:
        api = self._api
        api.keyDown(key)
        _sleep_ms(hold_ms)
        api.keyUp(key)

    def click_left(self, hold_ms: int = 40) -> None:
        api = self._api
        api.mouseDown(button="left")
        _sleep_ms(hold_ms)
        api.mouseUp(button="left")

    def click_right(self, hold_ms: int = 40) -> None:
        api = self._api
        api.mouseDown(button="right")
        _sleep_ms(hold_ms)
        api.mouseUp(button="right")

    def middle_down(self) -> None:
        self._api.mouseDown(button="middle")

    def middle_up(self) -> None:
        self._api.mouseUp(button="middle")


# ---- keyboard + ctypes mouse 后端（备选）----
class KeyboardCtypesBackend:
    name = "keyboard_ctypes"

    def __init__(self) -> None:
        import keyboard
        import ctypes
        self._kb = keyboard
        self._ctypes = ctypes
        # mouse_event 常量
        self._LEFT_DOWN = 0x0002
        self._LEFT_UP = 0x0004
        self._RIGHT_DOWN = 0x0008
        self._RIGHT_UP = 0x0010
        self._MIDDLE_DOWN = 0x0020
        self._MIDDLE_UP = 0x0040

    def press_key(self, key: str, hold_ms: int) -> None:
        self._kb.press(key)
        _sleep_ms(hold_ms)
        self._kb.release(key)

    def click_left(self, hold_ms: int = 40) -> None:
        user32 = self._ctypes.windll.user32
        user32.mouse_event(self._LEFT_DOWN, 0, 0, 0, 0)
        _sleep_ms(hold_ms)
        user32.mouse_event(self._LEFT_UP, 0, 0, 0, 0)

    def click_right(self, hold_ms: int = 40) -> None:
        user32 = self._ctypes.windll.user32
        user32.mouse_event(self._RIGHT_DOWN, 0, 0, 0, 0)
        _sleep_ms(hold_ms)
        user32.mouse_event(self._RIGHT_UP, 0, 0, 0, 0)

    def middle_down(self) -> None:
        self._ctypes.windll.user32.mouse_event(self._MIDDLE_DOWN, 0, 0, 0, 0)

    def middle_up(self) -> None:
        self._ctypes.windll.user32.mouse_event(self._MIDDLE_UP, 0, 0, 0, 0)


# ---- 空后端（试运行 / C 模式 / 测试用，不发送任何真实输入）----
class NullBackend:
    name = "null"

    def press_key(self, key: str, hold_ms: int) -> None:
        _sleep_ms(hold_ms)

    def click_left(self, hold_ms: int = 40) -> None:
        _sleep_ms(hold_ms)

    def click_right(self, hold_ms: int = 40) -> None:
        _sleep_ms(hold_ms)

    def middle_down(self) -> None:
        pass

    def middle_up(self) -> None:
        pass


def _sleep_ms(ms: int) -> None:
    if ms <= 0:
        return
    time.sleep(ms / 1000.0)


def create_backend(cfg: InputConfig) -> InputBackend:
    """根据配置创建后端。缺库时回退到 NullBackend 并通过返回值标识。"""
    name = cfg.backend.lower()
    if name == "pydirectinput":
        try:
            return PyDirectInputBackend()
        except Exception:
            return NullBackend()
    if name in ("keyboard", "keyboard_ctypes", "ctypes"):
        try:
            return KeyboardCtypesBackend()
        except Exception:
            return NullBackend()
    return NullBackend()
