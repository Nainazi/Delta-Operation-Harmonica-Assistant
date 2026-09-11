"""简谱解析器。

将文本简谱解析为音符事件序列，并做音域校验。

记法（空白分隔的 token）：
  1 2 3 4 5 6 7        音级 do re mi fa sol la ti
  #1 #3 ...            升（演奏时：按住中键 + 对应字母键）
  b3 b6 ...            降（演奏时：按住中键 + 对应字母键，b 为小写）
  1^                   高八度（演奏时：按住右键 + 字母）
  1,                   低八度（演奏时：按住左键 + 字母）
  1^^                  最高 do（演奏时：按住右键 + 逗号键「,」）
  -                    延长前一个音符一拍（可连用 ---）
  .                    附点（前音符时值 ×1.5）
  _                    减时（前音符时值 ×0.5，可连用 __）
  0                    休止（一拍），可用 - 延长
  |                    小节线（忽略）
  // 注释              行注释
  @bpm 120             可选：曲谱内 BPM（覆盖配置）
  @key C               可选：调号（仅参考，不影响演奏）

音域说明：
  基础音区 z–m；左键降八度、右键升八度；最高 do 为右键+逗号。
  半音范围约低八度 b1 到最高 do（相对 do 约 [-13, 24]）。
  超出映射的音符会产生警告，但解析仍会完成。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Optional


# 自然音级 -> 相对 do 的半音数
DEGREE_SEMITONE = {1: 0, 2: 2, 3: 4, 4: 5, 5: 7, 6: 9, 7: 11}

# 口琴可达半音范围（相对 do）：低八度 b1≈-13 … 最高 do≈24
PLAYABLE_MIN = -13
PLAYABLE_MAX = 24


@dataclass
class NoteEvent:
    degree: int            # 1-7，休止为 0
    accidental: int        # -1 降 / 0 还原 / 1 升
    beats: float           # 时值（拍）
    octave: int            # 八度偏移：-1 左键 / 0 基础 / +1 右键 / +2 最高 do（右键+，）
    is_rest: bool = False
    # 实际可发半音（degree+accidental，无八度）与意图半音（含八度）
    playable_semitone: Optional[int] = None
    intended_semitone: Optional[int] = None
    # 原始 token 文本，便于 GUI 高亮定位
    source: str = ""


@dataclass
class ParseResult:
    events: List[NoteEvent]
    warnings: List[Tuple[int, str]]   # (事件索引或 -1, 警告文本)
    bpm_override: Optional[float] = None
    key_override: Optional[str] = None


class ParseError(ValueError):
    pass


def _semitone(degree: int, accidental: int, octave: int) -> int:
    return DEGREE_SEMITONE[degree] + accidental + 12 * octave


def _parse_pitch_token(tok: str) -> Tuple[int, int, int]:
    """解析形如 #1^ / b3, / 5 的音高 token，返回 (degree, accidental, octave)。"""
    s = tok
    accidental = 0
    if s.startswith("#"):
        accidental = 1
        s = s[1:]
    elif s.startswith("b"):
        accidental = -1
        s = s[1:]
    if not s or not s[0].isdigit():
        raise ParseError(f"无法识别的音高 token: {tok!r}")
    # 八度标记可能在数字之后
    degree = int(s[0])
    if degree < 1 or degree > 7:
        raise ParseError(f"音级必须在 1-7 之间: {tok!r}")
    rest = s[1:]
    octave = 0
    for ch in rest:
        if ch == "^":
            octave += 1
        elif ch == ",":
            octave -= 1
        else:
            raise ParseError(f"音高 token 含非法字符 {ch!r}: {tok!r}")
    return degree, accidental, octave


def parse(text: str) -> ParseResult:
    """解析简谱文本，返回事件序列与警告。"""
    events: List[NoteEvent] = []
    warnings: List[Tuple[int, str]] = []
    bpm_override: Optional[float] = None
    key_override: Optional[str] = None

    # 预处理：去掉行注释，保留行结构以便错误定位
    lines = text.splitlines()
    flat_tokens: List[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("//"):
            continue
        if stripped.startswith("@"):
            # 头部指令
            parts = stripped[1:].split(None, 1)
            key = parts[0].lower() if parts else ""
            val = parts[1].strip() if len(parts) > 1 else ""
            if key == "bpm":
                try:
                    bpm_override = float(val)
                except ValueError:
                    warnings.append((-1, f"@bpm 值无效: {val!r}"))
            elif key == "key":
                key_override = val or None
            else:
                warnings.append((-1, f"未知指令 @{key}"))
            continue
        flat_tokens.extend(stripped.split())

    i = 0
    n = len(flat_tokens)
    while i < n:
        tok = flat_tokens[i]
        i += 1

        if tok == "|":
            continue

        if tok == "0":
            # 休止，默认一拍，后续 - . _ 可修饰
            ev = NoteEvent(degree=0, accidental=0, beats=1.0, octave=0,
                           is_rest=True, source=tok)
            events.append(ev)
            i = _consume_modifiers(flat_tokens, i, ev)
            continue

        if tok.startswith("-"):
            # 孤立的 -（前面无音符）
            warnings.append((-1, f"孤立延长符 '-' 被忽略"))
            # 把多个 - 一起跳过
            while i < n and flat_tokens[i] == "-":
                i += 1
            continue

        # 音高 token
        try:
            degree, accidental, octave = _parse_pitch_token(tok)
        except ParseError as e:
            warnings.append((-1, str(e)))
            continue

        playable = _semitone(degree, accidental, 0)
        intended = _semitone(degree, accidental, octave)
        ev = NoteEvent(
            degree=degree, accidental=accidental, beats=1.0, octave=octave,
            is_rest=False, playable_semitone=playable,
            intended_semitone=intended, source=tok,
        )
        events.append(ev)

        # 音域校验：八度由左/右键演奏；仅超出映射时警告
        if octave < -1:
            warnings.append((len(events) - 1,
                f"音符 {tok!r} 低于一个八度：仅支持按住左键降一个八度"))
        elif octave > 2 or (octave == 2 and degree != 1):
            warnings.append((len(events) - 1,
                f"音符 {tok!r} 超出最高音映射（最高 do 为 1^^ = 右键+，）；将按最接近的高八度演奏"))
        if intended < PLAYABLE_MIN or intended > PLAYABLE_MAX:
            warnings.append((len(events) - 1,
                f"音符 {tok!r} 意图半音 {intended} 超出口琴可达范围 [{PLAYABLE_MIN},{PLAYABLE_MAX}]，需移调"))

        # 处理修饰符
        i = _consume_modifiers(flat_tokens, i, ev)

    return ParseResult(events=events, warnings=warnings,
                       bpm_override=bpm_override, key_override=key_override)


def _consume_modifiers(tokens: List[str], idx: int, ev: Optional[NoteEvent] = None) -> int:
    """从 idx 起消费连续的 - . _ 修饰符，应用到 ev（若提供）。返回新的 idx。"""
    n = len(tokens)
    while idx < n:
        t = tokens[idx]
        if t == "-":
            if ev is not None:
                ev.beats += 1.0
            idx += 1
        elif t == ".":
            if ev is not None:
                ev.beats *= 1.5
            idx += 1
        elif t == "_":
            if ev is not None:
                ev.beats *= 0.5
            idx += 1
        else:
            break
    return idx


def events_to_text(events: List[NoteEvent]) -> str:
    """把事件序列回显为可读字符串，供 GUI 预览。"""
    out = []
    for ev in events:
        if ev.is_rest:
            out.append(f"0({ev.beats:.2g})")
            continue
        acc = {1: "#", -1: "b", 0: ""}[ev.accidental]
        octv = "^" * ev.octave if ev.octave > 0 else "," * (-ev.octave)
        out.append(f"{acc}{ev.degree}{octv}({ev.beats:.2g})")
    return " ".join(out)
