"""输入分发器。

负责把音符事件序列按节拍调度为实际输入（B 模式）或视觉提示（C 模式）。

特性：
  - 独立线程播放，支持外部 stop()
  - 高精度时序：winmm.timeBeginPeriod(1) + perf_counter 绝对对齐，防误差累积
  - 键-点击先后可配置（timing.key_before_click）
  - 进度回调：on_progress(index, total, event) 供 GUI 更新
  - C 模式：仅回调不注入，零风险
"""
from __future__ import annotations

import random
import threading
import time
from typing import Callable, Optional, List

from .config import AppConfig
from .humanizer import humanize_event
from .input_backend import InputBackend, NullBackend
from .score_parser import NoteEvent


# winmm 高精度定时
try:
    import ctypes
    _winmm = ctypes.windll.winmm
    _HAS_WINMM = True
except Exception:
    _winmm = None
    _HAS_WINMM = False


ProgressCallback = Callable[[int, int, NoteEvent], None]


class Dispatcher:
    """调度器：B 注入 / C 提示。"""

    def __init__(self, cfg: AppConfig, backend: Optional[InputBackend] = None,
                 on_progress: Optional[ProgressCallback] = None) -> None:
        self.cfg = cfg
        self.backend: InputBackend = backend if backend is not None else NullBackend()
        self.on_progress = on_progress
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._winmm_acquired = False

    # ---- 生命周期 ----
    def play_b(self, events: List[NoteEvent]) -> None:
        """B 模式：自动注入。"""
        self._start(events, inject=True)

    def play_c(self, events: List[NoteEvent]) -> None:
        """C 模式：仅提示，不注入。"""
        self._start(events, inject=False)

    def stop(self) -> None:
        self._stop.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def wait(self, timeout: Optional[float] = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    # ---- 内部 ----
    def _start(self, events: List[NoteEvent], inject: bool) -> None:
        if self.is_running():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, args=(events, inject), daemon=True
        )
        self._thread.start()

    def _run(self, events: List[NoteEvent], inject: bool) -> None:
        self._begin_period()
        try:
            self._dispatch(events, inject)
        finally:
            self._end_period()
            if self.on_progress is not None:
                # 播放结束信号：传 None 让 GUI 复位
                try:
                    self.on_progress(0, 0, None)
                except Exception:
                    pass

    def _dispatch(self, events: List[NoteEvent], inject: bool) -> None:
        cfg = self.cfg
        rng = random.Random(cfg.humanize.seed if cfg.humanize.seed else None)
        beat_seconds = cfg.timing.beat_seconds or (60.0 / max(1.0, cfg.timing.bpm))
        total = len(events)
        start = time.perf_counter()
        cursor = 0.0  # 相对开始的累计秒数

        for idx, ev in enumerate(events):
            if self._stop.is_set():
                return

            timing = humanize_event(ev.beats, beat_seconds, cfg.humanize, rng, first=(idx == 0))

            # 前导间隔（人性化）
            if timing.gap_s > 0:
                cursor += timing.gap_s
                self._sleep_until(start + cursor)

            if self.on_progress is not None:
                try:
                    self.on_progress(idx, total, ev)
                except Exception:
                    pass

            if ev.is_rest:
                # 休止：只等待
                cursor += timing.duration_s
                self._sleep_until(start + cursor)
                continue

            if inject:
                self._inject_note(ev, timing.hold_ms)

            # 音符保持
            cursor += timing.duration_s
            self._sleep_until(start + cursor)

    def _inject_note(self, ev: NoteEvent, hold_ms: int) -> None:
        """按配置顺序发送键 + 可选左/右键修饰。"""
        cfg = self.cfg
        key = cfg.input.key_map.get(ev.degree, str(ev.degree))
        need_click = ev.accidental != 0
        click_fn = None
        if ev.accidental == 1:
            click_fn = self.backend.click_left
        elif ev.accidental == -1:
            click_fn = self.backend.click_right

        if cfg.timing.key_before_click:
            self.backend.press_key(key, hold_ms)
            if need_click and click_fn is not None:
                click_fn(hold_ms)
        else:
            if need_click and click_fn is not None:
                click_fn(hold_ms)
            self.backend.press_key(key, hold_ms)

    # ---- 高精度等待 ----
    def _sleep_until(self, target: float) -> None:
        """睡眠至 perf_counter 的绝对时间点，避免误差累积。
        分段睡眠，每 ~20ms 检查 stop 标志，使停止能在 ~20ms 内生效。"""
        end = target
        while True:
            if self._stop.is_set():
                return
            now = time.perf_counter()
            remaining = end - now
            if remaining <= 0:
                return
            # 最后 ~2ms 用忙等保精度，其余用 sleep 让出 CPU
            if remaining <= 0.002:
                while time.perf_counter() < end and not self._stop.is_set():
                    pass
                return
            time.sleep(min(0.02, remaining - 0.002))

    def _begin_period(self) -> None:
        if not _HAS_WINMM:
            return
        try:
            _winmm.timeBeginPeriod(1)
            self._winmm_acquired = True
        except Exception:
            self._winmm_acquired = False

    def _end_period(self) -> None:
        if _HAS_WINMM and self._winmm_acquired:
            try:
                _winmm.timeEndPeriod(1)
            except Exception:
                pass
            self._winmm_acquired = False
