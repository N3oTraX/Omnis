"""Tests for the root self-elevation guard in the Omnis entry point.

On the live ISO, closing then relaunching Omnis (CLI or menu icon) must run it
with the same privileges as the autostart. ``_reexec_as_root_if_needed`` re-execs
via passwordless ``sudo`` when possible, and stays a no-op everywhere else.
"""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

pytest.importorskip("omnis")

from omnis.main import _reexec_as_root_if_needed  # noqa: E402


def test_noop_when_already_root() -> None:
    with (
        patch("omnis.main.os.geteuid", return_value=0),
        patch("omnis.main.os.execvp") as execvp,
    ):
        _reexec_as_root_if_needed()
    execvp.assert_not_called()


def test_noop_when_disabled_by_env() -> None:
    with (
        patch.dict("omnis.main.os.environ", {"OMNIS_NO_REEXEC": "1"}),
        patch("omnis.main.os.geteuid", return_value=1000),
        patch("omnis.main.os.execvp") as execvp,
    ):
        _reexec_as_root_if_needed()
    execvp.assert_not_called()


def test_noop_when_sudo_absent() -> None:
    with (
        patch.dict("omnis.main.os.environ", {}, clear=True),
        patch("omnis.main.os.geteuid", return_value=1000),
        patch("omnis.main.shutil.which", return_value=None),
        patch("omnis.main.os.execvp") as execvp,
    ):
        _reexec_as_root_if_needed()
    execvp.assert_not_called()


def test_noop_when_sudo_needs_password() -> None:
    with (
        patch.dict("omnis.main.os.environ", {}, clear=True),
        patch("omnis.main.os.geteuid", return_value=1000),
        patch("omnis.main.shutil.which", return_value="/usr/bin/sudo"),
        patch(
            "omnis.main.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "sudo"),
        ),
        patch("omnis.main.os.execvp") as execvp,
    ):
        _reexec_as_root_if_needed()
    execvp.assert_not_called()


def test_reexecs_via_sudo_when_passwordless() -> None:
    with (
        patch.dict("omnis.main.os.environ", {}, clear=True),
        patch("omnis.main.os.geteuid", return_value=1000),
        patch("omnis.main.shutil.which", return_value="/run/wrappers/bin/sudo"),
        patch("omnis.main.subprocess.run") as run,
        patch("omnis.main.os.execvp") as execvp,
    ):
        run.return_value = None  # `sudo -n true` succeeds (no exception)
        _reexec_as_root_if_needed()

    execvp.assert_called_once()
    prog, argv = execvp.call_args[0]
    assert prog == "sudo"
    assert argv[0] == "sudo"
    assert argv[1] == "-n"
    assert any(a.startswith("--preserve-env=") for a in argv)
