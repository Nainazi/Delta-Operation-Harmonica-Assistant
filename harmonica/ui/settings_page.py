"""设置页构建（含键位预览）。"""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Dict, List

import customtkinter as ctk

from ..config import DEFAULT_KEY_MAP
from .theme import (
    C_BG, C_CARD_HI, C_TEXT, C_TEXT_DIM, C_ACCENT, C_ACCENT_HOVER, ToolTip, make_card,
)

if TYPE_CHECKING:
    from .app import App

_DEGREE_NAMES = {1: "do", 2: "re", 3: "mi", 4: "fa", 5: "sol", 6: "la", 7: "ti"}


def build_settings_page(app: "App") -> ctk.CTkScrollableFrame:
    page = ctk.CTkScrollableFrame(app.root, fg_color=C_BG, corner_radius=0)

    # 键位预览
    kp = make_card(page, "键位预览（z–m）")
    kp.pack(fill="x", padx=16, pady=(16, 10))
    chip_row = ctk.CTkFrame(kp, fg_color="transparent")
    chip_row.pack(fill="x", padx=16, pady=(4, 6))
    app._key_chips: Dict[str, ctk.CTkLabel] = {}
    for d in range(1, 8):
        key = (app.cfg.input.key_map or DEFAULT_KEY_MAP).get(d, DEFAULT_KEY_MAP[d])
        chip = ctk.CTkLabel(
            chip_row,
            text=f" {key.upper()} \n{_DEGREE_NAMES[d]} / {d}",
            width=64, height=52, corner_radius=10,
            fg_color=C_CARD_HI, text_color=C_TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
        chip.pack(side="left", padx=4)
        app._key_chips[key.lower()] = chip
    ctk.CTkLabel(
        kp, text="按住鼠标中键 + 上列任一键 = 半音（♯ / ♭）。设置页聚焦时可按物理键高亮（尽力而为）。",
        text_color=C_TEXT_DIM, font=ctk.CTkFont(family="Segoe UI", size=10),
        anchor="w").pack(fill="x", padx=16, pady=(0, 12))
    page.bind("<FocusIn>", lambda e: app._settings_key_preview_on())
    page.bind("<FocusOut>", lambda e: app._settings_key_preview_off())
    # 也在页面可见时尝试挂钩：由 App._show_page 调用

    # 节奏
    gf = make_card(page, "节奏")
    gf.pack(fill="x", padx=16, pady=(0, 10))
    row = ctk.CTkFrame(gf, fg_color="transparent")
    row.pack(fill="x", padx=16, pady=(0, 12))
    ctk.CTkLabel(
        row, text="BPM", text_color=C_TEXT,
        font=ctk.CTkFont(family="Segoe UI", size=12)).pack(side="left")
    app.bpm_var = tk.DoubleVar(value=app.cfg.timing.bpm)
    bpm_spin = ctk.CTkEntry(
        row, textvariable=app.bpm_var, width=70, justify="center",
        fg_color="#1a1b24", text_color=C_TEXT, border_color=C_CARD_HI)
    bpm_spin.pack(side="left", padx=10)
    app.bpm_var.trace_add("write", lambda *_: app._on_bpm_change())
    ToolTip(bpm_spin, "数字越大节奏越快；曲谱内 @bpm 会覆盖此值")
    ctk.CTkLabel(
        row, text="一拍 ≈ %.2f 秒" % app.cfg.timing.beat_seconds,
        text_color=C_TEXT_DIM,
        font=ctk.CTkFont(family="Segoe UI", size=11)).pack(side="left", padx=10)

    # 人性化
    hf = make_card(page, "时序人性化（降低行为检测概率，不能消除风险）")
    hf.pack(fill="x", padx=16, pady=(0, 10))
    app.humanize_var = tk.BooleanVar(value=app.cfg.humanize.enabled)
    ctk.CTkCheckBox(
        hf, text="启用时长/间隔抖动", variable=app.humanize_var,
        command=app._on_humanize_change, text_color=C_TEXT,
        fg_color=C_ACCENT, font=ctk.CTkFont(family="Segoe UI", size=12)
    ).pack(anchor="w", padx=16, pady=(6, 8))
    ctk.CTkLabel(
        hf, text="时长抖动幅度", text_color=C_TEXT_DIM,
        font=ctk.CTkFont(family="Segoe UI", size=11)).pack(anchor="w", padx=16)
    app.jitter_var = tk.DoubleVar(value=app.cfg.humanize.duration_jitter_pct)
    js = ctk.CTkSlider(
        hf, from_=0.0, to=0.30, variable=app.jitter_var,
        command=lambda v: app._on_jitter_change(),
        button_color=C_ACCENT, button_hover_color=C_ACCENT_HOVER)
    js.pack(fill="x", padx=16, pady=(4, 12))
    ToolTip(js, "0=关闭抖动；建议 5%~15%，过大节奏不稳")

    # 键-点击顺序
    kf = make_card(page, "键-点击顺序")
    kf.pack(fill="x", padx=16, pady=(0, 10))
    app.key_first_var = tk.BooleanVar(value=app.cfg.timing.key_before_click)
    cb = ctk.CTkCheckBox(
        kf, text="先按字母键、再点中键（不勾选=先按住中键再按字母，推荐）",
        variable=app.key_first_var, command=app._on_key_order_change,
        text_color=C_TEXT, fg_color=C_ACCENT,
        font=ctk.CTkFont(family="Segoe UI", size=12))
    cb.pack(anchor="w", padx=16, pady=(6, 8))
    ToolTip(cb, "半音=按住中键+字母。推荐不勾选（先中键再字母）；若不准可勾选换序")
    ctk.CTkLabel(
        kf, text="演奏键位：1→z  2→x  3→c  4→v  5→b  6→n  7→m｜半音：按住鼠标中键",
        text_color=C_TEXT_DIM, font=ctk.CTkFont(family="Segoe UI", size=10),
        anchor="w").pack(fill="x", padx=16, pady=(0, 12))

    # 全局热键
    hk = make_card(page, "全局热键（手动辅助 / 自动注入）")
    hk.pack(fill="x", padx=16, pady=(0, 10))
    hk_row = ctk.CTkFrame(hk, fg_color="transparent")
    hk_row.pack(fill="x", padx=16, pady=(6, 4))
    ctk.CTkLabel(
        hk_row, text="开始", text_color=C_TEXT,
        font=ctk.CTkFont(family="Segoe UI", size=12), width=40).pack(side="left")
    app.hotkey_start_var = tk.StringVar(value=app.cfg.hotkey.start)
    e1 = ctk.CTkEntry(
        hk_row, textvariable=app.hotkey_start_var, width=100, justify="center",
        fg_color="#1a1b24", text_color=C_TEXT, border_color=C_CARD_HI)
    e1.pack(side="left", padx=(0, 16))
    ctk.CTkLabel(
        hk_row, text="停止", text_color=C_TEXT,
        font=ctk.CTkFont(family="Segoe UI", size=12), width=40).pack(side="left")
    app.hotkey_stop_var = tk.StringVar(value=app.cfg.hotkey.stop)
    e2 = ctk.CTkEntry(
        hk_row, textvariable=app.hotkey_stop_var, width=100, justify="center",
        fg_color="#1a1b24", text_color=C_TEXT, border_color=C_CARD_HI)
    e2.pack(side="left")
    ctk.CTkLabel(
        hk, text="默认 F5 开始 / F6 停止（避开 z x c v b n m 与 WASD）。曲中按停止可立即中断。",
        text_color=C_TEXT_DIM, font=ctk.CTkFont(family="Segoe UI", size=10),
        anchor="w").pack(fill="x", padx=16, pady=(4, 4))
    ctk.CTkButton(
        hk, text="应用热键", width=100, height=30, corner_radius=8,
        fg_color=C_CARD_HI, hover_color="#3a5044", text_color=C_TEXT,
        command=app._apply_hotkeys).pack(anchor="w", padx=16, pady=(0, 12))

    # 输入后端
    bf = make_card(page, "输入后端（仅 B 模式）")
    bf.pack(fill="x", padx=16, pady=(0, 10))
    ctk.CTkLabel(
        bf, text="注入方式", text_color=C_TEXT_DIM,
        font=ctk.CTkFont(family="Segoe UI", size=11)).pack(anchor="w", padx=16, pady=(6, 4))
    app.backend_var = tk.StringVar(value=app.cfg.input.backend)
    bb = ctk.CTkOptionMenu(
        bf, variable=app.backend_var,
        values=["pydirectinput", "keyboard_ctypes", "null"],
        command=app._on_backend_change,
        fg_color=C_CARD_HI, button_color=C_CARD_HI,
        button_hover_color="#3a3c50", text_color=C_TEXT,
        dropdown_fg_color="#1a2126", dropdown_text_color=C_TEXT,
        dropdown_hover_color=C_CARD_HI)
    bb.pack(anchor="w", padx=16)
    app.backend_var.trace_add("write", lambda *_: app._on_backend_change())
    ToolTip(bb, "pydirectinput=DirectInput（默认）；keyboard_ctypes=备选；null=不注入（测试）。B 模式若后端缺失会报错并拒绝开始，不会假装演奏。")
    ctk.CTkLabel(
        bf, text="keyboard 注入需以管理员身份运行 exe。后端库缺失时自动注入会弹窗报错，而不是空跑。",
        text_color=C_TEXT_DIM, font=ctk.CTkFont(family="Segoe UI", size=10)).pack(anchor="w", padx=16, pady=(8, 12))

    # 新手向导
    wz = make_card(page, "新手向导")
    wz.pack(fill="x", padx=16, pady=(0, 16))
    ctk.CTkButton(
        wz, text="再次查看新手向导", width=160, height=32, corner_radius=8,
        fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#0b0f11",
        command=lambda: app._show_wizard(force=True)).pack(anchor="w", padx=16, pady=(6, 12))

    return page
