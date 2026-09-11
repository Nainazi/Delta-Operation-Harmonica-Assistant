"""演奏页构建。"""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk

from ..admin_check import UNELEVATED_HINT
from .theme import (
    C_BG, C_CARD, C_CARD_HI, C_TEXT, C_TEXT_DIM, C_ACCENT, C_ACCENT_HOVER,
    C_DANGER, C_WARN, RISK_BANNER, ToolTip, make_card,
)

if TYPE_CHECKING:
    from .app import App


def build_play_page(app: "App") -> ctk.CTkFrame:
    page = ctk.CTkFrame(app.root, fg_color=C_BG, corner_radius=0)

    page.grid_columnconfigure(0, weight=1)
    page.grid_rowconfigure(3, weight=1)

    ctk.CTkLabel(
        page, text=RISK_BANNER, fg_color=C_DANGER, text_color="#ffffff",
        corner_radius=8, font=ctk.CTkFont(family="Segoe UI", size=11),
        anchor="w", pady=8, padx=12).grid(
            row=0, column=0, sticky="ew", padx=16, pady=(14, 8))

    app.admin_banner = ctk.CTkFrame(page, fg_color="#4a3210", corner_radius=8)
    admin_row = ctk.CTkFrame(app.admin_banner, fg_color="transparent")
    admin_row.pack(fill="x", padx=10, pady=8)
    app.admin_banner_label = ctk.CTkLabel(
        admin_row, text="⚠ " + UNELEVATED_HINT,
        text_color=C_WARN, font=ctk.CTkFont(family="Segoe UI", size=12),
        anchor="w", justify="left", wraplength=760)
    app.admin_banner_label.pack(side="left", fill="x", expand=True)
    app.admin_relaunch_btn = ctk.CTkButton(
        admin_row, text="以管理员身份重启", width=148, height=28, corner_radius=8,
        fg_color=C_CARD_HI, hover_color="#3a5044", text_color=C_TEXT,
        font=ctk.CTkFont(family="Segoe UI", size=12),
        command=app._on_relaunch_elevated)
    app.admin_relaunch_btn.pack(side="right", padx=(8, 0))
    ToolTip(
        app.admin_relaunch_btn,
        "关闭本窗口并弹出一次 UAC。取消授权则保持当前进程，不会反复弹窗。")

    ctrl = ctk.CTkFrame(page, fg_color=C_CARD, corner_radius=14)
    ctrl.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 10))
    ctrl.grid_columnconfigure(0, weight=1)

    def row_action(parent, label, text, cmd, accent=False, tip=None):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", pady=2)
        ctk.CTkLabel(
            f, text=label, text_color=C_TEXT_DIM, width=56, anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=11)).pack(side="left")
        btn = ctk.CTkButton(
            f, text=text, height=32, corner_radius=8,
            fg_color=(C_ACCENT if accent else C_CARD_HI),
            hover_color=(C_ACCENT_HOVER if accent else "#3a5044"),
            text_color=("#0b0f11" if accent else C_TEXT),
            command=cmd)
        btn.pack(side="left", fill="x", expand=True, padx=(6, 0))
        if tip:
            ToolTip(btn, tip)
        return btn, f

    top = ctk.CTkFrame(ctrl, fg_color="transparent")
    top.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
    ctk.CTkLabel(
        top, text="模式", text_color=C_TEXT_DIM,
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")).pack(side="left")
    app.mode_var = tk.StringVar(value=app.cfg.mode)
    app._mode_radios = []
    for m, desc, tip in [
        ("C", "手动辅助", "脚本只显示提示（z x c v b n m + 中键半音），你自己按，不注入"),
        ("E", "鼠标宏教程", "导出 Markdown 手写鼠标宏教程（新键位 + 中键半音）"),
        ("B", "自动注入", "脚本自动模拟 z–m 键与中键半音，违反游戏 ToS。游戏若以管理员运行，本工具也须以管理员运行。")]:
        rb = ctk.CTkRadioButton(
            top, text=desc, variable=app.mode_var, value=m,
            # 把选中值直接传给 handler，避免个别 CTk 版本 command 早于 variable 更新
            command=lambda selected=m: app._on_mode_change(selected),
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=C_TEXT, fg_color=C_ACCENT)
        rb.pack(side="left", padx=8)
        ToolTip(rb, tip)
        app._mode_radios.append(rb)

    mid = ctk.CTkFrame(ctrl, fg_color="transparent")
    mid.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 12))
    mid.grid_columnconfigure((0, 1, 2), weight=1)

    col1 = ctk.CTkFrame(mid, fg_color="transparent")
    col1.grid(row=0, column=0, sticky="ew", padx=4)
    ctk.CTkLabel(
        col1, text="播放控制", text_color=C_TEXT_DIM,
        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        anchor="w").pack(fill="x")
    app.primary_btn, _ = row_action(col1, "播放", "▶ 开始演奏", app._on_start, accent=True)
    row_action(col1, "停止", "⏹ 停止", app._on_stop)
    app.test_btn, _ = row_action(
        col1, "试运行", "👁 试运行", app._on_test_run,
        tip="只走时序与提示，不发送任何输入")
    row_action(col1, "解析", "🔍 解析预览", app._on_parse_preview)
    app.hotkey_hint = ctk.CTkLabel(
        col1,
        text="热键  " + app.cfg.hotkey.start.upper() + " 开始 / "
             + app.cfg.hotkey.stop.upper() + " 停止",
        text_color=C_TEXT_DIM, font=ctk.CTkFont(family="Segoe UI", size=10),
        anchor="w")
    app.hotkey_hint.pack(fill="x", pady=(6, 0))

    col2 = ctk.CTkFrame(mid, fg_color="transparent")
    col2.grid(row=0, column=1, sticky="ew", padx=4)
    app._file_col = col2
    ctk.CTkLabel(
        col2, text="曲谱文件", text_color=C_TEXT_DIM,
        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        anchor="w").pack(fill="x")
    row_action(col2, "载入", "📂 载入曲谱", app._on_load_file)
    app.save_btn, _ = row_action(col2, "保存", "💾 保存曲谱", app._on_save_file)
    app.export_md_btn, app.export_md_row = row_action(
        col2, "导出", "📤 导出宏教程 MD", app._on_export_macro_md,
        tip="导出可读 Markdown：教你按新键位手写鼠标宏（含中键半音与 BPM）")
    app.convert_btn, _ = row_action(
        col2, "转换", "🔄 转换简谱", app._on_convert,
        tip="把括号/点八度、空分隔连写等简谱转为本工具记法")

    col3 = ctk.CTkFrame(mid, fg_color="transparent")
    col3.grid(row=0, column=2, sticky="ew", padx=4)
    ctk.CTkLabel(
        col3, text="悬浮提示", text_color=C_TEXT_DIM,
        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        anchor="w").pack(fill="x")
    app.hud_btn, _ = row_action(
        col3, "HUD", "🖥 显示覆盖层", app._toggle_hud, accent=True,
        tip="在游戏画面上悬浮一个半透明、点击穿透的当前音符提示窗")

    main = ctk.CTkFrame(page, fg_color="transparent")
    main.grid(row=3, column=0, sticky="nsew", padx=16, pady=(0, 6))
    main.grid_columnconfigure(0, weight=3)
    main.grid_columnconfigure(1, weight=2)
    main.grid_rowconfigure(0, weight=1)

    left = make_card(main, "曲谱编辑（简谱）")
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
    app.score_text = ctk.CTkTextbox(
        left, font=ctk.CTkFont(family="Consolas", size=13),
        fg_color="#0e1417", text_color=C_TEXT,
        corner_radius=8, wrap="word")
    app.score_text.pack(fill="both", expand=True, padx=12, pady=(0, 4))
    ctk.CTkLabel(
        left,
        text="记法: 1-7 音级(键 z x c v b n m) · #升 b降=按住中键 · ^高 ,低八度 · - . _ · 0休止 · | · // · @bpm",
        text_color=C_TEXT_DIM, font=ctk.CTkFont(family="Segoe UI", size=10),
        anchor="w").pack(fill="x", padx=12, pady=(0, 10))

    ai_card = make_card(main, None)
    ai_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
    ai_head = ctk.CTkFrame(ai_card, fg_color="transparent")
    ai_head.pack(fill="x", padx=12, pady=(10, 4))
    ctk.CTkLabel(
        ai_head, text="AI 简谱提示词",
        font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        text_color=C_ACCENT, anchor="w").pack(side="left")
    btn_row = ctk.CTkFrame(ai_head, fg_color="transparent")
    btn_row.pack(side="right")
    ctk.CTkButton(
        btn_row, text="从剪贴板填入", width=110, height=28, corner_radius=8,
        fg_color=C_CARD_HI, hover_color="#3a5044", text_color=C_TEXT,
        font=ctk.CTkFont(family="Segoe UI", size=12),
        command=app._paste_ai_from_clipboard).pack(side="left", padx=(0, 6))
    ctk.CTkButton(
        btn_row, text="复制", width=64, height=28, corner_radius=8,
        fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#0b0f11",
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        command=app._copy_ai_prompt).pack(side="left")
    app.ai_prompt_box = ctk.CTkTextbox(
        ai_card, font=ctk.CTkFont(family="Consolas", size=11),
        fg_color="#0e1417", text_color=C_TEXT, corner_radius=8, wrap="word")
    app.ai_prompt_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
    app.ai_prompt_box.insert("1.0", app._ai_prompt_text())
    app.ai_prompt_box.configure(state="disabled")

    bottom = ctk.CTkFrame(page, fg_color="transparent")
    bottom.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 12))

    strip = ctk.CTkFrame(bottom, fg_color=C_CARD, corner_radius=8)
    strip.pack(fill="x")
    row = ctk.CTkFrame(strip, fg_color="transparent")
    row.pack(fill="x", padx=12, pady=6)

    ctk.CTkLabel(
        row, text="当前", text_color=C_TEXT_DIM,
        font=ctk.CTkFont(family="Segoe UI", size=11)).pack(side="left")
    app.current_note_label = ctk.CTkLabel(
        row, text="—",
        font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
        text_color=C_ACCENT, width=120)
    app.current_note_label.pack(side="left", padx=(6, 8))
    app.beat_label = ctk.CTkLabel(
        row, text="", text_color=C_TEXT_DIM,
        font=ctk.CTkFont(family="Segoe UI", size=11))
    app.beat_label.pack(side="left")
    app.progress = ctk.CTkProgressBar(
        row, progress_color=C_ACCENT, fg_color=C_CARD_HI, height=8, width=160)
    app.progress.set(0)
    app.progress.pack(side="left", padx=(12, 10))
    app.status_label = ctk.CTkLabel(
        row, text="就绪 · 建议先用「试运行」预览节奏",
        anchor="w", text_color=C_TEXT_DIM,
        font=ctk.CTkFont(family="Segoe UI", size=11))
    app.status_label.pack(side="left", fill="x", expand=True)

    app.warn_text = ctk.CTkTextbox(
        bottom, height=42, font=ctk.CTkFont(family="Consolas", size=11),
        fg_color="#201a10", text_color=C_WARN, corner_radius=8, wrap="word")
    app.warn_text.pack(fill="x", pady=(4, 0))
    app.warn_text.configure(state="disabled")
    app._warn_has_content = False

    return page
