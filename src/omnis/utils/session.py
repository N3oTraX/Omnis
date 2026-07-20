"""Desktop-session resolution for the privileged installer process.

The installer runs as root (sudo). Anything that has to talk to the *session*
D-Bus bus — ``gsettings``, GNOME Control Center, the NetworkManager secret
agent that asks for a Wi-Fi passphrase — is unreachable from root: the system
bus is visible, the session bus is not. Such commands must therefore be
dropped back into the desktop user's session before being executed.
"""

from __future__ import annotations

import logging
import os
import pwd
import shutil

logger = logging.getLogger(__name__)

_RUN_USER = "/run/user"

# Forwarded so GUI helpers spawned in the user session still find a display.
_DISPLAY_VARS = ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY")


def session_bus_path(uid: int) -> str:
    """Return the conventional session bus socket path for ``uid``."""
    return f"{_RUN_USER}/{uid}/bus"


def _explicit_uid_candidates() -> list[int]:
    """Session uids advertised by the environment, most trustworthy first."""
    candidates: list[int] = []
    sudo_uid = os.environ.get("SUDO_UID", "")
    if sudo_uid.isdigit() and int(sudo_uid) != 0:
        candidates.append(int(sudo_uid))
    runtime = os.environ.get("XDG_RUNTIME_DIR", "")
    if runtime.startswith(f"{_RUN_USER}/"):
        tail = runtime.rsplit("/", 1)[1]
        if tail.isdigit() and int(tail) != 0 and int(tail) not in candidates:
            candidates.append(int(tail))
    return candidates


def _discover_uid_with_bus() -> int | None:
    """Find a uid owning a live session bus socket under ``/run/user``."""
    try:
        entries = os.listdir(_RUN_USER)
    except OSError:
        return None
    uids = sorted(
        uid
        for uid in (int(e) for e in entries if e.isdigit())
        if uid != 0 and os.path.exists(session_bus_path(uid))
    )
    if not uids:
        return None
    if len(uids) > 1:
        logger.warning(f"Several session buses found under {_RUN_USER} ({uids}), using {uids[0]}")
    return uids[0]


def resolve_session_uid() -> int | None:
    """Resolve the uid owning the graphical session, or None if unknown.

    Environment hints win; otherwise the live bus sockets are probed. There is
    deliberately no fallback to a hardcoded uid: guessing wrong sends commands
    into a session that does not exist and fails silently.
    """
    candidates = _explicit_uid_candidates()
    if candidates:
        return candidates[0]
    uid = _discover_uid_with_bus()
    if uid is None:
        logger.warning(
            f"No desktop session identifiable: SUDO_UID and XDG_RUNTIME_DIR are unset "
            f"and no session bus socket was found under {_RUN_USER}"
        )
    return uid


def session_environment(uid: int) -> dict[str, str]:
    """Build the environment needed to reach the session bus of ``uid``."""
    inherited_bus = os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")
    env = {
        "XDG_RUNTIME_DIR": f"{_RUN_USER}/{uid}",
        # Under `sudo -E` the real address is already inherited and may not be
        # the conventional socket path; overwriting it would break the session.
        "DBUS_SESSION_BUS_ADDRESS": inherited_bus or f"unix:path={session_bus_path(uid)}",
    }
    for var in _DISPLAY_VARS:
        value = os.environ.get(var, "")
        if value:
            env[var] = value
    return env


def resolve_session_user() -> tuple[str, dict[str, str]] | None:
    """Return the desktop user name and its session environment, or None."""
    uid = resolve_session_uid()
    if uid is None:
        return None
    try:
        user = pwd.getpwuid(uid).pw_name
    except KeyError:
        logger.warning(f"No passwd entry for session uid {uid}")
        return None
    return user, session_environment(uid)


def wrap_in_user_session(cmd: list[str]) -> list[str] | None:
    """Wrap ``cmd`` so it runs inside the desktop user's session.

    Args:
        cmd: Command and arguments to execute.

    Returns:
        ``cmd`` unchanged when already running unprivileged, the wrapped
        command when the session could be reached, or None when it could not
        (the caller must then treat the operation as unavailable).
    """
    if os.geteuid() != 0:
        return cmd
    context = resolve_session_user()
    if context is None:
        return None
    user, env = context
    if not shutil.which("runuser"):
        logger.warning("runuser is unavailable: cannot enter the user session")
        return None
    env_args = [f"{k}={v}" for k, v in env.items()]
    return ["runuser", "-u", user, "--", "env", *env_args, *cmd]
