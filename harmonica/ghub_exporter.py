"""G HUB Lua 脚本导出器（E 模式）。

把音符序列渲染为可粘贴进罗技 G HUB 脚本编辑器的 Lua 文件。
用户在 G HUB 中绑定该脚本到 G 键或鼠标侧键，对局中按下即可回放。

G HUB Lua API（参考 jehillert/logitech-ghub-lua-cheatsheet）：
  PressAndReleaseKey(key) / PressKey / ReleaseKey
  PressAndReleaseMouseButton(n)   1=左 2=中 3=右
  Sleep(ms)
  GetRunningTime()
  math.random / math.randomseed
  OutputLogMessage(...)
  OnEvent(event, arg, family)

注意：E 模式仍违反游戏 ToS（G HUB 是 ACE 已知监控对象），风险高。
本导出器仅生成文件，不发送任何输入。
"""
from __future__ import annotations

from typing import List

from .config import AppConfig
from .humanizer import lua_duration_expr, lua_gap_expr, lua_hold_expr
from .score_parser import NoteEvent


def render_lua(events: List[NoteEvent], cfg: AppConfig, song_name: str = "未命名") -> str:
    """渲染完整 Lua 脚本字符串。"""
    beat_seconds = cfg.timing.beat_seconds or (60.0 / max(1.0, cfg.timing.bpm))
    lines: List[str] = []

    lines.append("-- =====================================================")
    lines.append(f"-- 曲目: {song_name}")
    lines.append(f"-- BPM: {cfg.timing.bpm:.1f}  (一拍 = {beat_seconds:.3f}s)")
    lines.append(f"-- 键-点击顺序: {'先键后点击' if cfg.timing.key_before_click else '先点击后键'}")
    lines.append(f"-- 人性化抖动: {'开' if cfg.humanize.enabled else '关'}")
    lines.append("-- 由 佐拉口琴谱伴 生成；粘贴到 G HUB 脚本编辑器并绑定到 G 键/鼠标侧键")
    lines.append("-- 风险提示: G HUB 是反作弊已知监控对象，使用风险自负，严禁用于竞技场景")
    lines.append("-- =====================================================")
    lines.append("")
    lines.append("local function play()")
    lines.append("    math.randomseed(GetRunningTime())")
    lines.append("")

    for ev in events:
        if ev.is_rest:
            dur_ms = max(1, int(round(ev.beats * beat_seconds * 1000)))
            dur_expr = lua_duration_expr(dur_ms, cfg.humanize)
            lines.append(f"    -- 休止 {ev.beats:g} 拍")
            lines.append(f"    Sleep({dur_expr})")
            continue

        key = cfg.input.key_map.get(ev.degree, str(ev.degree))
        dur_ms = max(1, int(round(ev.beats * beat_seconds * 1000)))
        dur_expr = lua_duration_expr(dur_ms, cfg.humanize)
        gap_expr = lua_gap_expr(cfg.humanize)
        hold_expr = lua_hold_expr(cfg.humanize)

        acc_text = {1: "升", -1: "降", 0: "还原"}[ev.accidental]
        comment = f"    -- {acc_text}{ev.degree} ({ev.beats:g} 拍)"

        # 构建按键 + 修饰序列
        if cfg.timing.key_before_click:
            seq = [f'PressAndReleaseKey("{key}")']
            if ev.accidental == 1:
                seq.append(f"PressAndReleaseMouseButton({cfg.input.left_button_code})")
            elif ev.accidental == -1:
                seq.append(f"PressAndReleaseMouseButton({cfg.input.right_button_code})")
        else:
            seq = []
            if ev.accidental == 1:
                seq.append(f"PressAndReleaseMouseButton({cfg.input.left_button_code})")
            elif ev.accidental == -1:
                seq.append(f"PressAndReleaseMouseButton({cfg.input.right_button_code})")
            seq.append(f'PressAndReleaseKey("{key}")')

        lines.append(comment)
        lines.append(f"    Sleep({gap_expr})")
        for s in seq:
            lines.append(f"    {s}")
        lines.append(f"    Sleep({dur_expr})")
        lines.append("")

    lines.append("end")
    lines.append("")
    lines.append("function OnEvent(event, arg, family)")
    lines.append('    if event == "PROFILE_ACTIVATED" then')
    lines.append('        OutputLogMessage("score loaded\\n")')
    lines.append("    end")
    lines.append('    if event == "G_PRESSED" and arg == 1 then')
    lines.append("        play()")
    lines.append("    end")
    lines.append("end")
    lines.append("")
    return "\n".join(lines)


def export_to_file(events: List[NoteEvent], cfg: AppConfig, path: str,
                   song_name: str = "未命名") -> None:
    """渲染并写入 .lua 文件。"""
    content = render_lua(events, cfg, song_name=song_name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
