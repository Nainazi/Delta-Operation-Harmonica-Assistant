"""鼠标宏 Markdown 教程导出器（E 模式）。

把当前曲谱渲染为可读的 Markdown 教程，教用户用手写鼠标宏（非 G HUB Lua）
按新键位（z x c v b n m）与「按住中键 = 半音」完成演奏。

风味：三角洲行动 / Delta Force 战术简报式，但保持实用可读。
本模块只生成文件，不发送任何输入。
"""
from __future__ import annotations

from typing import List

from .config import AppConfig, DEFAULT_KEY_MAP, degree_to_key
from .score_parser import NoteEvent


def _acc_label(acc: int) -> str:
    return {1: "升 ♯", -1: "降 ♭", 0: "还原"}[acc]


def _action_for(ev: NoteEvent, cfg: AppConfig) -> str:
    if ev.is_rest:
        return "停吹（休止）"
    key = degree_to_key(cfg, ev.degree)
    if ev.accidental != 0:
        return f"按住 **中键** + 按下 `{key}`（{_acc_label(ev.accidental)}）"
    return f"按下 `{key}`"


def _ms_for_beats(beats: float, beat_seconds: float) -> int:
    return max(1, int(round(beats * beat_seconds * 1000)))


def render_markdown(events: List[NoteEvent], cfg: AppConfig,
                    song_name: str = "未命名") -> str:
    """渲染完整 Markdown 教程字符串。"""
    beat_seconds = cfg.timing.beat_seconds or (60.0 / max(1.0, cfg.timing.bpm))
    bpm = cfg.timing.bpm
    km = cfg.input.key_map or DEFAULT_KEY_MAP
    map_line = "  ".join(f"{d}→`{km.get(d, DEFAULT_KEY_MAP[d])}`" for d in range(1, 8))

    lines: List[str] = []
    lines.append(f"# 战术简报 · 口琴宏手写教程 — {song_name}")
    lines.append("")
    lines.append("> 代号：佐拉彩蛋口琴｜场景：三角洲行动 / Delta Force 安全区")
    lines.append("> 本文件由「佐拉口琴谱伴」生成，教你**手写鼠标宏**，不再导出 G HUB Lua。")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## ⚠ 风险声明（必读）")
    lines.append("")
    lines.append("- 任何键鼠宏 / 驱动回放都可能被 ACE 标记，**中风险**。")
    lines.append("- **严禁竞技对局**；建议仅在单人训练场 / 安全区试用。")
    lines.append("- 查实可能面临封号与机器码封禁，后果自负。")
    lines.append("- 更安全的选择：本工具 **手动辅助（C）** —— 只看提示、自己按键，零注入。")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. 键位与半音（v1.0.2）")
    lines.append("")
    lines.append("| 音级 | 按键 | 唱名 |")
    lines.append("| --- | --- | --- |")
    names = ["do", "re", "mi", "fa", "sol", "la", "ti"]
    for d in range(1, 8):
        lines.append(f"| {d} | `{km.get(d, DEFAULT_KEY_MAP[d])}` | {names[d-1]} |")
    lines.append("")
    lines.append(f"- 映射速记：{map_line}")
    lines.append("- **半音（♯ 升 / ♭ 降）**：按住鼠标**中键**的同时按下对应字母键。")
    lines.append("- 曲谱里 `#1` / `b3` 仍表示升/降；手上统一动作为「中键 + 字母」。")
    lines.append("- 避开 WASD 与数字键，方便边移动边吹（仍建议站桩演奏）。")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. 节奏参数")
    lines.append("")
    lines.append(f"| 项目 | 值 |")
    lines.append(f"| --- | --- |")
    lines.append(f"| BPM | **{bpm:.1f}** |")
    lines.append(f"| 一拍时长 | **{beat_seconds*1000:.0f} ms**（{beat_seconds:.3f}s） |")
    lines.append(f"| 建议按键保持 | ~{cfg.humanize.press_hold_ms} ms |")
    lines.append(f"| 音符间间隙 | ~{cfg.humanize.inter_note_gap_ms} ms（可微调） |")
    lines.append("")
    lines.append("手写宏时：每个音的「等待」≈ 拍数 × 一拍毫秒；休止只等待不按键。")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3. 手写宏通用步骤（任意鼠标宏软件）")
    lines.append("")
    lines.append("1. 打开你的鼠标驱动 / 宏编辑器（罗技、雷蛇、卓威等均可；**不必**再用 G HUB Lua）。")
    lines.append("2. 新建宏 → 选择「录制」或「手动添加动作」。")
    lines.append("3. 按下一节「逐音动作表」依次添加：")
    lines.append("   - 普通音：`按键按下(字母)` → 延迟 hold → `按键抬起` → 延迟（拍时值 − hold）")
    lines.append("   - 半音：`中键按下` → `按键按下(字母)` → 延迟 hold → `按键抬起` → `中键抬起` → 延迟剩余时值")
    lines.append("   - 休止：仅插入延迟")
    lines.append("4. 把宏绑到侧键 / G 键；进安全区 → 呼出口琴界面 → 触发宏。")
    lines.append("5. 若升降不准：改为「先中键再字母」，并略微加长中键与字母的重叠时间。")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"## 4. 逐音动作表 — {song_name}")
    lines.append("")
    lines.append("| # | 谱面 | 动作 | 时值(拍) | 建议等待(ms) |")
    lines.append("| --- | --- | --- | --- | --- |")
    for i, ev in enumerate(events, 1):
        if ev.is_rest:
            src = "0"
        else:
            acc = {1: "#", -1: "b", 0: ""}[ev.accidental]
            src = f"{acc}{ev.degree}"
        action = _action_for(ev, cfg)
        ms = _ms_for_beats(ev.beats, beat_seconds)
        lines.append(f"| {i} | `{src}` | {action} | {ev.beats:g} | {ms} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 5. 伪代码示例（便于对照手写）")
    lines.append("")
    lines.append("```")
    lines.append(f"// {song_name} @ {bpm:.1f} BPM")
    for ev in events:
        ms = _ms_for_beats(ev.beats, beat_seconds)
        if ev.is_rest:
            lines.append(f"SLEEP {ms}            // 休止 {ev.beats:g} 拍")
            continue
        key = degree_to_key(cfg, ev.degree)
        if ev.accidental != 0:
            lines.append(f"MIDDLE DOWN")
            lines.append(f"KEY DOWN  {key}       // {_acc_label(ev.accidental)}{ev.degree}")
            lines.append(f"SLEEP     {min(ms, max(30, cfg.humanize.press_hold_ms))}")
            lines.append(f"KEY UP    {key}")
            lines.append(f"MIDDLE UP")
            rem = max(0, ms - max(30, cfg.humanize.press_hold_ms))
            if rem:
                lines.append(f"SLEEP     {rem}        // 余下时值")
        else:
            lines.append(f"KEY DOWN  {key}       // {ev.degree}")
            lines.append(f"SLEEP     {min(ms, max(30, cfg.humanize.press_hold_ms))}")
            lines.append(f"KEY UP    {key}")
            rem = max(0, ms - max(30, cfg.humanize.press_hold_ms))
            if rem:
                lines.append(f"SLEEP     {rem}")
        lines.append("")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 6. 战术提示")
    lines.append("")
    lines.append("- 宏触发前先确认口琴演奏 UI 已打开，否则按键落到移动/开火上。")
    lines.append("- 第一次先用本工具 **试运行 / 手动辅助** 跟一遍节奏，再手写宏。")
    lines.append("- BPM 不对：改曲谱 `@bpm` 或设置页 BPM 后重新导出本教程。")
    lines.append("- 旧版 G HUB Lua 导出路径已弃用；请以本 Markdown 为准手写宏。")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*佐拉口琴谱伴 v1.0.2 · 仅供彩蛋娱乐*")
    lines.append("")
    return "\n".join(lines)


def export_to_file(events: List[NoteEvent], cfg: AppConfig, path: str,
                   song_name: str = "未命名") -> None:
    """渲染并写入 .md 文件。"""
    content = render_markdown(events, cfg, song_name=song_name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
