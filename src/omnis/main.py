"""
Omnis Installer - Entry point.

This module handles:
- Argument parsing
- Process separation (UI vs Engine)
- Application initialization
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from omnis import __version__
from omnis.core.engine import Engine, ConfigurationError
from omnis.gui.bridge import EngineBridge

if TYPE_CHECKING:
    from omnis.core.engine import BrandingConfig


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
    print(f"\n[Qt]")
    print(f"  Version: {qVersion()}")
    print(f"  Plugins path: {QLibraryInfo.path(QLibraryInfo.PluginsPath)}")

    # Platform
    print(f"\n[Platform]")
    print(f"  Plugin: {app.platformName()}")
    print(f"  DISPLAY: {os.environ.get('DISPLAY', 'not set')}")
    print(f"  WAYLAND_DISPLAY: {os.environ.get('WAYLAND_DISPLAY', 'not set')}")
    print(f"  XDG_SESSION_TYPE: {os.environ.get('XDG_SESSION_TYPE', 'not set')}")
    print(f"  XDG_CURRENT_DESKTOP: {os.environ.get('XDG_CURRENT_DESKTOP', 'not set')}")

    # Theme
    print(f"\n[Theme]")
    print(f"  QT_QPA_PLATFORMTHEME: {os.environ.get('QT_QPA_PLATFORMTHEME', 'not set')}")
    print(f"  QT_STYLE_OVERRIDE: {os.environ.get('QT_STYLE_OVERRIDE', 'not set')}")

    # Screens
    print(f"\n[Screens]")
    for i, screen in enumerate(app.screens()):
        print(f"  Screen {i}: {screen.name()}")
        print(f"    Size: {screen.size().width()}x{screen.size().height()}")
        print(f"    DPI: {screen.logicalDotsPerInch():.0f}")
        print(f"    Scale: {screen.devicePixelRatio()}")

    # Available platform plugins
    plugins_path = Path(QLibraryInfo.path(QLibraryInfo.PluginsPath)) / "platforms"
    if plugins_path.exists():
        print(f"\n[Available Platform Plugins]")
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
    app = QGuiApplication(sys.argv)

    # Set application metadata from branding
    app.setApplicationName(branding.name)
    app.setApplicationVersion(branding.version)
    app.setOrganizationName("Omnis")

    return app


def main() -> int:
    """
    Application entry point.

    Returns:
        Exit code (0 = success)
    """
    args = parse_args()

    # Handle --platform-info
    if args.platform_info:
        print_platform_info()
        return 0

    # Find and load configuration
    try:
        config_path = find_config_file(args.config)
        if args.debug:
            print(f"Using config: {config_path}")
        engine = Engine.from_config_file(config_path)
    except ConfigurationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    branding = engine.get_branding()

    # Resolve theme path (relative to config file directory)
    theme_path = engine.get_theme_path()
    if theme_path:
        theme_base = (config_path.parent / theme_path).resolve()
    else:
        theme_base = config_path.parent

    if args.debug:
        print(f"Theme base: {theme_base}")

    # Create Qt application
    app = create_application(branding)

    # Set up QML engine
    qml_engine = QQmlApplicationEngine()

    # Create bridge between QML and Python engine
    bridge = EngineBridge(engine, theme_base, debug=args.debug, dry_run=args.dry_run)

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


if __name__ == "__main__":
    sys.exit(main())
