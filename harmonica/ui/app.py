"""主应用壳：侧边栏导航、页面切换与业务逻辑。"""
from __future__ import annotations

import os
import queue
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional, List

import customtkinter as ctk

from .. import config as cfgmod
from .. import score_parser as parser
from .. import score_convert as convert
from .. import dispatcher as disp
from .. import input_backend as backend_mod
from .. import macro_md_exporter
from ..config import (
    DEFAULT_KEY_MAP, degree_to_key, MD_TEMPLATE_LABELS, MD_TEMPLATES,
    extract_song_title, sanitize_filename,
)

from .theme import (
    C_BG, C_SIDEBAR, C_CARD, C_CARD_HI, C_TEXT, C_TEXT_DIM, C_ACCENT, C_ACCENT_HOVER,
    C_OK, C_WARN, C_DANGER, init_theme, make_card, ToolTip,
)
from .hud import HUDOverlay
from . import play_page
from . import settings_page
from . import guide_page
from . import library_page
from . import wizard as wizard_mod


class App:
    def __init__(self, root: ctk.CTk, initial_score: Optional[str] = None,
                 initial_mode: Optional[str] = None) -> None:
        self.root = root
        self.cfg = cfgmod.load()
        self.dispatcher: Optional[disp.Dispatcher] = None
        self.current_events: List[parser.NoteEvent] = []
        self.hud: Optional[HUDOverlay] = None
        self._nav_buttons: dict = {}
        self._progress_queue: "queue.Queue" = queue.Queue()
        self._settings_preview_hooks: list = []
        self._settings_preview_active = False
        self._key_chips = {}

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
        self.root.after(50, self._poll_progress)
        self._hotkey_handles = []
        self.root.after(200, self._register_hotkeys)
        # 首次向导
        if not self.cfg.wizard_seen:
            self.root.after(400, lambda: self._show_wizard(force=False))

    # ---- shell ----
    def _build_sidebar(self) -> None:
        bar = ctk.CTkFrame(self.root, width=190, corner_radius=0, fg_color=C_SIDEBAR)
        bar.pack(side="left", fill="y")
        bar.pack_propagate(False)

        title = ctk.CTkLabel(
            bar, text="🎵  佐拉口琴谱伴",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=C_TEXT, anchor="w")
        title.pack(fill="x", padx=18, pady=(22, 4))
        sub = ctk.CTkLabel(
            bar, text="三角洲行动 · 彩蛋口琴",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C_TEXT_DIM, anchor="w")
        sub.pack(fill="x", padx=18, pady=(0, 14))
        ctk.CTkFrame(bar, height=2, fg_color=C_ACCENT, corner_radius=0).pack(
            fill="x", padx=18, pady=(0, 14))

        for key, icon, label in [
            ("play", "▶", "演奏"),
            ("library", "📚", "曲库"),
            ("guide", "📖", "使用引导"),
            ("settings", "⚙", "设置"),
        ]:
            btn = ctk.CTkButton(
                bar, text="  " + icon + "   " + label, anchor="w",
                fg_color="transparent", hover_color=C_CARD_HI,
                text_color=C_TEXT, corner_radius=8, height=42,
                font=ctk.CTkFont(family="Segoe UI", size=14),
                command=lambda k=key: self._show_page(k))
            btn.pack(fill="x", padx=10, pady=4)
            self._nav_buttons[key] = btn

        badge = ctk.CTkLabel(
            bar, text="C 零风险\nE 宏教程·中\nB 高风险",
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
                btn.configure(
                    fg_color=C_ACCENT, text_color="#0b0f11",
                    font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"))
            else:
                btn.configure(
                    fg_color="transparent", text_color=C_TEXT,
                    font=ctk.CTkFont(family="Segoe UI", size=14))
        if key == "settings":
            self._settings_key_preview_on()
        else:
            self._settings_key_preview_off()
        if key == "library":
            self._refresh_library()

    def _build_content(self) -> None:
        self._pages = {}
        self._pages["play"] = play_page.build_play_page(self)
        self._pages["library"] = library_page.build_library_page(self)
        self._pages["guide"] = guide_page.build_guide_page(self)
        self._pages["settings"] = settings_page.build_settings_page(self)

    def _card(self, parent, text=None) -> ctk.CTkFrame:
        return make_card(parent, text)

    # ---- wizard ----
    def _show_wizard(self, force: bool = False) -> None:
        if not force and self.cfg.wizard_seen:
            return

        def finish() -> None:
            self.cfg.wizard_seen = True
            self._save_cfg()
            self._set_status("新手向导已完成 · 建议使用「手动辅助」")

        wizard_mod.show_wizard(self, on_finish=finish)

    # ---- library ----
    def _library_set_section(self, value: str) -> None:
        self._library_section = value
        library_page.render_library_list(self)

    def _refresh_library(self) -> None:
        library_page.render_library_list(self)

    def _library_open(self, entry_id: str, path: str) -> None:
        self._load_score_file(path)
        # 写入最近
        recent = [x for x in self.cfg.recent if x != entry_id]
        recent.insert(0, entry_id)
        self.cfg.recent = recent[:20]
        self._save_cfg()
        self._show_page("play")
        self._set_status("已从曲库打开: " + path)

    def _library_toggle_favorite(self, entry_id: str) -> None:
        fav = list(self.cfg.favorites)
        if entry_id in fav:
            fav = [x for x in fav if x != entry_id]
        else:
            fav.insert(0, entry_id)
        self.cfg.favorites = fav
        self._save_cfg()
        self._refresh_library()

    def _library_delete_user(self, entry_id: str, path: str) -> None:
        if not messagebox.askyesno("删除曲谱", "确定从「我的」删除该曲谱文件？\n" + path):
            return
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError as e:
            messagebox.showerror("删除失败", str(e))
            return
        self.cfg.favorites = [x for x in self.cfg.favorites if x != entry_id]
        self.cfg.recent = [x for x in self.cfg.recent if x != entry_id]
        self._save_cfg()
        self._refresh_library()
        self._set_status("已删除: " + path)

    # ---- settings key preview ----
    def _settings_key_preview_on(self) -> None:
        if self._settings_preview_active:
            return
        self._settings_preview_active = True
        self._settings_preview_hooks = []
        try:
            import keyboard as _kb

            def make_handlers(key: str):
                def on_press(_e=None):
                    self.root.after(0, lambda: self._highlight_key_chip(key, True))

                def on_release(_e=None):
                    self.root.after(0, lambda: self._highlight_key_chip(key, False))

                return on_press, on_release

            for key in list(getattr(self, "_key_chips", {}).keys()):
                on_p, on_r = make_handlers(key)
                try:
                    h1 = _kb.on_press_key(key, on_p, suppress=False)
                    h2 = _kb.on_release_key(key, on_r, suppress=False)
                    self._settings_preview_hooks.append(h1)
                    self._settings_preview_hooks.append(h2)
                except Exception:
                    pass
        except Exception:
            pass

    def _settings_key_preview_off(self) -> None:
        self._settings_preview_active = False
        hooks = list(self._settings_preview_hooks)
        self._settings_preview_hooks = []
        try:
            import keyboard as _kb
            for h in hooks:
                try:
                    _kb.unhook(h)
                except Exception:
                    pass
        except Exception:
            pass
        for chip in getattr(self, "_key_chips", {}).values():
            try:
                chip.configure(fg_color=C_CARD_HI, text_color=C_TEXT)
            except Exception:
                pass

    def _highlight_key_chip(self, key: str, on: bool) -> None:
        chip = getattr(self, "_key_chips", {}).get(key.lower())
        if chip is None:
            return
        try:
            if on:
                chip.configure(fg_color=C_ACCENT, text_color="#0b0f11")
            else:
                chip.configure(fg_color=C_CARD_HI, text_color=C_TEXT)
        except Exception:
            pass

    # ---- settings handlers ----
    def _sync_mode_from_ui(self) -> str:
        """以演奏页单选项为源，写回 cfg.mode。返回 C/B/E。"""
        if hasattr(self, "mode_var"):
            m = (self.mode_var.get() or "").strip().upper()
            if m in ("C", "B", "E"):
                self.cfg.mode = m
        return self.cfg.mode

    def _on_mode_change(self, selected: Optional[str] = None) -> None:
        if selected in ("C", "B", "E"):
            self.cfg.mode = selected
            if hasattr(self, "mode_var") and self.mode_var.get() != selected:
                self.mode_var.set(selected)
        else:
            self._sync_mode_from_ui()
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

    def _on_backend_change(self, value: Optional[str] = None) -> None:
        raw = value if value is not None else (
            self.backend_var.get() if hasattr(self, "backend_var") else self.cfg.input.backend)
        name = (raw or "").strip().lower()
        if name in ("keyboard", "ctypes"):
            name = "keyboard_ctypes"
        if name not in ("pydirectinput", "keyboard_ctypes", "null"):
            return
        self.cfg.input.backend = name
        self._save_cfg()

    def _save_cfg(self) -> None:
        if hasattr(self, "score_text"):
            self.cfg.last_score = self.score_text.get("1.0", "end")
        cfgmod.save(self.cfg)

    def _fill_warn_text(self, lines) -> None:
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
        state = "disabled" if playing else "normal"
        try:
            self.primary_btn.configure(state=state)
            self.test_btn.configure(state=state)
            for rb in getattr(self, "_mode_radios", []):
                rb.configure(state=state)
        except Exception:
            pass

    def _on_dispatch_error(self, exc: BaseException) -> None:
        """dispatcher 线程回调：转回主线程提示，避免 B 模式静默中断。"""
        msg = str(exc) or exc.__class__.__name__

        def _ui() -> None:
            self._set_playing(False)
            self._set_status("自动注入失败：" + msg)
            self._fill_warn_text(["自动注入失败：" + msg])
            messagebox.showerror(
                "自动注入失败",
                msg + "\n\n可到「设置」切换输入后端，或以管理员身份运行。\n"
                "并确认游戏窗口保持聚焦。")

        try:
            self.root.after(0, _ui)
        except Exception:
            pass

    def _ensure_inject_backend(self) -> Optional[backend_mod.InputBackend]:
        """B 模式用：拿到真实后端。缺库时弹出安装对话框，取消则返回 None。"""
        be = backend_mod.create_backend(self.cfg.input)
        if be is not None and be.name != "null":
            return be
        retried = self._prompt_install_inject_backend()
        if not retried:
            self._set_status("已取消自动注入（未安装输入后端）")
            return None
        be = backend_mod.create_backend(self.cfg.input)
        if be is not None and be.name != "null":
            return be
        detail = backend_mod.LAST_BACKEND_ERROR or "输入后端仍不可用"
        self._set_status("自动注入未启动：输入后端仍不可用")
        self._fill_warn_text([detail])
        return None

    def _prompt_install_inject_backend(self) -> bool:
        """依赖缺失提示：一键安装后重试 create_backend。取消/关闭返回 False。"""
        detail = (backend_mod.LAST_BACKEND_ERROR or "").strip() or (
            "未能加载 pydirectinput / keyboard。"
        )
        result = {"ok": False}

        win = ctk.CTkToplevel(self.root)
        win.title("需要安装注入依赖")
        win.configure(fg_color=C_BG)
        win.geometry("560x420")
        win.transient(self.root)
        win.grab_set()
        try:
            win.focus_force()
        except Exception:
            pass

        ctk.CTkLabel(
            win, text="自动注入需要输入库",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=C_ACCENT, anchor="w").pack(fill="x", padx=20, pady=(18, 6))
        ctk.CTkLabel(
            win,
            text="当前 Python 缺少 pydirectinput 或 keyboard，B 模式不会发送 z–m / 中键。\n"
                 "可点「一键安装」执行：python -m pip install pydirectinput keyboard",
            text_color=C_TEXT, font=ctk.CTkFont(family="Segoe UI", size=12),
            wraplength=520, justify="left", anchor="w").pack(fill="x", padx=20)
        box = ctk.CTkTextbox(
            win, height=180, font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0e1417", text_color=C_WARN, corner_radius=8, wrap="word")
        box.pack(fill="both", expand=True, padx=20, pady=12)
        box.insert("1.0", detail)
        box.configure(state="disabled")

        status = ctk.CTkLabel(
            win, text="", text_color=C_TEXT_DIM,
            font=ctk.CTkFont(family="Segoe UI", size=11), anchor="w")
        status.pack(fill="x", padx=20)

        btns = ctk.CTkFrame(win, fg_color="transparent")
        btns.pack(fill="x", padx=20, pady=(8, 16))

        def _set_log(text: str) -> None:
            box.configure(state="normal")
            box.delete("1.0", "end")
            box.insert("1.0", text)
            box.configure(state="disabled")

        def do_cancel() -> None:
            result["ok"] = False
            try:
                win.grab_release()
            except Exception:
                pass
            win.destroy()

        def do_install() -> None:
            install_btn.configure(state="disabled")
            cancel_btn.configure(state="disabled")
            status.configure(text="正在安装 pydirectinput / keyboard…")
            win.update_idletasks()
            ok, log = backend_mod.install_inject_dependencies()
            if ok:
                be = backend_mod.create_backend(self.cfg.input)
                if be is not None and be.name != "null":
                    result["ok"] = True
                    status.configure(text="安装成功，后端：" + be.name, text_color=C_OK)
                    try:
                        win.grab_release()
                    except Exception:
                        pass
                    win.destroy()
                    return
                _set_log((log + "\n\n" if log else "") + (
                    backend_mod.LAST_BACKEND_ERROR or "安装后仍无法创建输入后端。"))
                status.configure(text="已安装，但后端仍不可用。可取消后检查设置。",
                                 text_color=C_DANGER)
            else:
                _set_log(log or "安装失败")
                status.configure(text="安装失败。可手动 pip 后重试，或取消。",
                                 text_color=C_DANGER)
            install_btn.configure(state="normal")
            cancel_btn.configure(state="normal")

        cancel_btn = ctk.CTkButton(
            btns, text="取消", width=100, height=34, corner_radius=8,
            fg_color=C_CARD_HI, hover_color="#3a5044", text_color=C_TEXT,
            command=do_cancel)
        cancel_btn.pack(side="left")
        install_btn = ctk.CTkButton(
            btns, text="一键安装", width=140, height=34, corner_radius=8,
            fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#0b0f11",
            command=do_install)
        install_btn.pack(side="right")

        win.protocol("WM_DELETE_WINDOW", do_cancel)
        win.wait_window()
        return bool(result["ok"])

    def _on_start(self) -> None:
        if self.dispatcher is not None and self.dispatcher.is_running():
            self._set_status("正在播放中，请先停止")
            return
        mode = self._sync_mode_from_ui()
        if mode == "E":
            self._on_export_macro_md()
            return
        if mode == "B" and not self.cfg.risk_acknowledged:
            if not messagebox.askyesno(
                    "风险确认",
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
            be = self._ensure_inject_backend()
            if be is None or be.name == "null":
                return
            note = getattr(be, "warning", None)
            self.dispatcher = disp.Dispatcher(
                self.cfg, backend=be, on_progress=self._on_progress,
                on_error=self._on_dispatch_error)
            self.dispatcher.play_b(r.events)
            self._set_playing(True)
            status = "B 模式播放中（%s）… 切到游戏窗口保持聚焦" % be.name
            if note:
                status = note + " · " + status
                self._fill_warn_text([note])
            self._set_status(status)
        else:
            self.dispatcher = disp.Dispatcher(
                self.cfg, backend=backend_mod.NullBackend(),
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
        self.dispatcher = disp.Dispatcher(
            self.cfg, backend=backend_mod.NullBackend(),
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
        self._progress_queue.put((idx, total, ev))

    def _poll_progress(self) -> None:
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
                self.hud.update_note(
                    hint, idx, total, beats=ev.beats,
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
            if hasattr(self, "export_md_row"):
                self.export_md_row.pack_forget()
        else:
            self.primary_btn.configure(text="▶  开始演奏", command=self._on_start)
            if hasattr(self, "export_md_row") and hasattr(self, "convert_btn"):
                if not self.export_md_row.winfo_ismapped():
                    self.export_md_row.pack(fill="x", pady=2, before=self.convert_btn.master)

    def _format_play_hint(self, ev: "parser.NoteEvent") -> str:
        key = degree_to_key(self.cfg, ev.degree)
        acc = {1: "♯", -1: "♭", 0: ""}[ev.accidental]
        if ev.accidental != 0:
            return "中键+" + key + " " + acc
        return key

    def _ai_prompt_text(self) -> str:
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

    def _paste_ai_from_clipboard(self) -> None:
        """从剪贴板读取文本填入曲谱编辑器（编辑器非空时确认）。"""
        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            messagebox.showwarning("剪贴板", "剪贴板为空或无法读取。请先复制 AI 输出的简谱。")
            return
        text = (text or "").strip()
        if not text:
            messagebox.showwarning("剪贴板", "剪贴板内容为空。")
            return
        # 去掉常见 markdown 代码围栏
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        cur = self.score_text.get("1.0", "end-1c").strip()
        if cur:
            if not messagebox.askyesno("填入编辑器", "当前编辑器非空，是否用剪贴板内容覆盖？"):
                return
        self.score_text.delete("1.0", "end")
        self.score_text.insert("1.0", text + "\n")
        self._set_status("已从剪贴板填入曲谱编辑器")

    def _register_hotkeys(self) -> None:
        self._unregister_hotkeys()
        start = (self.cfg.hotkey.start or "f5").strip().lower()
        stop = (self.cfg.hotkey.stop or "f6").strip().lower()
        self.cfg.hotkey.start = start
        self.cfg.hotkey.stop = stop
        ok = False
        try:
            import keyboard as _kb
            h1 = _kb.add_hotkey(start, lambda: self.root.after(0, self._hotkey_start))
            h2 = _kb.add_hotkey(stop, lambda: self.root.after(0, self._hotkey_stop))
            self._hotkey_handles = [("keyboard", h1), ("keyboard", h2)]
            ok = True
        except Exception:
            ok = False
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
        if self.dispatcher is not None and self.dispatcher.is_running():
            return
        self._on_start()

    def _hotkey_stop(self) -> None:
        self._on_stop()

    def _on_convert(self) -> None:
        win = ctk.CTkToplevel(self.root)
        win.title("简谱转换")
        win.configure(fg_color=C_BG)
        win.geometry("680x560")
        win.transient(self.root)
        win.grab_set()

        ctk.CTkLabel(
            win, text="输入简谱（支持括号/点八度、无分隔连写、# b ♯ ♭）",
            text_color=C_TEXT_DIM, font=ctk.CTkFont(family="Segoe UI", size=11),
            anchor="w").pack(fill="x", padx=16, pady=(14, 4))
        src = ctk.CTkTextbox(
            win, height=140, font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#0e1417", text_color=C_TEXT, corner_radius=8, wrap="word")
        src.pack(fill="both", expand=True, padx=16)
        src.insert("1.0", self.score_text.get("1.0", "end"))

        btns = ctk.CTkFrame(win, fg_color="transparent")
        btns.pack(fill="x", padx=16, pady=10)

        out = ctk.CTkTextbox(
            win, height=140, font=ctk.CTkFont(family="Consolas", size=12),
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
            if res.warnings:
                extra = []
                for idx, msg in res.warnings:
                    extra.append(("[" + str(idx) + "] " if idx >= 0 else "") + msg)
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
                defaultextension=".txt",
                filetypes=[("脚本文本", "*.txt"), ("所有文件", "*.*")],
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

        ctk.CTkButton(
            btns, text="规范化为记法", height=36, corner_radius=8,
            fg_color=C_CARD_HI, hover_color="#3a5044", text_color=C_TEXT,
            command=do_normalize).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(
            btns, text="脚本可用文本", height=36, corner_radius=8,
            fg_color=C_CARD_HI, hover_color="#3a5044", text_color=C_TEXT,
            command=do_script_text).pack(side="left", expand=True, fill="x", padx=4)
        ctk.CTkButton(
            btns, text="应用到曲谱", height=36, corner_radius=8,
            fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#0b0f11",
            command=do_apply).pack(side="left", expand=True, fill="x", padx=4)
        ctk.CTkButton(
            btns, text="导出文本", height=36, corner_radius=8,
            fg_color=C_CARD_HI, hover_color="#3a5044", text_color=C_TEXT,
            command=do_export).pack(side="left", expand=True, fill="x", padx=(4, 0))

    def _default_md_filename(self, song_title: str, bpm: float) -> str:
        safe = sanitize_filename(song_title)
        bpm_s = str(int(bpm)) if abs(bpm - int(bpm)) < 1e-6 else ("%.1f" % bpm)
        return f"{safe}_bpm{bpm_s}_宏教程.md"

    def _on_export_macro_md(self) -> None:
        r = self._parse_current()
        if r is None or not r.events:
            self._set_status("无事件可导出")
            return

        score_body = self.score_text.get("1.0", "end")
        song_title = extract_song_title(score_body, fallback="未命名")
        bpm = self.cfg.timing.bpm
        default_name = self._default_md_filename(song_title, bpm)

        # 模板选择对话框
        win = ctk.CTkToplevel(self.root)
        win.title("导出宏教程 MD")
        win.configure(fg_color=C_BG)
        win.geometry("420x260")
        win.transient(self.root)
        win.grab_set()

        ctk.CTkLabel(
            win, text="选择驱动模板",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=C_ACCENT).pack(anchor="w", padx=20, pady=(18, 8))
        ctk.CTkLabel(
            win, text="将影响教程第 3 节步骤与第 5 节伪代码风格。默认「通用伪代码」。",
            text_color=C_TEXT_DIM, font=ctk.CTkFont(family="Segoe UI", size=11),
            wraplength=380, justify="left").pack(anchor="w", padx=20)

        labels = [MD_TEMPLATE_LABELS[t] for t in MD_TEMPLATES]
        label_to_key = {MD_TEMPLATE_LABELS[t]: t for t in MD_TEMPLATES}
        cur_label = MD_TEMPLATE_LABELS.get(self.cfg.md_template, "通用伪代码")
        tpl_var = tk.StringVar(value=cur_label)
        seg = ctk.CTkSegmentedButton(
            win, values=labels, variable=tpl_var,
            fg_color=C_CARD, selected_color=C_ACCENT, selected_hover_color=C_ACCENT_HOVER,
            unselected_color=C_CARD_HI, unselected_hover_color="#2a343a",
            text_color=C_TEXT)
        seg.pack(fill="x", padx=20, pady=16)

        ctk.CTkLabel(
            win, text="默认文件名：" + default_name,
            text_color=C_TEXT_DIM, font=ctk.CTkFont(family="Segoe UI", size=10),
            anchor="w").pack(fill="x", padx=20)

        result = {"ok": False}

        def do_export():
            result["ok"] = True
            key = label_to_key.get(tpl_var.get(), "generic")
            self.cfg.md_template = key
            self._save_cfg()
            win.destroy()

        def do_cancel():
            result["ok"] = False
            win.destroy()

        row = ctk.CTkFrame(win, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=16)
        ctk.CTkButton(
            row, text="取消", width=100, height=34, corner_radius=8,
            fg_color=C_CARD_HI, hover_color="#3a5044", text_color=C_TEXT,
            command=do_cancel).pack(side="left")
        ctk.CTkButton(
            row, text="选择保存位置…", width=140, height=34, corner_radius=8,
            fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#0b0f11",
            command=do_export).pack(side="right")

        win.wait_window()
        if not result["ok"]:
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown 教程", "*.md"), ("所有文件", "*.*")],
            initialfile=default_name,
            title="保存鼠标宏手写教程 (Markdown)",
        )
        if not path:
            return
        try:
            macro_md_exporter.export_to_file(
                r.events, self.cfg, path,
                song_name=song_title, template=self.cfg.md_template)
        except OSError as e:
            messagebox.showerror("导出失败", str(e))
            return
        self._set_status("已导出宏教程: " + path)
        tpl_name = MD_TEMPLATE_LABELS.get(self.cfg.md_template, "通用伪代码")
        messagebox.showinfo(
            "导出完成",
            "鼠标宏 Markdown 教程已保存到:\n" + path + "\n\n"
            "驱动模板：" + tpl_name + "\n\n"
            "用法:\n"
            "1. 用任意编辑器打开 .md\n"
            "2. 按键位表与逐音动作表，在鼠标驱动里手写宏\n"
            "3. 普通音：按下字母 z–m；半音：按住中键 + 字母\n"
            "4. 绑到侧键，安全区呼出口琴后再触发\n\n"
            "旧版 G HUB Lua 导出已弃用。宏仍有封号风险，后果自负。")

    def _on_export_ghub(self) -> None:
        self._on_export_macro_md()

    def _on_load_file(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("文本曲谱", "*.txt"), ("所有文件", "*.*")],
            title="载入曲谱文件",
        )
        if path:
            self._load_score_file(path)
            # 也记入最近（用户路径）
            abs_p = os.path.abspath(path)
            recent = [x for x in self.cfg.recent if x != abs_p]
            recent.insert(0, abs_p)
            self.cfg.recent = recent[:20]
            self._save_cfg()

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
        # 默认保存到用户曲谱目录
        initial_dir = cfgmod.user_scores_dir()
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本曲谱", "*.txt"), ("所有文件", "*.*")],
            title="保存曲谱",
            initialdir=initial_dir,
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
        abs_p = os.path.abspath(path)
        recent = [x for x in self.cfg.recent if x != abs_p]
        recent.insert(0, abs_p)
        self.cfg.recent = recent[:20]
        self._save_cfg()
        self._set_status("已保存: " + path)

    def _load_default_score(self) -> None:
        # 优先内置小星星
        twinkle = os.path.join(cfgmod.builtin_scores_dir(), "twinkle.txt")
        if os.path.isfile(twinkle):
            try:
                with open(twinkle, "r", encoding="utf-8") as f:
                    self.score_text.insert("1.0", f.read())
                return
            except OSError:
                pass
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
        self._settings_key_preview_off()
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
    init_theme()
    root = ctk.CTk()
    App(root, initial_score=initial_score, initial_mode=initial_mode)
    root.mainloop()
