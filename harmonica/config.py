"""配置定义与持久化。

配置以 JSON 文件保存于用户目录，避免写入安装目录（exe 可能位于只读位置）。
所有可调参数集中在此，供 GUI 与各模块共享。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from typing import Dict, Any


# ---- 中性命名，规避反作弊内存关键词扫描（见计划缓解措施 3）----
APP_NAME = "佐拉口琴谱伴"
APP_VERSION = "1.0.0"


def _config_dir() -> str:
    """返回配置存放目录（用户级，跨 exe 位置稳定）。"""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def _config_path() -> str:
    return os.path.join(_config_dir(), "settings.json")


@dataclass
class HumanizeConfig:
    """时序人性化参数（B 端 Python 与 E 端 Lua 共用同一组数值）。"""
    enabled: bool = True            # 是否启用抖动
    duration_jitter_pct: float = 0.10   # 时长抖动幅度 ±10%
    inter_note_gap_ms: int = 40         # 音符间随机间隔基准
    inter_note_gap_jitter_ms: int = 30  # 间隔抖动幅度
    press_hold_ms: int = 45             # 按键按下到抬起时长基准
    press_hold_jitter_ms: int = 25      # 按键时长抖动幅度
    seed: int = 0                       # 0 表示每次随机；非 0 用于复现


@dataclass
class TimingConfig:
    bpm: float = 90.0            # 每分钟拍数
    beat_seconds: float = 0.6    # 一拍秒数（= 60/bpm，缓存用）
    # 键-点击先后：True=先按数字键再左/右键修饰；False=先点击再按键
    key_before_click: bool = True


@dataclass
class InputConfig:
    backend: str = "pydirectinput"   # pydirectinput | keyboard | ctypes
    key_map: Dict[int, str] = field(default_factory=lambda: {
        1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7",
    })
    left_button_code: int = 1   # G HUB Lua: 1=左
    right_button_code: int = 3  # G HUB Lua: 3=右


@dataclass
class HotkeyConfig:
    start: str = "ctrl+alt+h"
    stop: str = "esc"


@dataclass
class AppConfig:
    timing: TimingConfig = field(default_factory=TimingConfig)
    humanize: HumanizeConfig = field(default_factory=HumanizeConfig)
    input: InputConfig = field(default_factory=InputConfig)
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    # 默认模式：C=手动辅助（零风险）；B=自动注入；E=导出 G HUB
    mode: str = "C"
    last_score: str = ""
    # 风险确认：用户须在 GUI 显式勾选，B 模式才可用
    risk_acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AppConfig":
        cfg = cls()
        if not d:
            return cfg
        for section in ("timing", "humanize", "input", "hotkey"):
            sub = d.get(section, {})
            if isinstance(sub, dict):
                getattr(cfg, section).__dict__.update(sub)
        cfg.mode = d.get("mode", cfg.mode)
        cfg.last_score = d.get("last_score", "")
        cfg.risk_acknowledged = bool(d.get("risk_acknowledged", False))
        return cfg


def load() -> AppConfig:
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            return AppConfig.from_dict(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return AppConfig()


def save(cfg: AppConfig) -> None:
    try:
        with open(_config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg.to_dict(), f, ensure_ascii=False, indent=2)
    except OSError:
        # 配置写失败不应影响主流程
        pass


def config_path() -> str:
    return _config_path()
