"""时序人性化模块。

目的：避免绝对等距、瞬时脉冲等「机器特征」输入，降低行为异常检测概率。
注意：人性化只能降低、不能消除检测概率，仍违反游戏 ToS（见 README 风险声明）。

提供两类输出：
  1. Python 端（B 模式 dispatcher 使用）：humanize_duration / humanize_gap / humanize_hold
  2. 时序数值亦供 E 模式鼠标宏 Markdown 教程参考（macro_md_exporter）

B 端注入与 E 端教程共用同一组 HumanizeConfig 数值，便于对照手写宏。
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .config import HumanizeConfig

# 按住时长占音符时值的比例；略短于 100% 以便抬键后再接下一个音
HOLD_RATIO_MIN = 0.85
HOLD_RATIO_MAX = 0.90
KEYUP_PAD_MS = 8


@dataclass
class HumanizedTiming:
    duration_s: float       # 该音符保持时长（秒）
    gap_s: float            # 音符前等待间隔（秒）
    hold_ms: int            # 按键按下到抬起时长（毫秒）


def _make_rng(cfg: "HumanizeConfig") -> random.Random:
    seed = cfg.seed if cfg.seed and cfg.seed != 0 else None
    return random.Random(seed)


def humanize_duration(beats: float, beat_seconds: float, cfg: "HumanizeConfig", rng: random.Random) -> float:
    """把拍数转秒并叠加时长抖动。"""
    base = beats * beat_seconds
    if not cfg.enabled:
        return base
    jitter = rng.uniform(-cfg.duration_jitter_pct, cfg.duration_jitter_pct)
    return max(0.02, base * (1.0 + jitter))


def humanize_gap(cfg: "HumanizeConfig", rng: random.Random) -> float:
    """音符间随机间隔（秒）。"""
    if not cfg.enabled:
        return 0.0
    base = cfg.inter_note_gap_ms / 1000.0
    jitter = rng.uniform(-cfg.inter_note_gap_jitter_ms, cfg.inter_note_gap_jitter_ms) / 1000.0
    return max(0.0, base + jitter)


def humanize_hold(
    cfg: "HumanizeConfig",
    rng: random.Random,
    duration_s: Optional[float] = None,
) -> int:
    """按键按下到抬起时长（毫秒）。

    传入 duration_s 时：保持 ≈ 音符时值的 85%–90%，且不低于 press_hold_ms
    （该配置现为最短按下时间，不是唯一脉冲长度），并留出 KEYUP_PAD_MS
    给抬键、再接下一个音。未传 duration_s 时回退为旧的固定脉冲（宏教程等）。
    """
    floor = max(1, int(cfg.press_hold_ms))
    if duration_s is None:
        if not cfg.enabled:
            return max(20, floor)
        jitter = rng.randint(-cfg.press_hold_jitter_ms, cfg.press_hold_jitter_ms)
        return max(15, floor + jitter)

    duration_ms = max(0.0, float(duration_s) * 1000.0)
    if cfg.enabled:
        ratio = rng.uniform(HOLD_RATIO_MIN, HOLD_RATIO_MAX)
    else:
        ratio = (HOLD_RATIO_MIN + HOLD_RATIO_MAX) / 2.0
    hold = int(round(duration_ms * ratio))
    max_hold = int(round(duration_ms)) - KEYUP_PAD_MS
    if max_hold < 1:
        return max(1, int(round(duration_ms)) if duration_ms >= 1 else 1)
    hold = max(floor, hold)
    hold = min(hold, max_hold)
    return max(1, hold)


def humanize_event(beats: float, beat_seconds: float, cfg: "HumanizeConfig",
                   rng: random.Random, first: bool = False) -> HumanizedTiming:
    """一次音符的完整时序。first=True 时通常不加前导 gap。"""
    duration = humanize_duration(beats, beat_seconds, cfg, rng)
    gap = 0.0 if first else humanize_gap(cfg, rng)
    hold = humanize_hold(cfg, rng, duration_s=duration)
    return HumanizedTiming(duration_s=duration, gap_s=gap, hold_ms=hold)


# ---- Lua 端（E 模式）----
def render_lua_jitter(cfg: "HumanizeConfig", var_base_ms: str) -> str:
    """生成 Lua 中对某基准时长叠加抖动的表达式字符串。

    返回形如 `base_ms + math.random(-38, 38)` 的表达式（整数毫秒）。
    若 enabled=False，返回 var_base_ms（无抖动）。
    """
    if not cfg.enabled:
        return var_base_ms
    # Lua 端用整数随机，幅度取配置的 10% 对应毫秒
    # duration_jitter_pct 作用于时长（拍×beat_seconds），此处由调用方换算成 ms 后传入
    # 这里返回一个通用抖动宏调用，幅度由调用方决定
    return var_base_ms  # 占位，实际抖动由 render 时按场景生成


def lua_duration_expr(base_ms: int, cfg: "HumanizeConfig") -> str:
    """音符保持时长的 Lua 表达式（含抖动）。"""
    if not cfg.enabled:
        return str(base_ms)
    amp = max(1, int(base_ms * cfg.duration_jitter_pct))
    return f"{base_ms} + math.random(-{amp}, {amp})"


def lua_gap_expr(cfg: "HumanizeConfig") -> str:
    """音符间间隔的 Lua 表达式（含抖动）。"""
    if not cfg.enabled:
        return "0"
    base = cfg.inter_note_gap_ms
    amp = cfg.inter_note_gap_jitter_ms
    return f"math.random({max(0, base - amp)}, {base + amp})"


def lua_hold_expr(cfg: "HumanizeConfig") -> str:
    """按键按下到抬起时长的 Lua 表达式（含抖动）。"""
    if not cfg.enabled:
        return str(max(20, cfg.press_hold_ms))
    base = cfg.press_hold_ms
    amp = cfg.press_hold_jitter_ms
    return f"math.random({max(15, base - amp)}, {base + amp})"
