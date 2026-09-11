"""图形界面入口（兼容层）。

v1.0.4 起实现拆分至 harmonica.ui.*；本模块保留 App / run / 主题色与 HUD
等公开符号，确保 `from harmonica import gui` 与 main.py 继续可用。
"""
from __future__ import annotations

from .ui.app import App, run
from .ui.hud import HUDOverlay, ToolTip, ttk_Progressbar
from .ui.theme import (
    RISK_BANNER,
    C_BG, C_SIDEBAR, C_CARD, C_CARD_HI, C_TEXT, C_TEXT_DIM,
    C_ACCENT, C_ACCENT_HOVER, C_OK, C_WARN, C_DANGER,
    init_theme as _init_theme,
)

__all__ = [
    "App", "run", "HUDOverlay", "ToolTip", "ttk_Progressbar",
    "RISK_BANNER",
    "C_BG", "C_SIDEBAR", "C_CARD", "C_CARD_HI", "C_TEXT", "C_TEXT_DIM",
    "C_ACCENT", "C_ACCENT_HOVER", "C_OK", "C_WARN", "C_DANGER",
    "_init_theme",
]
