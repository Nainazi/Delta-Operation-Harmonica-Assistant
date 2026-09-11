"""输入后端抽象。

提供统一接口 press_key / key_down / key_up / mouse_down / mouse_up，
底层可在 sendinput / pydirectinput / keyboard+ctypes 之间切换。

演奏键位：z x c v b n m（对应音级 1-7）；最高 do 为逗号键「,」。
修饰（整音按住，不是点按）：
  左键 = 低八度；右键 = 高八度；中键 = 半音（# / b）。
"""
from __future__ import annotations

import sys
import time
from typing import Callable, List, Optional, Tuple

from .config import InputConfig

# 最近一次 create_backend 失败原因（B 模式安装对话框展示）。成功时清空。
LAST_BACKEND_ERROR: Optional[str] = None


class BackendUnavailable(RuntimeError):
    """请求的真实输入后端无法创建（缺库 / 导入失败 / 被设为 null）。"""


class InputBackend:
    """运行时后端接口。用具体类而非 Protocol，便于挂 warning 等属性。"""

    name: str = "base"
    warning: Optional[str] = None

    def key_down(self, key: str) -> None:
        raise NotImplementedError

    def key_up(self, key: str) -> None:
        raise NotImplementedError

    def press_key(self, key: str, hold_ms: int) -> None:
        self.key_down(key)
        try:
            _sleep_ms(hold_ms)
        finally:
            self.key_up(key)

    def click_left(self, hold_ms: int = 40) -> None:
        self.left_down()
        try:
            _sleep_ms(hold_ms)
        finally:
            self.left_up()

    def click_right(self, hold_ms: int = 40) -> None:
        self.right_down()
        try:
            _sleep_ms(hold_ms)
        finally:
            self.right_up()

    def mouse_down(self, button: str) -> None:
        b = (button or "").strip().lower()
        if b == "left":
            self.left_down()
        elif b == "right":
            self.right_down()
        elif b in ("middle", "mid"):
            self.middle_down()
        else:
            raise ValueError("未知鼠标键 %r" % button)

    def mouse_up(self, button: str) -> None:
        b = (button or "").strip().lower()
        if b == "left":
            self.left_up()
        elif b == "right":
            self.right_up()
        elif b in ("middle", "mid"):
            self.middle_up()
        else:
            raise ValueError("未知鼠标键 %r" % button)

    def left_down(self) -> None:
        raise NotImplementedError

    def left_up(self) -> None:
        raise NotImplementedError

    def right_down(self) -> None:
        raise NotImplementedError

    def right_up(self) -> None:
        raise NotImplementedError

    def middle_down(self) -> None:
        raise NotImplementedError

    def middle_up(self) -> None:
        raise NotImplementedError

    def release_all_mouse(self) -> None:
        for fn in (self.middle_up, self.left_up, self.right_up):
            try:
                fn()
            except Exception:
                pass


def _norm_key(key: str) -> str:
    """pydirectinput 对未知键名会静默 no-op；统一小写字母键。"""
    return (key or "").strip().lower()


def _call_input(fn: Callable, *args) -> object:
    """兼容带 / 不带 _pause 参数的键鼠库。"""
    try:
        return fn(*args, _pause=False)
    except TypeError:
        return fn(*args)


# US QWERTY 扫描码（KEYEVENTF_SCANCODE）。游戏侧通常认扫描码而不是 VK。
SCANCODES = {
    "z": 0x2C, "x": 0x2D, "c": 0x2E, "v": 0x2F,
    "b": 0x30, "n": 0x31, "m": 0x32,
    ",": 0x33, "<": 0x33,
}

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040

_MOUSE_FLAGS = {
    ("left", True): MOUSEEVENTF_LEFTDOWN,
    ("left", False): MOUSEEVENTF_LEFTUP,
    ("right", True): MOUSEEVENTF_RIGHTDOWN,
    ("right", False): MOUSEEVENTF_RIGHTUP,
    ("middle", True): MOUSEEVENTF_MIDDLEDOWN,
    ("middle", False): MOUSEEVENTF_MIDDLEUP,
}


def key_to_scancode(key: str) -> int:
    """字母/逗号 → 扫描码。未知键名抛 ValueError（测试与 SendInput 共用）。"""
    k = _norm_key(key)
    if k in ("comma", "oem_comma"):
        k = ","
    code = SCANCODES.get(k)
    if code:
        return code
    raise ValueError("无扫描码映射: %r" % key)


class SendInputBackend(InputBackend):
    """Windows SendInput：扫描码按键 + 鼠标按键。B 模式默认后端。"""

    name = "sendinput"

    def __init__(self, *, _user32=None) -> None:
        if _user32 is None and sys.platform != "win32":
            raise BackendUnavailable("SendInput 仅 Windows 可用")
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self._user32 = _user32 if _user32 is not None else ctypes.windll.user32
        ULONG_PTR = wintypes.WPARAM

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = (
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR),
            )

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = (
                ("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR),
            )

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = (
                ("uMsg", wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD),
            )

        class INPUTUNION(ctypes.Union):
            _fields_ = (("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT))

        class INPUT(ctypes.Structure):
            _fields_ = (("type", wintypes.DWORD), ("union", INPUTUNION))

        self._KEYBDINPUT = KEYBDINPUT
        self._MOUSEINPUT = MOUSEINPUT
        self._INPUTUNION = INPUTUNION
        self._INPUT = INPUT

    def _send(self, inputs: list) -> None:
        n = len(inputs)
        arr = (self._INPUT * n)(*inputs)
        sent = int(self._user32.SendInput(n, arr, self._ctypes.sizeof(self._INPUT)))
        if sent != n:
            raise RuntimeError("SendInput 未完整发送（%s/%s）。请以管理员身份运行。" % (sent, n))

    def _scan_of(self, key: str) -> int:
        k = _norm_key(key)
        try:
            return key_to_scancode(k)
        except ValueError:
            pass
        # 回退：VkKeyScanW + MapVirtualKeyW（仅 Windows）
        if len(k) != 1:
            raise RuntimeError("SendInput 不支持的按键名 %r" % key)
        try:
            vk_scan = int(self._user32.VkKeyScanW(k))
            vk = vk_scan & 0xFF
            code = int(self._user32.MapVirtualKeyW(vk, 0))
        except Exception as e:
            raise RuntimeError("无法解析按键 %r 的扫描码: %s" % (key, e)) from e
        if not code:
            raise RuntimeError("SendInput 无法映射按键 %r" % key)
        return code

    def key_down(self, key: str) -> None:
        scan = self._scan_of(key)
        ki = self._KEYBDINPUT(0, scan, KEYEVENTF_SCANCODE, 0, 0)
        inp = self._INPUT(INPUT_KEYBOARD, self._INPUTUNION(ki=ki))
        self._send([inp])

    def key_up(self, key: str) -> None:
        scan = self._scan_of(key)
        ki = self._KEYBDINPUT(0, scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0, 0)
        inp = self._INPUT(INPUT_KEYBOARD, self._INPUTUNION(ki=ki))
        self._send([inp])

    def _mouse(self, button: str, down: bool) -> None:
        flags = _MOUSE_FLAGS.get((button, down))
        if flags is None:
            raise ValueError("未知鼠标键 %r" % button)
        mi = self._MOUSEINPUT(0, 0, 0, flags, 0, 0)
        inp = self._INPUT(INPUT_MOUSE, self._INPUTUNION(mi=mi))
        self._send([inp])

    def left_down(self) -> None:
        self._mouse("left", True)

    def left_up(self) -> None:
        self._mouse("left", False)

    def right_down(self) -> None:
        self._mouse("right", True)

    def right_up(self) -> None:
        self._mouse("right", False)

    def middle_down(self) -> None:
        self._mouse("middle", True)

    def middle_up(self) -> None:
        self._mouse("middle", False)


# ---- pydirectinput 后端（备选，DirectInput 路径）----
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

    def key_down(self, key: str) -> None:
        k = _norm_key(key)
        if not k:
            raise RuntimeError("空按键名，无法发送")
        downed = _call_input(self._api.keyDown, k)
        if downed is False:
            raise RuntimeError(
                "pydirectinput.keyDown(%r) 未成功发送。请以管理员身份运行，或到设置改用 sendinput / keyboard_ctypes。"
                % k
            )

    def key_up(self, key: str) -> None:
        k = _norm_key(key)
        if not k:
            return
        _call_input(self._api.keyUp, k)

    def press_key(self, key: str, hold_ms: int) -> None:
        self.key_down(key)
        try:
            _sleep_ms(hold_ms)
        finally:
            self.key_up(key)

    def click_left(self, hold_ms: int = 40) -> None:
        self.left_down()
        try:
            _sleep_ms(hold_ms)
        finally:
            self.left_up()

    def click_right(self, hold_ms: int = 40) -> None:
        self.right_down()
        try:
            _sleep_ms(hold_ms)
        finally:
            self.right_up()

    def left_down(self) -> None:
        self._mouse("left", down=True)

    def left_up(self) -> None:
        self._mouse("left", down=False)

    def right_down(self) -> None:
        self._mouse("right", down=True)

    def right_up(self) -> None:
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

    def key_down(self, key: str) -> None:
        k = _norm_key(key)
        if not k:
            raise RuntimeError("空按键名，无法发送")
        self._kb.press(k)

    def key_up(self, key: str) -> None:
        k = _norm_key(key)
        if not k:
            return
        self._kb.release(k)

    def press_key(self, key: str, hold_ms: int) -> None:
        self.key_down(key)
        try:
            _sleep_ms(hold_ms)
        finally:
            self.key_up(key)

    def click_left(self, hold_ms: int = 40) -> None:
        self.left_down()
        try:
            _sleep_ms(hold_ms)
        finally:
            self.left_up()

    def click_right(self, hold_ms: int = 40) -> None:
        self.right_down()
        try:
            _sleep_ms(hold_ms)
        finally:
            self.right_up()

    def left_down(self) -> None:
        self._ctypes.windll.user32.mouse_event(self._LEFT_DOWN, 0, 0, 0, 0)

    def left_up(self) -> None:
        self._ctypes.windll.user32.mouse_event(self._LEFT_UP, 0, 0, 0, 0)

    def right_down(self) -> None:
        self._ctypes.windll.user32.mouse_event(self._RIGHT_DOWN, 0, 0, 0, 0)

    def right_up(self) -> None:
        self._ctypes.windll.user32.mouse_event(self._RIGHT_UP, 0, 0, 0, 0)

    def middle_down(self) -> None:
        self._ctypes.windll.user32.mouse_event(self._MIDDLE_DOWN, 0, 0, 0, 0)

    def middle_up(self) -> None:
        self._ctypes.windll.user32.mouse_event(self._MIDDLE_UP, 0, 0, 0, 0)


# ---- 空后端（试运行 / C 模式 / 测试用，不发送任何真实输入）----
class NullBackend(InputBackend):
    name = "null"

    def key_down(self, key: str) -> None:
        pass

    def key_up(self, key: str) -> None:
        pass

    def press_key(self, key: str, hold_ms: int) -> None:
        _sleep_ms(hold_ms)

    def click_left(self, hold_ms: int = 40) -> None:
        _sleep_ms(hold_ms)

    def click_right(self, hold_ms: int = 40) -> None:
        _sleep_ms(hold_ms)

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
    if name == "sendinput":
        return SendInputBackend()
    if name == "pydirectinput":
        return PyDirectInputBackend()
    if name == "keyboard_ctypes":
        return KeyboardCtypesBackend()
    if name == "null":
        return NullBackend()
    raise BackendUnavailable("未知输入后端 %r。请选择 sendinput / pydirectinput / keyboard_ctypes / null。" % name)


def _preferred_then_fallback(name: str) -> List[str]:
    """sendinput 优先；pydirectinput / keyboard_ctypes 为备选。"""
    chain = ["sendinput", "pydirectinput", "keyboard_ctypes"]
    if name in chain:
        return [name] + [x for x in chain if x != name]
    return list(chain)


def create_backend(cfg: InputConfig) -> InputBackend:
    """按配置创建后端。

    先试首选，再试另一种真实后端；全部失败才返回 NullBackend，
    并把原因写入 LAST_BACKEND_ERROR（成功则清空）。
    """
    global LAST_BACKEND_ERROR
    LAST_BACKEND_ERROR = None

    name = _alias_backend_name(cfg.backend)
    if name == "null":
        LAST_BACKEND_ERROR = (
            "设置中的输入后端为 null（不发送按键）。\n"
            "请到「设置」选择 sendinput / pydirectinput / keyboard_ctypes 后再使用自动注入。"
        )
        be = NullBackend()
        be.warning = LAST_BACKEND_ERROR
        return be

    if name not in ("sendinput", "pydirectinput", "keyboard_ctypes"):
        LAST_BACKEND_ERROR = (
            "未知输入后端 %r，将依次尝试 sendinput / pydirectinput / keyboard_ctypes。" % name
        )
        name = "sendinput"

    errors: List[str] = []
    for candidate in _preferred_then_fallback(name):
        try:
            be = _try_construct(candidate)
        except Exception as e:
            errors.append("%s: %s" % (candidate, e))
            continue
        if candidate != name:
            be.warning = (
                "首选后端 %s 不可用（%s），已改用 %s。"
                % (name, errors[-1] if errors else "未知原因", candidate)
            )
        LAST_BACKEND_ERROR = None
        return be

    detail = "；".join(errors) if errors else "无可用后端"
    LAST_BACKEND_ERROR = (
        "无法创建输入后端（不会发送 z–m / 逗号 / 鼠标修饰）。\n"
        "%s\n\n"
        "Windows 下默认 sendinput 不需要额外库。若你强制使用 pydirectinput / keyboard：\n"
        "可点「一键安装」执行：python -m pip install pydirectinput keyboard\n"
        "或到「设置」切换输入后端；仍失败时以管理员身份运行。"
        % detail
    )
    be = NullBackend()
    be.warning = LAST_BACKEND_ERROR
    return be


def resolve_backend(
    cfg: InputConfig, *, require_real: bool = False
) -> Tuple[InputBackend, Optional[str]]:
    """create_backend 的包装：返回 (backend, warning)。require_real 时 null 会抛错。"""
    be = create_backend(cfg)
    if require_real and be.name == "null":
        raise BackendUnavailable(LAST_BACKEND_ERROR or "无法创建输入后端")
    return be, be.warning


def install_inject_dependencies() -> Tuple[bool, str]:
    """运行 python -m pip install pydirectinput keyboard。供 B 模式一键安装。"""
    import subprocess
    import sys

    if getattr(sys, "frozen", False):
        return (
            False,
            "当前是打包后的 exe，无法用 pip 往捆绑环境装库。\n"
            "请下载带依赖的发行版，或改用源码：python -m harmonica",
        )
    cmd = [sys.executable, "-m", "pip", "install", "pydirectinput", "keyboard"]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=180, check=False,
        )
        out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        if proc.returncode == 0:
            return True, out or "安装完成"
        return False, out or ("pip 退出码 %s" % proc.returncode)
    except Exception as e:
        return False, str(e)
