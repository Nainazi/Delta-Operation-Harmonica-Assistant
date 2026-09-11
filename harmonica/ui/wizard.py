"""首次启动三步向导。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

import customtkinter as ctk

from .theme import C_BG, C_CARD, C_CARD_HI, C_TEXT, C_TEXT_DIM, C_ACCENT, C_ACCENT_HOVER

if TYPE_CHECKING:
    from .app import App

_STEPS = [
    {
        "title": "① 键位：z–m = 1–7",
        "body": (
            "音级 1 2 3 4 5 6 7（do–ti）对应键盘：\n"
            "    z   x   c   v   b   n   m\n\n"
            "避开了 WASD 与数字键，方便边站边吹。\n"
            "曲谱里写 1–7，手上按对应字母即可。"
        ),
    },
    {
        "title": "② 半音与八度：鼠标键",
        "body": (
            "半音（# 升 / b 降）：按住鼠标中键 + 字母。\n"
            "高八度（^）：按住右键 + 字母。\n"
            "低八度（,）：按住左键 + 字母。\n"
            "最高 do（1^^）：按住右键 + 逗号键「,」。\n"
            "修饰键要按住整个音符，不要点按。"
        ),
    },
    {
        "title": "③ 热键 F5 / F6 · 推荐手动辅助",
        "body": (
            "默认热键：\n"
            "    F5  开始演奏 / 导出（视模式）\n"
            "    F6  停止（曲中立即生效）\n\n"
            "强烈推荐模式「手动辅助」：只显示提示，你自己按键，\n"
            "零注入、零封号风险。自动注入与鼠标宏仅供了解。"
        ),
    },
]


def show_wizard(app: "App", on_finish: Optional[Callable[[], None]] = None) -> None:
    """弹出模态三步向导。"""
    win = ctk.CTkToplevel(app.root)
    win.title("新手向导")
    win.configure(fg_color=C_BG)
    win.geometry("520x360")
    win.transient(app.root)
    win.grab_set()
    try:
        win.focus_force()
    except Exception:
        pass

    step_idx = {"i": 0}

    title_lbl = ctk.CTkLabel(
        win, text="", font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
        text_color=C_ACCENT, anchor="w")
    title_lbl.pack(fill="x", padx=24, pady=(24, 8))

    body_lbl = ctk.CTkLabel(
        win, text="", font=ctk.CTkFont(family="Segoe UI", size=13),
        text_color=C_TEXT, justify="left", anchor="nw")
    body_lbl.pack(fill="both", expand=True, padx=24, pady=(0, 8))

    progress = ctk.CTkLabel(
        win, text="", text_color=C_TEXT_DIM,
        font=ctk.CTkFont(family="Segoe UI", size=11))
    progress.pack(anchor="w", padx=24)

    btns = ctk.CTkFrame(win, fg_color="transparent")
    btns.pack(fill="x", padx=24, pady=20)

    def render() -> None:
        i = step_idx["i"]
        s = _STEPS[i]
        title_lbl.configure(text=s["title"])
        body_lbl.configure(text=s["body"])
        progress.configure(text=f"步骤 {i + 1} / {len(_STEPS)}")
        prev_btn.configure(state="normal" if i > 0 else "disabled")
        next_btn.configure(text="完成" if i >= len(_STEPS) - 1 else "下一步")

    def go_prev() -> None:
        if step_idx["i"] > 0:
            step_idx["i"] -= 1
            render()

    def go_next() -> None:
        if step_idx["i"] >= len(_STEPS) - 1:
            if on_finish:
                on_finish()
            try:
                win.grab_release()
            except Exception:
                pass
            win.destroy()
            return
        step_idx["i"] += 1
        render()

    prev_btn = ctk.CTkButton(
        btns, text="上一步", width=100, height=36, corner_radius=8,
        fg_color=C_CARD_HI, hover_color="#3a5044", text_color=C_TEXT,
        command=go_prev)
    prev_btn.pack(side="left")
    next_btn = ctk.CTkButton(
        btns, text="下一步", width=120, height=36, corner_radius=8,
        fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#0b0f11",
        command=go_next)
    next_btn.pack(side="right")

    render()
