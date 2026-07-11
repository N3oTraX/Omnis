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
        ERR_HASH_FAILED,
        ERR_NOT_CONFIRMED,
        NixosJob,
        _NixProgress,
        _throttle_cores,
        _throttled,
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


def _base_cmd(cmd: list[str]) -> list[str]:
    """Strip the leading ``nice``/``ionice`` throttle prefix for assertions.

    The throttle prefix is host-dependent (present only when the binaries
    exist), so tests match on the *real* command regardless of throttling.
    """
    c = list(cmd)
    if c[:1] == ["nice"]:
        c = c[3:]  # nice -n 15
    if c[:1] == ["ionice"]:
        c = c[5:]  # ionice -c 2 -n 7
    return c


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

    def test_always_systemd_boot_never_grub(self) -> None:
        # GLF OS boots with systemd-boot only; GRUB/BIOS is not supported, so the
        # config is always systemd-boot regardless of any firmware hint.
        job = NixosJob()
        with patch.object(job, "_gpu_config", return_value=""):
            cfg = job._build_configuration(_context(firmware_type="bios", disk="/dev/sdb"))
        assert "boot.loader.systemd-boot.enable = true;" in cfg
        assert "grub" not in cfg

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
        # earlySetup is required so the LUKS passphrase prompt (initrd) follows
        # the chosen keyboard layout instead of defaulting to QWERTY/US.
        assert "console.earlySetup = true;" in cfg

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
    """The job must NOT emit boot.initrd.luks.devices for the root device.

    ``nixos-generate-config`` detects the LUKS-wrapped root and writes the device
    (by-uuid) into ``hardware-configuration.nix``. Emitting it in
    ``configuration.nix`` as well produced a fatal "conflicting definition
    values" error in ``nixos-install``, so the job stays silent.
    """

    def test_no_luks_when_encryption_disabled(self) -> None:
        job = NixosJob()
        cfg = job._build_configuration(_context(encryption=False))
        assert "boot.initrd.luks.devices" not in cfg

    def test_no_manual_luks_when_encryption_enabled(self) -> None:
        # Root LUKS is owned by nixos-generate-config; a manual block here would
        # double-define the option and abort nixos-install.
        job = NixosJob()
        cfg = job._build_configuration(_context(encryption=True, root_partition="/dev/sda2"))
        assert "boot.initrd.luks.devices" not in cfg

    def test_no_manual_luks_custom_mapper(self) -> None:
        job = NixosJob()
        cfg = job._build_configuration(
            _context(encryption=True, root_partition="/dev/nvme0n1p2", luks_mapper_name="glfroot")
        )
        assert "boot.initrd.luks.devices" not in cfg


# =============================================================================
# Declarative password hashing (hashedPassword)
# =============================================================================


def _fake_hash(password: str) -> str:
    """Deterministic fake SHA-512 crypt hash keyed on the plaintext length."""
    # Distinct per plaintext so user/root hashes are distinguishable, and the
    # plaintext is never embedded (mirrors the real no-leak guarantee).
    return f"$6$abc${'d' * len(password)}"


class TestPasswordHashing:
    """Tests for declarative user/root ``hashedPassword`` injection."""

    def test_user_hashed_password_present_when_password_provided(self) -> None:
        job = NixosJob()
        with patch.object(job, "_hash_password", side_effect=_fake_hash) as m:
            hashes = job._compute_password_hashes(_context(password="userpw"))
        cfg = job._build_configuration(_context(username="gamer"), hashes)
        assert 'hashedPassword = "$6$abc$dddddd";' in cfg
        # The user block owns the hash line.
        assert "users.users.gamer = {" in cfg
        m.assert_called_once_with("userpw")

    def test_no_user_hashed_password_when_absent(self) -> None:
        job = NixosJob()
        hashes = job._compute_password_hashes(_context(password=""))
        cfg = job._build_configuration(_context(username="gamer"), hashes)
        assert "users.users.gamer = {" in cfg
        assert "hashedPassword" not in cfg

    def test_root_hashed_password_block_present(self) -> None:
        job = NixosJob()
        with patch.object(job, "_hash_password", side_effect=_fake_hash):
            hashes = job._compute_password_hashes(
                _context(password="userpw", root_password="rootpw")
            )
        cfg = job._build_configuration(_context(username="gamer"), hashes)
        assert "users.users.root.hashedPassword = " in cfg

    def test_root_same_as_user_reuses_user_hash_single_call(self) -> None:
        """root_same_as_user=True → root shares the user hash, hashed once."""
        job = NixosJob()
        with patch.object(job, "_hash_password", side_effect=_fake_hash) as m:
            hashes = job._compute_password_hashes(
                _context(password="userpw", root_same_as_user=True, root_password="")
            )
        # Same hash for both accounts.
        assert hashes.user == hashes.root == "$6$abc$dddddd"
        # Hashed exactly once (no re-hash for root).
        m.assert_called_once_with("userpw")

    def test_root_distinct_password_distinct_hash(self) -> None:
        """root_same_as_user=False with a distinct root password → distinct hash."""
        job = NixosJob()
        with patch.object(job, "_hash_password", side_effect=_fake_hash) as m:
            hashes = job._compute_password_hashes(
                _context(
                    password="userpw",  # len 6
                    root_password="rootpassword",  # len 12
                    root_same_as_user=False,
                )
            )
        assert hashes.user == "$6$abc$dddddd"  # 6 d's
        assert hashes.root == "$6$abc$dddddddddddd"  # 12 d's
        assert hashes.user != hashes.root
        assert m.call_count == 2

    def test_full_config_has_both_hashes(self) -> None:
        job = NixosJob()
        with patch.object(job, "_hash_password", side_effect=_fake_hash):
            hashes = job._compute_password_hashes(
                _context(password="userpw", root_same_as_user=True)
            )
        cfg = job._build_configuration(_context(username="gamer"), hashes)
        assert 'hashedPassword = "$6$abc$dddddd";' in cfg
        assert 'users.users.root.hashedPassword = "$6$abc$dddddd";' in cfg

    def test_build_configuration_without_hashes_is_safe(self) -> None:
        """_build_configuration must not crash / hash when hashes omitted."""
        job = NixosJob()
        # No hashing tool is invoked; no hashedPassword line emitted.
        cfg = job._build_configuration(_context(username="gamer", password="x"))
        assert "hashedPassword" not in cfg


class TestHashPasswordTool:
    """Tests for the low-level ``_hash_password`` subprocess wrapper."""

    def test_hash_password_uses_mkpasswd_via_stdin(self) -> None:
        job = NixosJob()
        captured: dict[str, Any] = {}

        def fake_run(cmd: list[str], **kwargs: Any) -> MagicMock:
            captured["cmd"] = cmd
            captured["kwargs"] = kwargs
            return MagicMock(returncode=0, stdout="$6$salt$hashed\n", stderr="")

        with (
            patch("omnis.jobs.nixos.shutil.which", side_effect=lambda t: t == "mkpasswd"),
            patch("omnis.jobs.nixos.subprocess.run", side_effect=fake_run),
        ):
            digest = job._hash_password("plaintextpw")

        assert digest == "$6$salt$hashed"
        assert captured["cmd"][0] == "mkpasswd"
        # SECURITY: plaintext passed via STDIN, never in argv.
        assert captured["kwargs"].get("input") == "plaintextpw"
        assert "plaintextpw" not in " ".join(captured["cmd"])

    def test_hash_password_falls_back_to_openssl(self) -> None:
        job = NixosJob()

        def fake_run(_cmd: list[str], **_kwargs: Any) -> MagicMock:
            return MagicMock(returncode=0, stdout="$6$s$openssl\n", stderr="")

        # Only openssl available.
        with (
            patch("omnis.jobs.nixos.shutil.which", side_effect=lambda t: t == "openssl"),
            patch("omnis.jobs.nixos.subprocess.run", side_effect=fake_run),
        ):
            digest = job._hash_password("pw")

        assert digest == "$6$s$openssl"

    def test_hash_password_raises_when_no_tool(self) -> None:
        job = NixosJob()
        with (
            patch("omnis.jobs.nixos.shutil.which", return_value=None),
            pytest.raises(RuntimeError),
        ):
            job._hash_password("pw")

    def test_run_returns_hash_failed_when_hashing_fails(self) -> None:
        """A hashing failure surfaces as a clean JobResult (ERR_HASH_FAILED)."""
        job = NixosJob()
        with (
            patch.object(job, "_detect_state_version", return_value="25.11"),
            patch.object(job, "_hash_password", side_effect=RuntimeError("no tool")),
            patch("omnis.jobs.nixos.subprocess.run") as mock_run,
        ):
            result = job.run(_context(dry_run=True, password="userpw"))
        assert result.success is False
        assert result.error_code == ERR_HASH_FAILED
        # No install command ran.
        mock_run.assert_not_called()


# =============================================================================
# Command sequence (all subprocess mocked)
# =============================================================================


class TestInstallSequence:
    """Tests for the mocked install command sequence."""

    def test_dry_run_executes_no_real_command(self) -> None:
        """dry_run=True must never issue a real install command."""
        job = NixosJob()
        # The benign, read-only stateVersion + GPU (lspci) queries are stubbed so
        # the assertion targets the destructive install sequence only.
        with (
            patch.object(job, "_detect_state_version", return_value="25.11"),
            patch.object(job, "_gpu_config", return_value=""),
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

        def fake_popen(cmd: list[str], **_kwargs: Any) -> MagicMock:
            # nixos-install is streamed via Popen; record it in the same log.
            calls.append(cmd)
            proc = MagicMock()
            proc.stdout = iter([])
            proc.stderr = iter([])  # prebuild streams @nix progress on STDERR
            proc.wait.return_value = 0
            return proc

        # Patch subprocess.run/Popen (command execution) and the config/flake
        # writing filesystem ops so nothing touches the real disk. The
        # stateVersion query is stubbed so ``calls`` is only the install sequence.
        # fake_run returns empty stdout ⇒ store-path capture yields nothing ⇒
        # the install falls back to the historical ``--flake`` flow.
        with (
            patch.object(job, "_detect_state_version", return_value="25.11"),
            patch.object(job, "_gpu_config", return_value=""),
            patch.object(job, "_harden_target", return_value="/mnt/target/var/tmp/nix-installer"),
            patch("omnis.jobs.nixos.subprocess.run", side_effect=fake_run),
            patch("omnis.jobs.nixos.subprocess.Popen", side_effect=fake_popen),
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
        # customized.nix (glf-customizer managed) is imported by the target
        # flake, so it must be copied alongside the others.
        assert "customized.nix" in copied
        # hardware-configuration.nix is NEVER copied over (it is preserved).
        assert "hardware-configuration.nix" not in copied

        # Last command is nixos-install with the exact GLF flags (throttle stripped).
        install = _base_cmd(calls[-1])
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
            patch.object(job, "_gpu_config", return_value=""),
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

        def fake_popen(_cmd: list[str], **_kwargs: Any) -> MagicMock:
            proc = MagicMock()
            proc.stdout = iter([])  # nixos-install emits no output in the stub
            proc.wait.return_value = 0
            return proc

        with (
            patch.object(job, "_harden_target", return_value="/mnt/target/var/tmp/nix-installer"),
            patch("omnis.jobs.nixos.subprocess.run") as mock_run,
            patch("omnis.jobs.nixos.subprocess.Popen", side_effect=fake_popen),
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
        """Passwords / passphrases (and derived hashes) must never appear in logs."""
        job = NixosJob()
        secret_pass = "S3cr3tUserPass!"
        secret_root = "R00tPass!"
        secret_luks = "LuksPhrase123!"
        # Deterministic fake hashes so we can assert they never leak either.
        fake_user_hash = "$6$salt$USERHASHVALUE"
        fake_root_hash = "$6$salt$ROOTHASHVALUE"

        def fake_hash(pw: str) -> str:
            return fake_user_hash if pw == secret_pass else fake_root_hash

        with (
            caplog.at_level(logging.DEBUG),
            patch.object(job, "_hash_password", side_effect=fake_hash),
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
        # SECURITY: the derived crypt hashes must not leak into logs either.
        assert fake_user_hash not in blob
        assert fake_root_hash not in blob

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


class TestNixProgress:
    """Parse real nix internal-json events into a monotonic 0..1 fraction."""

    @staticmethod
    def _build(id_: int, done: int, expected: int) -> str:
        return f'@nix {{"action":"result","fields":[{done},{expected},0,0],"id":{id_},"type":105}}'

    def test_ignores_non_nix_and_malformed_lines(self) -> None:
        p = _NixProgress()
        assert p.feed("copying path '/nix/store/x'") is None
        assert p.feed("@nix not-json") is None
        assert p.feed('@nix {"action":"msg","level":3,"msg":"building:"}') is None

    def test_builds_and_copies_are_aggregated(self) -> None:
        p = _NixProgress()
        # Builds activity opens and reports progress (only activities that have
        # a resProgress contribute to 'expected').
        p.feed('@nix {"action":"start","id":1,"type":104}')
        assert p.feed(self._build(1, 2, 10)) == 0.2  # 2/10 built
        assert p.feed(self._build(1, 6, 10)) == 0.6  # 6/10 built
        assert "6/10 built" in p.message()
        # copyPaths joins in: 6 built + 10 copied over (10 + 10) = 16/20 = 0.8.
        p.feed('@nix {"action":"start","id":2,"type":103}')
        assert p.feed(self._build(2, 10, 10)) == 0.8
        assert "10/10 copied" in p.message()

    def test_ignores_per_byte_file_transfer_results(self) -> None:
        p = _NixProgress()
        p.feed('@nix {"action":"start","id":1,"type":104}')
        p.feed(self._build(1, 1, 4))
        # A file-transfer (type 101) progress result for an unregistered id must
        # not perturb the fraction (its id was never a build/copy activity).
        before = p._fraction
        assert p.feed('@nix {"action":"result","fields":[84,84,0,0],"id":99,"type":105}') is None
        assert p._fraction == before

    def test_fraction_is_monotonic_but_stays_alive(self) -> None:
        """Le pct affiché ne régresse jamais, MAIS feed() reste « vivant » :
        un event pertinent retourne toujours une valeur non-None (message vivant)
        même quand le nombre n'augmente pas."""
        p = _NixProgress()
        p.feed('@nix {"action":"start","id":1,"type":104}')
        assert p.feed(self._build(1, 8, 10)) == 0.8
        # A newly discovered activity enlarges 'expected'; the numeric fraction
        # would dip to 8/20=0.4 but the DISPLAYED value must not move backwards…
        p.feed('@nix {"action":"start","id":2,"type":103}')
        result = p.feed(self._build(2, 0, 10))
        # …and feed() still returns a usable (non-None) monotone value so the
        # caller re-emits an up-to-date message.
        assert result == 0.8
        assert p._fraction == 0.8

    def test_expected_growth_yields_live_non_none_series(self) -> None:
        """``expected`` croissant → série de retours non-None, fraction monotone."""
        p = _NixProgress()
        p.feed('@nix {"action":"start","id":1,"type":104}')
        seen: list[float | None] = [
            p.feed(self._build(1, 1, 5)),  # 0.2
            p.feed(self._build(1, 2, 20)),  # 2/20=0.1 → clampé à 0.2 (monotone)
            p.feed(self._build(1, 5, 20)),  # 0.25
        ]
        assert all(v is not None for v in seen)
        # Chaque valeur est un float non décroissant.
        floats = [v for v in seen if v is not None]
        assert floats == sorted(floats)
        assert p._fraction == 0.25

    def test_extracts_current_package_from_build_start(self) -> None:
        """Le nom du paquet en cours vient du champ ``text`` d'un event 104."""
        p = _NixProgress()
        p.feed(
            '@nix {"action":"start","id":1,"type":104,'
            '"text":"building \'/nix/store/xxxx-mesa-24.0.drv\'"}'
        )
        assert p.current_package() == "mesa-24.0"
        # Et le paquet apparaît dans le message une fois les compteurs connus.
        p.feed(self._build(1, 1, 4))
        assert "mesa-24.0" in p.message()
        assert "1/4 built" in p.message()

    def test_secret_in_event_never_reaches_message(self) -> None:
        """SÉCURITÉ : un faux secret injecté dans un champ d'event n'apparaît
        jamais dans message() ni dans current_package()."""
        p = _NixProgress()
        secret = "hunter2-SECRET-passphrase"
        # Secret glissé dans le texte d'un build start ET dans les fields d'un
        # result — aucun des deux ne doit fuiter.
        p.feed(f'@nix {{"action":"start","id":1,"type":104,"text":"building for user {secret}"}}')
        p.feed(f'@nix {{"action":"result","fields":[2,10,"{secret}"],"id":1,"type":105}}')
        assert secret not in p.message()
        assert secret not in p.current_package()


class TestNixProgressPlain:
    """Plain-text ``nixos-install`` output (the wrapper ignores ``--log-format``)."""

    _COPY = "copying path '/nix/store/jlyahda14aya375lv7k9fsin2zk90nxz-glib-2.88.1' to 'local'..."
    _BUILD = "building '/nix/store/6a3k2hzqpr1czvxlgmy53xaannmnpd3i-copy-extra-files.drv'..."

    def test_plain_lines_advance_counters_and_package(self) -> None:
        p = _NixProgress()
        assert p.feed(self._COPY) is None  # not an @nix line
        f1 = p.feed_plain(self._COPY)
        assert f1 is not None and f1 > 0.0
        assert "1 copiés" in p.message()
        assert "glib-2.88.1" in p.message()
        p.feed_plain(self._BUILD)
        assert "1 construits" in p.message()
        assert "copy-extra-files" in p.message()

    def test_plain_fraction_is_monotonic_and_never_frozen(self) -> None:
        p = _NixProgress()
        seen = [p.feed_plain(self._COPY) for _ in range(5)]
        assert all(v is not None for v in seen)
        floats = [v for v in seen if v is not None]
        assert floats == sorted(floats)
        assert floats[-1] > floats[0]

    def test_plain_denominator_yields_real_ratio(self) -> None:
        p = _NixProgress(plain_total=453)
        for _ in range(10):
            p.feed_plain(self._COPY)
        assert "10/453 copiés" in p.message()
        frac = p.feed_plain(self._COPY)
        assert frac == pytest.approx(11 / 453)

    def test_plain_ignores_unrelated_lines(self) -> None:
        p = _NixProgress()
        assert p.feed_plain("installing bootloader") is None
        assert p.feed_plain("setting up /etc...") is None
        assert p.message() == "Installing NixOS..."

    def test_at_nix_parsing_still_works_alongside_plain(self) -> None:
        p = _NixProgress()
        p.feed('@nix {"action":"start","id":1,"type":104}')
        assert p.feed('@nix {"action":"result","fields":[3,10,0,0],"id":1,"type":105}') == 0.3
        assert "3/10 built" in p.message()

    def test_parses_nix_announced_totals_and_counts_from(self) -> None:
        p = _NixProgress()
        # nixos-install prints its own totals up front.
        assert p.feed_plain("these 458 derivations will be built:") is None
        assert p.feed_plain("these 1793 paths will be fetched (3.3 GiB download):") is None
        # Substitutions use the 'from <cache>' form, which must count too.
        for _ in range(10):
            p.feed_plain(
                "copying path '/nix/store/aaaa-glib-2.88.1' from 'https://cache.nixos.org'..."
            )
        assert "10/2251 copiés" in p.message()
        frac = p.feed_plain(self._BUILD)
        assert frac == pytest.approx(11 / 2251)

    def test_plain_copy_destination_never_reaches_message(self) -> None:
        p = _NixProgress()
        secret = "hunter2-SECRET-passphrase"
        p.feed_plain(f"copying path '/nix/store/aaaa-thing' to 'ssh://{secret}'...")
        # Only the source store path is parsed; the destination URI is dropped.
        assert secret not in p.message()
        assert "ssh://" not in p.message()
        assert "thing" in p.message()


class TestHardenTarget:
    """Securing the Nix build-dir hierarchy before nixos-install."""

    def test_dry_run_returns_path_without_touching_fs(self) -> None:
        job = NixosJob()
        with patch("omnis.jobs.nixos.os.makedirs") as mk:
            path = job._harden_target("/mnt/target", dry_run=True)
        assert path == "/mnt/target/var/tmp/nix-installer"
        mk.assert_not_called()

    def test_creates_and_secures_nix_dirs(self) -> None:
        job = NixosJob()
        with (
            patch("omnis.jobs.nixos.os.makedirs") as mk,
            patch("omnis.jobs.nixos.os.chmod") as chm,
            patch("omnis.jobs.nixos.os.chown") as cho,
        ):
            path = job._harden_target("/mnt/target", dry_run=False)
        made = {c.args[0] for c in mk.call_args_list}
        assert "/mnt/target/nix/var/nix/builds" in made
        assert "/mnt/target/nix/var/nix/db" in made
        assert "/mnt/target/nix/var/nix/profiles" in made
        assert path in made  # the secure TMPDIR is created too
        assert all(c.args[1:] == (0, 0) for c in cho.call_args_list)  # root:root
        assert chm.called

    def test_install_uses_flake_no_prebuild(self) -> None:
        """L'install passe par ``--flake`` (aucun nix build/eval préalable)."""
        job = NixosJob()
        calls: list[tuple[list[str], dict[str, Any]]] = []

        def fake_popen(cmd: list[str], **kwargs: Any) -> MagicMock:
            calls.append((cmd, kwargs.get("env", {})))
            proc = MagicMock()
            proc.stdout = iter([])
            proc.wait.return_value = 0
            return proc

        with (
            patch("omnis.jobs.nixos.subprocess.Popen", side_effect=fake_popen),
            patch("omnis.jobs.nixos.subprocess.run") as run,
        ):
            result = job._nixos_install("/mnt/target", dry_run=False, tmpdir="/secure/tmp")

        assert result.success is True
        run.assert_not_called()  # plus d'éval-only : le total vient des annonces nix
        install = _base_cmd(calls[-1][0])
        assert install[0] == "nixos-install"
        assert "--flake" in install
        assert "/mnt/target/etc/nixos#GLF-OS" in install
        assert "--system" not in install
        assert all(_base_cmd(cmd)[:2] != ["nix", "build"] for cmd, _env in calls)
        assert calls[-1][1].get("TMPDIR") == "/secure/tmp"

    def test_install_dry_run_skips_eval_and_runs_nothing(self) -> None:
        """En dry-run : pas d'évaluation de closure, aucune commande exécutée."""
        job = NixosJob()
        with (
            patch("omnis.jobs.nixos.subprocess.Popen") as popen,
            patch("omnis.jobs.nixos.subprocess.run") as run,
        ):
            result = job._nixos_install("/mnt/target", dry_run=True)
        assert result.success is True
        popen.assert_not_called()
        run.assert_not_called()


class TestNetworkConfigCopy:
    """Carry over the live NetworkManager connections (Wi-Fi + wired)."""

    def test_noop_when_no_source(self) -> None:
        job = NixosJob()
        with (
            patch("omnis.jobs.nixos.Path.is_dir", return_value=False),
            patch("omnis.jobs.nixos.Path.mkdir") as mk,
        ):
            job._copy_network_config("/mnt/target", dry_run=False)
        mk.assert_not_called()

    def test_dry_run_copies_nothing(self) -> None:
        job = NixosJob()
        with (
            patch("omnis.jobs.nixos.Path.is_dir", return_value=True),
            patch("omnis.jobs.nixos.Path.mkdir") as mk,
        ):
            job._copy_network_config("/mnt/target", dry_run=True)
        mk.assert_not_called()

    def test_copies_nmconnection_files_secured(self) -> None:
        job = NixosJob()
        conn = MagicMock()
        conn.name = "MyWifi.nmconnection"
        conn.read_bytes.return_value = b"[wifi]\npsk=secret\n"
        with (
            patch("omnis.jobs.nixos.Path.is_dir", return_value=True),
            patch("omnis.jobs.nixos.Path.mkdir"),
            patch("omnis.jobs.nixos.Path.glob", return_value=[conn]),
            patch("omnis.jobs.nixos.Path.write_bytes") as write_bytes,
            patch("omnis.jobs.nixos.os.chmod") as chmod,
            patch("omnis.jobs.nixos.os.chown") as chown,
        ):
            job._copy_network_config("/mnt/target", dry_run=False)
        write_bytes.assert_called_once_with(b"[wifi]\npsk=secret\n")
        # The copied secret is locked down (root:root, 0600).
        assert any(call.args[1] == 0o600 for call in chmod.call_args_list)
        assert chown.call_args_list and chown.call_args_list[-1].args[1:] == (0, 0)


class TestThrottle:
    """AXE 1 : les commandes lourdes sont préfixées nice+ionice (dégradation propre)."""

    def test_prefixes_nice_and_ionice_when_available(self) -> None:
        with patch("omnis.jobs.nixos.shutil.which", return_value="/usr/bin/x"):
            out = _throttled(["nix", "build"])
        assert out == ["nice", "-n", "15", "ionice", "-c", "2", "-n", "7", "nix", "build"]

    def test_no_prefix_when_both_missing(self) -> None:
        with patch("omnis.jobs.nixos.shutil.which", return_value=None):
            assert _throttled(["nix", "copy"]) == ["nix", "copy"]

    def test_partial_degradation_nice_only(self) -> None:
        def which(name: str) -> str | None:
            return "/usr/bin/nice" if name == "nice" else None

        with patch("omnis.jobs.nixos.shutil.which", side_effect=which):
            assert _throttled(["nix", "copy"]) == ["nice", "-n", "15", "nix", "copy"]

    def test_partial_degradation_ionice_only(self) -> None:
        def which(name: str) -> str | None:
            return "/usr/bin/ionice" if name == "ionice" else None

        with patch("omnis.jobs.nixos.shutil.which", side_effect=which):
            assert _throttled(["nix", "copy"]) == ["ionice", "-c", "2", "-n", "7", "nix", "copy"]


class TestThrottleCores:
    """AXE 1 : le parallélisme suit ~80 % des cœurs de la machine."""

    def test_cores_is_80_percent_of_cpu_count(self) -> None:
        with patch("omnis.jobs.nixos.os.cpu_count", return_value=10):
            assert _throttle_cores() == 8  # int(10 * 0.8)

    def test_cores_never_below_one(self) -> None:
        with patch("omnis.jobs.nixos.os.cpu_count", return_value=1):
            assert _throttle_cores() == 1

    def test_cores_defaults_to_one_when_cpu_count_unknown(self) -> None:
        with patch("omnis.jobs.nixos.os.cpu_count", return_value=None):
            assert _throttle_cores() == 1

    def test_substitution_flags_cap_parallel_substitutions(self) -> None:
        from omnis.jobs.nixos import _substitution_flags

        with patch("omnis.jobs.nixos.os.cpu_count", return_value=4):
            # int(4 * 0.8) == 3 cores → 2 parallel substitutions (leaves headroom).
            assert _substitution_flags() == ["--option", "max-substitution-jobs", "2"]
        with patch("omnis.jobs.nixos.os.cpu_count", return_value=1):
            assert _substitution_flags() == ["--option", "max-substitution-jobs", "1"]


class TestIndeterminateInstall:
    """AXE 2 : barre honnête — indéterminée sans total, déterminée avec total."""

    @staticmethod
    def _recorder() -> tuple[JobContext, list[tuple[str, Any]]]:
        events: list[tuple[str, Any]] = []
        ctx = JobContext(target_root="/mnt/target")
        ctx.on_progress = lambda pct, _msg: events.append(("progress", pct))
        ctx.on_indeterminate = lambda active: events.append(("indet", active))
        return ctx, events

    @staticmethod
    def _popen_lines(lines: list[str], code: int = 0) -> Any:
        def fake_popen(_cmd: list[str], **_k: Any) -> MagicMock:
            proc = MagicMock()
            proc.stdout = iter([ln + "\n" for ln in lines])
            proc.wait.return_value = code
            return proc

        return fake_popen

    def test_indeterminate_without_total_freezes_pct_until_exit(self) -> None:
        job = NixosJob()
        ctx, events = self._recorder()
        lines = [
            "building '/nix/store/aaa-foo.drv'...",
            "copying path '/nix/store/bbb-bar' to '/mnt/target'...",
            "copying path '/nix/store/ccc-baz' to '/mnt/target'...",
        ]
        with patch("omnis.jobs.nixos.subprocess.Popen", side_effect=self._popen_lines(lines)):
            result = job._run_install_streamed(
                ["nixos-install"],
                "install",
                dry_run=False,
                context=ctx,
                pct_start=96,
                pct_end=100,
                closure_total=None,
                allow_indeterminate=True,
            )
        assert result.success is True
        indet = [active for kind, active in events if kind == "indet"]
        assert indet[0] is True
        assert indet[-1] is False
        prog = [pct for kind, pct in events if kind == "progress"]
        # pct_end (100) is only reached AFTER a clean exit (last progress event).
        assert prog[-1] == 100
        # During streaming the pct stays frozen at pct_start (no invented ramp).
        assert all(pct <= 96 for pct in prog[:-1])

    def test_determinate_with_total_advances_without_indeterminate(self) -> None:
        job = NixosJob()
        ctx, events = self._recorder()
        lines = [f"copying path '/nix/store/p{i}-x' to '/mnt/target'..." for i in range(4)]
        with patch("omnis.jobs.nixos.subprocess.Popen", side_effect=self._popen_lines(lines)):
            result = job._run_install_streamed(
                ["nixos-install"],
                "install",
                dry_run=False,
                context=ctx,
                pct_start=96,
                pct_end=100,
                closure_total=4,
                allow_indeterminate=True,
            )
        assert result.success is True
        # A reliable total ⇒ never indeterminate; the bar advances deterministically.
        assert not any(kind == "indet" for kind, _ in events)
        prog = [pct for kind, pct in events if kind == "progress"]
        assert prog and max(prog) <= 100

    def test_indeterminate_reset_and_no_full_pct_on_failure(self) -> None:
        job = NixosJob()
        ctx, events = self._recorder()
        lines = ["building '/nix/store/a-x.drv'..."]
        with patch(
            "omnis.jobs.nixos.subprocess.Popen", side_effect=self._popen_lines(lines, code=1)
        ):
            result = job._run_install_streamed(
                ["nixos-install"],
                "install",
                dry_run=False,
                context=ctx,
                pct_start=96,
                pct_end=100,
                closure_total=None,
                allow_indeterminate=True,
            )
        assert result.success is False
        indet = [active for kind, active in events if kind == "indet"]
        assert indet[0] is True
        assert indet[-1] is False
        prog = [pct for kind, pct in events if kind == "progress"]
        assert 100 not in prog  # never claims completion on a failed install

    def test_announced_total_switches_from_pulse_to_determinate(self) -> None:
        job = NixosJob()
        ctx, events = self._recorder()
        lines = [
            "these 2 derivations will be built:",
            "these 4 paths will be fetched (1.0 MiB download):",
            *[
                f"copying path '/nix/store/p{i}-x' from 'https://cache.nixos.org'..."
                for i in range(4)
            ],
        ]
        with patch("omnis.jobs.nixos.subprocess.Popen", side_effect=self._popen_lines(lines)):
            result = job._run_install_streamed(
                ["nixos-install"],
                "install",
                dry_run=False,
                context=ctx,
                pct_start=60,
                pct_end=100,
                closure_total=None,
                allow_indeterminate=True,
            )
        assert result.success is True
        indet = [active for kind, active in events if kind == "indet"]
        assert indet[0] is True and indet[-1] is False  # pulse, puis déterminé
        prog = [pct for kind, pct in events if kind == "progress"]
        # Total connu (2+4=6) ⇒ la barre dépasse pct_start au lieu de rester figée.
        assert max(prog[:-1]) > 60
