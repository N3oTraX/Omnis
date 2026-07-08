"""Unit tests for BootloaderJob."""

import subprocess
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

try:
    from omnis.jobs.base import JobContext, JobResult, JobStatus
    from omnis.jobs.bootloader import BootloaderJob

    HAS_BOOTLOADER_JOB = True
except ImportError:
    HAS_BOOTLOADER_JOB = False

# Skip entire module if omnis is not available
pytestmark = pytest.mark.skipif(not HAS_BOOTLOADER_JOB, reason="BootloaderJob not available")


# =============================================================================
# BootloaderJob Initialization Tests
# =============================================================================


class TestBootloaderJobInit:
    """Tests for BootloaderJob initialization."""

    def test_init_defaults(self) -> None:
        """BootloaderJob should have correct defaults."""
        job = BootloaderJob()
        assert job.name == "bootloader"
        assert job.description == "System bootloader installation"
        assert job.status == JobStatus.PENDING

    def test_init_with_config(self) -> None:
        """BootloaderJob should accept configuration."""
        config = {"timeout": 5}
        job = BootloaderJob(config)
        assert job._config == config

    def test_bootloader_constants(self) -> None:
        """BootloaderJob should define bootloader constants."""
        assert BootloaderJob.SYSTEMD_BOOT == "systemd-boot"
        assert BootloaderJob.GRUB == "grub"

    def test_estimate_duration(self) -> None:
        """estimate_duration should return reasonable value."""
        job = BootloaderJob()
        duration = job.estimate_duration()
        assert duration == 60


# =============================================================================
# EFI System Validation Tests
# =============================================================================


class TestValidateEfiSystem:
    """Tests for EFI system validation."""

    @patch("omnis.jobs.bootloader.Path")
    def test_validate_efi_system_no_efivars(self, mock_path: MagicMock) -> None:
        """Should fail if system not booted in UEFI mode."""
        job = BootloaderJob()

        # Mock efivars path not existing
        mock_efivars = MagicMock()
        mock_efivars.exists.return_value = False

        def path_side_effect(path_str: str) -> MagicMock:
            if "efivars" in str(path_str):
                return mock_efivars
            mock_other = MagicMock()
            mock_other.exists.return_value = False
            return mock_other

        mock_path.side_effect = path_side_effect

        context = JobContext(target_root="/mnt")
        result = job._validate_efi_system(context)

        assert result.success is False
        assert result.error_code == 50
        assert "UEFI mode" in result.message

    def test_validate_efi_system_efi_mounted(self) -> None:
        """Should succeed if EFI partition is mounted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create EFI mount point
            efi_mount = Path(tmpdir) / "boot" / "efi"
            efi_mount.mkdir(parents=True, exist_ok=True)

            job = BootloaderJob()

            with patch("omnis.jobs.bootloader.Path") as mock_path:
                # Mock efivars exists
                mock_efivars = MagicMock()
                mock_efivars.exists.return_value = True

                def path_side_effect(path_str: str) -> MagicMock:
                    if "efivars" in str(path_str):
                        return mock_efivars
                    if "boot/efi" in str(path_str):
                        mock_efi = MagicMock()
                        mock_efi.exists.return_value = True
                        mock_efi.__truediv__ = lambda *_: Path(tmpdir) / "boot" / "efi"
                        return efi_mount
                    mock_other = MagicMock()
                    mock_other.exists.return_value = False
                    mock_other.__truediv__ = lambda *_: MagicMock()
                    return mock_other

                mock_path.side_effect = path_side_effect

                context = JobContext(target_root=tmpdir)
                result = job._validate_efi_system(context)

                assert result.success is True
                assert job._efi_mount is not None

    @patch("omnis.jobs.bootloader.Path")
    def test_validate_efi_system_no_efi_mount(self, mock_path: MagicMock) -> None:
        """Should fail if EFI partition not mounted."""
        job = BootloaderJob()

        # Mock efivars exists but no EFI mount points
        mock_efivars = MagicMock()
        mock_efivars.exists.return_value = True

        # Create mock for target_root path
        mock_target = MagicMock()

        # Create mock for each possible EFI mount that doesn't exist
        mock_efi_mount = MagicMock()
        mock_efi_mount.exists.return_value = False

        # Mock __truediv__ to return mock_efi_mount for path divisions
        mock_target.__truediv__.return_value = mock_efi_mount
        mock_efi_mount.__truediv__.return_value = mock_efi_mount

        def path_side_effect(path_str: str) -> MagicMock:
            if "efivars" in str(path_str):
                return mock_efivars
            return mock_target

        mock_path.side_effect = path_side_effect

        context = JobContext(target_root="/mnt")
        result = job._validate_efi_system(context)

        assert result.success is False
        assert result.error_code == 51
        assert "not mounted" in result.message


# =============================================================================
# Kernel Detection Tests
# =============================================================================


class TestDetectKernels:
    """Tests for kernel detection."""

    def test_detect_kernels_success(self) -> None:
        """Should detect kernels in boot directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            boot_dir = Path(tmpdir) / "boot"
            boot_dir.mkdir(parents=True, exist_ok=True)

            # Create mock kernel files
            (boot_dir / "vmlinuz-6.1.0").touch()
            (boot_dir / "vmlinuz-6.1.1").touch()
            (boot_dir / "initramfs-6.1.0.img").touch()
            (boot_dir / "initramfs-6.1.1.img").touch()

            job = BootloaderJob()
            context = JobContext(target_root=tmpdir)

            result = job._detect_kernels(context)

            assert result.success is True
            assert len(job._kernels) == 2
            assert "vmlinuz-6.1.0" in job._kernels
            assert "vmlinuz-6.1.1" in job._kernels

    def test_detect_kernels_no_boot_dir(self) -> None:
        """Should fail if boot directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job = BootloaderJob()
            context = JobContext(target_root=tmpdir)

            result = job._detect_kernels(context)

            assert result.success is False
            assert result.error_code == 53
            assert "Boot directory not found" in result.message

    def test_detect_kernels_no_kernels(self) -> None:
        """Should fail if no kernel images found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            boot_dir = Path(tmpdir) / "boot"
            boot_dir.mkdir(parents=True, exist_ok=True)

            job = BootloaderJob()
            context = JobContext(target_root=tmpdir)

            result = job._detect_kernels(context)

            assert result.success is False
            assert result.error_code == 54
            assert "No kernel images found" in result.message

    def test_detect_kernels_missing_initramfs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Should warn if initramfs missing but not fail."""
        with tempfile.TemporaryDirectory() as tmpdir:
            boot_dir = Path(tmpdir) / "boot"
            boot_dir.mkdir(parents=True, exist_ok=True)

            # Create kernel without initramfs
            (boot_dir / "vmlinuz-6.1.0").touch()

            job = BootloaderJob()
            context = JobContext(target_root=tmpdir)

            result = job._detect_kernels(context)

            assert result.success is True
            assert len(job._kernels) == 1

            # Check warning was logged
            warnings = [rec.message for rec in caplog.records if rec.levelname == "WARNING"]
            assert any("Missing initramfs" in msg for msg in warnings)


# =============================================================================
# systemd-boot Installation Tests
# =============================================================================


class TestInstallSystemdBoot:
    """Tests for systemd-boot installation."""

    @patch("omnis.jobs.bootloader.BootloaderJob._create_systemd_boot_entries")
    @patch("omnis.jobs.bootloader.BootloaderJob._configure_systemd_boot_loader")
    @patch("omnis.jobs.bootloader.subprocess.run")
    def test_install_systemd_boot_success(
        self,
        mock_subprocess: MagicMock,
        mock_configure: MagicMock,
        mock_entries: MagicMock,
    ) -> None:
        """Should install systemd-boot successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job = BootloaderJob()
            job._efi_mount = Path(tmpdir) / "boot" / "efi"
            job._efi_mount.mkdir(parents=True, exist_ok=True)

            mock_subprocess.return_value = MagicMock(returncode=0, stdout="Success")
            mock_configure.return_value = JobResult.ok()
            mock_entries.return_value = JobResult.ok()

            context = JobContext(target_root=tmpdir)
            result = job._install_systemd_boot(context)

            assert result.success is True
            assert "systemd-boot installed" in result.message

            # Verify bootctl was called
            mock_subprocess.assert_called_once()
            call_args = mock_subprocess.call_args[0][0]
            assert "bootctl" in call_args
            assert "install" in call_args

    @patch("omnis.jobs.bootloader.subprocess.run")
    def test_install_systemd_boot_no_efi_mount(self, _mock_subprocess: MagicMock) -> None:
        """Should fail if EFI mount not initialized."""
        job = BootloaderJob()
        job._efi_mount = None

        context = JobContext(target_root="/mnt")
        result = job._install_systemd_boot(context)

        assert result.success is False
        assert result.error_code == 55

    @patch("omnis.jobs.bootloader.subprocess.run")
    def test_install_systemd_boot_command_fails(self, mock_subprocess: MagicMock) -> None:
        """Should handle bootctl failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job = BootloaderJob()
            job._efi_mount = Path(tmpdir) / "boot" / "efi"
            job._efi_mount.mkdir(parents=True, exist_ok=True)

            mock_subprocess.side_effect = subprocess.CalledProcessError(
                returncode=1, cmd=["bootctl"], stderr="Installation failed"
            )

            context = JobContext(target_root=tmpdir)
            result = job._install_systemd_boot(context)

            assert result.success is False
            assert result.error_code == 56
            assert "Failed to install systemd-boot" in result.message

    @patch("omnis.jobs.bootloader.subprocess.run")
    def test_install_systemd_boot_tool_not_found(self, mock_subprocess: MagicMock) -> None:
        """Should handle missing bootctl tool."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job = BootloaderJob()
            job._efi_mount = Path(tmpdir) / "boot" / "efi"
            job._efi_mount.mkdir(parents=True, exist_ok=True)

            mock_subprocess.side_effect = FileNotFoundError()

            context = JobContext(target_root=tmpdir)
            result = job._install_systemd_boot(context)

            assert result.success is False
            assert result.error_code == 57


# =============================================================================
# systemd-boot Configuration Tests
# =============================================================================


class TestConfigureSystemdBootLoader:
    """Tests for systemd-boot loader configuration."""

    def test_configure_loader_default_timeout(self) -> None:
        """Should create loader.conf with default timeout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job = BootloaderJob()
            job._efi_mount = Path(tmpdir) / "boot" / "efi"
            job._efi_mount.mkdir(parents=True, exist_ok=True)

            context = JobContext(target_root=tmpdir)
            result = job._configure_systemd_boot_loader(context)

            assert result.success is True

            loader_conf = job._efi_mount / "loader" / "loader.conf"
            assert loader_conf.exists()

            content = loader_conf.read_text()
            assert "timeout 3" in content
            assert "default arch.conf" in content
            assert "editor no" in content

    def test_configure_loader_custom_timeout(self) -> None:
        """Should respect custom timeout from config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job = BootloaderJob(config={"timeout": 10})
            job._efi_mount = Path(tmpdir) / "boot" / "efi"
            job._efi_mount.mkdir(parents=True, exist_ok=True)

            context = JobContext(target_root=tmpdir)
            result = job._configure_systemd_boot_loader(context)

            assert result.success is True

            loader_conf = job._efi_mount / "loader" / "loader.conf"
            content = loader_conf.read_text()
            assert "timeout 10" in content

    def test_configure_loader_no_efi_mount(self) -> None:
        """Should fail if EFI mount not initialized."""
        job = BootloaderJob()
        job._efi_mount = None

        context = JobContext(target_root="/mnt")
        result = job._configure_systemd_boot_loader(context)

        assert result.success is False
        assert result.error_code == 58


# =============================================================================
# systemd-boot Entries Tests
# =============================================================================


class TestCreateSystemdBootEntries:
    """Tests for systemd-boot boot entry creation."""

    @patch("omnis.jobs.bootloader.BootloaderJob._get_root_partition_uuid")
    def test_create_entries_single_kernel(self, mock_uuid: MagicMock) -> None:
        """Should create boot entry for single kernel."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup boot directory with kernel and initramfs
            boot_dir = Path(tmpdir) / "boot"
            boot_dir.mkdir(parents=True, exist_ok=True)
            (boot_dir / "vmlinuz-6.1.0").touch()
            (boot_dir / "initramfs-6.1.0.img").touch()

            job = BootloaderJob()
            job._efi_mount = Path(tmpdir) / "boot" / "efi"
            job._efi_mount.mkdir(parents=True, exist_ok=True)
            job._kernels = ["vmlinuz-6.1.0"]

            mock_uuid.return_value = "1234-5678"

            context = JobContext(target_root=tmpdir)
            result = job._create_systemd_boot_entries(context)

            assert result.success is True

            # Verify entry was created
            entries_dir = job._efi_mount / "loader" / "entries"
            entry_file = entries_dir / "arch-6.1.0.conf"
            assert entry_file.exists()

            content = entry_file.read_text()
            assert "linux   /vmlinuz-6.1.0" in content
            assert "initrd  /initramfs-6.1.0.img" in content
            assert "root=UUID=1234-5678" in content
            assert "quiet splash" in content

    @patch("omnis.jobs.bootloader.BootloaderJob._get_root_partition_uuid")
    def test_create_entries_multiple_kernels(self, mock_uuid: MagicMock) -> None:
        """Should create entries for multiple kernels."""
        with tempfile.TemporaryDirectory() as tmpdir:
            boot_dir = Path(tmpdir) / "boot"
            boot_dir.mkdir(parents=True, exist_ok=True)
            (boot_dir / "vmlinuz-6.1.0").touch()
            (boot_dir / "vmlinuz-6.1.1").touch()
            (boot_dir / "initramfs-6.1.0.img").touch()
            (boot_dir / "initramfs-6.1.1.img").touch()

            job = BootloaderJob()
            job._efi_mount = Path(tmpdir) / "boot" / "efi"
            job._efi_mount.mkdir(parents=True, exist_ok=True)
            job._kernels = ["vmlinuz-6.1.0", "vmlinuz-6.1.1"]

            mock_uuid.return_value = "1234-5678"

            context = JobContext(target_root=tmpdir)
            result = job._create_systemd_boot_entries(context)

            assert result.success is True

            # Verify both entries were created
            entries_dir = job._efi_mount / "loader" / "entries"
            assert (entries_dir / "arch-6.1.0.conf").exists()
            assert (entries_dir / "arch-6.1.1.conf").exists()

            # Verify default symlink points to latest
            default_link = entries_dir / "arch.conf"
            assert default_link.is_symlink()
            assert default_link.resolve().name == "arch-6.1.1.conf"

    @patch("omnis.jobs.bootloader.BootloaderJob._get_root_partition_uuid")
    def test_create_entries_custom_kernel_params(self, mock_uuid: MagicMock) -> None:
        """Should use custom kernel parameters if provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            boot_dir = Path(tmpdir) / "boot"
            boot_dir.mkdir(parents=True, exist_ok=True)
            (boot_dir / "vmlinuz-6.1.0").touch()
            (boot_dir / "initramfs-6.1.0.img").touch()

            job = BootloaderJob()
            job._efi_mount = Path(tmpdir) / "boot" / "efi"
            job._efi_mount.mkdir(parents=True, exist_ok=True)
            job._kernels = ["vmlinuz-6.1.0"]

            mock_uuid.return_value = "1234-5678"

            context = JobContext(
                target_root=tmpdir,
                selections={"kernel_params": "quiet loglevel=3 nowatchdog"},
            )
            result = job._create_systemd_boot_entries(context)

            assert result.success is True

            entry_file = job._efi_mount / "loader" / "entries" / "arch-6.1.0.conf"
            content = entry_file.read_text()
            assert "quiet loglevel=3 nowatchdog" in content

    @patch("omnis.jobs.bootloader.BootloaderJob._get_root_partition_uuid")
    def test_create_entries_no_root_uuid(self, mock_uuid: MagicMock) -> None:
        """Should fail if cannot determine root UUID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job = BootloaderJob()
            job._efi_mount = Path(tmpdir) / "boot" / "efi"
            job._efi_mount.mkdir(parents=True, exist_ok=True)
            job._kernels = ["vmlinuz-6.1.0"]

            mock_uuid.return_value = None

            context = JobContext(target_root=tmpdir)
            result = job._create_systemd_boot_entries(context)

            assert result.success is False
            assert result.error_code == 61


# =============================================================================
# GRUB Installation Tests
# =============================================================================


class TestInstallGrub:
    """Tests for GRUB installation."""

    @patch("omnis.jobs.bootloader.subprocess.run")
    def test_install_grub_success(self, mock_subprocess: MagicMock) -> None:
        """Should install GRUB successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job = BootloaderJob()
            job._efi_mount = Path(tmpdir) / "boot" / "efi"
            job._efi_mount.mkdir(parents=True, exist_ok=True)

            mock_subprocess.return_value = MagicMock(returncode=0, stdout="Success")

            context = JobContext(target_root=tmpdir)
            result = job._install_grub(context)

            assert result.success is True
            assert "GRUB installed" in result.message

            # Verify grub-install and grub-mkconfig were called
            assert mock_subprocess.call_count == 2
            calls = [str(call) for call in mock_subprocess.call_args_list]
            assert any("grub-install" in call for call in calls)
            assert any("grub-mkconfig" in call for call in calls)

    @patch("omnis.jobs.bootloader.subprocess.run")
    def test_install_grub_no_efi_mount(self, _mock_subprocess: MagicMock) -> None:
        """Should fail if EFI mount not initialized."""
        job = BootloaderJob()
        job._efi_mount = None

        context = JobContext(target_root="/mnt")
        result = job._install_grub(context)

        assert result.success is False
        assert result.error_code == 63

    @patch("omnis.jobs.bootloader.subprocess.run")
    def test_install_grub_install_fails(self, mock_subprocess: MagicMock) -> None:
        """Should handle grub-install failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job = BootloaderJob()
            job._efi_mount = Path(tmpdir) / "boot" / "efi"
            job._efi_mount.mkdir(parents=True, exist_ok=True)

            mock_subprocess.side_effect = subprocess.CalledProcessError(
                returncode=1, cmd=["grub-install"], stderr="Installation failed"
            )

            context = JobContext(target_root=tmpdir)
            result = job._install_grub(context)

            assert result.success is False
            assert result.error_code == 64

    @patch("omnis.jobs.bootloader.subprocess.run")
    def test_install_grub_mkconfig_fails(self, mock_subprocess: MagicMock) -> None:
        """Should handle grub-mkconfig failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job = BootloaderJob()
            job._efi_mount = Path(tmpdir) / "boot" / "efi"
            job._efi_mount.mkdir(parents=True, exist_ok=True)

            # First call (grub-install) succeeds, second (grub-mkconfig) fails
            def run_side_effect(*args: Any, **_kwargs: Any) -> MagicMock:
                cmd = args[0]
                if "grub-install" in cmd:
                    return MagicMock(returncode=0, stdout="Success")
                if "grub-mkconfig" in cmd:
                    raise subprocess.CalledProcessError(
                        returncode=1, cmd=cmd, stderr="Config generation failed"
                    )
                return MagicMock()

            mock_subprocess.side_effect = run_side_effect

            context = JobContext(target_root=tmpdir)
            result = job._install_grub(context)

            assert result.success is False
            assert result.error_code == 66


# =============================================================================
# Root UUID Detection Tests
# =============================================================================


class TestGetRootPartitionUuid:
    """Tests for root partition UUID detection."""

    def test_get_uuid_from_fstab(self) -> None:
        """Should read UUID from fstab."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fstab with UUID
            fstab_path = Path(tmpdir) / "etc" / "fstab"
            fstab_path.parent.mkdir(parents=True, exist_ok=True)
            fstab_content = """# /etc/fstab
UUID=1234-5678-abcd / ext4 rw,relatime 0 1
UUID=9999-0000-ffff /boot/efi vfat defaults 0 2
"""
            fstab_path.write_text(fstab_content)

            job = BootloaderJob()
            context = JobContext(target_root=tmpdir)

            uuid = job._get_root_partition_uuid(context)

            assert uuid == "1234-5678-abcd"

    @patch("omnis.jobs.bootloader.subprocess.run")
    def test_get_uuid_from_blkid(self, mock_subprocess: MagicMock) -> None:
        """Should fallback to blkid if fstab not available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job = BootloaderJob()

            # Mock findmnt and blkid
            def run_side_effect(*args: Any, **_kwargs: Any) -> MagicMock:
                cmd = args[0]
                if "findmnt" in cmd:
                    return MagicMock(stdout="/dev/sda2\n")
                if "blkid" in cmd:
                    return MagicMock(stdout="abcd-1234-efgh\n")
                return MagicMock()

            mock_subprocess.side_effect = run_side_effect

            context = JobContext(target_root=tmpdir)
            uuid = job._get_root_partition_uuid(context)

            assert uuid == "abcd-1234-efgh"

    @patch("omnis.jobs.bootloader.subprocess.run")
    def test_get_uuid_failure(self, mock_subprocess: MagicMock) -> None:
        """Should return None if UUID cannot be determined."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job = BootloaderJob()

            mock_subprocess.side_effect = subprocess.CalledProcessError(
                returncode=1, cmd=["findmnt"], stderr="Not found"
            )

            context = JobContext(target_root=tmpdir)
            uuid = job._get_root_partition_uuid(context)

            assert uuid is None


# =============================================================================
# Validation Tests
# =============================================================================


class TestValidate:
    """Tests for bootloader configuration validation."""

    def test_validate_invalid_bootloader(self) -> None:
        """Should fail with invalid bootloader selection."""
        job = BootloaderJob()
        context = JobContext(
            selections={
                "bootloader": "lilo",  # Not supported
            }
        )

        result = job.validate(context)

        assert result.success is False
        assert result.error_code == 67
        assert "Invalid bootloader" in result.message

    @patch("omnis.jobs.bootloader.BootloaderJob._detect_kernels")
    @patch("omnis.jobs.bootloader.BootloaderJob._validate_efi_system")
    def test_validate_efi_system_fails(
        self,
        mock_validate_efi: MagicMock,
        _mock_detect_kernels: MagicMock,
    ) -> None:
        """Should fail if EFI system validation fails."""
        job = BootloaderJob()

        mock_validate_efi.return_value = JobResult.fail("No EFI", error_code=50)

        context = JobContext(
            selections={"bootloader": "systemd-boot"},
            target_root="/mnt",
        )

        result = job.validate(context)

        assert result.success is False
        assert result.error_code == 50

    @patch("omnis.jobs.bootloader.BootloaderJob._detect_kernels")
    @patch("omnis.jobs.bootloader.BootloaderJob._validate_efi_system")
    def test_validate_kernel_detection_fails(
        self,
        mock_validate_efi: MagicMock,
        mock_detect_kernels: MagicMock,
    ) -> None:
        """Should fail if kernel detection fails."""
        job = BootloaderJob()

        mock_validate_efi.return_value = JobResult.ok()
        mock_detect_kernels.return_value = JobResult.fail("No kernels", error_code=54)

        context = JobContext(
            selections={"bootloader": "systemd-boot"},
            target_root="/mnt",
        )

        result = job.validate(context)

        assert result.success is False
        assert result.error_code == 54

    @patch("omnis.jobs.bootloader.BootloaderJob._detect_kernels")
    @patch("omnis.jobs.bootloader.BootloaderJob._validate_efi_system")
    def test_validate_success(
        self,
        mock_validate_efi: MagicMock,
        mock_detect_kernels: MagicMock,
    ) -> None:
        """Should pass validation with valid configuration."""
        job = BootloaderJob()
        job._efi_mount = Path("/mnt/boot/efi")
        job._kernels = ["vmlinuz-6.1.0"]

        mock_validate_efi.return_value = JobResult.ok()
        mock_detect_kernels.return_value = JobResult.ok()

        context = JobContext(
            selections={"bootloader": "systemd-boot"},
            target_root="/mnt",
        )

        result = job.validate(context)

        assert result.success is True
        assert result.data["bootloader"] == "systemd-boot"
        assert result.data["kernels"] == ["vmlinuz-6.1.0"]


# =============================================================================
# Full Job Execution Tests
# =============================================================================


class TestBootloaderJobRun:
    """Tests for full BootloaderJob execution."""

    @patch("omnis.jobs.bootloader.BootloaderJob._install_systemd_boot")
    @patch("omnis.jobs.bootloader.BootloaderJob.validate")
    def test_run_systemd_boot_success(
        self,
        mock_validate: MagicMock,
        mock_install: MagicMock,
    ) -> None:
        """Should run systemd-boot installation successfully."""
        job = BootloaderJob()
        job._efi_mount = Path("/mnt/boot/efi")
        job._kernels = ["vmlinuz-6.1.0"]

        mock_validate.return_value = JobResult.ok()
        mock_install.return_value = JobResult.ok()

        context = JobContext(
            target_root="/mnt",
            selections={"bootloader": "systemd-boot"},
        )
        context.on_progress = MagicMock()

        result = job.run(context)

        assert result.success is True
        assert "systemd-boot" in result.message
        assert context.on_progress.called
        mock_install.assert_called_once()

    @patch("omnis.jobs.bootloader.BootloaderJob._install_grub")
    @patch("omnis.jobs.bootloader.BootloaderJob.validate")
    def test_run_grub_success(
        self,
        mock_validate: MagicMock,
        mock_install: MagicMock,
    ) -> None:
        """Should run GRUB installation successfully."""
        job = BootloaderJob()
        job._efi_mount = Path("/mnt/boot/efi")
        job._kernels = ["vmlinuz-6.1.0"]

        mock_validate.return_value = JobResult.ok()
        mock_install.return_value = JobResult.ok()

        context = JobContext(
            target_root="/mnt",
            selections={"bootloader": "grub"},
        )
        context.on_progress = MagicMock()

        result = job.run(context)

        assert result.success is True
        assert "grub" in result.message.lower()
        mock_install.assert_called_once()

    @patch("omnis.jobs.bootloader.BootloaderJob.validate")
    def test_run_validation_fails(self, mock_validate: MagicMock) -> None:
        """Should fail if validation fails."""
        job = BootloaderJob()

        mock_validate.return_value = JobResult.fail("Validation failed", error_code=50)

        context = JobContext(
            target_root="/mnt",
            selections={"bootloader": "systemd-boot"},
        )

        result = job.run(context)

        assert result.success is False
        assert result.error_code == 50

    @patch("omnis.jobs.bootloader.BootloaderJob._install_systemd_boot")
    @patch("omnis.jobs.bootloader.BootloaderJob.validate")
    def test_run_installation_fails(
        self,
        mock_validate: MagicMock,
        mock_install: MagicMock,
    ) -> None:
        """Should propagate installation failures."""
        job = BootloaderJob()

        mock_validate.return_value = JobResult.ok()
        mock_install.return_value = JobResult.fail("Installation failed", error_code=56)

        context = JobContext(
            target_root="/mnt",
            selections={"bootloader": "systemd-boot"},
        )

        result = job.run(context)

        assert result.success is False
        assert result.error_code == 56

    @patch("omnis.jobs.bootloader.BootloaderJob.validate")
    def test_run_default_systemd_boot(self, mock_validate: MagicMock) -> None:
        """Should default to systemd-boot if not specified."""
        job = BootloaderJob()

        mock_validate.return_value = JobResult.ok()

        with patch.object(job, "_install_systemd_boot") as mock_install:
            mock_install.return_value = JobResult.ok()

            context = JobContext(
                target_root="/mnt",
                selections={},  # No bootloader specified
            )

            result = job.run(context)

            assert result.success is True
            mock_install.assert_called_once()


# =============================================================================
# Integration Tests
# =============================================================================


class TestBootloaderJobIntegration:
    """Integration tests for complete BootloaderJob workflow."""

    @patch("omnis.jobs.bootloader.subprocess.run")
    @patch("omnis.jobs.bootloader.Path")
    def test_full_systemd_boot_workflow(
        self,
        mock_path: MagicMock,
        mock_subprocess: MagicMock,
    ) -> None:
        """Test complete systemd-boot installation workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup directory structure
            boot_dir = Path(tmpdir) / "boot"
            boot_dir.mkdir(parents=True, exist_ok=True)
            (boot_dir / "vmlinuz-6.1.0").touch()
            (boot_dir / "initramfs-6.1.0.img").touch()

            efi_mount = Path(tmpdir) / "boot" / "efi"
            efi_mount.mkdir(parents=True, exist_ok=True)

            fstab_path = Path(tmpdir) / "etc" / "fstab"
            fstab_path.parent.mkdir(parents=True, exist_ok=True)
            fstab_path.write_text("UUID=test-uuid / ext4 defaults 0 1\n")

            # Mock Path for efivars check
            mock_efivars = MagicMock()
            mock_efivars.exists.return_value = True

            def path_side_effect(path_str: str) -> Path | MagicMock:
                if "efivars" in str(path_str):
                    return mock_efivars
                return Path(path_str)

            mock_path.side_effect = path_side_effect

            # Mock subprocess calls
            mock_subprocess.return_value = MagicMock(returncode=0, stdout="Success")

            # Create and run job
            job = BootloaderJob(config={"timeout": 5})
            context = JobContext(
                target_root=tmpdir,
                selections={
                    "bootloader": "systemd-boot",
                    "kernel_params": "quiet",
                },
            )

            result = job.run(context)

            assert result.success is True
            assert result.data["bootloader"] == "systemd-boot"

            # Verify configuration files were created
            loader_conf = efi_mount / "loader" / "loader.conf"
            assert loader_conf.exists()
            assert "timeout 5" in loader_conf.read_text()

            entry_file = efi_mount / "loader" / "entries" / "arch-6.1.0.conf"
            assert entry_file.exists()
            content = entry_file.read_text()
            assert "vmlinuz-6.1.0" in content
            assert "initramfs-6.1.0.img" in content
            assert "UUID=test-uuid" in content
