"""
Bridge between QML UI and Python Engine.

Exposes engine functionality to QML via Qt properties and signals.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Property, QObject, QThread, QUrl, Signal, Slot

if TYPE_CHECKING:
    from omnis.core.engine import Engine


class InstallationWorker(QObject):
    """Worker that runs installation in a separate thread."""

    finished = Signal(bool)  # success: bool
    error = Signal(str)  # error_message

    def __init__(self, engine: Engine, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._engine = engine

    def run(self) -> None:
        """Execute the installation process."""
        try:
            success = self._engine.run_all()
            self.finished.emit(success)
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False)


class BrandingProxy(QObject):
    """Exposes branding configuration to QML."""

    def __init__(
        self, engine: Engine, theme_base: Path, parent: QObject | None = None, debug: bool = False
    ) -> None:
        super().__init__(parent)
        self._branding = engine.get_branding()
        self._theme_base = theme_base
        self._debug = debug

        if self._debug:
            print(f"[Branding] Loaded: {self._branding.name}")
            print(f"[Branding] Theme base: {self._theme_base}")
            print(
                f"[Branding] Colors - primary: {self._branding.colors.primary}, "
                f"bg: {self._branding.colors.background}, text: {self._branding.colors.text}"
            )

    def _resolve_asset(self, relative_path: str) -> str:
        """Resolve asset path to absolute file:// URL."""
        if not relative_path:
            if self._debug:
                print("[Branding] Asset path is empty")
            return ""
        full_path = self._theme_base / relative_path
        if full_path.exists():
            url = QUrl.fromLocalFile(str(full_path.resolve())).toString()
            if self._debug:
                print(f"[Branding] Resolved: {relative_path} -> {url}")
            return url
        if self._debug:
            print(f"[Branding] Asset not found: {full_path}")
        return ""

    @Property(str, constant=True)
    def name(self) -> str:
        """Distribution name."""
        return self._branding.name

    @Property(str, constant=True)
    def version(self) -> str:
        """Distribution version."""
        return self._branding.version

    @Property(str, constant=True)
    def edition(self) -> str:
        """Distribution edition."""
        return self._branding.edition

    @Property(str, constant=True)
    def primaryColor(self) -> str:
        """Primary brand color."""
        return self._branding.colors.primary

    @Property(str, constant=True)
    def secondaryColor(self) -> str:
        """Secondary brand color."""
        return self._branding.colors.secondary

    @Property(str, constant=True)
    def accentColor(self) -> str:
        """Accent color."""
        return self._branding.colors.accent

    @Property(str, constant=True)
    def backgroundColor(self) -> str:
        """Background color."""
        return self._branding.colors.background

    @Property(str, constant=True)
    def surfaceColor(self) -> str:
        """Surface color."""
        return self._branding.colors.surface

    @Property(str, constant=True)
    def textColor(self) -> str:
        """Primary text color."""
        return self._branding.colors.text

    @Property(str, constant=True)
    def textMutedColor(self) -> str:
        """Muted text color."""
        return self._branding.colors.text_muted

    @Property(str, constant=True)
    def welcomeTitle(self) -> str:
        """Welcome screen title."""
        return self._branding.strings.welcome_title

    @Property(str, constant=True)
    def welcomeSubtitle(self) -> str:
        """Welcome screen subtitle."""
        return self._branding.strings.welcome_subtitle

    @Property(str, constant=True)
    def installButton(self) -> str:
        """Install button text."""
        return self._branding.strings.install_button

    @Property(str, constant=True)
    def logoPath(self) -> str:
        """Path to logo asset."""
        return self._branding.assets.logo

    # Asset URLs (resolved to absolute file:// URLs)
    @Property(str, constant=True)
    def logoUrl(self) -> str:
        """URL to main logo."""
        return self._resolve_asset(self._branding.assets.logo)

    @Property(str, constant=True)
    def logoLightUrl(self) -> str:
        """URL to light variant logo."""
        return self._resolve_asset(self._branding.assets.logo_light)

    @Property(str, constant=True)
    def logoSmallUrl(self) -> str:
        """URL to small logo (64px)."""
        return self._resolve_asset(self._branding.assets.logo_small)

    @Property(str, constant=True)
    def backgroundUrl(self) -> str:
        """URL to background wallpaper."""
        return self._resolve_asset(self._branding.assets.background)

    @Property(str, constant=True)
    def iconUrl(self) -> str:
        """URL to icon."""
        return self._resolve_asset(self._branding.assets.icon)


class EngineBridge(QObject):
    """
    Main bridge between QML and installation engine.

    Exposes:
    - Installation control (start, pause, cancel)
    - Progress reporting
    - Job navigation
    - Branding configuration
    """

    # Signals for QML
    installationStarted = Signal()
    installationFinished = Signal(bool)  # success: bool
    jobStarted = Signal(str)  # job_name
    jobProgress = Signal(str, int, str)  # job_name, percent, message
    jobCompleted = Signal(str, bool)  # job_name, success
    errorOccurred = Signal(str, str)  # job_name, error_message

    def __init__(
        self,
        engine: Engine,
        theme_base: Path,
        debug: bool = False,
        dry_run: bool = False,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._debug = debug
        self._dry_run = dry_run
        self._branding_proxy = BrandingProxy(engine, theme_base, self, debug=debug)

        # Thread management
        self._worker: InstallationWorker | None = None
        self._thread: QThread | None = None

        # Connect engine callbacks
        self._engine.on_job_start = self._on_job_start
        self._engine.on_job_progress = self._on_job_progress
        self._engine.on_job_complete = self._on_job_complete
        self._engine.on_error = self._on_error

    @property
    def branding_proxy(self) -> BrandingProxy:
        """Get branding proxy for QML context."""
        return self._branding_proxy

    def _on_job_start(self, job_name: str) -> None:
        """Handle job start event."""
        self.jobStarted.emit(job_name)

    def _on_job_progress(self, job_name: str, percent: int, message: str) -> None:
        """Handle job progress event."""
        self.jobProgress.emit(job_name, percent, message)

    def _on_job_complete(self, job_name: str, result: Any) -> None:
        """Handle job completion event."""
        self.jobCompleted.emit(job_name, result.success)

    def _on_error(self, job_name: str, error: str) -> None:
        """Handle error event."""
        self.errorOccurred.emit(job_name, error)

    @Property(bool, constant=True)
    def debugMode(self) -> bool:
        """Check if debug mode is enabled."""
        return self._debug

    @Property(bool, constant=True)
    def dryRun(self) -> bool:
        """Check if dry-run mode is enabled."""
        return self._dry_run

    @Property(list, constant=True)
    def jobNames(self) -> list[str]:
        """Get list of job names in order."""
        return self._engine.get_job_names()

    @Property(int, constant=True)
    def totalJobs(self) -> int:
        """Get total number of jobs."""
        return len(self._engine.jobs)

    @Slot()
    def startInstallation(self) -> None:
        """Start the installation process in a separate thread."""
        # Prevent multiple concurrent installations
        if self._thread is not None and self._thread.isRunning():
            if self._debug:
                print("[Engine] Installation already in progress")
            return

        self.installationStarted.emit()

        # Create worker and thread
        self._thread = QThread(self)
        self._worker = InstallationWorker(self._engine)
        self._worker.moveToThread(self._thread)

        # Connect signals
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_installation_finished)
        self._worker.error.connect(self._on_installation_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._cleanup_thread)

        # Start installation
        if self._debug:
            print("[Engine] Starting installation in background thread")
        self._thread.start()

    def _on_installation_finished(self, success: bool) -> None:
        """Handle installation completion."""
        if self._debug:
            print(f"[Engine] Installation finished: {'success' if success else 'failed'}")
        self.installationFinished.emit(success)

    def _on_installation_error(self, error_message: str) -> None:
        """Handle installation error."""
        if self._debug:
            print(f"[Engine] Installation error: {error_message}")
        self.errorOccurred.emit("installation", error_message)

    def _cleanup_thread(self) -> None:
        """Clean up thread references after completion."""
        self._thread = None
        self._worker = None

    @Slot(result=int)
    def getCurrentJobIndex(self) -> int:
        """Get current job index (0-based)."""
        current, _ = self._engine.get_progress()
        return current - 1

    @Slot(result=str)
    def getCurrentJobName(self) -> str:
        """Get current job name."""
        idx = self.getCurrentJobIndex()
        if 0 <= idx < len(self._engine.jobs):
            return self._engine.jobs[idx].name
        return ""

    @Slot(result=bool)
    def isRunning(self) -> bool:
        """Check if installation is running."""
        return self._engine.state.is_running

    @Slot(result=bool)
    def isFinished(self) -> bool:
        """Check if installation is finished."""
        return self._engine.state.is_finished

    @Slot(result=str)
    def getLastError(self) -> str:
        """Get last error message."""
        return self._engine.state.last_error or ""
