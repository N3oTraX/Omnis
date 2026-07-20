"""Unit tests for PartitionJob."""

import logging
import subprocess
from typing import Any
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
        part_path,
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
    """Tests for _list_disks() method (delegates to disk_detector)."""

    @patch("omnis.jobs.partition.disk_detector.list_disks")
    def test_list_disks_adapts_detector_output(self, mock_list: MagicMock) -> None:
        """_list_disks should adapt detector dicts into DiskInfo dataclasses."""
        job = PartitionJob()

        mock_list.return_value = [
            {
                "name": "sda",
                "model": "Samsung SSD",
                "size": "256.0 GB",
                "sizeBytes": 256 * 1024**3,
                "type": "SSD",
                "removable": False,
                "partitions": [
                    {
                        "name": "sda1",
                        "sizeBytes": 512 * 1024**2,
                        "fstype": "vfat",
                        "partType": "efi",
                    },
                    {
                        "name": "sda2",
                        "sizeBytes": 255 * 1024**3,
                        "fstype": "ext4",
                        "partType": "linux",
                    },
                ],
            }
        ]

        disks = job._list_disks()

        assert len(disks) == 1
        assert disks[0].name == "sda"
        assert disks[0].path == "/dev/sda"
        assert disks[0].model == "Samsung SSD"
        assert disks[0].size == 256 * 1024**3
        assert disks[0].has_partitions is True
        assert len(disks[0].partitions) == 2

        # Check partition adaptation
        assert disks[0].partitions[0].name == "sda1"
        assert disks[0].partitions[0].path == "/dev/sda1"
        assert disks[0].partitions[0].fstype == "vfat"
        assert disks[0].partitions[0].has_data is True  # has fstype

    @patch("omnis.jobs.partition.disk_detector.list_disks")
    def test_list_disks_handles_no_partitions(self, mock_list: MagicMock) -> None:
        """_list_disks should handle disks with no partitions."""
        job = PartitionJob()

        mock_list.return_value = [
            {
                "name": "sda",
                "model": "Empty Disk",
                "size": "256.0 GB",
                "sizeBytes": 256 * 1024**3,
                "type": "SSD",
                "removable": False,
                "partitions": [],
            }
        ]

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

    def test_real_run_unmounts_target_before_partitioning(self) -> None:
        """A leftover mount from a previous attempt is torn down before wiping."""
        job = PartitionJob()

        with (
            patch.object(job, "validate") as mock_validate,
            patch.object(job, "_partition_auto") as mock_partition,
            patch("omnis.jobs.partition.subprocess.run") as mock_run,
        ):
            mock_validate.return_value = JobResult.ok()
            mock_partition.return_value = JobResult.ok()

            context = JobContext(
                selections={"disk": "/dev/sda", "dry_run": False, "confirmed": True}
            )
            job.run(context)

            umount_calls = [
                c for c in mock_run.call_args_list if c.args and c.args[0][:2] == ["umount", "-R"]
            ]
            assert umount_calls, "expected a recursive umount before partitioning"
            assert umount_calls[0].args[0][2] == context.target_root

    def test_dry_run_does_not_unmount_target(self) -> None:
        """Dry-run must not touch mounts."""
        job = PartitionJob()

        with (
            patch.object(job, "validate") as mock_validate,
            patch.object(job, "_partition_auto") as mock_partition,
            patch("omnis.jobs.partition.subprocess.run") as mock_run,
        ):
            mock_validate.return_value = JobResult.ok()
            mock_partition.return_value = JobResult.ok()

            context = JobContext(selections={"disk": "/dev/sda", "dry_run": True})
            job.run(context)

            assert not [
                c for c in mock_run.call_args_list if c.args and c.args[0][:2] == ["umount", "-R"]
            ]

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
            patch.object(job, "_release_target_disk", return_value=None),
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
            selections={"swap_strategy": "none"},
            passphrase="",
            dry_run=True,
        )

        assert result.success is True

        # Verify layout was created
        assert job._layout is not None
        assert job._layout.efi_partition == "/dev/sda1"
        assert job._layout.root_partition == "/dev/sda2"
        assert job._layout.swap_partition == ""  # No swap partition

        # Verify GPT creation was called
        calls = mock_run_cmd.call_args_list
        gpt_call = [c for c in calls if "mklabel" in str(c)]
        assert len(gpt_call) > 0

    @patch("omnis.jobs.partition.PartitionJob._mount_partitions")
    @patch("omnis.jobs.partition.PartitionJob._format_partitions")
    @patch("omnis.jobs.partition.PartitionJob._run_partitioning_command")
    def test_partition_auto_legacy_swap_partition(
        self,
        mock_run_cmd: MagicMock,
        mock_format: MagicMock,
        mock_mount: MagicMock,
    ) -> None:
        """_partition_auto should create a swap PARTITION for legacy swap_size."""
        job = PartitionJob()

        mock_run_cmd.return_value = JobResult.ok()
        mock_format.return_value = JobResult.ok()
        mock_mount.return_value = JobResult.ok()

        context = JobContext()

        result = job._partition_auto(
            context=context,
            disk="/dev/sda",
            filesystem="ext4",
            selections={"swap_size": 8},  # legacy GB partition path
            passphrase="",
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
            selections={"swap_strategy": "none"},
            passphrase="",
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
        result = job._mount_partitions(context, "ext4", dry_run=True)

        assert result.success is True

        # Verify mount commands were called with an explicit filesystem type
        # (``mount -t`` avoids stale-blkid auto-detection failures).
        calls = [c.args[0] for c in mock_run_cmd.call_args_list if c.args]
        mount_calls = [cmd for cmd in calls if cmd and cmd[0] == "mount"]
        assert len(mount_calls) >= 2  # root + EFI
        root_mount = next(c for c in mount_calls if c[-1] == "/mnt")
        assert root_mount[:3] == ["mount", "-t", "ext4"]
        efi_mount = next(c for c in mount_calls if str(c[-1]).endswith("boot"))
        assert efi_mount[:3] == ["mount", "-t", "vfat"]

    @patch("omnis.jobs.partition.Path")
    @patch("omnis.jobs.partition.PartitionJob._run_partitioning_command")
    def test_mount_partitions_creates_efi_mountpoint(
        self, mock_run_cmd: MagicMock, mock_path: MagicMock
    ) -> None:
        """_mount_partitions should create the ESP mount point (/boot for NixOS)."""
        job = PartitionJob()
        job._layout = PartitionLayout(
            efi_partition="/dev/sda1",
            root_partition="/dev/sda2",
        )

        mock_run_cmd.return_value = JobResult.ok()

        # ESP is now mounted on <target_root>/boot (single path join).
        mock_efi_mount = MagicMock()
        mock_path.return_value.__truediv__.return_value = mock_efi_mount

        context = JobContext(target_root="/mnt")
        result = job._mount_partitions(context, "ext4", dry_run=False)

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
        result = job._mount_partitions(context, "ext4", dry_run=True)

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
        result = job._mount_partitions(context, "ext4", dry_run=True)

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


class TestPartPath:
    """Tests for the part_path() helper (NVMe/eMMC separator handling)."""

    def test_sata_disk(self) -> None:
        """SATA/SCSI disks have no 'p' separator."""
        assert part_path("/dev/sda", 1) == "/dev/sda1"
        assert part_path("/dev/sda", 2) == "/dev/sda2"

    def test_nvme_disk(self) -> None:
        """NVMe disks (name ends with digit) require a 'p' separator."""
        assert part_path("/dev/nvme0n1", 1) == "/dev/nvme0n1p1"
        assert part_path("/dev/nvme0n1", 3) == "/dev/nvme0n1p3"

    def test_emmc_disk(self) -> None:
        """eMMC disks require a 'p' separator."""
        assert part_path("/dev/mmcblk0", 1) == "/dev/mmcblk0p1"

    def test_loop_disk(self) -> None:
        """Loop devices end with a digit -> 'p' separator."""
        assert part_path("/dev/loop0", 1) == "/dev/loop0p1"


class TestPartitionAutoSequence:
    """Tests for the AUTO partitioning command ordering and ESP mount target."""

    @patch("omnis.jobs.partition.PartitionJob._mount_partitions")
    @patch("omnis.jobs.partition.PartitionJob._format_partitions")
    @patch("omnis.jobs.partition.PartitionJob._run_partitioning_command")
    def test_wipe_label_settle_order(
        self,
        mock_run_cmd: MagicMock,
        mock_format: MagicMock,
        mock_mount: MagicMock,
    ) -> None:
        """wipefs -> sgdisk --zap-all -> mklabel -> mkpart -> partprobe -> settle."""
        job = PartitionJob()
        mock_run_cmd.return_value = JobResult.ok()
        mock_format.return_value = JobResult.ok()
        mock_mount.return_value = JobResult.ok()

        result = job._partition_auto(
            context=JobContext(),
            disk="/dev/sda",
            filesystem="ext4",
            selections={"swap_strategy": "none"},
            passphrase="",
            dry_run=True,
        )
        assert result.success is True

        # Flatten the issued command lines in order.
        issued = [list(c.args[0]) for c in mock_run_cmd.call_args_list]

        def index_of(token: str) -> int:
            for i, cmd in enumerate(issued):
                if token in cmd or any(token in part for part in cmd):
                    return i
            return -1

        i_wipefs = index_of("wipefs")
        i_sgdisk = index_of("--zap-all")
        i_mklabel = index_of("mklabel")
        i_mkpart = index_of("mkpart")
        i_partprobe = index_of("partprobe")
        i_settle = index_of("settle")

        assert -1 not in (i_wipefs, i_sgdisk, i_mklabel, i_mkpart, i_partprobe, i_settle)
        assert i_wipefs < i_sgdisk < i_mklabel < i_mkpart < i_partprobe < i_settle

        # _format_partitions (mkfs) must run only AFTER settle.
        assert mock_format.called

    @patch("omnis.jobs.partition.PartitionJob._run_partitioning_command")
    def test_esp_mounted_on_boot(self, mock_run_cmd: MagicMock) -> None:
        """ESP must be mounted to a path ending in /boot (not /boot/efi)."""
        job = PartitionJob()
        job._layout = PartitionLayout(
            efi_partition="/dev/sda1",
            root_partition="/dev/sda2",
        )
        mock_run_cmd.return_value = JobResult.ok()

        result = job._mount_partitions(JobContext(target_root="/mnt"), "ext4", dry_run=True)
        assert result.success is True

        # Find the mount command that targets the EFI partition.
        efi_mounts = [
            list(c.args[0])
            for c in mock_run_cmd.call_args_list
            if "mount" in c.args[0] and "/dev/sda1" in c.args[0]
        ]
        assert len(efi_mounts) == 1
        target = efi_mounts[0][-1]
        assert target.endswith("/boot")
        assert not target.endswith("/boot/efi")


class TestSwapStrategy:
    """Tests for swap_strategy handling (none/file/hibernate)."""

    @patch("omnis.jobs.partition.PartitionJob._mount_partitions")
    @patch("omnis.jobs.partition.PartitionJob._format_partitions")
    @patch("omnis.jobs.partition.PartitionJob._run_partitioning_command")
    def test_swap_none_creates_nothing(
        self,
        mock_run_cmd: MagicMock,
        mock_format: MagicMock,
        mock_mount: MagicMock,
    ) -> None:
        """swap_strategy=none: no swap partition and no swapfile."""
        job = PartitionJob()
        mock_run_cmd.return_value = JobResult.ok()
        mock_format.return_value = JobResult.ok()
        mock_mount.return_value = JobResult.ok()

        result = job._partition_auto(
            context=JobContext(),
            disk="/dev/sda",
            filesystem="ext4",
            selections={"swap_strategy": "none"},
            passphrase="",
            dry_run=True,
        )
        assert result.success is True
        assert job._layout is not None
        assert job._layout.swap_partition == ""

        issued = [str(c) for c in mock_run_cmd.call_args_list]
        assert not any("linux-swap" in c for c in issued)
        assert not any("swapfile" in c for c in issued)

    @patch("omnis.jobs.partition.PartitionJob._mount_partitions")
    @patch("omnis.jobs.partition.PartitionJob._format_partitions")
    @patch("omnis.jobs.partition.PartitionJob._run_partitioning_command")
    def test_swap_file_creates_swapfile(
        self,
        mock_run_cmd: MagicMock,
        mock_format: MagicMock,
        mock_mount: MagicMock,
    ) -> None:
        """swap_strategy=file: a swapfile is allocated, formatted and activated."""
        job = PartitionJob()
        mock_run_cmd.return_value = JobResult.ok()
        mock_format.return_value = JobResult.ok()
        mock_mount.return_value = JobResult.ok()

        result = job._partition_auto(
            context=JobContext(target_root="/mnt"),
            disk="/dev/sda",
            filesystem="ext4",
            selections={"swap_strategy": "file"},
            passphrase="",
            dry_run=True,
        )
        assert result.success is True

        issued = [list(c.args[0]) for c in mock_run_cmd.call_args_list]
        flat = [" ".join(cmd) for cmd in issued]
        # No swap partition.
        assert not any("linux-swap" in line for line in flat)
        # Swapfile lifecycle present.
        assert any("dd" in cmd and any("swapfile" in p for p in cmd) for cmd in issued)
        assert any("mkswap" in cmd for cmd in issued)
        assert any("swapon" in cmd for cmd in issued)

    @patch("omnis.jobs.partition.PartitionJob._mount_partitions")
    @patch("omnis.jobs.partition.PartitionJob._format_partitions")
    @patch("omnis.jobs.partition.PartitionJob._run_partitioning_command")
    def test_swap_hibernate_creates_swapfile(
        self,
        mock_run_cmd: MagicMock,
        mock_format: MagicMock,
        mock_mount: MagicMock,
    ) -> None:
        """swap_strategy=hibernate: a swapfile is created via the same path."""
        job = PartitionJob()
        mock_run_cmd.return_value = JobResult.ok()
        mock_format.return_value = JobResult.ok()
        mock_mount.return_value = JobResult.ok()

        result = job._partition_auto(
            context=JobContext(target_root="/mnt"),
            disk="/dev/sda",
            filesystem="ext4",
            selections={"swap_strategy": "hibernate"},
            passphrase="",
            dry_run=True,
        )
        assert result.success is True
        issued = [list(c.args[0]) for c in mock_run_cmd.call_args_list]
        assert any("mkswap" in cmd for cmd in issued)
        assert any("swapon" in cmd for cmd in issued)


class TestEncryption:
    """Tests for LUKS encryption of the root partition."""

    @patch("omnis.jobs.partition.PartitionJob._mount_partitions")
    @patch("omnis.jobs.partition.PartitionJob._run_secret_command")
    @patch("omnis.jobs.partition.PartitionJob._run_partitioning_command")
    def test_encryption_uses_luks_and_mapper(
        self,
        mock_run_cmd: MagicMock,
        mock_secret: MagicMock,
        mock_mount: MagicMock,
    ) -> None:
        """encryption=True: luksFormat + luksOpen called; mkfs targets the mapper."""
        job = PartitionJob()
        mock_run_cmd.return_value = JobResult.ok()
        mock_secret.return_value = JobResult.ok()
        mock_mount.return_value = JobResult.ok()

        result = job._partition_auto(
            context=JobContext(target_root="/mnt"),
            disk="/dev/sda",
            filesystem="ext4",
            selections={"swap_strategy": "none", "encryption": True},
            passphrase="S3cretPass!",
            dry_run=False,
        )
        assert result.success is True
        assert job._layout is not None
        assert job._layout.encrypted is True

        # cryptsetup luksFormat AND luksOpen were issued via the secret runner.
        secret_cmds = [list(c.args[0]) for c in mock_secret.call_args_list]
        assert any("luksFormat" in cmd for cmd in secret_cmds)
        assert any("luksOpen" in cmd for cmd in secret_cmds)

        # The format/mount target is the mapper device.
        assert job._layout.root_target == "/dev/mapper/cryptroot"

        # mkfs.ext4 (real format runs since _format_partitions is NOT mocked here?)
        # _format_partitions is real; verify it formatted the mapper.
        format_cmds = [list(c.args[0]) for c in mock_run_cmd.call_args_list]
        assert any("mkfs.ext4" in cmd and "/dev/mapper/cryptroot" in cmd for cmd in format_cmds)

    @patch("omnis.jobs.partition.PartitionJob._mount_partitions")
    @patch("omnis.jobs.partition.PartitionJob._run_partitioning_command")
    def test_passphrase_never_logged(
        self,
        mock_run_cmd: MagicMock,
        mock_mount: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """SECURITY: the LUKS passphrase must never appear in any log record."""
        import logging

        sentinel = "S3cretPass!"
        job = PartitionJob()
        mock_run_cmd.return_value = JobResult.ok()
        mock_mount.return_value = JobResult.ok()

        # Patch subprocess.run inside _run_secret_command so cryptsetup is not
        # actually invoked, but the real (secret-safe) logging path runs.
        with (
            caplog.at_level(logging.DEBUG),
            patch("omnis.jobs.partition.subprocess.run") as mock_sub,
        ):
            mock_sub.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = job._partition_auto(
                context=JobContext(target_root="/mnt"),
                disk="/dev/sda",
                filesystem="ext4",
                selections={"swap_strategy": "none", "encryption": True},
                passphrase=sentinel,
                dry_run=False,
            )

        assert result.success is True
        for record in caplog.records:
            assert sentinel not in record.getMessage()


class TestRunEncryptionValidation:
    """Tests for encryption validation in validate()."""

    @patch("omnis.jobs.partition.PartitionJob._list_disks")
    @patch("omnis.jobs.partition.Path")
    def test_validate_encryption_requires_passphrase(
        self, mock_path: MagicMock, mock_list_disks: MagicMock
    ) -> None:
        """validate should fail (46) when encryption is on but passphrase empty."""
        job = PartitionJob()
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
                "encryption": True,
                "encryption_passphrase": "",
            }
        )
        result = job.validate(context)
        assert result.success is False
        assert result.error_code == 46
        # SECURITY: message must not leak any passphrase (there is none here).
        assert "passphrase" in result.message.lower()


class TestManualPartitioning:
    """Tests for manual mode (_partition_manual): assign existing partitions."""

    @staticmethod
    def _ctx(assignments: list[dict[str, object]]) -> JobContext:
        return JobContext(
            target_root="/mnt/target",
            selections={"partition_assignments": assignments},
        )

    @staticmethod
    def _assign(
        name: str, mountpoint: str, fmt: bool = False, fstype: str = ""
    ) -> dict[str, object]:
        return {
            "name": name,
            "path": f"/dev/{name}",
            "mountpoint": mountpoint,
            "format": fmt,
            "fstype": fstype,
        }

    def test_requires_at_least_one_assignment(self) -> None:
        job = PartitionJob()
        result = job._partition_manual(
            context=self._ctx([]), disk="/dev/sdb", selections={}, dry_run=True
        )
        assert result.success is False
        assert result.error_code == 48

    def test_requires_exactly_one_root(self) -> None:
        job = PartitionJob()
        assignments = [self._assign("sdb1", "/boot")]
        result = job._partition_manual(
            context=self._ctx(assignments),
            disk="/dev/sdb",
            selections={"partition_assignments": assignments},
            dry_run=True,
        )
        assert result.success is False
        assert result.error_code == 49

    def test_rejects_duplicate_mount_point(self) -> None:
        job = PartitionJob()
        assignments = [
            self._assign("sdb1", "/"),
            self._assign("sdb2", "/home"),
            self._assign("sdb3", "/home"),
        ]
        result = job._partition_manual(
            context=self._ctx(assignments),
            disk="/dev/sdb",
            selections={"partition_assignments": assignments},
            dry_run=True,
        )
        assert result.success is False
        assert result.error_code == 50

    def test_formats_and_mounts_dry_run(self) -> None:
        job = PartitionJob()
        assignments = [
            self._assign("sdb1", "/boot", fmt=True, fstype="vfat"),
            self._assign("sdb2", "/", fmt=True, fstype="ext4"),
        ]
        with patch.object(job, "_run_partitioning_command") as mock_cmd:
            mock_cmd.return_value = JobResult.ok()
            result = job._partition_manual(
                context=self._ctx(assignments),
                disk="/dev/sdb",
                selections={"partition_assignments": assignments},
                dry_run=True,
            )

        assert result.success is True
        assert job._layout is not None
        assert job._layout.root_partition == "/dev/sdb2"
        assert job._layout.efi_partition == "/dev/sdb1"

        commands = [call.args[0] for call in mock_cmd.call_args_list]
        assert ["mkfs.fat", "-F32", "/dev/sdb1"] in commands
        assert ["mkfs.ext4", "-F", "/dev/sdb2"] in commands
        # Root must mount before /boot (shallowest path first).
        mount_cmds = [c for c in commands if c[0] == "mount"]
        assert mount_cmds[0] == ["mount", "/dev/sdb2", "/mnt/target"]
        assert mount_cmds[1] == ["mount", "/dev/sdb1", "/mnt/target/boot"]

    def test_does_not_format_when_flag_absent(self) -> None:
        job = PartitionJob()
        assignments = [self._assign("sdb2", "/", fmt=False, fstype="ext4")]
        with patch.object(job, "_run_partitioning_command") as mock_cmd:
            mock_cmd.return_value = JobResult.ok()
            result = job._partition_manual(
                context=self._ctx(assignments),
                disk="/dev/sdb",
                selections={"partition_assignments": assignments},
                dry_run=True,
            )
        assert result.success is True
        commands = [call.args[0] for call in mock_cmd.call_args_list]
        assert not any(c[0].startswith("mkfs") or c[0] == "mkswap" for c in commands)

    def test_mkfs_command_mapping(self) -> None:
        assert PartitionJob._mkfs_command("ext4", "/dev/x") == ["mkfs.ext4", "-F", "/dev/x"]
        assert PartitionJob._mkfs_command("btrfs", "/dev/x") == ["mkfs.btrfs", "-f", "/dev/x"]
        assert PartitionJob._mkfs_command("vfat", "/dev/x") == ["mkfs.fat", "-F32", "/dev/x"]
        assert PartitionJob._mkfs_command("swap", "/dev/x") == ["mkswap", "/dev/x"]
        assert PartitionJob._mkfs_command("reiserfs", "/dev/x") is None

    def test_run_routes_manual_mode(self) -> None:
        job = PartitionJob()
        with (
            patch.object(job, "validate") as mock_validate,
            patch.object(job, "_partition_manual") as mock_manual,
        ):
            mock_validate.return_value = JobResult.ok()
            mock_manual.return_value = JobResult.ok()
            context = JobContext(
                selections={"disk": "/dev/sdb", "partition_mode": "manual", "dry_run": True}
            )
            job.run(context)
            assert mock_manual.called


class TestManualOperationsIntegration:
    """Manual mode routing between the legacy M1 assignments and the M2 ops."""

    def test_operations_present_routes_to_apply_operations(self) -> None:
        """When partition_operations is present, _apply_operations drives it."""
        job = PartitionJob()
        with patch.object(job, "_apply_operations") as mock_apply:
            mock_apply.return_value = JobResult.ok()
            selections = {
                "partition_operations": [
                    {"type": "delete", "target": "/dev/sdb2", "params": {"number": 2}}
                ]
            }
            context = JobContext(selections=selections)
            result = job._partition_manual(
                context=context, disk="/dev/sdb", selections=selections, dry_run=True
            )
        assert result.success is True
        assert mock_apply.called

    def test_operations_absent_uses_legacy_assignment_path(self) -> None:
        """Without partition_operations, the legacy assignment path is used."""
        job = PartitionJob()
        with patch.object(job, "_apply_operations") as mock_apply:
            assignments = [
                {
                    "name": "sdb2",
                    "path": "/dev/sdb2",
                    "mountpoint": "/",
                    "format": False,
                    "fstype": "ext4",
                }
            ]
            selections = {"partition_assignments": assignments}
            context = JobContext(
                target_root="/mnt/target",
                selections=selections,
            )
            with patch.object(job, "_run_partitioning_command") as mock_cmd:
                mock_cmd.return_value = JobResult.ok()
                result = job._partition_manual(
                    context=context, disk="/dev/sdb", selections=selections, dry_run=True
                )
        assert result.success is True
        # The M2 path must NOT have been taken.
        mock_apply.assert_not_called()


class TestCleanupHandoff:
    """cleanup() must keep the target mounted on success (hand-off to nixos)."""

    def test_cleanup_skips_unmount_on_success(self) -> None:
        """On success the mounts are a deliverable for the nixos job: no umount."""
        job = PartitionJob()
        job._layout = PartitionLayout(root_partition="/dev/sda2", encrypted=True)
        job._succeeded = True
        context = JobContext(target_root="/mnt/target")

        with patch("omnis.jobs.partition.subprocess.run") as mock_run:
            job.cleanup(context)

        mock_run.assert_not_called()

    def test_cleanup_unmounts_on_failure(self) -> None:
        """On failure the mounts (and LUKS mapper) are torn down."""
        job = PartitionJob()
        job._layout = PartitionLayout(root_partition="/dev/sda2", encrypted=True)
        job._succeeded = False
        context = JobContext(target_root="/mnt/target")

        with patch("omnis.jobs.partition.subprocess.run") as mock_run:
            job.cleanup(context)

        cmds = [call.args[0] for call in mock_run.call_args_list]
        assert ["umount", "/mnt/target"] in cmds
        assert any(cmd[:2] == ["cryptsetup", "luksClose"] for cmd in cmds)

    def test_run_resets_succeeded_flag(self) -> None:
        """A fresh run() clears a stale hand-off flag so retries are safe."""
        job = PartitionJob()
        job._succeeded = True
        # Empty selections → validate() fails fast, before any mounting.
        context = JobContext(selections={})

        job.run(context)

        assert job._succeeded is False


class TestTargetDiskRelease:
    """The target disk must be freed (and the running system protected) before wiping."""

    def test_refuses_disk_backing_the_running_system(self) -> None:
        job = PartitionJob()

        with patch("omnis.jobs.partition.disk_release.holds_running_system", return_value=True):
            result = job._release_target_disk("/dev/sda", "/mnt/target")

        assert result is not None
        assert result.success is False
        assert result.error_code == 56

    def test_fails_when_a_holder_survives_the_release(self) -> None:
        job = PartitionJob()

        with (
            patch("omnis.jobs.partition.disk_release.holds_running_system", return_value=False),
            patch("omnis.jobs.partition.disk_release.release_disk", return_value=[]),
            patch(
                "omnis.jobs.partition.disk_release.disk_holders",
                return_value=["/dev/sda1 is mounted on /run/media/nixos/GLF"],
            ),
            patch("omnis.jobs.partition.subprocess.run"),
        ):
            result = job._release_target_disk("/dev/sda", "/mnt/target")

        assert result is not None
        assert result.success is False
        assert result.error_code == 57
        assert "/run/media/nixos/GLF" in result.message

    def test_returns_none_when_disk_is_free(self) -> None:
        job = PartitionJob()

        with (
            patch("omnis.jobs.partition.disk_release.holds_running_system", return_value=False),
            patch(
                "omnis.jobs.partition.disk_release.release_disk",
                return_value=["unmounted /dev/sda1 from /run/media/nixos/GLF"],
            ),
            patch("omnis.jobs.partition.disk_release.disk_holders", return_value=[]),
            patch("omnis.jobs.partition.subprocess.run"),
        ):
            result = job._release_target_disk("/dev/sda", "/mnt/target")

        assert result is None

    def test_logs_what_was_released(self, caplog: Any) -> None:
        """A critical step must not stay silent: report each released holder."""
        job = PartitionJob()

        with (
            patch("omnis.jobs.partition.disk_release.holds_running_system", return_value=False),
            patch(
                "omnis.jobs.partition.disk_release.release_disk",
                return_value=["disabled swap file /mnt/target/swapfile"],
            ),
            patch("omnis.jobs.partition.disk_release.disk_holders", return_value=[]),
            patch("omnis.jobs.partition.subprocess.run") as mock_run,
            caplog.at_level(logging.INFO, logger="omnis.jobs.partition"),
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            job._release_target_disk("/dev/sda", "/mnt/target")

        assert "disabled swap file /mnt/target/swapfile" in caplog.text
        assert "/dev/sda is free for partitioning" in caplog.text

    def test_logs_the_surviving_holders_on_failure(self, caplog: Any) -> None:
        job = PartitionJob()

        with (
            patch("omnis.jobs.partition.disk_release.holds_running_system", return_value=False),
            patch("omnis.jobs.partition.disk_release.release_disk", return_value=[]),
            patch(
                "omnis.jobs.partition.disk_release.disk_holders",
                return_value=["/mnt/target/swapfile is in use as a swap file"],
            ),
            patch("omnis.jobs.partition.subprocess.run") as mock_run,
            caplog.at_level(logging.INFO, logger="omnis.jobs.partition"),
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            job._release_target_disk("/dev/sda", "/mnt/target")

        assert "nothing had to be released" in caplog.text
        assert "still held by: /mnt/target/swapfile is in use as a swap file" in caplog.text


class TestCleanupLogging:
    """Cleanup must never claim a success it did not get from the return code."""

    def test_luks_close_failure_is_not_logged_as_a_success(self, caplog: Any) -> None:
        job = PartitionJob()
        job._layout = PartitionLayout(
            efi_partition="/dev/sda1",
            root_partition="/dev/sda2",
            encrypted=True,
        )
        context = JobContext(target_root="/mnt/target")

        with (
            patch("omnis.jobs.partition.subprocess.run") as mock_run,
            caplog.at_level(logging.INFO, logger="omnis.jobs.partition"),
        ):
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="device busy")
            job.cleanup(context)

        assert "Closed LUKS mapper" not in caplog.text
        assert "Failed to close LUKS mapper cryptroot" in caplog.text

    def test_luks_close_success_is_logged(self, caplog: Any) -> None:
        job = PartitionJob()
        job._layout = PartitionLayout(
            efi_partition="/dev/sda1",
            root_partition="/dev/sda2",
            encrypted=True,
        )
        context = JobContext(target_root="/mnt/target")

        with (
            patch("omnis.jobs.partition.subprocess.run") as mock_run,
            caplog.at_level(logging.INFO, logger="omnis.jobs.partition"),
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            job.cleanup(context)

        assert "Closed LUKS mapper cryptroot" in caplog.text
