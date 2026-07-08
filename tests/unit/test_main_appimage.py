"""
AppImage-context detection and the forced integrated-engine (--no-fork)
behaviour. A bundled AppImage cannot fork a privileged engine via pkexec: the
re-executed store path is absent from the host namespace, so the engine dies.
Inside an AppImage the UI must therefore run integrated.
"""

from __future__ import annotations

from omnis import main


def test_running_in_appimage_detects_appimage_var(monkeypatch):
    monkeypatch.delenv("APPDIR", raising=False)
    monkeypatch.setenv("APPIMAGE", "/tmp/omnis.AppImage")
    assert main._running_in_appimage() is True


def test_running_in_appimage_detects_appdir_var(monkeypatch):
    monkeypatch.delenv("APPIMAGE", raising=False)
    monkeypatch.setenv("APPDIR", "/tmp/.mount_omnis")
    assert main._running_in_appimage() is True


def test_running_in_appimage_false_without_vars(monkeypatch):
    monkeypatch.delenv("APPIMAGE", raising=False)
    monkeypatch.delenv("APPDIR", raising=False)
    assert main._running_in_appimage() is False


def test_appimage_forces_no_fork(monkeypatch, tmp_path):
    cfg = tmp_path / "glfos.yaml"
    cfg.write_text("branding: {}\n")
    monkeypatch.setenv("APPIMAGE", "/tmp/omnis.AppImage")
    monkeypatch.setattr(main, "find_config_file", lambda *_a: cfg)
    monkeypatch.setattr(main.sys, "argv", ["omnis"])

    captured: dict = {}
    monkeypatch.setattr(main, "run_ui_mode", lambda **kw: (captured.update(kw), 0)[1])

    assert main.main() == 0
    assert captured["no_fork"] is True


def test_no_appimage_keeps_fork(monkeypatch, tmp_path):
    cfg = tmp_path / "glfos.yaml"
    cfg.write_text("branding: {}\n")
    monkeypatch.delenv("APPIMAGE", raising=False)
    monkeypatch.delenv("APPDIR", raising=False)
    monkeypatch.setattr(main, "find_config_file", lambda *_a: cfg)
    monkeypatch.setattr(main.sys, "argv", ["omnis"])

    captured: dict = {}
    monkeypatch.setattr(main, "run_ui_mode", lambda **kw: (captured.update(kw), 0)[1])

    assert main.main() == 0
    assert captured["no_fork"] is False
