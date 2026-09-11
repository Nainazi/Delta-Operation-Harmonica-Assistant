"""[已弃用] 原 G HUB Lua 导出器。

v1.0.2 起改由 macro_md_exporter 导出鼠标宏 Markdown 教程。
保留本模块以免旧引用报错；所有 API 转发到 MD 导出。
"""
from __future__ import annotations

from typing import List, Optional

from .config import AppConfig
from .score_parser import NoteEvent
from . import macro_md_exporter


def render_lua(events: List[NoteEvent], cfg: AppConfig, song_name: str = "未命名",
               template: Optional[str] = None) -> str:
    """已弃用：返回 Markdown 教程（不再生成 Lua）。"""
    return macro_md_exporter.render_markdown(
        events, cfg, song_name=song_name, template=template)


def export_to_file(events: List[NoteEvent], cfg: AppConfig, path: str,
                   song_name: str = "未命名",
                   template: Optional[str] = None) -> None:
    """已弃用：写入 Markdown 教程。若扩展名仍为 .lua 也写入 MD 内容。"""
    if path.lower().endswith(".lua"):
        path = path[:-4] + ".md"
    macro_md_exporter.export_to_file(
        events, cfg, path, song_name=song_name, template=template)


# 新名别名
render_markdown = macro_md_exporter.render_markdown
