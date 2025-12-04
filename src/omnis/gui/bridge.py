"""
Bridge between QML UI and Python Engine.

Exposes engine functionality to QML via Qt properties and signals.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Property, QObject, QThread, QUrl, Signal, Slot

from omnis.i18n.translator import get_translator
from omnis.jobs.requirements import SystemRequirementsChecker

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
        """Welcome screen title with i18n interpolation."""
        translator = get_translator()
        return translator.get(
            "title",
            "welcome",
            default=self._branding.strings.welcome_title,
            distro_name=self._branding.name,
        )

    @Property(str, constant=True)
    def welcomeSubtitle(self) -> str:
        """Welcome screen subtitle with i18n interpolation."""
        translator = get_translator()
        # Get tagline from branding config
        tagline = getattr(self._branding, "tagline", "")
        return translator.get(
            "subtitle",
            "welcome",
            default=self._branding.strings.welcome_subtitle,
            distro_tagline=tagline,
        )

    @Property(str, constant=True)
    def installButton(self) -> str:
        """Install button text with i18n interpolation."""
        translator = get_translator()
        return translator.get(
            "install_button",
            "welcome",
            default=self._branding.strings.install_button,
            distro_name=self._branding.name,
        )

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

    # Links
    @Property(str, constant=True)
    def websiteUrl(self) -> str:
        """Main website URL."""
        return self._branding.links.website

    @Property(str, constant=True)
    def websiteLabel(self) -> str:
        """Display label for website link (falls back to URL if empty)."""
        label = self._branding.links.website_label
        if not label and self._branding.links.website:
            # Extract domain from URL as fallback
            url = self._branding.links.website
            # Remove protocol and www prefix for cleaner display
            for prefix in ("https://", "http://", "www."):
                if url.startswith(prefix):
                    url = url[len(prefix) :]
            # Remove trailing slash
            label = url.rstrip("/")
        return label

    @Property(str, constant=True)
    def gitUrl(self) -> str:
        """Git repository URL."""
        return self._branding.links.git

    @Property(str, constant=True)
    def documentationUrl(self) -> str:
        """Documentation URL."""
        return self._branding.links.documentation

    @Property(str, constant=True)
    def supportUrl(self) -> str:
        """Support/forum URL."""
        return self._branding.links.support


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
    requirementsChanged = Signal()  # emitted when requirements check completes

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
        self._theme_base = theme_base

        # Thread management
        self._worker: InstallationWorker | None = None
        self._thread: QThread | None = None

        # Requirements state
        self._requirements_checker: SystemRequirementsChecker | None = None
        self._requirements_model: list[dict[str, Any]] = []
        self._can_proceed: bool = True
        self._is_checking_requirements: bool = False
        self._show_requirements: bool = True

        # Connect engine callbacks
        self._engine.on_job_start = self._on_job_start
        self._engine.on_job_progress = self._on_job_progress
        self._engine.on_job_complete = self._on_job_complete
        self._engine.on_error = self._on_error

        # Initialize requirements checker with config
        self._init_requirements_checker()

    @property
    def branding_proxy(self) -> BrandingProxy:
        """Get branding proxy for QML context."""
        return self._branding_proxy

    def _init_requirements_checker(self) -> None:
        """Initialize the requirements checker with config from engine."""
        # Get requirements config from welcome job config if available
        welcome_config = {}
        for job_def in self._engine.config.normalize_jobs():
            if job_def.name == "welcome":
                welcome_config = job_def.config.get("requirements", {})
                break

        self._requirements_checker = SystemRequirementsChecker(welcome_config)

        if self._debug:
            print(f"[Engine] Requirements checker initialized with config: {welcome_config}")

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

    # Requirements properties
    @Property(bool, notify=requirementsChanged)
    def showRequirements(self) -> bool:
        """Whether to show requirements panel."""
        return self._show_requirements

    @Property(list, notify=requirementsChanged)
    def requirementsModel(self) -> list[dict[str, Any]]:
        """Get requirements list for QML ListView."""
        return self._requirements_model

    @Property(bool, notify=requirementsChanged)
    def canProceed(self) -> bool:
        """Whether installation can proceed based on requirements."""
        return self._can_proceed

    @Property(bool, notify=requirementsChanged)
    def isCheckingRequirements(self) -> bool:
        """Whether requirements are currently being checked."""
        return self._is_checking_requirements

    @Slot()
    def checkRequirements(self) -> None:
        """Perform requirements check and update model."""
        if self._requirements_checker is None:
            self._init_requirements_checker()

        # Safety check for mypy (should never be None after init)
        if self._requirements_checker is None:
            return

        self._is_checking_requirements = True
        self.requirementsChanged.emit()

        if self._debug:
            print("[Engine] Starting requirements check...")

        # Perform the check
        result = self._requirements_checker.check_all()

        # Convert to QML-compatible list
        self._requirements_model = []
        for check in result.checks:
            self._requirements_model.append(
                {
                    "name": check.name,
                    "description": check.description,
                    "status": check.status.name.lower(),
                    "currentValue": check.current_value,
                    "requiredValue": check.required_value,
                    "recommendedValue": check.recommended_value,
                    "details": check.details,
                }
            )

        # Update state
        self._can_proceed = result.can_continue
        self._is_checking_requirements = False

        # Hide panel if no checks are configured/enabled
        self._show_requirements = len(result.checks) > 0

        if self._debug:
            print(f"[Engine] Requirements check complete: {len(result.checks)} checks")
            print(f"[Engine] Can proceed: {self._can_proceed}")
            print(f"[Engine] Show requirements panel: {self._show_requirements}")
            for item in self._requirements_model:
                print(f"[Engine]   - {item['name']}: {item['status']}")

        self.requirementsChanged.emit()

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
