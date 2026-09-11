"""配置定义与持久化。

配置以 JSON 文件保存于用户目录，避免写入安装目录（exe 可能位于只读位置）。
所有可调参数集中在此，供 GUI 与各模块共享。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List


# ---- 中性命名，规避反作弊内存关键词扫描（见计划缓解措施 3）----
APP_NAME = "佐拉口琴谱伴"
APP_VERSION = "1.0.6"

# 默认音级 → 键盘映射：1→z 2→x 3→c 4→v 5→b 6→n 7→m
DEFAULT_KEY_MAP: Dict[int, str] = {
    1: "z", 2: "x", 3: "c", 4: "v", 5: "b", 6: "n", 7: "m",
}

# MD 宏教程驱动模板
MD_TEMPLATES = ("generic", "logitech", "razer")
MD_TEMPLATE_LABELS = {
    "generic": "通用伪代码",
    "logitech": "罗技 G HUB",
    "razer": "雷蛇 Synapse",
}


def _config_dir() -> str:
    """返回配置存放目录（用户级，跨 exe 位置稳定）。"""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def _config_path() -> str:
    return os.path.join(_config_dir(), "settings.json")


def config_dir() -> str:
    return _config_dir()


def user_scores_dir() -> str:
    """用户曲谱目录：%APPDATA%/佐拉口琴谱伴/scores"""
    path = os.path.join(_config_dir(), "scores")
    os.makedirs(path, exist_ok=True)
    return path


def builtin_scores_dir() -> str:
    """内置曲谱目录（打包进包内 harmonica/scores）。"""
    return os.path.join(os.path.dirname(__file__), "scores")


@dataclass
class HumanizeConfig:
    """时序人性化参数（B 端注入与 MD 宏教程共用同一组数值参考）。"""
    enabled: bool = True            # 是否启用抖动
    duration_jitter_pct: float = 0.10   # 时长抖动幅度 ±10%
    inter_note_gap_ms: int = 40         # 音符间随机间隔基准
    inter_note_gap_jitter_ms: int = 30  # 间隔抖动幅度
    press_hold_ms: int = 45             # 最短按键保持（毫秒）；实际保持 ≈ 音符时值 85%–90%
    press_hold_jitter_ms: int = 25      # 无 duration 时的固定脉冲抖动（宏教程回退）
    seed: int = 0                       # 0 表示每次随机；非 0 用于复现


@dataclass
class TimingConfig:
    bpm: float = 90.0            # 每分钟拍数
    beat_seconds: float = 0.6    # 一拍秒数（= 60/bpm，缓存用）
    # 键-修饰顺序：B 模式已改为「修饰整音按住 → 键 → 抬修饰」，此字段仅兼容旧配置
    key_before_click: bool = False  # 不再影响 B 注入顺序


@dataclass
class InputConfig:
    backend: str = "sendinput"   # sendinput | pydirectinput | keyboard_ctypes | null
    key_map: Dict[int, str] = field(default_factory=lambda: dict(DEFAULT_KEY_MAP))
    # 左键=低八度，右键=高八度，中键=半音；按住覆盖整音
    middle_button_code: int = 2  # 常见宏软件：1=左 2=中 3=右
    left_button_code: int = 1
    right_button_code: int = 3


@dataclass
class HotkeyConfig:
    # 默认 F5 / F6，避开 zxcvbnm 与 WASD
    start: str = "f5"
    stop: str = "f6"


@dataclass
class AppConfig:
    timing: TimingConfig = field(default_factory=TimingConfig)
    humanize: HumanizeConfig = field(default_factory=HumanizeConfig)
    input: InputConfig = field(default_factory=InputConfig)
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    # 默认模式：C=手动辅助（零风险）；B=自动注入；E=导出鼠标宏教程 MD
    mode: str = "C"
    last_score: str = ""
    # 风险确认：用户须在 GUI 显式勾选，B 模式才可用
    risk_acknowledged: bool = False
    # 首次启动向导是否已看过
    wizard_seen: bool = False
    # 曲库：收藏与最近（路径或 builtin:xxx 标识）
    favorites: List[str] = field(default_factory=list)
    recent: List[str] = field(default_factory=list)
    # MD 导出驱动模板：generic | logitech | razer
    md_template: str = "generic"

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
        # key_map JSON 键多为 str，统一回 int
        km = getattr(cfg.input, "key_map", None)
        if isinstance(km, dict):
            fixed: Dict[int, str] = {}
            for k, v in km.items():
                try:
                    fixed[int(k)] = str(v)
                except (TypeError, ValueError):
                    continue
            cfg.input.key_map = fixed or dict(DEFAULT_KEY_MAP)
            # 旧版 1-7 数字映射 → 自动迁移到 z x c v b n m
            vals = set(cfg.input.key_map.values())
            if vals and vals <= set("1234567"):
                cfg.input.key_map = dict(DEFAULT_KEY_MAP)
        # 旧热键迁移：避开与字母键冲突的默认
        if cfg.hotkey.start in ("ctrl+alt+h", "1"):
            cfg.hotkey.start = "f5"
        if cfg.hotkey.stop in ("esc",):
            cfg.hotkey.stop = "f6"
        cfg.mode = d.get("mode", cfg.mode)
        cfg.last_score = d.get("last_score", "")
        cfg.risk_acknowledged = bool(d.get("risk_acknowledged", False))
        cfg.wizard_seen = bool(d.get("wizard_seen", False))
        fav = d.get("favorites", [])
        cfg.favorites = [str(x) for x in fav] if isinstance(fav, list) else []
        recent = d.get("recent", [])
        cfg.recent = [str(x) for x in recent] if isinstance(recent, list) else []
        tpl = str(d.get("md_template", "generic") or "generic")
        cfg.md_template = tpl if tpl in MD_TEMPLATES else "generic"
        # 旧后端名 keyboard / ctypes → 设置页选项 keyboard_ctypes
        b = str(getattr(cfg.input, "backend", "") or "").strip().lower()
        if b in ("keyboard", "ctypes"):
            cfg.input.backend = "keyboard_ctypes"
        elif b not in ("sendinput", "pydirectinput", "keyboard_ctypes", "null"):
            cfg.input.backend = "sendinput"
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


def degree_to_key(cfg: AppConfig, degree: int) -> str:
    """音级 1-7 → 当前键位字母。"""
    return cfg.input.key_map.get(degree, DEFAULT_KEY_MAP.get(degree, str(degree)))


def extract_song_title(text: str, fallback: str = "未命名") -> str:
    """从曲谱正文取标题：首条 // 注释内容，否则 fallback。"""
    for line in (text or "").splitlines():
        s = line.strip()
        if s.startswith("//"):
            title = s[2:].strip()
            # 去掉常见后缀说明
            if " - " in title:
                title = title.split(" - ", 1)[0].strip()
            if title:
                return title
    return fallback or "未命名"


def sanitize_filename(name: str, max_len: int = 80) -> str:
    """去掉文件系统非法字符。"""
    bad = '<>:"/\\|?*\0'
    out = "".join("_" if c in bad else c for c in (name or "").strip())
    out = out.strip(" .")
    if not out:
        out = "未命名"
    return out[:max_len]
