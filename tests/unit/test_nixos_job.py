"""
Unit tests for :class:`omnis.jobs.nixos.NixosJob`.

CRITICAL: every privileged command (``nixos-generate-config``, ``cp``,
``nixos-install``) is MOCKED. No real installation ever runs. The tests verify
the command sequence, the generated ``configuration.nix`` contents, the LUKS
injection, the ``confirmed`` guard-rail, secret redaction and dry-run safety.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

try:
    from omnis.jobs.base import JobContext, JobResult, JobStatus
    from omnis.jobs.nixos import (
        DEFAULT_USER_GROUPS,
        ERR_NOT_CONFIRMED,
        NixosJob,
    )

    HAS_NIXOS_JOB = True
except ImportError:
    HAS_NIXOS_JOB = False

pytestmark = pytest.mark.skipif(not HAS_NIXOS_JOB, reason="NixosJob not available")


# =============================================================================
# Fixtures / helpers
# =============================================================================


def _selections(**overrides: Any) -> dict[str, Any]:
    """Build a realistic snake_case selections dict with sensible defaults."""
    base: dict[str, Any] = {
        "disk": "/dev/sda",
        "target_root": "/mnt/target",
        "username": "gamer",
        "fullname": "GLF Gamer",
        "hostname": "glf-box",
        "auto_login": True,
        "desktop_environment": "gnome",
        "edition": "standard",
        "locale": "fr_FR.UTF-8",
        "timezone": "Europe/Paris",
        "keymap": "fr",
        "keyboard_variant": "",
        "encryption": False,
    }
    base.update(overrides)
    return base


def _context(**overrides: Any) -> JobContext:
    """Build a JobContext with the given selections overrides."""
    return JobContext(target_root="/mnt/target", selections=_selections(**overrides))


# =============================================================================
# Basic contract
# =============================================================================


class TestNixosJobBasics:
    """Basic job contract."""

    def test_name_and_description(self) -> None:
        job = NixosJob()
        assert job.name == "nixos"
        assert "GLF OS" in job.description or "NixOS" in job.description
        assert job.status == JobStatus.PENDING

    def test_estimate_duration_is_realistic(self) -> None:
        # nixos-install is long; the estimate must reflect that.
        assert NixosJob().estimate_duration() >= 300

    def test_default_flake_config(self) -> None:
        job = NixosJob()
        assert job._flake_source() == "/iso/nixos"
        assert job._flake_attr() == "GLF-OS"

    def test_config_overrides_flake(self) -> None:
        job = NixosJob(config={"flake_source": "/custom/src", "flake_attr": "CUSTOM"})
        assert job._flake_source() == "/custom/src"
        assert job._flake_attr() == "CUSTOM"

    def test_job_class_is_loadable_name(self) -> None:
        # The dynamic loader picks a class ending in 'Job' inheriting BaseJob.
        assert NixosJob.__name__.endswith("Job")


# =============================================================================
# configuration.nix generation
# =============================================================================


class TestConfigurationGeneration:
    """Tests for the assembled configuration.nix contents."""

    def test_environment_and_edition_gnome_standard(self) -> None:
        job = NixosJob()
        cfg = job._build_configuration(_context(desktop_environment="gnome", edition="standard"))
        assert 'glf.environment.type = "gnome";' in cfg
        assert 'glf.environment.edition = "standard";' in cfg

    def test_environment_plasma_studio_pro(self) -> None:
        job = NixosJob()
        cfg = job._build_configuration(_context(desktop_environment="plasma", edition="studio-pro"))
        assert 'glf.environment.type = "plasma";' in cfg
        assert 'glf.environment.edition = "studio-pro";' in cfg

    def test_kde_alias_maps_to_plasma(self) -> None:
        job = NixosJob()
        cfg = job._build_configuration(_context(desktop_environment="kde"))
        assert 'glf.environment.type = "plasma";' in cfg

    def test_efi_bootloader_is_default(self) -> None:
        job = NixosJob()
        cfg = job._build_configuration(_context())
        assert "boot.loader.systemd-boot.enable = true;" in cfg
        assert "boot.loader.efi.canTouchEfiVariables = true;" in cfg

    def test_bios_bootloader_when_requested(self) -> None:
        job = NixosJob()
        cfg = job._build_configuration(_context(firmware_type="bios", disk="/dev/sdb"))
        assert "boot.loader.grub.enable = true;" in cfg
        assert 'boot.loader.grub.device = "/dev/sdb";' in cfg

    def test_user_and_groups(self) -> None:
        job = NixosJob()
        cfg = job._build_configuration(_context(username="gamer", fullname="GLF Gamer"))
        assert "users.users.gamer = {" in cfg
        assert 'description = "GLF Gamer";' in cfg
        for group in DEFAULT_USER_GROUPS:
            assert f'"{group}"' in cfg

    def test_autologin_present_when_enabled(self) -> None:
        job = NixosJob()
        cfg = job._build_configuration(_context(auto_login=True))
        assert "services.displayManager.autoLogin.enable = true;" in cfg
        assert 'services.displayManager.autoLogin.user = "gamer";' in cfg

    def test_autologin_absent_when_disabled(self) -> None:
        job = NixosJob()
        cfg = job._build_configuration(_context(auto_login=False))
        assert "autoLogin.enable" not in cfg

    def test_locale_timezone_keymap(self) -> None:
        job = NixosJob()
        cfg = job._build_configuration(_context())
        assert 'i18n.defaultLocale = "fr_FR.UTF-8";' in cfg
        assert 'time.timeZone = "Europe/Paris";' in cfg
        assert 'layout = "fr";' in cfg

    def test_locale_utf8_normalised(self) -> None:
        job = NixosJob()
        cfg = job._build_configuration(_context(locale="de_DE.utf8"))
        assert 'i18n.defaultLocale = "de_DE.UTF-8";' in cfg

    def test_hostname_defaults_to_glfos(self) -> None:
        job = NixosJob()
        cfg = job._build_configuration(_context(hostname=""))
        assert 'networking.hostName = "GLF-OS";' in cfg

    def test_imports_and_statuversion_present(self) -> None:
        job = NixosJob()
        cfg = job._build_configuration(_context())
        assert "./hardware-configuration.nix" in cfg
        assert "./customConfig" in cfg
        assert "system.stateVersion" in cfg


# =============================================================================
# LUKS injection
# =============================================================================


class TestLuksInjection:
    """Tests for boot.initrd.luks.devices injection."""

    def test_no_luks_when_encryption_disabled(self) -> None:
        job = NixosJob()
        cfg = job._build_configuration(_context(encryption=False))
        assert "boot.initrd.luks.devices" not in cfg

    def test_luks_injected_when_encryption_enabled(self) -> None:
        job = NixosJob()
        cfg = job._build_configuration(_context(encryption=True, root_partition="/dev/sda2"))
        assert 'boot.initrd.luks.devices."cryptroot".device = "/dev/sda2";' in cfg

    def test_luks_custom_mapper(self) -> None:
        job = NixosJob()
        cfg = job._build_configuration(
            _context(encryption=True, root_partition="/dev/nvme0n1p2", luks_mapper_name="glfroot")
        )
        assert 'boot.initrd.luks.devices."glfroot".device = "/dev/nvme0n1p2";' in cfg


# =============================================================================
# Command sequence (all subprocess mocked)
# =============================================================================


class TestInstallSequence:
    """Tests for the mocked install command sequence."""

    def test_dry_run_executes_no_real_command(self) -> None:
        """dry_run=True must never issue a real install command."""
        job = NixosJob()
        # The benign, read-only stateVersion query is stubbed so the assertion
        # targets the destructive install sequence only.
        with (
            patch.object(job, "_detect_state_version", return_value="25.11"),
            patch("omnis.jobs.nixos.subprocess.run") as mock_run,
        ):
            result = job.run(_context(dry_run=True))
        assert result.success is True
        mock_run.assert_not_called()

    def test_real_run_command_sequence(self) -> None:
        """A confirmed real run issues generate-config, cp*, then nixos-install."""
        job = NixosJob()
        calls: list[list[str]] = []

        def fake_run(cmd: list[str], **_kwargs: Any) -> MagicMock:
            calls.append(cmd)
            return MagicMock(returncode=0, stdout="", stderr="")

        # Patch subprocess.run (command execution) and the config/flake writing
        # filesystem ops so nothing touches the real disk. The stateVersion
        # query is stubbed so ``calls`` contains only the install sequence.
        with (
            patch.object(job, "_detect_state_version", return_value="25.11"),
            patch("omnis.jobs.nixos.subprocess.run", side_effect=fake_run),
            patch("omnis.jobs.nixos.Path.is_dir", return_value=True),
            patch("omnis.jobs.nixos.Path.exists", return_value=True),
            patch("omnis.jobs.nixos.Path.mkdir"),
            patch("omnis.jobs.nixos.Path.write_text"),
        ):
            result = job.run(_context(dry_run=False, confirmed=True))

        assert result.success is True, result.message

        # First real command is nixos-generate-config with --root.
        assert calls[0][0] == "nixos-generate-config"
        assert "--root" in calls[0]
        assert "/mnt/target" in calls[0]

        # Flake files are copied (cp -r) preserving hardware-configuration.nix.
        cp_calls = [c for c in calls if c[0] == "cp"]
        copied = " ".join(" ".join(c) for c in cp_calls)
        assert "flake.nix" in copied
        assert "flake.lock" in copied
        assert "customConfig" in copied
        # hardware-configuration.nix is NEVER copied over (it is preserved).
        assert "hardware-configuration.nix" not in copied

        # Last command is nixos-install with the exact GLF flags.
        install = calls[-1]
        assert install[0] == "nixos-install"
        assert "--no-root-passwd" in install
        assert install[install.index("--flake") + 1] == "/mnt/target/etc/nixos#GLF-OS"
        assert install[install.index("--root") + 1] == "/mnt/target"
        # sandbox false + empty build-users-group options.
        assert install[install.index("sandbox") + 1] == "false"
        assert "build-users-group" in install

    def test_generate_config_failure_aborts(self) -> None:
        """A failing nixos-generate-config must abort before nixos-install."""
        job = NixosJob()

        def fake_run(cmd: list[str], **_kwargs: Any) -> MagicMock:
            if cmd[0] == "nixos-generate-config":
                raise subprocess.CalledProcessError(1, cmd, stderr="boom")
            return MagicMock(returncode=0, stdout="", stderr="")

        with (
            patch("omnis.jobs.nixos.subprocess.run", side_effect=fake_run),
            patch("omnis.jobs.nixos.Path.is_dir", return_value=True),
            patch("omnis.jobs.nixos.Path.exists", return_value=True),
        ):
            result = job.run(_context(dry_run=False, confirmed=True))

        assert result.success is False
        assert "Generating" in result.message or "failed" in result.message


# =============================================================================
# Security guard-rails
# =============================================================================


class TestSecurityGuards:
    """Tests for the confirmed guard-rail and secret redaction."""

    def test_dry_run_default_true(self) -> None:
        """Without an explicit flag, dry_run must default to True."""
        job = NixosJob()
        with (
            patch.object(job, "_detect_state_version", return_value="25.11"),
            patch("omnis.jobs.nixos.subprocess.run") as mock_run,
        ):
            # No dry_run/confirmed keys at all.
            ctx = JobContext(target_root="/mnt/target", selections=_selections())
            ctx.selections.pop("dry_run", None)
            result = job.run(ctx)
        assert result.success is True
        mock_run.assert_not_called()

    def test_real_run_refused_without_confirmed(self) -> None:
        """dry_run=False AND confirmed=False must be refused (no commands)."""
        job = NixosJob()
        with (
            patch("omnis.jobs.nixos.subprocess.run") as mock_run,
            patch("omnis.jobs.nixos.Path.is_dir", return_value=True),
            patch("omnis.jobs.nixos.Path.exists", return_value=True),
        ):
            result = job.run(_context(dry_run=False, confirmed=False))
        assert result.success is False
        assert result.error_code == ERR_NOT_CONFIRMED
        mock_run.assert_not_called()

    def test_real_run_allowed_with_confirmed(self) -> None:
        """dry_run=False AND confirmed=True proceeds to run commands."""
        job = NixosJob()
        with (
            patch("omnis.jobs.nixos.subprocess.run") as mock_run,
            patch("omnis.jobs.nixos.Path.is_dir", return_value=True),
            patch("omnis.jobs.nixos.Path.exists", return_value=True),
            patch("omnis.jobs.nixos.Path.mkdir"),
            patch("omnis.jobs.nixos.Path.write_text"),
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = job.run(_context(dry_run=False, confirmed=True))
        assert result.success is True
        assert mock_run.called

    def test_secrets_never_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """Passwords / passphrases must never appear in logs."""
        job = NixosJob()
        secret_pass = "S3cr3tUserPass!"
        secret_root = "R00tPass!"
        secret_luks = "LuksPhrase123!"
        with (
            caplog.at_level(logging.DEBUG),
            patch("omnis.jobs.nixos.subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            job.run(
                _context(
                    dry_run=True,
                    encryption=True,
                    root_partition="/dev/sda2",
                    password=secret_pass,
                    root_password=secret_root,
                    encryption_passphrase=secret_luks,
                )
            )
        blob = "\n".join(rec.getMessage() for rec in caplog.records)
        assert secret_pass not in blob
        assert secret_root not in blob
        assert secret_luks not in blob

    def test_secrets_never_in_configuration(self) -> None:
        """The generated configuration.nix must not embed any secret."""
        job = NixosJob()
        cfg = job._build_configuration(
            _context(
                encryption=True,
                root_partition="/dev/sda2",
                password="S3cr3tUserPass!",
                root_password="R00tPass!",
                encryption_passphrase="LuksPhrase123!",
            )
        )
        assert "S3cr3tUserPass!" not in cfg
        assert "R00tPass!" not in cfg
        assert "LuksPhrase123!" not in cfg


# =============================================================================
# Validation
# =============================================================================


class TestValidation:
    """Tests for validate()."""

    def test_missing_target_root_fails(self) -> None:
        job = NixosJob()
        ctx = JobContext(target_root="", selections=_selections())
        result = job.validate(ctx)
        assert result.success is False

    def test_dry_run_validation_relaxed(self) -> None:
        """Dry-run validation must not require a real mounted target."""
        job = NixosJob()
        result = job.validate(_context(dry_run=True))
        assert result.success is True

    def test_real_validation_requires_mounted_target(self) -> None:
        job = NixosJob()
        with patch("omnis.jobs.nixos.Path.is_dir", return_value=False):
            result = job.validate(_context(dry_run=False))
        assert result.success is False


# =============================================================================
# Cleanup
# =============================================================================


class TestCleanup:
    """Tests for cleanup() unmount behaviour."""

    def test_cleanup_noop_in_dry_run(self) -> None:
        job = NixosJob()
        with patch("omnis.jobs.nixos.subprocess.run") as mock_run:
            job.cleanup(_context(dry_run=True))
        mock_run.assert_not_called()

    def test_cleanup_unmounts_recursively(self) -> None:
        job = NixosJob()
        with patch("omnis.jobs.nixos.subprocess.run") as mock_run:
            job.cleanup(_context(dry_run=False))
        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        assert cmd[:2] == ["umount", "-R"]
        assert cmd[2] == "/mnt/target"

    def test_cleanup_never_raises(self) -> None:
        job = NixosJob()
        with patch("omnis.jobs.nixos.subprocess.run", side_effect=OSError("nope")):
            # Must swallow the error.
            job.cleanup(_context(dry_run=False))


def test_result_is_jobresult() -> None:
    """run() must always return a JobResult."""
    job = NixosJob()
    with patch("omnis.jobs.nixos.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = job.run(_context(dry_run=True))
    assert isinstance(result, JobResult)
