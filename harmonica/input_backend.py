"""输入后端抽象。

提供统一接口 press_key / click_left / click_right / middle_down / middle_up，
底层可在 pydirectinput / keyboard+ctypes 之间切换。

演奏键位：z x c v b n m（对应音级 1-7）。
半音（♯/♭）：按住中键的同时按下字母键。
"""
from __future__ import annotations

import time
from typing import Callable, List, Optional, Tuple

from .config import InputConfig


class BackendUnavailable(RuntimeError):
    """请求的真实输入后端无法创建（缺库 / 导入失败 / 被设为 null）。"""


class InputBackend:
    """运行时后端接口。用具体类而非 Protocol，便于挂 warning 等属性。"""

    name: str = "base"
    warning: Optional[str] = None

    def press_key(self, key: str, hold_ms: int) -> None:
        raise NotImplementedError

    def click_left(self, hold_ms: int = 40) -> None:
        raise NotImplementedError

    def click_right(self, hold_ms: int = 40) -> None:
        raise NotImplementedError

    def middle_down(self) -> None:
        raise NotImplementedError

    def middle_up(self) -> None:
        raise NotImplementedError


def _norm_key(key: str) -> str:
    """pydirectinput 对未知键名会静默 no-op；统一小写字母键。"""
    return (key or "").strip().lower()


def _call_input(fn: Callable, *args) -> object:
    """兼容带 / 不带 _pause 参数的键鼠库。"""
    try:
        return fn(*args, _pause=False)
    except TypeError:
        return fn(*args)


# ---- pydirectinput 后端（默认，DirectInput 路径，游戏兼容性较好）----
class PyDirectInputBackend(InputBackend):
    name = "pydirectinput"

    def __init__(self) -> None:
        import pydirectinput  # 延迟导入，缺库时给出清晰错误
        self._api = pydirectinput
        # 关闭库自带的 keyDown/mouseDown 后置延迟
        try:
            self._api.PAUSE = 0
        except AttributeError:
            pass
        # FAILSAFE 在光标位于屏幕角落时抛异常。游戏常把光标停在 (0,0)，
        # 会导致 B 模式看起来像“按了没反应”。这是可靠性修复，不是隐蔽手段。
        try:
            self._api.FAILSAFE = False
        except AttributeError:
            pass

    def press_key(self, key: str, hold_ms: int) -> None:
        api = self._api
        k = _norm_key(key)
        if not k:
            raise RuntimeError("空按键名，无法发送")
        downed = _call_input(api.keyDown, k)
        if downed is False:
            raise RuntimeError(
                "pydirectinput.keyDown(%r) 未成功发送。请以管理员身份运行，或到设置改用 keyboard_ctypes。"
                % k
            )
        try:
            _sleep_ms(hold_ms)
        finally:
            _call_input(api.keyUp, k)

    def click_left(self, hold_ms: int = 40) -> None:
        self._mouse("left", down=True)
        try:
            _sleep_ms(hold_ms)
        finally:
            self._mouse("left", down=False)

    def click_right(self, hold_ms: int = 40) -> None:
        self._mouse("right", down=True)
        try:
            _sleep_ms(hold_ms)
        finally:
            self._mouse("right", down=False)

    def middle_down(self) -> None:
        self._mouse("middle", down=True)

    def middle_up(self) -> None:
        self._mouse("middle", down=False)

    def _mouse(self, button: str, down: bool) -> None:
        api = self._api
        fn = api.mouseDown if down else api.mouseUp
        try:
            fn(button=button, _pause=False)
        except TypeError:
            fn(button=button)


# ---- keyboard + ctypes mouse 后端（备选）----
class KeyboardCtypesBackend(InputBackend):
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
        k = _norm_key(key)
        if not k:
            raise RuntimeError("空按键名，无法发送")
        self._kb.press(k)
        try:
            _sleep_ms(hold_ms)
        finally:
            self._kb.release(k)

    def click_left(self, hold_ms: int = 40) -> None:
        user32 = self._ctypes.windll.user32
        user32.mouse_event(self._LEFT_DOWN, 0, 0, 0, 0)
        try:
            _sleep_ms(hold_ms)
        finally:
            user32.mouse_event(self._LEFT_UP, 0, 0, 0, 0)

    def click_right(self, hold_ms: int = 40) -> None:
        user32 = self._ctypes.windll.user32
        user32.mouse_event(self._RIGHT_DOWN, 0, 0, 0, 0)
        try:
            _sleep_ms(hold_ms)
        finally:
            user32.mouse_event(self._RIGHT_UP, 0, 0, 0, 0)

    def middle_down(self) -> None:
        self._ctypes.windll.user32.mouse_event(self._MIDDLE_DOWN, 0, 0, 0, 0)

    def middle_up(self) -> None:
        self._ctypes.windll.user32.mouse_event(self._MIDDLE_UP, 0, 0, 0, 0)


# ---- 空后端（试运行 / C 模式 / 测试用，不发送任何真实输入）----
class NullBackend(InputBackend):
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


def _alias_backend_name(name: str) -> str:
    n = (name or "").strip().lower()
    if n in ("keyboard", "ctypes"):
        return "keyboard_ctypes"
    return n


def _try_construct(name: str) -> InputBackend:
    if name == "pydirectinput":
        return PyDirectInputBackend()
    if name == "keyboard_ctypes":
        return KeyboardCtypesBackend()
    if name == "null":
        return NullBackend()
    raise BackendUnavailable("未知输入后端 %r。请选择 pydirectinput / keyboard_ctypes / null。" % name)


def resolve_backend(
    cfg: InputConfig, *, require_real: bool = False
) -> Tuple[InputBackend, Optional[str]]:
    """按配置创建后端。

    require_real=True（B 模式）：禁止静默落到 NullBackend。
    首选后端失败时自动尝试另一种真实后端，并通过 warning 告知。
    """
    name = _alias_backend_name(cfg.backend)
    if name == "null":
        if require_real:
            raise BackendUnavailable(
                "设置中的输入后端为 null（不发送按键）。\n"
                "请到「设置」选择 pydirectinput 或 keyboard_ctypes 后再使用自动注入。"
            )
        be = NullBackend()
        return be, None

    order: List[str] = []
    if name in ("pydirectinput", "keyboard_ctypes"):
        order.append(name)
    else:
        if require_real:
            raise BackendUnavailable(
                "未知输入后端 %r。请到「设置」选择 pydirectinput 或 keyboard_ctypes。" % name
            )
        return NullBackend(), "未知输入后端 %r，已使用空后端。" % name

    other = "keyboard_ctypes" if name == "pydirectinput" else "pydirectinput"
    if other not in order:
        order.append(other)

    errors: List[str] = []
    for candidate in order:
        try:
            be = _try_construct(candidate)
        except Exception as e:
            errors.append("%s: %s" % (candidate, e))
            continue
        note = None
        if candidate != name:
            note = (
                "首选后端 %s 不可用（%s），已改用 %s。"
                % (name, errors[-1] if errors else "未知原因", candidate)
            )
            be.warning = note
        return be, note

    detail = "；".join(errors) if errors else "无可用后端"
    if require_real:
        raise BackendUnavailable(
            "无法创建输入后端，自动注入不会发送按键。\n"
            "%s\n\n"
            "请安装依赖：pip install pydirectinput keyboard\n"
            "打包版请确认 exe 含这些库；仍失败时以管理员身份运行，"
            "并到「设置」切换输入后端。"
            % detail
        )
    be = NullBackend()
    be.warning = "输入后端不可用（%s），已回退空后端。" % detail
    return be, be.warning


def create_backend(cfg: InputConfig, *, require_real: bool = False) -> InputBackend:
    """根据配置创建后端。缺库时：require_real=False 回退 NullBackend；True 则抛错。"""
    be, _note = resolve_backend(cfg, require_real=require_real)
    return be
