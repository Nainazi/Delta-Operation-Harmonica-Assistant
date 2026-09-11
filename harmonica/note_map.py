"""佐拉口琴游戏键位映射（社区公开操作，非 MIDI）。

基础音区：z x c v b n m = 音级 1–7
低八度：按住 **左键** + 字母（曲谱 ``,`` / 八度 -1）
高八度：按住 **右键** + 字母（曲谱 ``^`` / 八度 +1）
最高 do（1^^，八度 +2 且音级 1）：按住 **右键** + 逗号键 ``,``
半音：按住 **中键**（曲谱 # / b 演奏动作相同）
可组合：例如 右键+中键+， = 最高 #do
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Union

from .config import DEFAULT_KEY_MAP
from .score_parser import NoteEvent

COMMA_KEY = ","
COMMA_DISPLAY = "，"

KeyMap = Mapping[Union[int, str], str]


@dataclass(frozen=True)
class NoteMapping:
    key: str
    left: bool
    right: bool
    middle: bool
    display_key: str

    @property
    def mouse_buttons(self) -> Sequence[str]:
        buttons = []
        if self.left:
            buttons.append("left")
        if self.right:
            buttons.append("right")
        if self.middle:
            buttons.append("middle")
        return tuple(buttons)


def _lookup_letter(degree: int, key_map: Optional[KeyMap]) -> str:
    km = key_map or DEFAULT_KEY_MAP
    raw = None
    try:
        raw = km.get(int(degree))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raw = None
    if raw is None:
        raw = km.get(str(degree))  # type: ignore[arg-type]
    if not raw:
        raw = DEFAULT_KEY_MAP.get(int(degree), str(degree))
    return str(raw).strip().lower()


def map_note(
    degree: int,
    accidental: int = 0,
    octave: int = 0,
    key_map: Optional[KeyMap] = None,
) -> NoteMapping:
    """degree/accidental/octave → 按键 + 鼠标修饰（整音按住）。"""
    middle = accidental != 0
    # 最高 do：右键 + 逗号。八度 ≥+2 的 do 都走此键。
    if int(degree) == 1 and int(octave) >= 2:
        return NoteMapping(
            key=COMMA_KEY,
            left=False,
            right=True,
            middle=middle,
            display_key=COMMA_DISPLAY,
        )
    key = _lookup_letter(degree, key_map)
    return NoteMapping(
        key=key,
        left=int(octave) < 0,
        right=int(octave) > 0,
        middle=middle,
        display_key=key,
    )


def map_event(ev: NoteEvent, key_map: Optional[KeyMap] = None) -> NoteMapping:
    return map_note(ev.degree, ev.accidental, ev.octave, key_map)


def format_play_hint(mapping: NoteMapping) -> str:
    """C 模式 / HUD 标签：左键/右键/中键/， 按需拼接。"""
    parts = []
    if mapping.left:
        parts.append("左键")
    if mapping.right:
        parts.append("右键")
    if mapping.middle:
        parts.append("中键")
    parts.append(mapping.display_key)
    return "+".join(parts)


def format_event_hint(ev: NoteEvent, key_map: Optional[KeyMap] = None) -> str:
    if ev.is_rest:
        return "休止"
    return format_play_hint(map_event(ev, key_map))
