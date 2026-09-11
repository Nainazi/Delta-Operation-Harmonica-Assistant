"""HUD 覆盖层与 ToolTip 再导出。"""
from __future__ import annotations

import tkinter as tk
from typing import Optional

from .theme import ToolTip  # re-export

__all__ = ["HUDOverlay", "ToolTip", "ttk_Progressbar"]


def ttk_Progressbar(master, length=200):
    """HUD 用原生 ttk 进度条（customtkinter 进度条不便嵌入透明 Toplevel）。"""
    import tkinter.ttk as _ttk
    return _ttk.Progressbar(master, length=length, mode="determinate")


class HUDOverlay:
    """图形 HUD 覆盖层：无边框、置顶、半透明、点击穿透的浮动窗口。"""

    _BG = "#000000"

    def __init__(self, parent: tk.Misc) -> None:
        self.win = tk.Toplevel(parent)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-alpha", 0.82)
        except tk.TclError:
            pass
        try:
            self.win.attributes("-transparentcolor", self._BG)
        except tk.TclError:
            pass

        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        x = max(0, sw - 280)
        self.win.geometry("+%d+60" % x)

        self.note_label = tk.Label(
            self.win, text="—", font=("Segoe UI", 36, "bold"),
            fg="#00e5ff", bg=self._BG)
        self.note_label.pack(padx=26, pady=(20, 2))

        self.beat_label = tk.Label(
            self.win, text="", font=("Segoe UI", 12),
            fg="#cfe8ff", bg=self._BG)
        self.beat_label.pack(pady=(0, 6))

        self.progress = ttk_Progressbar(self.win, length=210)
        self.progress.pack(pady=(0, 10))

        self.hint = tk.Label(
            self.win, text="拖动移动 · 双击换边角 · 右键关闭",
            font=("Segoe UI", 8), fg="#7fb0d8", bg=self._BG)
        self.hint.pack(pady=(0, 8))

        self._drag = {"x": 0, "y": 0}
        for w in (self.note_label, self.beat_label, self.hint):
            w.bind("<ButtonPress-1>", self._on_drag_start)
            w.bind("<B1-Motion>", self._on_drag_motion)
            w.bind("<Double-Button-1>", self._on_dblclick)
            w.bind("<Button-3>", lambda e: self.destroy())
        self.win.bind("<Button-3>", lambda e: self.destroy())

    def update_note(self, text: Optional[str], idx: int, total: int,
                    beats: float = 0.0, accidental: int = 0,
                    is_rest: bool = False) -> None:
        if not self.exists():
            return
        if text is None:
            self.note_label.config(text="—", fg="#00e5ff")
            self.beat_label.config(text="")
            self.progress["value"] = 0
            return
        color = "#9aa6b2" if is_rest else ("#ffd166" if accidental != 0 else "#00e5ff")
        self.note_label.config(text=text, fg=color)
        self.beat_label.config(text=(str(beats) + " 拍") if beats else "")
        self.progress["maximum"] = max(1, total)
        self.progress["value"] = idx

    def _on_drag_start(self, e: tk.Event) -> None:
        self._drag["x"] = e.x_root
        self._drag["y"] = e.y_root

    def _on_drag_motion(self, e: tk.Event) -> None:
        dx = e.x_root - self._drag["x"]
        dy = e.y_root - self._drag["y"]
        self._drag["x"] = e.x_root
        self._drag["y"] = e.y_root
        self.win.geometry("+%d+%d" % (self.win.winfo_x() + dx, self.win.winfo_y() + dy))

    def _on_dblclick(self, e: tk.Event) -> None:
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        x, y = self.win.winfo_x(), self.win.winfo_y()
        corners = [(0, 60), (sw - w, 60), (0, sh - h - 60), (sw - w, sh - h - 60)]
        nearest = min(range(4), key=lambda i: (corners[i][0] - x) ** 2 + (corners[i][1] - y) ** 2)
        nxt = corners[(nearest + 1) % 4]
        self.win.geometry("+%d+%d" % nxt)

    def exists(self) -> bool:
        try:
            return bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def destroy(self) -> None:
        try:
            self.win.destroy()
        except tk.TclError:
            pass
