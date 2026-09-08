"""时序人性化模块。

目的：避免绝对等距、瞬时脉冲等「机器特征」输入，降低行为异常检测概率。
注意：人性化只能降低、不能消除检测概率，仍违反游戏 ToS（见 README 风险声明）。

提供两类输出：
  1. Python 端（B 模式 dispatcher 使用）：humanize_duration / humanize_gap / humanize_hold
  2. Lua 端片段（E 模式 ghub_exporter 使用）：render_lua_jitter，生成等价的抖动表达式

B 端与 E 端共用同一组 HumanizeConfig 数值，保证两条链路行为一致。
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import HumanizeConfig


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


def humanize_hold(cfg: "HumanizeConfig", rng: random.Random) -> int:
    """按键按下到抬起时长（毫秒）。"""
    if not cfg.enabled:
        return max(20, cfg.press_hold_ms)
    jitter = rng.randint(-cfg.press_hold_jitter_ms, cfg.press_hold_jitter_ms)
    return max(15, cfg.press_hold_ms + jitter)


def humanize_event(beats: float, beat_seconds: float, cfg: "HumanizeConfig",
                   rng: random.Random, first: bool = False) -> HumanizedTiming:
    """一次音符的完整时序。first=True 时通常不加前导 gap。"""
    duration = humanize_duration(beats, beat_seconds, cfg, rng)
    gap = 0.0 if first else humanize_gap(cfg, rng)
    hold = humanize_hold(cfg, rng)
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
