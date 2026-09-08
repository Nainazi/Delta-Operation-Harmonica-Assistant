"""佐拉口琴谱伴 - 入口。

启动 tkinter GUI。命令行参数：
  --score <path>   启动时载入指定曲谱文件
  --mode C|B|E     启动时预设模式

带全局异常捕获：未捕获的异常会写入 %APPDATA%\\佐拉口琴谱伴\\error.log，
便于 exe 运行时排查问题（windowed 模式下 stderr 不可见）。
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
import traceback


def _log_path() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "佐拉口琴谱伴")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        path = base
    return os.path.join(path, "error.log")


def _install_excepthook() -> None:
    def hook(exc_type, exc_value, exc_tb):
        try:
            with open(_log_path(), "a", encoding="utf-8") as f:
                f.write("\n==== %s ====\n" % datetime.datetime.now().isoformat())
                traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
        except Exception:
            pass
        # 仍交给默认 hook 处理（windowed 下不可见，但开发模式可见）
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = hook


def main() -> int:
    _install_excepthook()
    parser = argparse.ArgumentParser(prog="佐拉口琴谱伴",
                                     description="三角洲行动 佐拉彩蛋口琴 曲谱辅助工具")
    parser.add_argument("--score", help="启动时载入的曲谱文件路径")
    parser.add_argument("--mode", choices=["C", "B", "E"], help="启动预设模式")
    args = parser.parse_args()

    # 延迟导入，便于 --help 快速响应，且让全局 excepthook 先就位
    # 注意：必须用绝对导入。PyInstaller 将本文件作为入口脚本冻结后以 __main__ 运行，
    # __package__ 为空，相对导入 from . import gui 会失败。
    from harmonica import gui

    gui.run(initial_score=args.score, initial_mode=args.mode)
    return 0


if __name__ == "__main__":
    main()
