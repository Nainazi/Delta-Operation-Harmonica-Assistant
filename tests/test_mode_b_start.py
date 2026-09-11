"""演奏页 mode B 与开始逻辑：同步 mode、拒绝空后端。

本环境可能没有系统 tkinter；在导入 App 前装入轻量 stub。
"""
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock, patch


def _install_gui_stubs() -> None:
    if "tkinter" in sys.modules:
        return
    tk = types.ModuleType("tkinter")
    tk.TclError = type("TclError", (Exception,), {})
    tk.StringVar = object
    tk.DoubleVar = object
    tk.BooleanVar = object
    tk.Widget = object
    tk.Misc = object
    tk.Event = object
    tk.Toplevel = object
    tk.Label = object
    tk.Text = object
    sys.modules["tkinter"] = tk
    sys.modules["tkinter.filedialog"] = types.ModuleType("tkinter.filedialog")
    sys.modules["tkinter.messagebox"] = types.ModuleType("tkinter.messagebox")
    sys.modules["tkinter.ttk"] = types.ModuleType("tkinter.ttk")
    sys.modules["customtkinter"] = types.ModuleType("customtkinter")


_install_gui_stubs()

from harmonica.config import AppConfig
from harmonica.input_backend import BackendUnavailable, NullBackend
from harmonica.ui.app import App


class _FakeVar:
    def __init__(self, value: str) -> None:
        self._v = value

    def get(self) -> str:
        return self._v

    def set(self, v: str) -> None:
        self._v = v


class ModeSyncTests(unittest.TestCase):
    def test_sync_mode_from_radio(self) -> None:
        app = App.__new__(App)
        app.cfg = AppConfig()
        app.cfg.mode = "C"
        app.mode_var = _FakeVar("B")
        self.assertEqual(app._sync_mode_from_ui(), "B")
        self.assertEqual(app.cfg.mode, "B")

    def test_on_mode_change_uses_selected_value(self) -> None:
        app = App.__new__(App)
        app.cfg = AppConfig()
        app.cfg.mode = "C"
        app.mode_var = _FakeVar("C")
        app._update_primary_button = lambda: None
        app._save_cfg = lambda: None
        app._on_mode_change("B")
        self.assertEqual(app.cfg.mode, "B")
        self.assertEqual(app.mode_var.get(), "B")


class ModeBStartTests(unittest.TestCase):
    def _bare_app(self) -> App:
        app = App.__new__(App)
        app.cfg = AppConfig()
        app.cfg.mode = "B"
        app.cfg.risk_acknowledged = True
        app.mode_var = _FakeVar("B")
        app.dispatcher = None
        app.score_text = MagicMock()
        app.score_text.get.return_value = "1 2 3\n"
        app.progress = MagicMock()
        app.status_label = MagicMock()
        app.warn_text = MagicMock()
        app.bpm_var = MagicMock()
        app.primary_btn = MagicMock()
        app.test_btn = MagicMock()
        app._mode_radios = []
        app._warn_has_content = False
        app.root = MagicMock()
        return app

    def test_start_b_aborts_when_backend_missing(self) -> None:
        app = self._bare_app()
        with patch("harmonica.ui.app.backend_mod.resolve_backend",
                   side_effect=BackendUnavailable("missing libs")), \
             patch("harmonica.ui.app.messagebox") as mb:
            app._on_start()
        self.assertIsNone(app.dispatcher)
        mb.showerror.assert_called()
        args = app.status_label.configure.call_args
        self.assertIn("未启动", str(args))

    def test_start_b_uses_real_backend_not_null(self) -> None:
        app = self._bare_app()
        fake = MagicMock()
        fake.name = "pydirectinput"
        fake.warning = None
        captured = {}

        def fake_dispatcher(cfg, backend=None, on_progress=None, on_error=None):
            captured["backend"] = backend
            d = MagicMock()
            d.play_b = MagicMock()
            d.is_running = MagicMock(return_value=False)
            return d

        with patch("harmonica.ui.app.backend_mod.resolve_backend",
                   return_value=(fake, None)), \
             patch("harmonica.ui.app.disp.Dispatcher", side_effect=fake_dispatcher), \
             patch("harmonica.ui.app.messagebox"):
            app._on_start()
        self.assertIsNotNone(app.dispatcher)
        app.dispatcher.play_b.assert_called_once()
        self.assertIs(captured["backend"], fake)
        self.assertNotIsInstance(captured["backend"], NullBackend)
        self.assertEqual(captured["backend"].name, "pydirectinput")
        status = str(app.status_label.configure.call_args)
        self.assertIn("pydirectinput", status)

    def test_start_c_uses_null_backend(self) -> None:
        app = self._bare_app()
        app.cfg.mode = "C"
        app.mode_var = _FakeVar("C")
        captured = {}

        def fake_dispatcher(cfg, backend=None, on_progress=None, on_error=None):
            captured["backend"] = backend
            d = MagicMock()
            d.play_c = MagicMock()
            return d

        with patch("harmonica.ui.app.disp.Dispatcher", side_effect=fake_dispatcher), \
             patch("harmonica.ui.app.messagebox"):
            app._on_start()
        self.assertIsInstance(captured["backend"], NullBackend)
        app.dispatcher.play_c.assert_called_once()

    def test_primary_button_b_keeps_on_start(self) -> None:
        app = App.__new__(App)
        app.cfg = AppConfig()
        app.cfg.mode = "B"
        app.primary_btn = MagicMock()
        app.export_md_row = MagicMock()
        app.convert_btn = MagicMock()
        app.export_md_row.winfo_ismapped.return_value = True
        app._update_primary_button()
        kwargs = app.primary_btn.configure.call_args.kwargs
        self.assertEqual(kwargs.get("command"), app._on_start)
        self.assertIn("开始演奏", kwargs.get("text", ""))

    def test_primary_button_e_exports(self) -> None:
        app = App.__new__(App)
        app.cfg = AppConfig()
        app.cfg.mode = "E"
        app.primary_btn = MagicMock()
        app.export_md_row = MagicMock()
        app._update_primary_button()
        kwargs = app.primary_btn.configure.call_args.kwargs
        self.assertEqual(kwargs.get("command"), app._on_export_macro_md)


if __name__ == "__main__":
    unittest.main()
