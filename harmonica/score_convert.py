"""简谱转换工具。

把常见网络简谱文本规范化为本工具可用的记法，
并支持导出为脚本可用的解析后文本格式。

常见输入形态：
  - 字符无分隔：11556654433221
  - 括号八度：[1] 高八度、(1) 低八度
  - 点八度：1.（高八度）或 1..（更高）
  - 简谱升降：#1 或 b1 或 ♯1 ♭1
  - 小节线 |、空格、换行混排
输出规范 token：#1 b3 1^ 1, 等，空格分隔，附 - . _ 0 | 修饰。

脚本可用文本（export_script_text）：每音符一行
  degree accidental beats
"""
from __future__ import annotations

from typing import List, Tuple

from .score_parser import parse, ParseResult, NoteEvent


# 点八度：数字后的 . 表示升八度，. 前的多个 . 表示降八度
def _strip_dots(s: str) -> Tuple[str, int]:
    """解析形如 '1..' / '1.' / '3' 的八度标记，返回 (core, octave)。"""
    core = s
    up = 0
    down = 0
    # 数字后面的点是升八度
    while core.endswith("."):
        core = core[:-1]
        up += 1
    # 数字前面的点（少见）忽略或视为降八度
    while core.startswith("."):
        core = core[1:]
        down += 1
    return core, up - down


def _normalize_char_accidental(s: str) -> str:
    """把 ♯ ♭ 符号转为 # b。"""
    return s.replace("♯", "#").replace("♭", "b").replace("ｂ", "b")


def to_tokens(text: str) -> List[str]:
    """把自由格式的简谱文本解析为规范 token 列表（空格分隔）。

    支持：
      - 括号八度 [1] 高八度 / (1) 低八度
      - 点八度 1. 高八度
      - 升降 #1 b1 ♯1 ♭1
      - 无分隔连写 1155665
      - 修饰 - . _ 0 | 原样保留
      - 行注释 // 去掉
    """
    text = _normalize_char_accidental(text)
    tokens: List[str] = []
    i = 0
    n = len(text)

    def emit_pitch(core: str, accidental: int, octave: int) -> None:
        acc = {1: "#", -1: "b", 0: ""}[accidental]
        octv = "^" * octave if octave > 0 else "," * (-octave)
        tokens.append(acc + core + octv)

    while i < n:
        ch = text[i]
        # 注释
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            i = n if j < 0 else j + 1
            continue
        # 小节线/空格/换行/制表符
        if ch in " \t\r\n":
            i += 1
            continue
        if ch == "|":
            tokens.append("|")
            i += 1
            continue
        # 修饰符
        if ch in "-._":
            tokens.append(ch)
            i += 1
            continue
        # 括号八度
        if ch == "[":
            j = text.find("]", i)
            if j > i:
                inner = text[i + 1:j].strip()
                acc = 0
                if inner.startswith("#"):
                    acc = 1
                    inner = inner[1:]
                elif inner.startswith("b"):
                    acc = -1
                    inner = inner[1:]
                if inner.isdigit() and 1 <= int(inner) <= 7:
                    emit_pitch(inner, acc, 1)
                i = j + 1
                continue
        if ch == "(":
            j = text.find(")", i)
            if j > i:
                inner = text[i + 1:j].strip()
                acc = 0
                if inner.startswith("#"):
                    acc = 1
                    inner = inner[1:]
                elif inner.startswith("b"):
                    acc = -1
                    inner = inner[1:]
                if inner.isdigit() and 1 <= int(inner) <= 7:
                    emit_pitch(inner, acc, -1)
                i = j + 1
                continue
        # 升降号
        if ch in "#b":
            if i + 1 < n and text[i + 1].isdigit():
                acc = 1 if ch == "#" else -1
                # 可能带八度点
                j = i + 1
                core = text[j]
                k = j + 1
                up = 0
                while k < n and text[k] == ".":
                    up += 1
                    k += 1
                emit_pitch(core, acc, up)
                i = k
                continue
        # 数字音级（可带点八度）
        if ch.isdigit():
            d = int(ch)
            if 1 <= d <= 7:
                j = i + 1
                up = 0
                while j < n and text[j] == ".":
                    up += 1
                    j += 1
                emit_pitch(ch, 0, up)
                i = j
                continue
            if d == 0:
                tokens.append("0")
                i += 1
                continue
        # 其他字符跳过
        i += 1

    return tokens


def normalize_to_tokens_text(text: str) -> str:
    """把自由格式简谱转换为空格分隔的规范 token 文本。"""
    return " ".join(to_tokens(text))


def export_script_text(text: str) -> Tuple[str, ParseResult]:
    """把简谱文本解析为脚本可用格式（每行：degree accidental beats），返回 (text, parse_result)。

    degree: 0 休止 / 1-7 音级
    accidental: -1 降 / 0 还原 / 1 升
    beats: 时值（拍，浮点）
    """
    tokens_text = normalize_to_tokens_text(text)
    result = parse(tokens_text)
    lines: List[str] = []
    for ev in result.events:
        if ev.is_rest:
            lines.append("0 0 %.3g" % ev.beats)
        else:
            lines.append("%d %d %.3g" % (ev.degree, ev.accidental, ev.beats))
    return "\n".join(lines), result
