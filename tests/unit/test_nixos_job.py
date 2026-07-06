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
            patch.object(
                job, "_hash_password", side_effect=RuntimeError("no tool")
            ),
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

        def fake_popen(cmd: list[str], **_kwargs: Any) -> MagicMock:
            # nixos-install is streamed via Popen; record it in the same log.
            calls.append(cmd)
            proc = MagicMock()
            proc.stdout = iter([])
            proc.wait.return_value = 0
            return proc

        # Patch subprocess.run/Popen (command execution) and the config/flake
        # writing filesystem ops so nothing touches the real disk. The
        # stateVersion query is stubbed so ``calls`` is only the install sequence.
        with (
            patch.object(job, "_detect_state_version", return_value="25.11"),
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

        def fake_popen(_cmd: list[str], **_kwargs: Any) -> MagicMock:
            proc = MagicMock()
            proc.stdout = iter([])  # nixos-install emits no output in the stub
            proc.wait.return_value = 0
            return proc

        with (
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

    def test_fraction_is_monotonic(self) -> None:
        p = _NixProgress()
        p.feed('@nix {"action":"start","id":1,"type":104}')
        assert p.feed(self._build(1, 8, 10)) == 0.8
        # A newly discovered activity enlarges 'expected'; the fraction would dip
        # but must not move backwards.
        p.feed('@nix {"action":"start","id":2,"type":103}')
        assert p.feed(self._build(2, 0, 10)) is None
        assert p._fraction == 0.8
