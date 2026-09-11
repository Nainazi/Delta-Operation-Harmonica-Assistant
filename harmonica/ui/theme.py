"""UI 主题色与通用小部件。"""
from __future__ import annotations

import tkinter as tk
from typing import Optional

import customtkinter as ctk

RISK_BANNER = (
    "⚠ B 模式自动注入键鼠属游戏禁止行为，封号风险高；"
    "E 模式导出鼠标宏手写教程（中风险）。仅限单人/安全区/非竞技场景，风险自负。C 模式零风险。"
)

# 三角洲行动风格配色（战术青绿 + 深色军事质感）
C_BG = "#0e1316"
C_SIDEBAR = "#141a1e"
C_CARD = "#1a2126"
C_CARD_HI = "#222b31"
C_TEXT = "#e8eef0"
C_TEXT_DIM = "#93a3a8"
C_ACCENT = "#3fd0b0"
C_ACCENT_HOVER = "#2fbfa0"
C_OK = "#3fd0b0"
C_WARN = "#ffb454"
C_DANGER = "#ff5f5f"


def init_theme() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    ctk.deactivate_automatic_dpi_awareness()


def make_card(parent, text=None) -> ctk.CTkFrame:
    f = ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=14)
    if text:
        lbl = ctk.CTkLabel(
            f, text=text, anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=C_ACCENT)
        lbl.pack(fill="x", padx=16, pady=(12, 6))
    return f


class ToolTip:
    """简易悬停提示气泡。"""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _e: tk.Event) -> None:
        if self.tip is not None or not self.text:
            return
        x = self.widget.winfo_rootx() + 14
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.overrideredirect(True)
        self.tip.attributes("-topmost", True)
        lbl = tk.Label(
            self.tip, text=self.text, justify="left",
            background="#11121a", foreground=C_TEXT,
            relief="flat", padx=10, pady=6, font=("Segoe UI", 9))
        lbl.pack()
        self.tip.geometry("+%d+%d" % (x, y))

    def _hide(self, _e: tk.Event) -> None:
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None
