"""Live keyboard layout application for the running installer session.

The installer's target-system keyboard config is written by the ``locale``
job (see ``omnis.jobs.locale``) and is unaffected by this module. This module
only handles the best-effort, cosmetic affordance of switching the *live*
session's keyboard layout so the on-screen keyboard test field (and every
other input in the installer) immediately reflects the user's choice.

On GNOME Wayland — the live session used by GLF OS — ``setxkbmap`` has no
effect because layout switching is owned by the compositor via
``org.gnome.desktop.input-sources``. This module therefore prefers
``gsettings`` and falls back to ``setxkbmap`` for X11 sessions or when
``gsettings`` is unavailable.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess

logger = logging.getLogger(__name__)

_COMMAND_TIMEOUT = 5  # seconds


def build_xkb_layout_string(layout: str, variant: str) -> str:
    """Build the XKB ``layout[+variant]`` string, e.g. ``fr`` or ``fr+azerty``."""
    if variant:
        return f"{layout}+{variant}"
    return layout


def apply_keyboard_layout_live(layout: str, variant: str = "") -> bool:
    """
    Apply a keyboard layout to the running desktop session (best-effort).

    Args:
        layout: XKB layout code (e.g. "fr", "us").
        variant: XKB variant code (e.g. "azerty"), or "" for the default.

    Returns:
        True if a live-apply command was executed successfully, False
        otherwise. Never raises: this is a cosmetic UX affordance and must
        not break the installer if the session tooling is unavailable.
    """
    if not layout:
        return False

    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()

    if session_type != "x11" and shutil.which("gsettings"):
        return _apply_via_gsettings(build_xkb_layout_string(layout, variant))

    if shutil.which("setxkbmap"):
        return _apply_via_setxkbmap(layout, variant)

    # Wayland without setxkbmap: gsettings is still worth a try even if the
    # session-type check above missed it (e.g. unset XDG_SESSION_TYPE).
    if shutil.which("gsettings"):
        return _apply_via_gsettings(build_xkb_layout_string(layout, variant))

    logger.warning("No supported keyboard layout tool found (gsettings/setxkbmap)")
    return False


def _apply_via_gsettings(xkb_layout: str) -> bool:
    """Apply the layout via GNOME's input-sources (GNOME Wayland/X11)."""
    sources_value = f"[('xkb', '{xkb_layout}')]"
    try:
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.input-sources", "sources", sources_value],
            check=True,
            timeout=_COMMAND_TIMEOUT,
        )
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.input-sources", "current", "0"],
            check=True,
            timeout=_COMMAND_TIMEOUT,
        )
        logger.info(f"Applied live keyboard layout via gsettings: {xkb_layout}")
        return True
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning(f"Failed to apply keyboard layout via gsettings: {exc}")
        return False


def _apply_via_setxkbmap(layout: str, variant: str) -> bool:
    """Apply the layout via setxkbmap (X11 sessions)."""
    cmd = ["setxkbmap", layout]
    if variant:
        cmd += ["-variant", variant]
    try:
        subprocess.run(cmd, check=True, timeout=_COMMAND_TIMEOUT)
        logger.info(f"Applied live keyboard layout via setxkbmap: {layout} {variant}")
        return True
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning(f"Failed to apply keyboard layout via setxkbmap: {exc}")
        return False
