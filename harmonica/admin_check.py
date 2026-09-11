"""Windows 进程提权检测（B 模式提示用）。

游戏若以管理员启动，未提权的辅助进程注入会表现为「按了没反应」。
本模块只检测与（用户主动点击后）请求一次 UAC 重启，不循环弹窗。
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional, Tuple

# 界面与对话框共用的短提示
UNELEVATED_HINT = "请以管理员身份运行；游戏若也是管理员启动则必须一致"

# ShellExecuteW：返回值 > 32 表示成功（MSDN）
_SHELLEXECUTE_SUCCESS = 32


def is_elevated() -> Optional[bool]:
    """当前进程是否已提权。非 Windows 或检测失败时返回 None。"""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return None


def should_warn_unelevated() -> bool:
    """仅在「确定未提权」时警告；未知/非 Windows 不打扰。"""
    return is_elevated() is False


def relaunch_command() -> Tuple[str, str]:
    """返回 (executable, parameters) 供 ShellExecuteW 使用。"""
    extra = list(sys.argv[1:]) if sys.argv else []
    if getattr(sys, "frozen", False):
        return sys.executable, subprocess.list2cmdline(extra)

    argv0 = sys.argv[0] if sys.argv else ""
    base = os.path.basename(argv0).lower()
    if base in ("__main__.py", "harmonica") or base.endswith(".__main__.py"):
        parts = ["-m", "harmonica"] + extra
    elif argv0:
        parts = [os.path.abspath(argv0)] + extra
    else:
        parts = ["-m", "harmonica"] + extra
    return sys.executable, subprocess.list2cmdline(parts)


def relaunch_elevated() -> Tuple[bool, str]:
    """请求一个提权的新实例。用户取消 UAC 时失败并保持当前进程，不重试。"""
    if sys.platform != "win32":
        return False, "仅 Windows 支持以管理员身份重启。"
    if is_elevated() is True:
        return False, "当前已是管理员，无需重启。"

    exe, params = relaunch_command()
    try:
        import ctypes
        rc = int(ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, params or None, None, 1
        ))
    except Exception as e:
        return False, str(e)

    if rc <= _SHELLEXECUTE_SUCCESS:
        return False, "未获得管理员权限（已取消 UAC 或系统拒绝）。当前窗口保持不变。"
    return True, ""
