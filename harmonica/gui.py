"""现代图形界面（customtkinter 暗色主题 + 侧边栏导航）。

布局：
  左侧边栏：标题 + 导航（演奏 / 使用引导 / 设置）+ 风险徽标
  主内容区：按导航切换
    演奏    曲谱编辑 + 模式 + 控制 + 当前音符大号显示
    使用引导  完整分模式操作步骤
    设置    BPM / 人性化 / 键-点击顺序 / 输入后端

HUD 覆盖层仍用原生 tk.Toplevel（customtkinter 不支持 -transparentcolor）。
线程安全：dispatcher 进度回调通过 root.after 转回主线程。
"""
from __future__ import annotations

import os
import queue
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional, List

import customtkinter as ctk

from . import config as cfgmod
from . import score_parser as parser
from . import score_convert as convert
from . import dispatcher as disp
from . import input_backend as backend_mod
from . import macro_md_exporter
from . import ghub_exporter  # 兼容旧名；实际转发 MD 导出
from .config import DEFAULT_KEY_MAP, degree_to_key


RISK_BANNER = (
    "⚠ B 模式自动注入键鼠属游戏禁止行为，封号风险高；"
    "E 模式导出鼠标宏手写教程（中风险）。仅限单人/安全区/非竞技场景，风险自负。C 模式零风险。"
)

# 三角洲行动风格配色（战术青绿 + 深色军事质感）
C_BG = "#0e1316"          # 近黑深蓝灰
C_SIDEBAR = "#141a1e"     # 侧边栏稍亮
C_CARD = "#1a2126"        # 卡片深青灰
C_CARD_HI = "#222b31"     # 卡片悬停/高亮
C_TEXT = "#e8eef0"        # 主文字近白
C_TEXT_DIM = "#93a3a8"    # 次要文字灰
C_ACCENT = "#3fd0b0"      # 战术青绿（三角洲行动标志性强调色）
C_ACCENT_HOVER = "#2fbfa0"
C_OK = "#3fd0b0"
C_WARN = "#ffb454"
C_DANGER = "#ff5f5f"

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
        lbl = tk.Label(self.tip, text=self.text, justify="left",
                       background="#11121a", foreground=C_TEXT,
                       relief="flat", padx=10, pady=6, font=("Segoe UI", 9))
        lbl.pack()
        self.tip.geometry("+%d+%d" % (x, y))

    def _hide(self, _e: tk.Event) -> None:
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


def _init_theme() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    ctk.deactivate_automatic_dpi_awareness()

class App:
    def __init__(self, root: ctk.CTk, initial_score: Optional[str] = None,
                 initial_mode: Optional[str] = None) -> None:
        self.root = root
        self.cfg = cfgmod.load()
        self.dispatcher: Optional[disp.Dispatcher] = None
        self.current_events: List[parser.NoteEvent] = []
        self.hud: Optional["HUDOverlay"] = None
        self._nav_buttons: dict = {}
        self._progress_queue: "queue.Queue" = queue.Queue()

        root.title(cfgmod.APP_NAME + "  v" + cfgmod.APP_VERSION)
        root.configure(fg_color=C_BG)
        root.geometry("1180x720")
        root.minsize(1020, 640)

        self._build_sidebar()
        self._build_content()

        if initial_score and os.path.isfile(initial_score):
            self._load_score_file(initial_score)
        elif self.cfg.last_score:
            self.score_text.insert("1.0", self.cfg.last_score)
        else:
            self._load_default_score()

        if initial_mode in ("C", "B", "E"):
            self.cfg.mode = initial_mode
        self.mode_var.set(self.cfg.mode)
        self._update_primary_button()

        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._show_page("play")
        # 启动进度队列轮询（主线程消费，避免子线程直接调用 tkinter）
        self.root.after(50, self._poll_progress)
        self._hotkey_handles = []
        self.root.after(200, self._register_hotkeys)

    def _build_sidebar(self) -> None:
        bar = ctk.CTkFrame(self.root, width=190, corner_radius=0, fg_color=C_SIDEBAR)
        bar.pack(side="left", fill="y")
        bar.pack_propagate(False)

        title = ctk.CTkLabel(bar, text="🎵  佐拉口琴谱伴",
                             font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
                             text_color=C_TEXT, anchor="w")
        title.pack(fill="x", padx=18, pady=(22, 4))
        sub = ctk.CTkLabel(bar, text="三角洲行动 · 彩蛋口琴",
                           font=ctk.CTkFont(family="Segoe UI", size=11),
                           text_color=C_TEXT_DIM, anchor="w")
        sub.pack(fill="x", padx=18, pady=(0, 14))
        # 装饰性分割线（战术风）
        ctk.CTkFrame(bar, height=2, fg_color=C_ACCENT, corner_radius=0).pack(fill="x", padx=18, pady=(0, 14))

        for key, icon, label in [("play", "▶", "演奏"),
                                 ("guide", "📖", "使用引导"),
                                 ("settings", "⚙", "设置")]:
            btn = ctk.CTkButton(bar, text="  " + icon + "   " + label, anchor="w",
                                fg_color="transparent", hover_color=C_CARD_HI,
                                text_color=C_TEXT, corner_radius=8, height=42,
                                font=ctk.CTkFont(family="Segoe UI", size=14),
                                command=lambda k=key: self._show_page(k))
            btn.pack(fill="x", padx=10, pady=4)
            self._nav_buttons[key] = btn

        # 底部风险徽标
        badge = ctk.CTkLabel(bar, text="C 零风险\nE 宏教程·中\nB 高风险",
                             font=ctk.CTkFont(family="Segoe UI", size=10),
                             text_color=C_TEXT_DIM, justify="left", anchor="w",
                             fg_color=C_CARD, corner_radius=10)
        badge.pack(fill="x", side="bottom", padx=14, pady=14)

    def _show_page(self, key: str) -> None:
        for k, f in self._pages.items():
            if k == key:
                f.pack(fill="both", expand=True, side="left")
            else:
                f.pack_forget()
        for k, btn in self._nav_buttons.items():
            if k == key:
                btn.configure(fg_color=C_ACCENT, text_color="#0b0f11",
                              font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"))
            else:
                btn.configure(fg_color="transparent", text_color=C_TEXT,
                              font=ctk.CTkFont(family="Segoe UI", size=14))

    def _build_content(self) -> None:
        self._pages = {}
        self._pages["play"] = self._build_play_page()
        self._pages["guide"] = self._build_guide_page()
        self._pages["settings"] = self._build_settings_page()

    def _card(self, parent, text=None) -> ctk.CTkFrame:
        f = ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=14)
        if text:
            lbl = ctk.CTkLabel(f, text=text, anchor="w",
                               font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                               text_color=C_ACCENT)
            lbl.pack(fill="x", padx=16, pady=(12, 6))
        return f

    def _build_play_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.root, fg_color=C_BG, corner_radius=0)

        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(2, weight=1)

        # 风险横幅
        ctk.CTkLabel(page, text=RISK_BANNER, fg_color=C_DANGER, text_color="#ffffff",
                      corner_radius=8, font=ctk.CTkFont(family="Segoe UI", size=11),
                      anchor="w", pady=8, padx=12).grid(row=0, column=0, sticky="ew",
                                                        padx=16, pady=(14, 8))

        # ---- 原版三列工具栏 ----
        ctrl = ctk.CTkFrame(page, fg_color=C_CARD, corner_radius=14)
        ctrl.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        ctrl.grid_columnconfigure(0, weight=1)

        def row_action(parent, label, text, cmd, accent=False, tip=None):
            """左侧标签 + 右侧按钮的一行。"""
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.pack(fill="x", pady=2)
            ctk.CTkLabel(f, text=label, text_color=C_TEXT_DIM, width=56, anchor="w",
                         font=ctk.CTkFont(family="Segoe UI", size=11)).pack(side="left")
            btn = ctk.CTkButton(f, text=text, height=32, corner_radius=8,
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
        ctk.CTkLabel(top, text="模式", text_color=C_TEXT_DIM,
                     font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")).pack(side="left")
        self.mode_var = tk.StringVar(value=self.cfg.mode)
        self._mode_radios = []
        for m, desc, tip in [
            ("C", "手动辅助", "脚本只显示提示（z x c v b n m + 中键半音），你自己按，不注入"),
            ("E", "鼠标宏教程", "导出 Markdown 手写鼠标宏教程（新键位 + 中键半音）"),
            ("B", "自动注入", "脚本自动模拟 z–m 键与中键半音，违反游戏 ToS")]:
            rb = ctk.CTkRadioButton(top, text=desc, variable=self.mode_var, value=m,
                                    command=self._on_mode_change,
                                    font=ctk.CTkFont(family="Segoe UI", size=12),
                                    text_color=C_TEXT, fg_color=C_ACCENT)
            rb.pack(side="left", padx=8)
            ToolTip(rb, tip)
            self._mode_radios.append(rb)

        mid = ctk.CTkFrame(ctrl, fg_color="transparent")
        mid.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 12))
        mid.grid_columnconfigure((0, 1, 2), weight=1)

        col1 = ctk.CTkFrame(mid, fg_color="transparent")
        col1.grid(row=0, column=0, sticky="ew", padx=4)
        ctk.CTkLabel(col1, text="播放控制", text_color=C_TEXT_DIM,
                     font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                     anchor="w").pack(fill="x")
        self.primary_btn, _ = row_action(col1, "播放", "▶ 开始演奏", self._on_start, accent=True)
        row_action(col1, "停止", "⏹ 停止", self._on_stop)
        self.test_btn, _ = row_action(col1, "试运行", "👁 试运行", self._on_test_run,
                   tip="只走时序与提示，不发送任何输入")
        row_action(col1, "解析", "🔍 解析预览", self._on_parse_preview)
        self.hotkey_hint = ctk.CTkLabel(
            col1,
            text="热键  " + self.cfg.hotkey.start.upper() + " 开始 / "
                 + self.cfg.hotkey.stop.upper() + " 停止",
            text_color=C_TEXT_DIM, font=ctk.CTkFont(family="Segoe UI", size=10),
            anchor="w")
        self.hotkey_hint.pack(fill="x", pady=(6, 0))

        col2 = ctk.CTkFrame(mid, fg_color="transparent")
        col2.grid(row=0, column=1, sticky="ew", padx=4)
        self._file_col = col2
        ctk.CTkLabel(col2, text="曲谱文件", text_color=C_TEXT_DIM,
                     font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                     anchor="w").pack(fill="x")
        row_action(col2, "载入", "📂 载入曲谱", self._on_load_file)
        self.save_btn, _ = row_action(col2, "保存", "💾 保存曲谱", self._on_save_file)
        self.export_md_btn, self.export_md_row = row_action(
            col2, "导出", "📤 导出宏教程 MD", self._on_export_macro_md,
            tip="导出可读 Markdown：教你按新键位手写鼠标宏（含中键半音与 BPM）")
        self.convert_btn, _ = row_action(col2, "转换", "🔄 转换简谱", self._on_convert,
                   tip="把括号/点八度、空分隔连写等简谱转为本工具记法")

        col3 = ctk.CTkFrame(mid, fg_color="transparent")
        col3.grid(row=0, column=2, sticky="ew", padx=4)
        ctk.CTkLabel(col3, text="悬浮提示", text_color=C_TEXT_DIM,
                     font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                     anchor="w").pack(fill="x")
        self.hud_btn, _ = row_action(col3, "HUD", "🖥 显示覆盖层", self._toggle_hud, accent=True,
                                  tip="在游戏画面上悬浮一个半透明、点击穿透的当前音符提示窗")

        # ---- 主编辑区并排：曲谱略大，整体让位给工具栏 ----
        main = ctk.CTkFrame(page, fg_color="transparent")
        main.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 6))
        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=2)
        main.grid_rowconfigure(0, weight=1)

        left = self._card(main, "曲谱编辑（简谱）")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.score_text = ctk.CTkTextbox(left, font=ctk.CTkFont(family="Consolas", size=13),
                                          fg_color="#0e1417", text_color=C_TEXT,
                                          corner_radius=8, wrap="word")
        self.score_text.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        ctk.CTkLabel(
            left,
            text="记法: 1-7 音级(键 z x c v b n m) · #升 b降=按住中键 · ^高 ,低八度 · - . _ · 0休止 · | · // · @bpm",
            text_color=C_TEXT_DIM, font=ctk.CTkFont(family="Segoe UI", size=10),
            anchor="w").pack(fill="x", padx=12, pady=(0, 10))

        ai_card = self._card(main, None)
        ai_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ai_head = ctk.CTkFrame(ai_card, fg_color="transparent")
        ai_head.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(ai_head, text="AI 简谱提示词",
                     font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                     text_color=C_ACCENT, anchor="w").pack(side="left")
        ctk.CTkButton(ai_head, text="复制", width=64, height=28, corner_radius=8,
                      fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#0b0f11",
                      font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                      command=self._copy_ai_prompt).pack(side="right")
        self.ai_prompt_box = ctk.CTkTextbox(
            ai_card, font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0e1417", text_color=C_TEXT, corner_radius=8, wrap="word")
        self.ai_prompt_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.ai_prompt_box.insert("1.0", self._ai_prompt_text())
        self.ai_prompt_box.configure(state="disabled")

        # ---- 底栏 ----
        bottom = ctk.CTkFrame(page, fg_color="transparent")
        bottom.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 12))

        strip = ctk.CTkFrame(bottom, fg_color=C_CARD, corner_radius=8)
        strip.pack(fill="x")
        row = ctk.CTkFrame(strip, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=6)

        ctk.CTkLabel(row, text="当前",
                     text_color=C_TEXT_DIM, font=ctk.CTkFont(family="Segoe UI", size=11)
                     ).pack(side="left")
        self.current_note_label = ctk.CTkLabel(
            row, text="—",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=C_ACCENT, width=120)
        self.current_note_label.pack(side="left", padx=(6, 8))
        self.beat_label = ctk.CTkLabel(row, text="", text_color=C_TEXT_DIM,
                                       font=ctk.CTkFont(family="Segoe UI", size=11))
        self.beat_label.pack(side="left")
        self.progress = ctk.CTkProgressBar(row, progress_color=C_ACCENT, fg_color=C_CARD_HI,
                                           height=8, width=160)
        self.progress.set(0)
        self.progress.pack(side="left", padx=(12, 10))
        self.status_label = ctk.CTkLabel(
            row, text="就绪 · 建议先用「试运行」预览节奏",
            anchor="w", text_color=C_TEXT_DIM,
            font=ctk.CTkFont(family="Segoe UI", size=11))
        self.status_label.pack(side="left", fill="x", expand=True)

        self.warn_text = ctk.CTkTextbox(
            bottom, height=42, font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#201a10", text_color=C_WARN, corner_radius=8, wrap="word")
        self.warn_text.pack(fill="x", pady=(4, 0))
        self.warn_text.configure(state="disabled")
        self._warn_has_content = False

        return page

    def _build_guide_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.root, fg_color=C_BG, corner_radius=0)
        # 用原生 tk.Text 以支持 font 标签（CTkTextbox 禁止 font tag）
        txt = tk.Text(page, font=("Segoe UI", 12), bg=C_CARD, fg=C_TEXT,
                       relief="flat", bd=0, highlightthickness=0, wrap="word",
                       padx=20, pady=18)
        # 滚动条
        from tkinter import ttk as _ttk
        sb = _ttk.Scrollbar(page, command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 16), pady=16)
        txt.pack(fill="both", expand=True, padx=(16, 0), pady=16)
        guide = self._guide_text()
        for line in guide.splitlines():
            if line.startswith("# "):
                txt.insert("end", line[2:] + "\n", "h1")
            elif line.startswith("## "):
                txt.insert("end", line[3:] + "\n", "h2")
            elif line.startswith("- "):
                txt.insert("end", "  • " + line[2:] + "\n", "li")
            elif line.startswith("> "):
                txt.insert("end", line + "\n", "warn")
            else:
                txt.insert("end", line + "\n")
        txt.tag_config("h1", font=("Segoe UI", 18, "bold"), foreground=C_ACCENT,
                       spacing3=6)
        txt.tag_config("h2", font=("Segoe UI", 14, "bold"), foreground="#7fb0ff",
                       spacing3=4)
        txt.tag_config("li", lmargin1=14, lmargin2=28)
        txt.tag_config("warn", foreground=C_WARN, font=("Segoe UI", 12, "bold"))
        txt.configure(state="disabled")
        return page

    def _build_settings_page(self) -> ctk.CTkFrame:
        page = ctk.CTkScrollableFrame(self.root, fg_color=C_BG, corner_radius=0)

        # 节奏
        gf = self._card(page, "节奏")
        gf.pack(fill="x", padx=16, pady=(16, 10))
        row = ctk.CTkFrame(gf, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkLabel(row, text="BPM", text_color=C_TEXT,
                     font=ctk.CTkFont(family="Segoe UI", size=12)).pack(side="left")
        self.bpm_var = tk.DoubleVar(value=self.cfg.timing.bpm)
        bpm_spin = ctk.CTkEntry(row, textvariable=self.bpm_var, width=70, justify="center",
                                fg_color="#1a1b24", text_color=C_TEXT, border_color=C_CARD_HI)
        bpm_spin.pack(side="left", padx=10)
        self.bpm_var.trace_add("write", lambda *_: self._on_bpm_change())
        ToolTip(bpm_spin, "数字越大节奏越快；曲谱内 @bpm 会覆盖此值")
        ctk.CTkLabel(row, text="一拍 ≈ %.2f 秒" % self.cfg.timing.beat_seconds,
                     text_color=C_TEXT_DIM,
                     font=ctk.CTkFont(family="Segoe UI", size=11)).pack(side="left", padx=10)

        # 人性化
        hf = self._card(page, "时序人性化（降低行为检测概率，不能消除风险）")
        hf.pack(fill="x", padx=16, pady=(0, 10))
        self.humanize_var = tk.BooleanVar(value=self.cfg.humanize.enabled)
        ctk.CTkCheckBox(hf, text="启用时长/间隔抖动", variable=self.humanize_var,
                        command=self._on_humanize_change, text_color=C_TEXT,
                        fg_color=C_ACCENT, font=ctk.CTkFont(family="Segoe UI", size=12)
                        ).pack(anchor="w", padx=16, pady=(6, 8))
        ctk.CTkLabel(hf, text="时长抖动幅度", text_color=C_TEXT_DIM,
                     font=ctk.CTkFont(family="Segoe UI", size=11)).pack(anchor="w", padx=16)
        self.jitter_var = tk.DoubleVar(value=self.cfg.humanize.duration_jitter_pct)
        js = ctk.CTkSlider(hf, from_=0.0, to=0.30, variable=self.jitter_var,
                           command=lambda v: self._on_jitter_change(),
                           button_color=C_ACCENT, button_hover_color=C_ACCENT_HOVER)
        js.pack(fill="x", padx=16, pady=(4, 12))
        ToolTip(js, "0=关闭抖动；建议 5%~15%，过大节奏不稳")

        # 键-点击顺序
        kf = self._card(page, "键-点击顺序")
        kf.pack(fill="x", padx=16, pady=(0, 10))
        self.key_first_var = tk.BooleanVar(value=self.cfg.timing.key_before_click)
        cb = ctk.CTkCheckBox(kf, text="先按字母键、再点中键（不勾选=先按住中键再按字母，推荐）",
                            variable=self.key_first_var, command=self._on_key_order_change,
                            text_color=C_TEXT, fg_color=C_ACCENT,
                            font=ctk.CTkFont(family="Segoe UI", size=12))
        cb.pack(anchor="w", padx=16, pady=(6, 8))
        ToolTip(cb, "半音=按住中键+字母。推荐不勾选（先中键再字母）；若不准可勾选换序")
        ctk.CTkLabel(kf, text="演奏键位：1→z  2→x  3→c  4→v  5→b  6→n  7→m｜半音：按住鼠标中键",
                     text_color=C_TEXT_DIM, font=ctk.CTkFont(family="Segoe UI", size=10),
                     anchor="w").pack(fill="x", padx=16, pady=(0, 12))

        # 全局热键（手动辅助 / 自动注入 开始·停止）
        hk = self._card(page, "全局热键（手动辅助 / 自动注入）")
        hk.pack(fill="x", padx=16, pady=(0, 10))
        hk_row = ctk.CTkFrame(hk, fg_color="transparent")
        hk_row.pack(fill="x", padx=16, pady=(6, 4))
        ctk.CTkLabel(hk_row, text="开始", text_color=C_TEXT,
                     font=ctk.CTkFont(family="Segoe UI", size=12), width=40).pack(side="left")
        self.hotkey_start_var = tk.StringVar(value=self.cfg.hotkey.start)
        e1 = ctk.CTkEntry(hk_row, textvariable=self.hotkey_start_var, width=100, justify="center",
                          fg_color="#1a1b24", text_color=C_TEXT, border_color=C_CARD_HI)
        e1.pack(side="left", padx=(0, 16))
        ctk.CTkLabel(hk_row, text="停止", text_color=C_TEXT,
                     font=ctk.CTkFont(family="Segoe UI", size=12), width=40).pack(side="left")
        self.hotkey_stop_var = tk.StringVar(value=self.cfg.hotkey.stop)
        e2 = ctk.CTkEntry(hk_row, textvariable=self.hotkey_stop_var, width=100, justify="center",
                          fg_color="#1a1b24", text_color=C_TEXT, border_color=C_CARD_HI)
        e2.pack(side="left")
        ctk.CTkLabel(hk, text="默认 F5 开始 / F6 停止（避开 z x c v b n m 与 WASD）。曲中按停止可立即中断。",
                     text_color=C_TEXT_DIM, font=ctk.CTkFont(family="Segoe UI", size=10),
                     anchor="w").pack(fill="x", padx=16, pady=(4, 4))
        ctk.CTkButton(hk, text="应用热键", width=100, height=30, corner_radius=8,
                      fg_color=C_CARD_HI, hover_color="#3a5044", text_color=C_TEXT,
                      command=self._apply_hotkeys).pack(anchor="w", padx=16, pady=(0, 12))

        # 输入后端
        bf = self._card(page, "输入后端（仅 B 模式）")
        bf.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkLabel(bf, text="注入方式", text_color=C_TEXT_DIM,
                     font=ctk.CTkFont(family="Segoe UI", size=11)).pack(anchor="w", padx=16, pady=(6, 4))
        self.backend_var = tk.StringVar(value=self.cfg.input.backend)
        bb = ctk.CTkOptionMenu(bf, variable=self.backend_var,
                               values=["pydirectinput", "keyboard_ctypes", "null"],
                               fg_color=C_CARD_HI, button_color=C_CARD_HI,
                               button_hover_color="#3a3c50", text_color=C_TEXT,
                               dropdown_fg_color=C_CARD, dropdown_text_color=C_TEXT,
                               dropdown_hover_color=C_CARD_HI)
        bb.pack(anchor="w", padx=16)
        self.backend_var.trace_add("write", lambda *_: self._on_backend_change())
        ToolTip(bb, "pydirectinput=DirectInput（默认）；keyboard_ctypes=备选；null=不注入（测试）")
        ctk.CTkLabel(bf, text="keyboard 注入需以管理员身份运行 exe", text_color=C_TEXT_DIM,
                     font=ctk.CTkFont(family="Segoe UI", size=10)).pack(anchor="w", padx=16, pady=(8, 12))

        return page

    def _guide_text(self) -> str:
        return """# 佐拉口琴谱伴 · 使用引导

## 0. 这是什么
三角洲行动 2 周年庆「佐拉」彩蛋任务链奖励道具「口琴」的曲谱辅助工具。
口琴演奏机制（v1.0.2）：使用道具弹出演奏界面后，
按键 z x c v b n m 对应 do-re-mi-fa-sol-la-ti（音级 1-7），
按住鼠标中键的同时按字母 = 半音（曲谱 # 升 / b 降）。

本工具提供三种链路：C 手动辅助（零风险）/ E 鼠标宏教程（中风险）/ B 自动注入（高风险）。

## 1. 快速上手（C 模式，推荐）
1. 启动程序，默认进入「演奏」页，左侧已载入示例曲谱「小星星」。
2. 顶部模式选「手动辅助」。
3. 点「试运行」预览节奏，观察底部提示：字母键 + 半音时「中键+字母」。
4. 点「显示 HUD 覆盖层」，把悬浮窗拖到不挡视野的位置（双击换边角，右键关闭）。
5. 进入游戏，在局内使用口琴道具呼出演奏界面。
6. 回到本程序点「开始演奏」（或按 F5），照 HUD / 界面提示自己按 z–m；
   遇到升/降音时按住中键再按对应字母。
7. 点「停止」或按 F6 可随时中断（曲中立刻生效）。

## 2. E 模式（鼠标宏教程，中风险）
> 导出 Markdown 手写教程，按任意鼠标宏软件自行编排；已不再导出 G HUB Lua。

1. 顶部模式选「鼠标宏教程」。
2. 点「导出宏教程 MD」（或主按钮），保存 .md 文件。
3. 打开教程：内含键位表、BPM/时值、逐音动作表、伪代码。
4. 在你的鼠标驱动里按教程手写宏（中键按下 → 字母 → 抬起）。
5. 绑到侧键；安全区呼出口琴界面后再触发。

## 3. B 模式（自动注入，高风险）
> 仅限单人 / 安全区 / 非竞技场景，违反游戏 ToS，封号风险自负。

1. 先装依赖：pip install pydirectinput keyboard。
2. 顶部模式选「自动注入」，首次会弹风险确认窗。
3. 在游戏内先呼出口琴演奏界面，并保持游戏窗口聚焦（不要切走）。
4. 点「开始演奏」或按 F5，脚本自动按曲谱注入 z–m 与中键半音。
5. 点「停止」或按 F6 中断；演奏结束自动停止。
- 若升降音不生效：到「设置」页切换「键-中键顺序」再试。
- 若无任何反应：到「设置」把输入后端改为 keyboard_ctypes，并以管理员身份运行 exe。

## 4. 简谱记法
- 1 2 3 4 5 6 7 = do re mi fa sol la ti（演奏键 z x c v b n m）
- #1 #3 ... 升；b3 b6 ... 降（演奏时均为：按住中键 + 字母）
- 1^ 1, 高/低八度标记（仅用于音域校验，口琴无八度键，会警告）
- - 延长前音符一拍（可连用，如 5 - - = 三拍）
- . 附点（时值 ×1.5）；_ 减时（时值 ×0.5，可连用）
- 0 休止（一拍，可用 - 延长）；| 小节线（忽略）；// 行注释
- @bpm 120 曲谱内 BPM（覆盖设置）；@key C 调号（仅参考）

## 5. 音域与移调
口琴无八度键，实际可发音高 = 音级 + 升降（无八度偏移），
半音范围约 -1 到 12（b1 到 #7），约一个半八度。
- 带八度标记的音符会触发警告：口琴无法演奏该八度，将按基础音区发音。
- 意图半音超出范围的音符会触发警告：需移调/改编。
- 示例曲谱（harmonica/scores/）均已移调至口琴基础音区，可直接使用。

## 6. 反作弊风险（必读）
> 三角洲行动采用 ACE 内核级反作弊，强制启动、无法关闭。
> 官方禁止清单「Emulation Scripts」明确点名 AutoHotkey 与 Python。
> 查实即封号十年 + 机器码永久封禁，换号换硬盘无效，实名关联账号连坐。

- C 模式：零风险（不注入任何输入，仅显示提示）。
- B 模式：高风险（Python 直接注入键鼠，明令禁止）。
- E 模式：中风险（手写/驱动宏仍可能被监控；旧 G HUB Lua 路径已弃用）。
- 人性化抖动只能降低、不能消除检测概率。
- 本工具不读写游戏内存/封包、不绕过 ACE，仅供彩蛋娱乐，严禁用于竞技场景。

## 7. 配置与日志
- 配置保存在 %APPDATA%\\佐拉口琴谱伴\\settings.json
- 运行异常写入 %APPDATA%\\佐拉口琴谱伴\\error.log（便于 exe 排错）
- 命令行：python -m harmonica --score path --mode C
- 全局热键默认 F5 开始 / F6 停止，可在「设置」修改
"""

    def _on_mode_change(self) -> None:
        self.cfg.mode = self.mode_var.get()
        self._update_primary_button()
        self._save_cfg()

    def _on_bpm_change(self) -> None:
        try:
            bpm = float(self.bpm_var.get())
        except (tk.TclError, ValueError):
            return
        self.cfg.timing.bpm = bpm
        self.cfg.timing.beat_seconds = 60.0 / max(1.0, bpm)
        self._save_cfg()

    def _on_humanize_change(self) -> None:
        self.cfg.humanize.enabled = self.humanize_var.get()
        self._save_cfg()

    def _on_jitter_change(self) -> None:
        try:
            self.cfg.humanize.duration_jitter_pct = float(self.jitter_var.get())
        except (tk.TclError, ValueError):
            return
        self._save_cfg()

    def _on_key_order_change(self) -> None:
        self.cfg.timing.key_before_click = self.key_first_var.get()
        self._save_cfg()

    def _on_backend_change(self) -> None:
        self.cfg.input.backend = self.backend_var.get()
        self._save_cfg()

    def _save_cfg(self) -> None:
        self.cfg.last_score = self.score_text.get("1.0", "end")
        cfgmod.save(self.cfg)

    def _fill_warn_text(self, lines) -> None:
        """写入警告区；无内容时保持矮高度，有警告时略增高。"""
        if not hasattr(self, "warn_text"):
            return
        self.warn_text.configure(state="normal")
        self.warn_text.delete("1.0", "end")
        if lines:
            self.warn_text.insert("end", "\n".join(lines) + "\n")
            self.warn_text.configure(height=72)
            self._warn_has_content = True
        else:
            self.warn_text.configure(height=42)
            self._warn_has_content = False
        self.warn_text.configure(state="disabled")

    def _set_status(self, msg: str) -> None:
        if hasattr(self, "status_label"):
            self.status_label.configure(text=msg)

    def _parse_current(self) -> Optional[parser.ParseResult]:
        text = self.score_text.get("1.0", "end")
        try:
            result = parser.parse(text)
        except parser.ParseError as e:
            messagebox.showerror("曲谱错误", str(e))
            return None
        if result.bpm_override:
            self.bpm_var.set(result.bpm_override)
            self.cfg.timing.bpm = result.bpm_override
            self.cfg.timing.beat_seconds = 60.0 / result.bpm_override
        lines = []
        for idx, msg in result.warnings:
            tag = "[" + str(idx) + "] " if idx >= 0 else ""
            lines.append(tag + msg)
        self._fill_warn_text(lines)
        self.current_events = result.events
        self.progress.set(0)
        return result

    def _on_parse_preview(self) -> None:
        r = self._parse_current()
        if r is None:
            return
        self._set_status("解析完成：" + str(len(r.events)) + " 个事件")

    def _set_playing(self, playing: bool) -> None:
        """播放中禁用开始/试运行/模式切换，结束时恢复，防止并发多次播放。"""
        state = "disabled" if playing else "normal"
        try:
            self.primary_btn.configure(state=state)
            self.test_btn.configure(state=state)
            for rb in getattr(self, "_mode_radios", []):
                rb.configure(state=state)
        except Exception:
            pass

    def _on_start(self) -> None:
        # 守卫：已有播放线程在跑则拒绝再次开始
        if self.dispatcher is not None and self.dispatcher.is_running():
            self._set_status("正在播放中，请先停止")
            return
        mode = self.cfg.mode
        if mode == "E":
            self._on_export_macro_md()
            return
        if mode == "B" and not self.cfg.risk_acknowledged:
            if not messagebox.askyesno("风险确认",
                    "B 模式会向游戏自动注入键鼠输入，属游戏禁止行为，\n"
                    "存在封号十年 + 机器码永久封禁风险。\n\n"
                    "仅限单人/安全区/非竞技场景。\n\n确认理解风险并继续？"):
                return
            self.cfg.risk_acknowledged = True
            self._save_cfg()

        r = self._parse_current()
        if r is None or not r.events:
            self._set_status("无事件可播放")
            return

        if mode == "B":
            be = backend_mod.create_backend(self.cfg.input)
            if be.name == "null" and self.cfg.input.backend != "null":
                self._set_status("警告：输入后端库缺失，回退空后端（不会真正注入）")
            self.dispatcher = disp.Dispatcher(self.cfg, backend=be,
                                              on_progress=self._on_progress)
            self.dispatcher.play_b(r.events)
            self._set_playing(True)
            self._set_status("B 模式播放中… 切到游戏窗口保持聚焦")
        else:
            self.dispatcher = disp.Dispatcher(self.cfg,
                                               backend=backend_mod.NullBackend(),
                                               on_progress=self._on_progress)
            self.dispatcher.play_c(r.events)
            self._set_playing(True)
            self._set_status("C 模式提示中… 照提示按 z–m，半音按住中键（F6 可停）")

    def _on_test_run(self) -> None:
        if self.dispatcher is not None and self.dispatcher.is_running():
            self._set_status("正在播放中，请先停止")
            return
        r = self._parse_current()
        if r is None or not r.events:
            return
        self.dispatcher = disp.Dispatcher(self.cfg, backend=backend_mod.NullBackend(),
                                           on_progress=self._on_progress)
        self.dispatcher.play_c(r.events)
        self._set_playing(True)
        self._set_status("试运行中（不注入输入）")

    def _on_stop(self) -> None:
        if self.dispatcher and self.dispatcher.is_running():
            self.dispatcher.stop()
            self._set_playing(False)
            self._set_status("已停止")

    def _on_progress(self, idx: int, total: int, ev: Optional[parser.NoteEvent]) -> None:
        # 由 dispatcher 子线程调用：只放入队列，不直接碰 tkinter（线程安全）
        self._progress_queue.put((idx, total, ev))

    def _poll_progress(self) -> None:
        """主线程定期消费进度队列并刷新 UI。"""
        try:
            while True:
                idx, total, ev = self._progress_queue.get_nowait()
                self._update_progress(idx, total, ev)
        except queue.Empty:
            pass
        self.root.after(30, self._poll_progress)

    def _update_progress(self, idx: int, total: int, ev: Optional[parser.NoteEvent]) -> None:
        self.progress.set(idx / max(1, total))
        if ev is None:
            self.current_note_label.configure(text="—", text_color=C_ACCENT)
            self.beat_label.configure(text="")
            if self.hud is not None:
                self.hud.update_note(None, idx, total)
            self._set_playing(False)
            return
        if ev.is_rest:
            self.current_note_label.configure(text="休止", text_color=C_TEXT_DIM)
            self.beat_label.configure(text=str(ev.beats) + " 拍")
            if self.hud is not None:
                self.hud.update_note("休止", idx, total, beats=ev.beats, is_rest=True)
        else:
            hint = self._format_play_hint(ev)
            color = C_WARN if ev.accidental != 0 else C_ACCENT
            self.current_note_label.configure(text=hint, text_color=color)
            self.beat_label.configure(text=str(ev.beats) + " 拍")
            if self.hud is not None:
                self.hud.update_note(hint, idx, total, beats=ev.beats,
                                     accidental=ev.accidental, is_rest=False)

    def _toggle_hud(self) -> None:
        if self.hud is None or not self.hud.exists():
            self.hud = HUDOverlay(self.root)
            self.hud_btn.configure(text="🖥 隐藏覆盖层")
        else:
            self.hud.destroy()
            self.hud = None
            self.hud_btn.configure(text="🖥 显示覆盖层")

    def _update_primary_button(self) -> None:
        if not hasattr(self, "primary_btn"):
            return
        m = self.cfg.mode
        if m == "E":
            self.primary_btn.configure(text="📤  导出宏教程 MD", command=self._on_export_macro_md)
            # E 模式主按钮即导出，隐藏曲谱文件列里的重复导出行
            if hasattr(self, "export_md_row"):
                self.export_md_row.pack_forget()
        else:
            self.primary_btn.configure(text="▶  开始演奏", command=self._on_start)
            if hasattr(self, "export_md_row") and hasattr(self, "convert_btn"):
                if not self.export_md_row.winfo_ismapped():
                    # 插回「转换」行之前
                    self.export_md_row.pack(fill="x", pady=2, before=self.convert_btn.master)

    def _format_play_hint(self, ev: "parser.NoteEvent") -> str:
        """手动辅助大字提示：字母键；半音时带中键。"""
        key = degree_to_key(self.cfg, ev.degree)
        acc = {1: "♯", -1: "♭", 0: ""}[ev.accidental]
        if ev.accidental != 0:
            return "中键+" + key + " " + acc
        return key

    def _ai_prompt_text(self) -> str:
        """可复制的 AI 简谱生成提示词（贴合本工具 score_parser 记法）。"""
        return (
            "你是简谱助手。请把用户给出的旋律写成「佐拉口琴谱伴」可用的文本简谱。\n"
            "\n"
            "【输出格式硬性规则】\n"
            "1. 只用空白分隔的 token；可多行；可写 // 行注释。\n"
            "2. 音级只能是 1-7（do-re-mi-fa-sol-la-ti）；休止用 0。\n"
            "3. 升号写 #1 #3；降号写 b3 b6（b 必须小写，紧贴数字）。\n"
            "4. 时值修饰（跟在音符后的独立 token）：\n"
            "   - 延长一拍；可连用（5 - - = 三拍）\n"
            "   . 附点（×1.5）；_ 减半（×0.5，可连用 __）\n"
            "5. | 小节线可写但会被忽略；不要输出和弦、歌词、吉他谱。\n"
            "6. 开头可写 @bpm 90 这类速度；可选 @key C。\n"
            "7. 八度：^ 高八度、, 低八度仅作标记——口琴无八度键，尽量改编到基础音区 1-7。\n"
            "8. 半音范围约 b1..#7；超范围请先移调再输出。\n"
            "\n"
            "【演奏键位提示（给人类看，不要写进谱面）】\n"
            "音级 1-7 对应按键 z x c v b n m；升/降演奏时按住鼠标中键再按字母。\n"
            "\n"
            "【合法示例（小星星片段）】\n"
            "@bpm 100\n"
            "1 1 5 5 6 6 5 -\n"
            "4 4 3 3 2 2 1 -\n"
            "\n"
            "【含升降示例】\n"
            "@bpm 80\n"
            "6 1 2 3 - 5 3 2 1 -\n"
            "3 #4 5 6 5 3 2 1 -\n"
            "\n"
            "【请直接输出曲谱正文，不要 markdown 代码围栏，不要解释】\n"
            "用户旋律/歌名："
        )

    def _copy_ai_prompt(self) -> None:
        content = self.ai_prompt_box.get("1.0", "end-1c")
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.root.update_idletasks()
            self._set_status("已复制 AI 简谱提示词到剪贴板")
        except tk.TclError as e:
            messagebox.showerror("复制失败", str(e))

    def _register_hotkeys(self) -> None:
        """注册全局开始/停止热键；失败则回退到窗口内 F 键绑定。"""
        self._unregister_hotkeys()
        start = (self.cfg.hotkey.start or "f5").strip().lower()
        stop = (self.cfg.hotkey.stop or "f6").strip().lower()
        self.cfg.hotkey.start = start
        self.cfg.hotkey.stop = stop
        ok = False
        try:
            import keyboard as _kb
            # 用 after 切回主线程，避免 tk 线程问题
            h1 = _kb.add_hotkey(start, lambda: self.root.after(0, self._hotkey_start))
            h2 = _kb.add_hotkey(stop, lambda: self.root.after(0, self._hotkey_stop))
            self._hotkey_handles = [("keyboard", h1), ("keyboard", h2)]
            ok = True
        except Exception:
            ok = False
        # 窗口内绑定作为兜底（游戏失焦时仍可用）
        try:
            self.root.bind_all("<" + start.upper() + ">", lambda e: self._hotkey_start())
            self.root.bind_all("<" + stop.upper() + ">", lambda e: self._hotkey_stop())
            self._hotkey_handles.append(("tk", start.upper()))
            self._hotkey_handles.append(("tk", stop.upper()))
        except Exception:
            pass
        if hasattr(self, "hotkey_hint"):
            self.hotkey_hint.configure(
                text="热键  " + start.upper() + " 开始 / " + stop.upper() + " 停止"
                + (" · 已注册全局" if ok else " · 窗口内有效")
            )
        self._set_status(
            ("全局热键已注册：" if ok else "热键（窗口内）：")
            + start.upper() + " 开始 / " + stop.upper() + " 停止"
        )

    def _unregister_hotkeys(self) -> None:
        handles = getattr(self, "_hotkey_handles", [])
        for kind, h in handles:
            try:
                if kind == "keyboard":
                    import keyboard as _kb
                    _kb.remove_hotkey(h)
                elif kind == "tk":
                    self.root.unbind_all("<" + str(h) + ">")
            except Exception:
                pass
        self._hotkey_handles = []

    def _apply_hotkeys(self) -> None:
        start = self.hotkey_start_var.get().strip().lower() or "f5"
        stop = self.hotkey_stop_var.get().strip().lower() or "f6"
        # 粗校验：不要占用演奏字母键
        banned = set("zxcvbnmwasd")
        if start in banned or stop in banned:
            messagebox.showwarning("热键冲突", "热键不要使用 z x c v b n m 或 WASD")
            return
        self.cfg.hotkey.start = start
        self.cfg.hotkey.stop = stop
        self._save_cfg()
        self._register_hotkeys()
        messagebox.showinfo("热键", "已应用：" + start.upper() + " 开始 / " + stop.upper() + " 停止")

    def _hotkey_start(self) -> None:
        # E 模式热键也走导出；播放中忽略开始
        if self.dispatcher is not None and self.dispatcher.is_running():
            return
        self._on_start()

    def _hotkey_stop(self) -> None:
        self._on_stop()

    def _on_convert(self) -> None:

        """简谱转换对话框：输入自由格式简谱，转为本工具记法，并可导出脚本可用文本。"""
        win = ctk.CTkToplevel(self.root)
        win.title("简谱转换")
        win.configure(fg_color=C_BG)
        win.geometry("680x560")
        win.transient(self.root)
        win.grab_set()

        ctk.CTkLabel(win, text="输入简谱（支持括号/点八度、无分隔连写、# b ♯ ♭）",
                     text_color=C_TEXT_DIM, font=ctk.CTkFont(family="Segoe UI", size=11),
                     anchor="w").pack(fill="x", padx=16, pady=(14, 4))
        src = ctk.CTkTextbox(win, height=140, font=ctk.CTkFont(family="Consolas", size=12),
                             fg_color="#0e1417", text_color=C_TEXT, corner_radius=8, wrap="word")
        src.pack(fill="both", expand=True, padx=16)
        # 预填当前曲谱内容，便于就地转换
        src.insert("1.0", self.score_text.get("1.0", "end"))

        btns = ctk.CTkFrame(win, fg_color="transparent")
        btns.pack(fill="x", padx=16, pady=10)

        out = ctk.CTkTextbox(win, height=140, font=ctk.CTkFont(family="Consolas", size=12),
                             fg_color="#0e1417", text_color=C_OK, corner_radius=8, wrap="word")
        out.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        out.configure(state="disabled")

        def do_normalize():
            text = src.get("1.0", "end")
            out.configure(state="normal")
            out.delete("1.0", "end")
            out.insert("1.0", convert.normalize_to_tokens_text(text))
            out.configure(state="disabled")

        def do_script_text():
            text = src.get("1.0", "end")
            stext, res = convert.export_script_text(text)
            out.configure(state="normal")
            out.delete("1.0", "end")
            out.insert("1.0", stext)
            out.configure(state="disabled")
            # 警告提示
            if res.warnings:
                extra = []
                for idx, msg in res.warnings:
                    extra.append(("[" + str(idx) + "] " if idx >= 0 else "") + msg)
                # 追加到现有警告（转换场景）并增高
                self.warn_text.configure(state="normal")
                cur = self.warn_text.get("1.0", "end-1c").strip()
                merged = ([cur] if cur else []) + extra
                self._fill_warn_text(merged)

        def do_apply():
            text = src.get("1.0", "end")
            self.score_text.delete("1.0", "end")
            self.score_text.insert("1.0", convert.normalize_to_tokens_text(text))
            self._set_status("已转换并应用到曲谱编辑区")
            win.destroy()

        def do_export():
            text = src.get("1.0", "end")
            stext, res = convert.export_script_text(text)
            path = filedialog.asksaveasfilename(
                defaultextension=".txt", filetypes=[("脚本文本", "*.txt"), ("所有文件", "*.*")],
                initialfile="score_script.txt", title="保存脚本可用文本",
            )
            if not path:
                return
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(stext)
            except OSError as e:
                messagebox.showerror("导出失败", str(e))
                return
            self._set_status("已导出脚本文本: " + path)

        ctk.CTkButton(btns, text="规范化为记法", height=36, corner_radius=8,
                      fg_color=C_CARD_HI, hover_color="#3a5044", text_color=C_TEXT,
                      command=do_normalize).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(btns, text="脚本可用文本", height=36, corner_radius=8,
                      fg_color=C_CARD_HI, hover_color="#3a5044", text_color=C_TEXT,
                      command=do_script_text).pack(side="left", expand=True, fill="x", padx=4)
        ctk.CTkButton(btns, text="应用到曲谱", height=36, corner_radius=8,
                      fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#0b0f11",
                      command=do_apply).pack(side="left", expand=True, fill="x", padx=4)
        ctk.CTkButton(btns, text="导出文本", height=36, corner_radius=8,
                      fg_color=C_CARD_HI, hover_color="#3a5044", text_color=C_TEXT,
                      command=do_export).pack(side="left", expand=True, fill="x", padx=(4, 0))

    def _on_export_macro_md(self) -> None:
        r = self._parse_current()
        if r is None or not r.events:
            self._set_status("无事件可导出")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown 教程", "*.md"), ("所有文件", "*.*")],
            initialfile="harmonica_macro.md",
            title="保存鼠标宏手写教程 (Markdown)",
        )
        if not path:
            return
        song = os.path.splitext(os.path.basename(path))[0]
        try:
            macro_md_exporter.export_to_file(r.events, self.cfg, path, song_name=song)
        except OSError as e:
            messagebox.showerror("导出失败", str(e))
            return
        self._set_status("已导出宏教程: " + path)
        messagebox.showinfo("导出完成",
            "鼠标宏 Markdown 教程已保存到:\n" + path + "\n\n"
            "用法:\n"
            "1. 用任意编辑器打开 .md\n"
            "2. 按键位表与逐音动作表，在鼠标驱动里手写宏\n"
            "3. 普通音：按下字母 z–m；半音：按住中键 + 字母\n"
            "4. 绑到侧键，安全区呼出口琴后再触发\n\n"
            "旧版 G HUB Lua 导出已弃用。宏仍有封号风险，后果自负。")

    # 兼容旧按钮名（若有外部引用）
    def _on_export_ghub(self) -> None:
        self._on_export_macro_md()

    def _on_load_file(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("文本曲谱", "*.txt"), ("所有文件", "*.*")],
            title="载入曲谱文件",
        )
        if path:
            self._load_score_file(path)

    def _load_score_file(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            messagebox.showerror("载入失败", str(e))
            return
        self.score_text.delete("1.0", "end")
        self.score_text.insert("1.0", content)
        self._set_status("已载入: " + path)

    def _on_save_file(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("文本曲谱", "*.txt"), ("所有文件", "*.*")],
            title="保存曲谱",
        )
        if not path:
            return
        content = self.score_text.get("1.0", "end")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            messagebox.showerror("保存失败", str(e))
            return
        self._set_status("已保存: " + path)

    def _load_default_score(self) -> None:
        sample = (
            "// 小星星（示例，已适配口琴基础音区）\n"
            "@bpm 100\n"
            "1 1 5 5 6 6 5 -\n"
            "4 4 3 3 2 2 1 -\n"
            "5 5 4 4 3 3 2 -\n"
            "5 5 4 4 3 3 2 -\n"
            "1 1 5 5 6 6 5 -\n"
            "4 4 3 3 2 2 1 -\n"
        )
        self.score_text.insert("1.0", sample)

    def _on_close(self) -> None:
        self._unregister_hotkeys()
        if self.hud is not None:
            self.hud.destroy()
            self.hud = None
        if self.dispatcher and self.dispatcher.is_running():
            self.dispatcher.stop()
            self.dispatcher.wait(1.0)
        self._save_cfg()
        self.root.destroy()


def run(initial_score: Optional[str] = None, initial_mode: Optional[str] = None) -> None:
    _init_theme()
    root = ctk.CTk()
    App(root, initial_score=initial_score, initial_mode=initial_mode)
    root.mainloop()

class HUDOverlay:
    """图形 HUD 覆盖层：无边框、置顶、半透明、点击穿透的浮动窗口，
    悬浮于游戏画面之上，用于 C 模式手动演奏时实时显示当前音符与进度。
    用原生 tk.Toplevel（customtkinter 不支持 -transparentcolor）。"""

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

        self.note_label = tk.Label(self.win, text="—", font=("Segoe UI", 36, "bold"),
                                   fg="#00e5ff", bg=self._BG)
        self.note_label.pack(padx=26, pady=(20, 2))

        self.beat_label = tk.Label(self.win, text="", font=("Segoe UI", 12),
                                   fg="#cfe8ff", bg=self._BG)
        self.beat_label.pack(pady=(0, 6))

        self.progress = ttk_Progressbar(self.win, length=210)
        self.progress.pack(pady=(0, 10))

        self.hint = tk.Label(self.win, text="拖动移动 · 双击换边角 · 右键关闭",
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


def ttk_Progressbar(master, length=200):
    """HUD 用原生 ttk 进度条（customtkinter 进度条不便嵌入透明 Toplevel）。"""
    import tkinter.ttk as _ttk
    return _ttk.Progressbar(master, length=length, mode="determinate")
