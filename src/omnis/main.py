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
        default=Path("omnis.yaml"),
        help="Path to configuration file (default: omnis.yaml)",
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

    return parser.parse_args()


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

    # Load configuration
    try:
        engine = Engine.from_config_file(args.config)
    except ConfigurationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    branding = engine.get_branding()

    # Create Qt application
    app = create_application(branding)

    # Set up QML engine
    qml_engine = QQmlApplicationEngine()

    # Create bridge between QML and Python engine
    bridge = EngineBridge(engine, debug=args.debug, dry_run=args.dry_run)

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
