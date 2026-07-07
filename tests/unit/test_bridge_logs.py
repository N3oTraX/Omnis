"""
Unit tests for the EngineBridge logs/diagnostics surface.

Covers:
- ``installationLog`` / ``logChanged`` / ``logMessageAppended`` reflecting
  what is captured by the ``BridgeLogHandler`` installed on the ``omnis`` and
  root loggers.
- Secrets registered via ``setPassword`` / ``setRootPassword`` /
  ``setEncryptionPassphrase`` are never observable in ``installationLog``,
  even when logged verbatim by application code after being set.
- ``uploadInstallLog`` emits ``logUploadFinished(url, ok, error_message)`` on
  both success and failure, driven through a real (offscreen) QThread with
  ``upload_log`` monkeypatched so no network call is made.

Runs offscreen; no real network access is performed.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from omnis.core.engine import Engine  # noqa: E402
from omnis.gui.bridge import EngineBridge  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MINIMAL_CONFIG = PROJECT_ROOT / "config" / "examples" / "minimal.yaml"


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app  # type: ignore[return-value]


@pytest.fixture
def bridge(qapp: QApplication) -> Iterator[EngineBridge]:
    assert qapp is not None
    engine = Engine.from_config_file(MINIMAL_CONFIG)
    theme_base = MINIMAL_CONFIG.parent
    obj = EngineBridge(engine, theme_base, debug=False, dry_run=True, skip_requirements=True)
    yield obj
    # Detach the handler installed on shared loggers so subsequent tests /
    # bridge instances in the same process don't accumulate handlers.
    logging.getLogger("omnis").removeHandler(obj._log_handler)
    logging.getLogger().removeHandler(obj._log_handler)


class TestInstallationLogProperty:
    """installationLog / logChanged / logMessageAppended reflect captured logs."""

    def test_logged_message_appears_in_installation_log(self, bridge: EngineBridge) -> None:
        logger = logging.getLogger("omnis.test_bridge_logs")
        logger.info("hello from a job")

        assert "hello from a job" in bridge.installationLog

    def test_log_message_appended_signal_fires(self, bridge: EngineBridge) -> None:
        seen: list[str] = []
        bridge.logMessageAppended.connect(seen.append)

        logger = logging.getLogger("omnis.test_bridge_logs")
        logger.info("a distinct live line")

        assert any("a distinct live line" in line for line in seen)

    def test_log_changed_signal_fires(self, bridge: EngineBridge) -> None:
        changed = []
        bridge.logChanged.connect(lambda: changed.append(True))

        logger = logging.getLogger("omnis.test_bridge_logs")
        logger.info("triggers logChanged")

        assert changed


class TestSecretsNeverLeakIntoLog:
    """Anti-regression: password/passphrase values must never reach the log."""

    def test_password_never_appears_in_installation_log(self, bridge: EngineBridge) -> None:
        secret = "CorrectHorseBatteryStaple"
        bridge.setPassword(secret)

        logger = logging.getLogger("omnis.test_bridge_logs")
        logger.info("user password set to %s during setup", secret)

        assert secret not in bridge.installationLog
        assert "***" in bridge.installationLog

    def test_root_password_never_appears_in_installation_log(self, bridge: EngineBridge) -> None:
        secret = "R00tSecretValue"
        bridge.setRootPassword(secret)

        logger = logging.getLogger("omnis.test_bridge_logs")
        logger.info("root password: %s", secret)

        assert secret not in bridge.installationLog

    def test_encryption_passphrase_never_appears_in_installation_log(
        self, bridge: EngineBridge
    ) -> None:
        secret = "LuksPassphrase!2024"
        bridge.setEncryptionPassphrase(secret)

        logger = logging.getLogger("omnis.test_bridge_logs")
        logger.info("encryption passphrase in use: %s", secret)

        assert secret not in bridge.installationLog

    def test_apply_selections_registers_secrets_before_any_later_log(
        self, bridge: EngineBridge
    ) -> None:
        # Defense-in-depth path: a secret that only reached _selections (not
        # via the dedicated setters) is still registered by
        # applySelectionsToContext, before jobs run and could log it.
        secret = "DefenseInDepthSecret"
        bridge._selections["password"] = secret
        bridge.applySelectionsToContext()

        logger = logging.getLogger("omnis.test_bridge_logs")
        logger.info("late log referencing %s", secret)

        assert secret not in bridge.installationLog


class TestUploadInstallLog:
    """uploadInstallLog runs the upload on a background QThread."""

    @staticmethod
    def _run_and_wait(bridge: EngineBridge, timeout_ms: int = 5000) -> list[tuple[str, bool, str]]:
        results: list[tuple[str, bool, str]] = []
        loop = QEventLoop()

        def _on_finished(url: str, ok: bool, error_message: str) -> None:
            results.append((url, ok, error_message))
            loop.quit()

        bridge.logUploadFinished.connect(_on_finished)

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)

        bridge.uploadInstallLog()
        timer.start(timeout_ms)
        loop.exec()

        return results

    def test_upload_success_emits_finished_with_url(
        self, bridge: EngineBridge, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "omnis.gui.bridge.upload_log",
            lambda *_args, **_kwargs: "https://0x0.st/abcd",
        )

        results = self._run_and_wait(bridge)

        assert results == [("https://0x0.st/abcd", True, "")]

    def test_upload_failure_emits_finished_with_error(
        self, bridge: EngineBridge, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _fail(*_args: object, **_kwargs: object) -> str:
            raise RuntimeError("Log upload failed on all providers: 0x0.st: x; termbin.com: y")

        monkeypatch.setattr("omnis.gui.bridge.upload_log", _fail)

        results = self._run_and_wait(bridge)

        assert len(results) == 1
        url, ok, error_message = results[0]
        assert url == ""
        assert ok is False
        assert "Log upload failed" in error_message
