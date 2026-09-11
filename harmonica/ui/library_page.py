"""曲库页：内置 / 我的 / 收藏 / 最近。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Callable

import customtkinter as ctk

from .. import config as cfgmod
from .theme import (
    C_BG, C_CARD, C_CARD_HI, C_TEXT, C_TEXT_DIM, C_ACCENT, C_ACCENT_HOVER, C_DANGER,
    make_card,
)

if TYPE_CHECKING:
    from .app import App


@dataclass
class ScoreEntry:
    """曲库条目。"""
    id: str                 # builtin:<name> 或绝对路径
    title: str
    path: str
    builtin: bool = False


def _title_from_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read(400)
        return cfgmod.extract_song_title(text, fallback=os.path.splitext(os.path.basename(path))[0])
    except OSError:
        return os.path.splitext(os.path.basename(path))[0]


def list_builtin_scores() -> List[ScoreEntry]:
    folder = cfgmod.builtin_scores_dir()
    out: List[ScoreEntry] = []
    if not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(".txt"):
            continue
        path = os.path.join(folder, name)
        sid = "builtin:" + name
        out.append(ScoreEntry(id=sid, title=_title_from_file(path), path=path, builtin=True))
    return out


def list_user_scores() -> List[ScoreEntry]:
    folder = cfgmod.user_scores_dir()
    out: List[ScoreEntry] = []
    if not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(".txt"):
            continue
        path = os.path.abspath(os.path.join(folder, name))
        out.append(ScoreEntry(id=path, title=_title_from_file(path), path=path, builtin=False))
    return out


def resolve_entry(entry_id: str) -> Optional[ScoreEntry]:
    if entry_id.startswith("builtin:"):
        name = entry_id[len("builtin:"):]
        path = os.path.join(cfgmod.builtin_scores_dir(), name)
        if os.path.isfile(path):
            return ScoreEntry(id=entry_id, title=_title_from_file(path), path=path, builtin=True)
        return None
    if os.path.isfile(entry_id):
        return ScoreEntry(id=entry_id, title=_title_from_file(entry_id), path=entry_id, builtin=False)
    return None


def build_library_page(app: "App") -> ctk.CTkFrame:
    page = ctk.CTkFrame(app.root, fg_color=C_BG, corner_radius=0)

    header = ctk.CTkFrame(page, fg_color="transparent")
    header.pack(fill="x", padx=16, pady=(14, 6))
    ctk.CTkLabel(
        header, text="曲库",
        font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
        text_color=C_ACCENT).pack(side="left")
    ctk.CTkButton(
        header, text="刷新", width=72, height=28, corner_radius=8,
        fg_color=C_CARD_HI, hover_color="#3a5044", text_color=C_TEXT,
        command=lambda: app._refresh_library()).pack(side="right")
    ctk.CTkLabel(
        page,
        text="内置曲谱只读；「我的」对应配置目录 scores 文件夹。打开后载入演奏页编辑器。",
        text_color=C_TEXT_DIM, font=ctk.CTkFont(family="Segoe UI", size=11),
        anchor="w").pack(fill="x", padx=16, pady=(0, 8))

    # 分段：内置 / 我的 / 收藏 / 最近
    seg = ctk.CTkSegmentedButton(
        page, values=["内置", "我的", "收藏", "最近"],
        command=lambda v: app._library_set_section(v),
        fg_color=C_CARD, selected_color=C_ACCENT, selected_hover_color=C_ACCENT_HOVER,
        unselected_color=C_CARD_HI, unselected_hover_color="#2a343a",
        text_color=C_TEXT)
    seg.pack(fill="x", padx=16, pady=(0, 8))
    seg.set("内置")
    app._library_seg = seg
    app._library_section = "内置"

    list_card = make_card(page, None)
    list_card.pack(fill="both", expand=True, padx=16, pady=(0, 16))
    app._library_list = ctk.CTkScrollableFrame(list_card, fg_color="transparent")
    app._library_list.pack(fill="both", expand=True, padx=8, pady=8)

    app._refresh_library()
    return page


def render_library_list(app: "App") -> None:
    """根据当前分段刷新列表。"""
    frame = getattr(app, "_library_list", None)
    if frame is None:
        return
    for child in frame.winfo_children():
        child.destroy()

    section = getattr(app, "_library_section", "内置")
    entries: List[ScoreEntry] = []
    if section == "内置":
        entries = list_builtin_scores()
    elif section == "我的":
        entries = list_user_scores()
    elif section == "收藏":
        for sid in list(app.cfg.favorites):
            e = resolve_entry(sid)
            if e:
                entries.append(e)
    elif section == "最近":
        for sid in list(app.cfg.recent):
            e = resolve_entry(sid)
            if e:
                entries.append(e)

    if not entries:
        ctk.CTkLabel(
            frame, text="（空）", text_color=C_TEXT_DIM,
            font=ctk.CTkFont(family="Segoe UI", size=13)).pack(pady=24)
        return

    fav_set = set(app.cfg.favorites)
    for e in entries:
        row = ctk.CTkFrame(frame, fg_color=C_CARD_HI, corner_radius=10)
        row.pack(fill="x", pady=4, padx=4)
        title = e.title + ("  · 内置" if e.builtin else "")
        ctk.CTkLabel(
            row, text=title, anchor="w", text_color=C_TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        ).pack(side="left", fill="x", expand=True, padx=12, pady=10)

        is_fav = e.id in fav_set
        ctk.CTkButton(
            row, text="★ 取消" if is_fav else "☆ 收藏", width=80, height=28,
            corner_radius=8, fg_color=C_CARD, hover_color="#3a5044", text_color=C_TEXT,
            command=lambda eid=e.id: app._library_toggle_favorite(eid)
        ).pack(side="right", padx=(4, 8), pady=8)

        if not e.builtin and section == "我的":
            ctk.CTkButton(
                row, text="删除", width=56, height=28, corner_radius=8,
                fg_color=C_DANGER, hover_color="#e04848", text_color="#ffffff",
                command=lambda eid=e.id, p=e.path: app._library_delete_user(eid, p)
            ).pack(side="right", padx=4, pady=8)

        ctk.CTkButton(
            row, text="打开到编辑器", width=110, height=28, corner_radius=8,
            fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#0b0f11",
            command=lambda eid=e.id, p=e.path: app._library_open(eid, p)
        ).pack(side="right", padx=4, pady=8)
