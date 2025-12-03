"""
Omnis Installer - Entry point.

This module handles:
- Argument parsing
- Process separation (UI vs Engine)
- Application initialization
- IPC between UI (unprivileged) and Engine (root)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from omnis import __version__
from omnis.core.engine import ConfigurationError

if TYPE_CHECKING:
    from PySide6.QtGui import QGuiApplication

    from omnis.core.engine import BrandingConfig

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="omnis",
        description="Omnis Installer - Modern Linux installation system",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"Omnis Installer {__version__}",
    )

    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=None,
        help="Path to configuration file (default: auto-detect)",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate installation without making changes",
    )

    parser.add_argument(
        "--platform-info",
        action="store_true",
        help="Display Qt platform information and exit",
    )

    # IPC-related arguments
    parser.add_argument(
        "--engine",
        action="store_true",
        help="Run as engine server (requires root privileges)",
    )

    parser.add_argument(
        "--socket",
        type=Path,
        default=None,
        help="Path to IPC socket (default: /run/omnis/ipc.sock)",
    )

    parser.add_argument(
        "--no-fork",
        action="store_true",
        help="Run without forking engine process (for development/testing)",
    )

    return parser.parse_args()


def print_platform_info() -> None:
    """Display Qt platform and environment information."""
    import os

    from PySide6.QtCore import QLibraryInfo, qVersion
    from PySide6.QtGui import QGuiApplication

    # Initialize minimal app to get platform info
    app = QGuiApplication([])

    print("=" * 60)
    print("Omnis Installer - Platform Information")
    print("=" * 60)

    # Qt version
    print("\n[Qt]")
    print(f"  Version: {qVersion()}")
    print(f"  Plugins path: {QLibraryInfo.path(QLibraryInfo.PluginsPath)}")  # type: ignore[attr-defined]

    # Platform
    print("\n[Platform]")
    print(f"  Plugin: {app.platformName()}")
    print(f"  DISPLAY: {os.environ.get('DISPLAY', 'not set')}")
    print(f"  WAYLAND_DISPLAY: {os.environ.get('WAYLAND_DISPLAY', 'not set')}")
    print(f"  XDG_SESSION_TYPE: {os.environ.get('XDG_SESSION_TYPE', 'not set')}")
    print(f"  XDG_CURRENT_DESKTOP: {os.environ.get('XDG_CURRENT_DESKTOP', 'not set')}")

    # Theme
    print("\n[Theme]")
    print(f"  QT_QPA_PLATFORMTHEME: {os.environ.get('QT_QPA_PLATFORMTHEME', 'not set')}")
    print(f"  QT_STYLE_OVERRIDE: {os.environ.get('QT_STYLE_OVERRIDE', 'not set')}")

    # Screens
    print("\n[Screens]")
    for i, screen in enumerate(app.screens()):
        print(f"  Screen {i}: {screen.name()}")
        print(f"    Size: {screen.size().width()}x{screen.size().height()}")
        print(f"    DPI: {screen.logicalDotsPerInch():.0f}")
        print(f"    Scale: {screen.devicePixelRatio()}")

    # Available platform plugins
    plugins_path = Path(QLibraryInfo.path(QLibraryInfo.PluginsPath)) / "platforms"  # type: ignore[attr-defined]
    if plugins_path.exists():
        print("\n[Available Platform Plugins]")
        for plugin in sorted(plugins_path.glob("libq*.so")):
            name = plugin.stem.replace("libq", "")
            print(f"  - {name}")

    print("\n" + "=" * 60)
    app.quit()


def find_config_file(explicit_path: Path | None = None) -> Path:
    """
    Locate configuration file.

    Search order:
    1. Explicit path from --config
    2. omnis.yaml in current directory
    3. config/examples/glfos.yaml (development fallback)
    """
    if explicit_path is not None:
        if explicit_path.exists():
            return explicit_path
        raise ConfigurationError(
            f"Configuration file not found: {explicit_path}\n"
            f"Create one with: cp omnis.yaml.example omnis.yaml"
        )

    # Search locations
    candidates = [
        Path("omnis.yaml"),
        Path("config/examples/glfos.yaml"),
        Path("/etc/omnis/omnis.yaml"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise ConfigurationError(
        "No configuration file found.\n"
        "Create one with: cp omnis.yaml.example omnis.yaml\n"
        "Or specify: omnis --config config/examples/glfos.yaml"
    )


def find_qml_file() -> Path:
    """Locate the main QML file."""
    # Check multiple possible locations
    candidates = [
        Path(__file__).parent / "gui" / "qml" / "Main.qml",
        Path("src/omnis/gui/qml/Main.qml"),
        Path("/usr/share/omnis/qml/Main.qml"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError("Main.qml not found. Check installation.")


def create_application(branding: BrandingConfig) -> QGuiApplication:
    """Create and configure Qt application."""
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication(sys.argv)

    # Set application metadata from branding
    app.setApplicationName(branding.name)
    app.setApplicationVersion(branding.version)
    app.setOrganizationName("Omnis")

    return app


def run_ui_mode(
    config_path: Path,
    socket_path: Path | None,
    debug: bool,
    dry_run: bool,
    no_fork: bool,
) -> int:
    """
    Run the UI process.

    In normal mode, this forks the engine process first.
    In --no-fork mode, runs standalone without IPC.

    Args:
        config_path: Path to configuration file
        socket_path: Path to IPC socket
        debug: Enable debug mode
        dry_run: Enable dry-run mode
        no_fork: Skip forking engine process

    Returns:
        Exit code
    """
    # Import Qt modules here to avoid loading in engine mode
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine

    from omnis.core.engine import Engine
    from omnis.gui.bridge import EngineBridge
    from omnis.launcher import DEFAULT_SOCKET_PATH, EngineProcess

    # Load configuration for branding info
    engine = Engine.from_config_file(config_path)
    branding = engine.get_branding()

    # Resolve theme path
    theme_path = engine.get_theme_path()
    theme_base = (config_path.parent / theme_path).resolve() if theme_path else config_path.parent

    if debug:
        print(f"Theme base: {theme_base}")

    # Fork engine process if not in no-fork mode
    engine_process: EngineProcess | None = None
    effective_socket = socket_path or DEFAULT_SOCKET_PATH

    if not no_fork:
        logger.info("Starting engine process with elevated privileges")
        engine_process = EngineProcess(
            config_path=config_path,
            socket_path=effective_socket,
            debug=debug,
            dry_run=dry_run,
        )

        try:
            engine_process.start()
            engine_process.wait_for_ready()
            logger.info("Engine process ready")
        except Exception as e:
            print(f"Error starting engine: {e}", file=sys.stderr)
            if engine_process:
                engine_process.stop()
            return 1

    try:
        # Create Qt application
        app = create_application(branding)

        # Set up QML engine
        qml_engine = QQmlApplicationEngine()

        # Create bridge between QML and Python engine
        # In fork mode, bridge uses IPC; in no-fork mode, uses direct engine
        if no_fork:
            bridge = EngineBridge(engine, theme_base, debug=debug, dry_run=dry_run)
        else:
            # TODO: Create IPC-based bridge for v0.2.0
            # For now, fall back to direct bridge
            bridge = EngineBridge(engine, theme_base, debug=debug, dry_run=dry_run)

        # Expose bridge to QML
        qml_engine.rootContext().setContextProperty("engine", bridge)
        qml_engine.rootContext().setContextProperty("branding", bridge.branding_proxy)

        # Load QML
        try:
            qml_file = find_qml_file()
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        qml_engine.load(QUrl.fromLocalFile(str(qml_file)))

        if not qml_engine.rootObjects():
            print("Error: Failed to load QML interface", file=sys.stderr)
            return 1

        # Run application
        return app.exec()

    finally:
        # Clean up engine process
        if engine_process:
            logger.info("Stopping engine process")
            engine_process.stop()


def main() -> int:
    """
    Application entry point.

    Handles three modes:
    1. --engine: Run as engine server (root context)
    2. Normal: Fork engine, run UI (user context)
    3. --no-fork: Run standalone without IPC (development)

    Returns:
        Exit code (0 = success)
    """
    args = parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s]: %(message)s",
    )

    # Handle --platform-info
    if args.platform_info:
        print_platform_info()
        return 0

    # Find configuration file
    try:
        config_path = find_config_file(args.config)
        if args.debug:
            print(f"Using config: {config_path}")
    except ConfigurationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Engine mode: run as IPC server
    if args.engine:
        from omnis.launcher import DEFAULT_SOCKET_PATH, run_engine_server

        socket_path = args.socket or DEFAULT_SOCKET_PATH
        return run_engine_server(
            config_path=config_path,
            socket_path=socket_path,
            debug=args.debug,
            dry_run=args.dry_run,
        )

    # UI mode: run graphical interface
    return run_ui_mode(
        config_path=config_path,
        socket_path=args.socket,
        debug=args.debug,
        dry_run=args.dry_run,
        no_fork=args.no_fork,
    )


if __name__ == "__main__":
    sys.exit(main())
