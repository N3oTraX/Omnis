"""Unit tests for PartitionJob."""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

try:
    from omnis.jobs.base import JobContext, JobResult, JobStatus
    from omnis.jobs.partition import (
        DiskInfo,
        FilesystemType,
        PartitionInfo,
        PartitionJob,
        PartitionLayout,
        PartitionMode,
    )

    HAS_PARTITION_JOB = True
except ImportError:
    HAS_PARTITION_JOB = False

# Skip entire module if omnis is not available
pytestmark = pytest.mark.skipif(not HAS_PARTITION_JOB, reason="PartitionJob not available")


class TestPartitionJob:
    """Tests for PartitionJob basic functionality."""

    def test_init_defaults(self) -> None:
        """PartitionJob should have correct defaults."""
        job = PartitionJob()
        assert job.name == "partition"
        assert job.description == "Disk partitioning and formatting"
        assert job.status == JobStatus.PENDING

    def test_estimate_duration(self) -> None:
        """estimate_duration should return reasonable value."""
        job = PartitionJob()
        duration = job.estimate_duration()
        assert duration == 60


class TestEnums:
    """Tests for enum definitions."""

    def test_partition_mode_values(self) -> None:
        """PartitionMode should have correct values."""
        assert PartitionMode.AUTO.value == "auto"
        assert PartitionMode.MANUAL.value == "manual"

    def test_filesystem_type_values(self) -> None:
        """FilesystemType should have correct values."""
        assert FilesystemType.EXT4.value == "ext4"
        assert FilesystemType.BTRFS.value == "btrfs"


class TestDataClasses:
    """Tests for dataclass definitions."""

    def test_disk_info_creation(self) -> None:
        """DiskInfo should be creatable with required fields."""
        disk = DiskInfo(
            name="sda",
            path="/dev/sda",
            size=256 * 1024 * 1024 * 1024,
            size_human="256.0 GB",
        )
        assert disk.name == "sda"
        assert disk.path == "/dev/sda"
        assert disk.has_partitions is False
        assert disk.partitions == []

    def test_partition_info_creation(self) -> None:
        """PartitionInfo should be creatable with required fields."""
        partition = PartitionInfo(
            name="sda1",
            path="/dev/sda1",
            size=512 * 1024 * 1024,
            size_human="512.0 MB",
            fstype="vfat",
        )
        assert partition.name == "sda1"
        assert partition.has_data is False

    def test_partition_layout_defaults(self) -> None:
        """PartitionLayout should have sensible defaults."""
        layout = PartitionLayout()
        assert layout.efi_partition == ""
        assert layout.root_partition == ""
        assert layout.swap_partition == ""
        assert layout.efi_size_mb == 512
        assert layout.swap_size_mb == 0


class TestFormatSize:
    """Tests for _format_size() static method."""

    def test_format_bytes(self) -> None:
        """Format size should handle bytes."""
        assert "512.0 B" in PartitionJob._format_size(512)

    def test_format_kilobytes(self) -> None:
        """Format size should handle kilobytes."""
        assert "1.0 KB" in PartitionJob._format_size(1024)

    def test_format_megabytes(self) -> None:
        """Format size should handle megabytes."""
        assert "256.0 MB" in PartitionJob._format_size(256 * 1024 * 1024)

    def test_format_gigabytes(self) -> None:
        """Format size should handle gigabytes."""
        assert "128.0 GB" in PartitionJob._format_size(128 * 1024 * 1024 * 1024)


class TestListDisks:
    """Tests for _list_disks() method."""

    @patch("omnis.jobs.partition.subprocess.run")
    def test_list_disks_success(self, mock_subprocess: MagicMock) -> None:
        """_list_disks should parse lsblk JSON output."""
        job = PartitionJob()

        # Mock lsblk output
        lsblk_output = {
            "blockdevices": [
                {
                    "name": "sda",
                    "size": str(256 * 1024**3),
                    "type": "disk",
                    "model": "Samsung SSD",
                    "rm": "0",
                    "children": [
                        {
                            "name": "sda1",
                            "size": str(512 * 1024**2),
                            "type": "part",
                            "fstype": "vfat",
                            "mountpoint": None,
                        },
                        {
                            "name": "sda2",
                            "size": str(255 * 1024**3),
                            "type": "part",
                            "fstype": "ext4",
                            "mountpoint": "/",
                        },
                    ],
                },
                {
                    "name": "loop0",
                    "size": str(100 * 1024**2),
                    "type": "loop",
                },
            ]
        }

        mock_subprocess.return_value = MagicMock(
            stdout=json.dumps(lsblk_output),
            returncode=0,
        )

        disks = job._list_disks()

        # Should only return disk type (not loop)
        assert len(disks) == 1
        assert disks[0].name == "sda"
        assert disks[0].path == "/dev/sda"
        assert disks[0].model == "Samsung SSD"
        assert disks[0].has_partitions is True
        assert len(disks[0].partitions) == 2

        # Check partition details
        assert disks[0].partitions[0].name == "sda1"
        assert disks[0].partitions[0].fstype == "vfat"
        assert disks[0].partitions[0].has_data is True  # has fstype

    @patch("omnis.jobs.partition.subprocess.run")
    def test_list_disks_filters_removable(self, mock_subprocess: MagicMock) -> None:
        """_list_disks should filter out removable disks for safety."""
        job = PartitionJob()

        lsblk_output = {
            "blockdevices": [
                {
                    "name": "sdb",
                    "size": str(64 * 1024**3),
                    "type": "disk",
                    "model": "USB Drive",
                    "rm": "1",  # Removable - should be filtered out for safety
                }
            ]
        }

        mock_subprocess.return_value = MagicMock(
            stdout=json.dumps(lsblk_output),
            returncode=0,
        )

        disks = job._list_disks()

        # Removable disks are filtered out for safety (prevent accidental USB wipe)
        assert len(disks) == 0

    @patch("omnis.jobs.partition.subprocess.run")
    def test_list_disks_handles_no_partitions(self, mock_subprocess: MagicMock) -> None:
        """_list_disks should handle disks with no partitions."""
        job = PartitionJob()

        lsblk_output = {
            "blockdevices": [
                {
                    "name": "sda",
                    "size": str(256 * 1024**3),
                    "type": "disk",
                    "model": "Empty Disk",
                    "rm": "0",
                }
            ]
        }

        mock_subprocess.return_value = MagicMock(
            stdout=json.dumps(lsblk_output),
            returncode=0,
        )

        disks = job._list_disks()

        assert len(disks) == 1
        assert disks[0].has_partitions is False
        assert len(disks[0].partitions) == 0


class TestValidate:
    """Tests for the validate() method."""

    def test_validate_missing_disk(self) -> None:
        """validate should fail if disk is not specified."""
        job = PartitionJob()
        context = JobContext(selections={})

        result = job.validate(context)

        assert result.success is False
        assert result.error_code == 30
        assert "Disk selection is required" in result.message

    def test_validate_invalid_mode(self) -> None:
        """validate should fail for invalid partition mode."""
        job = PartitionJob()
        context = JobContext(
            selections={
                "disk": "/dev/sda",
                "mode": "invalid_mode",
            }
        )

        result = job.validate(context)

        assert result.success is False
        assert result.error_code == 31
        assert "Invalid partition mode" in result.message

    @patch("omnis.jobs.partition.Path")
    def test_validate_disk_not_found(self, mock_path: MagicMock) -> None:
        """validate should fail if disk doesn't exist."""
        job = PartitionJob()

        # Mock Path.exists() to return False
        mock_disk_path = MagicMock()
        mock_disk_path.exists.return_value = False
        mock_path.return_value = mock_disk_path

        context = JobContext(
            selections={
                "disk": "/dev/nonexistent",
            }
        )

        result = job.validate(context)

        assert result.success is False
        assert result.error_code == 32
        assert "Disk not found" in result.message

    @patch("omnis.jobs.partition.PartitionJob._list_disks")
    @patch("omnis.jobs.partition.Path")
    def test_validate_disk_too_small(
        self, mock_path: MagicMock, mock_list_disks: MagicMock
    ) -> None:
        """validate should fail if disk is smaller than 10 GB."""
        job = PartitionJob()

        mock_disk_path = MagicMock()
        mock_disk_path.exists.return_value = True
        mock_path.return_value = mock_disk_path

        # Mock disk with only 5 GB
        mock_list_disks.return_value = [
            DiskInfo(
                name="sda",
                path="/dev/sda",
                size=5 * 1024**3,
                size_human="5.0 GB",
            )
        ]

        context = JobContext(
            selections={
                "disk": "/dev/sda",
            }
        )

        result = job.validate(context)

        assert result.success is False
        assert result.error_code == 35
        assert "Disk too small" in result.message

    @patch("omnis.jobs.partition.PartitionJob._list_disks")
    @patch("omnis.jobs.partition.Path")
    def test_validate_detects_existing_data(
        self, mock_path: MagicMock, mock_list_disks: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """validate should warn about existing data but not fail."""
        job = PartitionJob()

        mock_disk_path = MagicMock()
        mock_disk_path.exists.return_value = True
        mock_path.return_value = mock_disk_path

        # Mock disk with existing partitions containing data
        mock_list_disks.return_value = [
            DiskInfo(
                name="sda",
                path="/dev/sda",
                size=256 * 1024**3,
                size_human="256.0 GB",
                has_partitions=True,
                partitions=[
                    PartitionInfo(
                        name="sda1",
                        path="/dev/sda1",
                        size=512 * 1024**2,
                        size_human="512.0 MB",
                        fstype="vfat",
                        has_data=True,
                    ),
                ],
            )
        ]

        context = JobContext(
            selections={
                "disk": "/dev/sda",
            }
        )

        result = job.validate(context)

        # Should pass validation but log warning
        assert result.success is True
        assert result.data["has_existing_data"] is True
        assert result.data["warnings"] == 1

        # Check warning was logged
        warning_messages = [rec.message for rec in caplog.records if rec.levelname == "WARNING"]
        assert any("EXISTING DATA DETECTED" in msg for msg in warning_messages)

    def test_validate_invalid_filesystem(self) -> None:
        """validate should fail for invalid filesystem type."""
        job = PartitionJob()

        with (
            patch("omnis.jobs.partition.Path") as mock_path,
            patch("omnis.jobs.partition.PartitionJob._list_disks") as mock_list_disks,
        ):
            mock_path.return_value.exists.return_value = True
            mock_list_disks.return_value = [
                DiskInfo(
                    name="sda",
                    path="/dev/sda",
                    size=256 * 1024**3,
                    size_human="256.0 GB",
                )
            ]

            context = JobContext(
                selections={
                    "disk": "/dev/sda",
                    "filesystem": "ntfs",  # Not supported
                }
            )

            result = job.validate(context)

            assert result.success is False
            assert result.error_code == 36
            assert "Invalid filesystem type" in result.message

    def test_validate_invalid_swap_size(self) -> None:
        """validate should fail for invalid swap size."""
        job = PartitionJob()

        with (
            patch("omnis.jobs.partition.Path") as mock_path,
            patch("omnis.jobs.partition.PartitionJob._list_disks") as mock_list_disks,
        ):
            mock_path.return_value.exists.return_value = True
            mock_list_disks.return_value = [
                DiskInfo(
                    name="sda",
                    path="/dev/sda",
                    size=256 * 1024**3,
                    size_human="256.0 GB",
                )
            ]

            context = JobContext(
                selections={
                    "disk": "/dev/sda",
                    "swap_size": -5,  # Negative
                }
            )

            result = job.validate(context)

            assert result.success is False
            assert result.error_code == 37


class TestSecurityGates:
    """Tests for critical security features."""

    def test_dry_run_default_true(self) -> None:
        """SECURITY: dry_run should default to True."""
        job = PartitionJob()

        with (
            patch.object(job, "validate") as mock_validate,
            patch.object(job, "_partition_auto") as mock_partition,
        ):
            mock_validate.return_value = JobResult.ok()
            mock_partition.return_value = JobResult.ok()

            context = JobContext(
                selections={
                    "disk": "/dev/sda",
                    # dry_run not specified - should default to True
                }
            )

            job.run(context)

            # Check that _partition_auto was called with dry_run=True
            call_args = mock_partition.call_args
            assert call_args.kwargs["dry_run"] is True

    def test_confirmed_default_false(self) -> None:
        """SECURITY: confirmed should default to False."""
        job = PartitionJob()

        with patch.object(job, "validate") as mock_validate:
            mock_validate.return_value = JobResult.ok()

            context = JobContext(
                selections={
                    "disk": "/dev/sda",
                    "dry_run": False,
                    # confirmed not specified - should default to False
                }
            )

            result = job.run(context)

            # Should fail due to missing confirmation
            assert result.success is False
            assert result.error_code == 38
            assert "explicit confirmation" in result.message

    def test_requires_confirmation_for_real_operations(self) -> None:
        """SECURITY: Real operations require both dry_run=False AND confirmed=True."""
        job = PartitionJob()

        with (
            patch.object(job, "validate") as mock_validate,
            patch.object(job, "_partition_auto") as mock_partition,
        ):
            mock_validate.return_value = JobResult.ok()
            mock_partition.return_value = JobResult.ok()

            # Test 1: dry_run=False without confirmed
            context = JobContext(
                selections={
                    "disk": "/dev/sda",
                    "dry_run": False,
                    "confirmed": False,
                }
            )

            result = job.run(context)
            assert result.success is False
            assert result.error_code == 38

            # Test 2: dry_run=False WITH confirmed
            context = JobContext(
                selections={
                    "disk": "/dev/sda",
                    "dry_run": False,
                    "confirmed": True,
                }
            )

            result = job.run(context)
            # Should succeed (calls _partition_auto)
            assert mock_partition.called

    def test_dry_run_blocks_real_operations(self) -> None:
        """SECURITY: dry_run mode should not execute real commands."""
        job = PartitionJob()

        # This test verifies _run_partitioning_command in dry_run mode
        result = job._run_partitioning_command(
            cmd=["parted", "-s", "/dev/sda", "mklabel", "gpt"],
            description="Creating GPT partition table",
            dry_run=True,
        )

        # Should return success without executing
        assert result.success is True
        assert "[DRY-RUN]" in result.message


class TestRunPartitioningCommand:
    """Tests for _run_partitioning_command() method."""

    def test_dry_run_logs_but_doesnt_execute(self, caplog: pytest.LogCaptureFixture) -> None:
        """_run_partitioning_command should log in dry-run mode but not execute."""
        import logging

        job = PartitionJob()

        # Capture logs at INFO level
        with caplog.at_level(logging.INFO):
            result = job._run_partitioning_command(
                cmd=["parted", "-s", "/dev/sda", "mklabel", "gpt"],
                description="Test operation",
                dry_run=True,
            )

        assert result.success is True
        assert "[DRY-RUN]" in result.message

        # Check it was logged
        log_messages = [rec.message for rec in caplog.records]
        assert any("[DRY-RUN]" in msg for msg in log_messages)

    @patch("omnis.jobs.partition.subprocess.run")
    def test_real_execution_success(self, mock_subprocess: MagicMock) -> None:
        """_run_partitioning_command should execute real commands when dry_run=False."""
        job = PartitionJob()

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="Success",
            stderr="",
        )

        result = job._run_partitioning_command(
            cmd=["parted", "-s", "/dev/sda", "mklabel", "gpt"],
            description="Test operation",
            dry_run=False,
        )

        assert result.success is True
        mock_subprocess.assert_called_once()

    @patch("omnis.jobs.partition.subprocess.run")
    def test_real_execution_failure(self, mock_subprocess: MagicMock) -> None:
        """_run_partitioning_command should handle command failures."""
        job = PartitionJob()

        mock_subprocess.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["parted"],
            stderr="Device or resource busy",
        )

        result = job._run_partitioning_command(
            cmd=["parted", "-s", "/dev/sda", "mklabel", "gpt"],
            description="Test operation",
            dry_run=False,
        )

        assert result.success is False
        assert result.error_code == 44
        assert "failed" in result.message

    @patch("omnis.jobs.partition.subprocess.run")
    def test_command_not_found(self, mock_subprocess: MagicMock) -> None:
        """_run_partitioning_command should handle missing commands."""
        job = PartitionJob()

        mock_subprocess.side_effect = FileNotFoundError()

        result = job._run_partitioning_command(
            cmd=["nonexistent_command"],
            description="Test operation",
            dry_run=False,
        )

        assert result.success is False
        assert result.error_code == 45
        assert "Required tool not found" in result.message


class TestPartitionAuto:
    """Tests for _partition_auto() method."""

    @patch("omnis.jobs.partition.PartitionJob._mount_partitions")
    @patch("omnis.jobs.partition.PartitionJob._format_partitions")
    @patch("omnis.jobs.partition.PartitionJob._run_partitioning_command")
    def test_partition_auto_creates_gpt_layout(
        self,
        mock_run_cmd: MagicMock,
        mock_format: MagicMock,
        mock_mount: MagicMock,
    ) -> None:
        """_partition_auto should create GPT with EFI and root partitions."""
        job = PartitionJob()

        mock_run_cmd.return_value = JobResult.ok()
        mock_format.return_value = JobResult.ok()
        mock_mount.return_value = JobResult.ok()

        context = JobContext()

        result = job._partition_auto(
            context=context,
            disk="/dev/sda",
            filesystem="ext4",
            swap_size_gb=0,
            dry_run=True,
        )

        assert result.success is True

        # Verify layout was created
        assert job._layout is not None
        assert job._layout.efi_partition == "/dev/sda1"
        assert job._layout.root_partition == "/dev/sda2"
        assert job._layout.swap_partition == ""  # No swap

        # Verify GPT creation was called
        calls = mock_run_cmd.call_args_list
        gpt_call = [c for c in calls if "mklabel" in str(c)]
        assert len(gpt_call) > 0

    @patch("omnis.jobs.partition.PartitionJob._mount_partitions")
    @patch("omnis.jobs.partition.PartitionJob._format_partitions")
    @patch("omnis.jobs.partition.PartitionJob._run_partitioning_command")
    def test_partition_auto_with_swap(
        self,
        mock_run_cmd: MagicMock,
        mock_format: MagicMock,
        mock_mount: MagicMock,
    ) -> None:
        """_partition_auto should create swap partition when requested."""
        job = PartitionJob()

        mock_run_cmd.return_value = JobResult.ok()
        mock_format.return_value = JobResult.ok()
        mock_mount.return_value = JobResult.ok()

        context = JobContext()

        result = job._partition_auto(
            context=context,
            disk="/dev/sda",
            filesystem="ext4",
            swap_size_gb=8,  # 8 GB swap
            dry_run=True,
        )

        assert result.success is True
        assert job._layout is not None
        assert job._layout.swap_partition == "/dev/sda3"
        assert job._layout.swap_size_mb == 8 * 1024

        # Verify swap partition creation was called
        calls = mock_run_cmd.call_args_list
        swap_calls = [c for c in calls if "linux-swap" in str(c)]
        assert len(swap_calls) > 0

    @patch("omnis.jobs.partition.PartitionJob._run_partitioning_command")
    def test_partition_auto_failure_propagates(self, mock_run_cmd: MagicMock) -> None:
        """_partition_auto should propagate failures from partitioning commands."""
        job = PartitionJob()

        # Simulate failure on first command
        mock_run_cmd.return_value = JobResult.fail("Partitioning failed", error_code=44)

        context = JobContext()

        result = job._partition_auto(
            context=context,
            disk="/dev/sda",
            filesystem="ext4",
            swap_size_gb=0,
            dry_run=True,
        )

        assert result.success is False
        assert result.error_code == 44


class TestFormatPartitions:
    """Tests for _format_partitions() method."""

    @patch("omnis.jobs.partition.PartitionJob._run_partitioning_command")
    def test_format_partitions_efi_and_root(self, mock_run_cmd: MagicMock) -> None:
        """_format_partitions should format EFI (FAT32) and root (ext4)."""
        job = PartitionJob()
        job._layout = PartitionLayout(
            efi_partition="/dev/sda1",
            root_partition="/dev/sda2",
        )

        mock_run_cmd.return_value = JobResult.ok()

        context = JobContext()
        result = job._format_partitions(context, "ext4", dry_run=True)

        assert result.success is True

        # Verify mkfs.fat was called for EFI
        calls = mock_run_cmd.call_args_list
        fat_calls = [c for c in calls if "mkfs.fat" in str(c)]
        assert len(fat_calls) == 1

        # Verify mkfs.ext4 was called for root
        ext4_calls = [c for c in calls if "mkfs.ext4" in str(c)]
        assert len(ext4_calls) == 1

    @patch("omnis.jobs.partition.PartitionJob._run_partitioning_command")
    def test_format_partitions_btrfs(self, mock_run_cmd: MagicMock) -> None:
        """_format_partitions should support btrfs filesystem."""
        job = PartitionJob()
        job._layout = PartitionLayout(
            efi_partition="/dev/sda1",
            root_partition="/dev/sda2",
        )

        mock_run_cmd.return_value = JobResult.ok()

        context = JobContext()
        result = job._format_partitions(context, "btrfs", dry_run=True)

        assert result.success is True

        # Verify mkfs.btrfs was called
        calls = mock_run_cmd.call_args_list
        btrfs_calls = [c for c in calls if "mkfs.btrfs" in str(c)]
        assert len(btrfs_calls) == 1

    @patch("omnis.jobs.partition.PartitionJob._run_partitioning_command")
    def test_format_partitions_with_swap(self, mock_run_cmd: MagicMock) -> None:
        """_format_partitions should format swap partition if present."""
        job = PartitionJob()
        job._layout = PartitionLayout(
            efi_partition="/dev/sda1",
            root_partition="/dev/sda2",
            swap_partition="/dev/sda3",
        )

        mock_run_cmd.return_value = JobResult.ok()

        context = JobContext()
        result = job._format_partitions(context, "ext4", dry_run=True)

        assert result.success is True

        # Verify mkswap was called
        calls = mock_run_cmd.call_args_list
        swap_calls = [c for c in calls if "mkswap" in str(c)]
        assert len(swap_calls) == 1

    def test_format_partitions_no_layout(self) -> None:
        """_format_partitions should fail if layout not initialized."""
        job = PartitionJob()
        job._layout = None

        context = JobContext()
        result = job._format_partitions(context, "ext4", dry_run=True)

        assert result.success is False
        assert result.error_code == 40

    def test_format_partitions_unsupported_filesystem(self) -> None:
        """_format_partitions should fail for unsupported filesystem."""
        job = PartitionJob()
        job._layout = PartitionLayout(
            efi_partition="/dev/sda1",
            root_partition="/dev/sda2",
        )

        with patch("omnis.jobs.partition.PartitionJob._run_partitioning_command") as mock_run_cmd:
            mock_run_cmd.return_value = JobResult.ok()

            context = JobContext()
            result = job._format_partitions(context, "xfs", dry_run=True)

            assert result.success is False
            assert result.error_code == 41


class TestMountPartitions:
    """Tests for _mount_partitions() method."""

    @patch("omnis.jobs.partition.PartitionJob._run_partitioning_command")
    def test_mount_partitions_success_dry_run(self, mock_run_cmd: MagicMock) -> None:
        """_mount_partitions should mount root and EFI in dry-run."""
        job = PartitionJob()
        job._layout = PartitionLayout(
            efi_partition="/dev/sda1",
            root_partition="/dev/sda2",
        )

        mock_run_cmd.return_value = JobResult.ok()

        context = JobContext(target_root="/mnt")
        result = job._mount_partitions(context, dry_run=True)

        assert result.success is True

        # Verify mount commands were called
        calls = mock_run_cmd.call_args_list
        mount_calls = [c for c in calls if "mount" in str(c)]
        assert len(mount_calls) >= 2  # root + EFI

    @patch("omnis.jobs.partition.Path")
    @patch("omnis.jobs.partition.PartitionJob._run_partitioning_command")
    def test_mount_partitions_creates_efi_mountpoint(
        self, mock_run_cmd: MagicMock, mock_path: MagicMock
    ) -> None:
        """_mount_partitions should create /boot/efi directory."""
        job = PartitionJob()
        job._layout = PartitionLayout(
            efi_partition="/dev/sda1",
            root_partition="/dev/sda2",
        )

        mock_run_cmd.return_value = JobResult.ok()

        # Mock Path to track mkdir call
        mock_efi_mount = MagicMock()
        mock_path.return_value.__truediv__.return_value.__truediv__.return_value = mock_efi_mount

        context = JobContext(target_root="/mnt")
        result = job._mount_partitions(context, dry_run=False)

        assert result.success is True
        mock_efi_mount.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("omnis.jobs.partition.PartitionJob._run_partitioning_command")
    def test_mount_partitions_with_swap(self, mock_run_cmd: MagicMock) -> None:
        """_mount_partitions should activate swap if present."""
        job = PartitionJob()
        job._layout = PartitionLayout(
            efi_partition="/dev/sda1",
            root_partition="/dev/sda2",
            swap_partition="/dev/sda3",
        )

        mock_run_cmd.return_value = JobResult.ok()

        context = JobContext(target_root="/mnt")
        result = job._mount_partitions(context, dry_run=True)

        assert result.success is True

        # Verify swapon was called
        calls = mock_run_cmd.call_args_list
        swap_calls = [c for c in calls if "swapon" in str(c)]
        assert len(swap_calls) == 1

    @patch("omnis.jobs.partition.PartitionJob._run_partitioning_command")
    def test_mount_partitions_swap_failure_not_critical(
        self, mock_run_cmd: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """_mount_partitions should continue if swap activation fails."""
        job = PartitionJob()
        job._layout = PartitionLayout(
            efi_partition="/dev/sda1",
            root_partition="/dev/sda2",
            swap_partition="/dev/sda3",
        )

        # Make only swapon fail - use **kwargs since method is called with keyword args
        def run_cmd_side_effect(cmd: list[str], **_kwargs: object) -> JobResult:
            if "swapon" in cmd:
                return JobResult.fail("Swap activation failed")
            return JobResult.ok()

        mock_run_cmd.side_effect = run_cmd_side_effect

        context = JobContext(target_root="/mnt")
        result = job._mount_partitions(context, dry_run=True)

        # Should still succeed
        assert result.success is True

        # Should log warning
        warnings = [rec.message for rec in caplog.records if rec.levelname == "WARNING"]
        assert any("Failed to activate swap" in msg for msg in warnings)


class TestCleanup:
    """Tests for cleanup() method."""

    @patch("omnis.jobs.partition.subprocess.run")
    def test_cleanup_unmounts_filesystems(self, mock_subprocess: MagicMock) -> None:
        """cleanup should attempt to unmount all mounted filesystems."""
        job = PartitionJob()
        job._layout = PartitionLayout(
            efi_partition="/dev/sda1",
            root_partition="/dev/sda2",
        )

        mock_subprocess.return_value = MagicMock(returncode=0)

        context = JobContext(target_root="/mnt")
        job.cleanup(context)

        # Should attempt to unmount EFI and root
        calls = mock_subprocess.call_args_list
        umount_calls = [c for c in calls if "umount" in str(c)]
        assert len(umount_calls) >= 2

    @patch("omnis.jobs.partition.subprocess.run")
    def test_cleanup_deactivates_swap(self, mock_subprocess: MagicMock) -> None:
        """cleanup should deactivate swap if present."""
        job = PartitionJob()
        job._layout = PartitionLayout(
            efi_partition="/dev/sda1",
            root_partition="/dev/sda2",
            swap_partition="/dev/sda3",
        )

        mock_subprocess.return_value = MagicMock(returncode=0)

        context = JobContext(target_root="/mnt")
        job.cleanup(context)

        # Should attempt to swapoff
        calls = mock_subprocess.call_args_list
        swap_calls = [c for c in calls if "swapoff" in str(c)]
        assert len(swap_calls) == 1

    @patch("omnis.jobs.partition.subprocess.run")
    def test_cleanup_handles_errors_gracefully(
        self, mock_subprocess: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """cleanup should handle unmount errors gracefully."""
        import logging

        job = PartitionJob()
        job._layout = PartitionLayout(
            efi_partition="/dev/sda1",
            root_partition="/dev/sda2",
        )

        # Make subprocess fail
        mock_subprocess.side_effect = Exception("Unmount failed")

        context = JobContext(target_root="/mnt")

        # Capture logs at DEBUG level
        with caplog.at_level(logging.DEBUG):
            # Should not raise exception
            job.cleanup(context)

        # Errors should be logged at debug level
        debug_logs = [rec.message for rec in caplog.records if rec.levelname == "DEBUG"]
        assert any("Failed to unmount" in msg for msg in debug_logs)

    def test_cleanup_no_layout(self) -> None:
        """cleanup should handle case where layout was never created."""
        job = PartitionJob()
        job._layout = None

        context = JobContext()

        # Should not raise exception
        job.cleanup(context)


class TestRunMethod:
    """Tests for the run() method integration."""

    @patch("omnis.jobs.partition.PartitionJob._partition_auto")
    @patch("omnis.jobs.partition.PartitionJob.validate")
    def test_run_validates_first(self, mock_validate: MagicMock, mock_partition: MagicMock) -> None:
        """run should validate configuration before proceeding."""
        job = PartitionJob()

        mock_validate.return_value = JobResult.fail("Validation failed", error_code=30)

        context = JobContext(
            selections={
                "disk": "/dev/sda",
            }
        )

        result = job.run(context)

        # Should fail at validation
        assert result.success is False
        assert result.error_code == 30

        # Should not call partitioning
        mock_partition.assert_not_called()

    @patch("omnis.jobs.partition.PartitionJob._partition_auto")
    @patch("omnis.jobs.partition.PartitionJob.validate")
    def test_run_manual_mode_not_implemented(
        self, mock_validate: MagicMock, _mock_partition: MagicMock
    ) -> None:
        """run should fail for manual mode (not yet implemented)."""
        job = PartitionJob()

        mock_validate.return_value = JobResult.ok()

        context = JobContext(
            selections={
                "disk": "/dev/sda",
                "mode": "manual",
                "dry_run": False,
                "confirmed": True,
            }
        )

        result = job.run(context)

        assert result.success is False
        assert result.error_code == 39
        assert "Manual partitioning mode not yet implemented" in result.message

    @patch("omnis.jobs.partition.PartitionJob._partition_auto")
    @patch("omnis.jobs.partition.PartitionJob.validate")
    def test_run_auto_mode_success(
        self, mock_validate: MagicMock, mock_partition: MagicMock
    ) -> None:
        """run should execute automatic partitioning successfully."""
        job = PartitionJob()

        mock_validate.return_value = JobResult.ok()
        mock_partition.return_value = JobResult.ok()

        # Set layout for result data
        job._layout = PartitionLayout(
            efi_partition="/dev/sda1",
            root_partition="/dev/sda2",
        )

        context = JobContext(
            selections={
                "disk": "/dev/sda",
                "mode": "auto",
                "filesystem": "ext4",
                "swap_size": 8,
            }
        )

        result = job.run(context)

        assert result.success is True
        assert "partitioned successfully" in result.message
        assert result.data["disk"] == "/dev/sda"
        assert result.data["layout"]["efi"] == "/dev/sda1"
        assert result.data["layout"]["root"] == "/dev/sda2"
