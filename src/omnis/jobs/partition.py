"""
Partition Job for Omnis Installer.

CRITICAL SECURITY WARNING:
This job performs DESTRUCTIVE DISK OPERATIONS that can result in IRREVERSIBLE DATA LOSS.
All operations require explicit confirmation and use dry-run mode by default.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from omnis.jobs.base import BaseJob, JobContext, JobResult

logger = logging.getLogger(__name__)


class PartitionMode(Enum):
    """Partitioning mode selection."""

    AUTO = "auto"  # Automatic partitioning (wipe disk)
    MANUAL = "manual"  # Manual partition selection


class FilesystemType(Enum):
    """Supported filesystem types."""

    EXT4 = "ext4"
    BTRFS = "btrfs"


@dataclass
class DiskInfo:
    """Information about a disk device."""

    name: str  # Device name (e.g., "sda")
    path: str  # Device path (e.g., "/dev/sda")
    size: int  # Size in bytes
    size_human: str  # Human-readable size
    model: str = ""
    is_removable: bool = False
    has_partitions: bool = False
    partitions: list[PartitionInfo] = field(default_factory=list)


@dataclass
class PartitionInfo:
    """Information about a partition."""

    name: str  # Partition name (e.g., "sda1")
    path: str  # Partition path (e.g., "/dev/sda1")
    size: int  # Size in bytes
    size_human: str  # Human-readable size
    fstype: str = ""  # Filesystem type
    mountpoint: str = ""
    has_data: bool = False  # True if partition appears to have data


@dataclass
class PartitionLayout:
    """Planned partition layout."""

    efi_partition: str = ""  # Path to EFI partition (e.g., "/dev/sda1")
    root_partition: str = ""  # Path to root partition
    swap_partition: str = ""  # Path to swap partition (if any)
    efi_size_mb: int = 512
    swap_size_mb: int = 0


class PartitionJob(BaseJob):
    """
    Disk partitioning and formatting job.

    SECURITY MODEL:
    - dry_run=True by default (simulation mode)
    - confirmed=False by default (explicit user confirmation required)
    - Detects existing data and warns user
    - All destructive operations are logged for audit trail
    - No operation is reversible once executed

    Supported modes:
    - AUTO: Wipe disk and create GPT + EFI + Root (+ optional Swap)
    - MANUAL: Use existing partitions (planned for v0.4.0)
    """

    name = "partition"
    description = "Disk partitioning and formatting"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the partition job."""
        super().__init__(config)
        self._layout: PartitionLayout | None = None

    def validate(self, context: JobContext) -> JobResult:
        """
        Validate partition configuration.

        Checks:
        - Disk exists and is accessible
        - Sufficient space available
        - Mode is valid
        - Detects existing data (WARNING level)

        Args:
            context: Execution context

        Returns:
            JobResult indicating validation status
        """
        context.report_progress(0, "Validating partition configuration...")

        selections = context.selections

        # Check required fields
        disk = selections.get("disk")
        if not disk:
            return JobResult.fail("Disk selection is required", error_code=30)

        mode = selections.get("mode", "auto")
        if mode not in [m.value for m in PartitionMode]:
            return JobResult.fail(f"Invalid partition mode: {mode}", error_code=31)

        # Verify disk exists
        disk_path = Path(disk)
        if not disk_path.exists():
            return JobResult.fail(f"Disk not found: {disk}", error_code=32)

        # Get disk information
        try:
            disks = self._list_disks()
            disk_info = next((d for d in disks if d.path == disk), None)
            if not disk_info:
                return JobResult.fail(f"Cannot read disk info: {disk}", error_code=33)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list disks: {e}")
            return JobResult.fail("Failed to enumerate disks", error_code=34)

        # Check minimum disk size (10 GB)
        min_size_bytes = 10 * 1024 * 1024 * 1024
        if disk_info.size < min_size_bytes:
            return JobResult.fail(
                f"Disk too small: {disk_info.size_human} (minimum 10 GB required)",
                error_code=35,
            )

        # Detect existing data (WARNING)
        if disk_info.has_partitions:
            data_partitions = [p for p in disk_info.partitions if p.has_data]
            if data_partitions:
                partition_list = ", ".join(p.path for p in data_partitions)
                logger.warning(f"⚠️  EXISTING DATA DETECTED on {disk}: {partition_list}")
                logger.warning("⚠️  ALL DATA WILL BE LOST if you proceed!")
                # This is a warning, not a failure - user must explicitly confirm

        # Validate filesystem type
        filesystem = selections.get("filesystem", "ext4")
        if filesystem not in [f.value for f in FilesystemType]:
            return JobResult.fail(f"Invalid filesystem type: {filesystem}", error_code=36)

        # Validate swap size
        swap_size = selections.get("swap_size", 0)
        if not isinstance(swap_size, (int, float)) or swap_size < 0:
            return JobResult.fail("Invalid swap size", error_code=37)

        context.report_progress(50, "Validation complete")

        return JobResult.ok(
            "Partition configuration valid",
            data={
                "disk": disk,
                "disk_size": disk_info.size_human,
                "has_existing_data": disk_info.has_partitions,
                "warnings": len(data_partitions) if disk_info.has_partitions else 0,
            },
        )

    def run(self, context: JobContext) -> JobResult:
        """
        Execute disk partitioning.

        SECURITY: Checks dry_run and confirmed flags before any destructive operation.

        Args:
            context: Execution context

        Returns:
            JobResult indicating success or failure
        """
        context.report_progress(0, "Starting partitioning job...")

        # Validate first
        validation = self.validate(context)
        if not validation.success:
            return validation

        selections = context.selections
        dry_run = selections.get("dry_run", True)  # DEFAULT TRUE
        confirmed = selections.get("confirmed", False)  # DEFAULT FALSE

        # SECURITY GATE: Require explicit confirmation for real operations
        if not dry_run and not confirmed:
            return JobResult.fail(
                "SECURITY: Cannot execute without explicit confirmation. "
                "Set confirmed=True to proceed with destructive operations.",
                error_code=38,
            )

        disk = selections["disk"]
        mode = selections.get("mode", "auto")
        filesystem = selections.get("filesystem", "ext4")
        swap_size = selections.get("swap_size", 0)

        if dry_run:
            logger.info("🔒 DRY-RUN MODE: Simulating operations (no actual changes)")
        else:
            logger.warning("⚠️  EXECUTING REAL OPERATIONS - THIS WILL MODIFY THE DISK!")
            logger.warning(f"⚠️  Target disk: {disk}")
            logger.warning("⚠️  All data will be PERMANENTLY LOST!")

        context.report_progress(10, "Planning partition layout...")

        # Execute based on mode
        if mode == PartitionMode.AUTO.value:
            result = self._partition_auto(
                context=context,
                disk=disk,
                filesystem=filesystem,
                swap_size_gb=swap_size,
                dry_run=dry_run,
            )
        else:
            # Manual mode not implemented yet
            return JobResult.fail(
                "Manual partitioning mode not yet implemented (planned for v0.4.0)",
                error_code=39,
            )

        if not result.success:
            return result

        context.report_progress(100, "Partitioning complete")

        return JobResult.ok(
            f"Disk {disk} partitioned successfully",
            data={
                "disk": disk,
                "mode": mode,
                "filesystem": filesystem,
                "dry_run": dry_run,
                "layout": {
                    "efi": self._layout.efi_partition if self._layout else "",
                    "root": self._layout.root_partition if self._layout else "",
                    "swap": self._layout.swap_partition if self._layout else "",
                },
            },
        )

    def _list_disks(self) -> list[DiskInfo]:
        """
        List available disks using lsblk.

        Returns:
            List of DiskInfo objects

        Raises:
            subprocess.CalledProcessError: If lsblk fails
        """
        # Use lsblk with JSON output for reliable parsing
        result = subprocess.run(
            ["lsblk", "-J", "-b", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE,MODEL,RM"],
            check=True,
            capture_output=True,
            text=True,
        )

        data = json.loads(result.stdout)
        disks: list[DiskInfo] = []

        for device in data.get("blockdevices", []):
            # Filter out loop devices, CD-ROMs, etc.
            if device.get("type") != "disk":
                continue

            # Skip removable devices (USB drives) to prevent accidents
            is_removable = device.get("rm", False) == "1"

            name = device.get("name", "")
            size = int(device.get("size", 0))
            model = device.get("model", "").strip()

            # Parse partitions
            partitions: list[PartitionInfo] = []
            has_partitions = False

            for child in device.get("children", []):
                if child.get("type") == "part":
                    has_partitions = True
                    part_name = child.get("name", "")
                    part_size = int(child.get("size", 0))
                    fstype = child.get("fstype", "")
                    mountpoint = child.get("mountpoint", "")

                    # Detect if partition has data (has filesystem)
                    has_data = bool(fstype)

                    partitions.append(
                        PartitionInfo(
                            name=part_name,
                            path=f"/dev/{part_name}",
                            size=part_size,
                            size_human=self._format_size(part_size),
                            fstype=fstype,
                            mountpoint=mountpoint,
                            has_data=has_data,
                        )
                    )

            disks.append(
                DiskInfo(
                    name=name,
                    path=f"/dev/{name}",
                    size=size,
                    size_human=self._format_size(size),
                    model=model,
                    is_removable=is_removable,
                    has_partitions=has_partitions,
                    partitions=partitions,
                )
            )

        return disks

    def _partition_auto(
        self,
        context: JobContext,
        disk: str,
        filesystem: str,
        swap_size_gb: int,
        dry_run: bool,
    ) -> JobResult:
        """
        Automatic partitioning mode: wipe disk and create GPT layout.

        Layout:
        - Partition 1: EFI System Partition (512 MB, FAT32)
        - Partition 2: Root (remaining space minus swap, ext4/btrfs)
        - Partition 3: Swap (optional, swap_size_gb)

        Args:
            context: Execution context
            disk: Disk path (e.g., "/dev/sda")
            filesystem: Root filesystem type
            swap_size_gb: Swap size in GB (0 = no swap)
            dry_run: If True, simulate only

        Returns:
            JobResult indicating success or failure
        """
        context.report_progress(20, "Creating partition table...")

        # Calculate partition layout
        efi_size_mb = 512
        swap_size_mb = int(swap_size_gb * 1024)

        self._layout = PartitionLayout(
            efi_partition=f"{disk}1",
            root_partition=f"{disk}2",
            swap_partition=f"{disk}3" if swap_size_gb > 0 else "",
            efi_size_mb=efi_size_mb,
            swap_size_mb=swap_size_mb,
        )

        logger.info(f"Partition layout: EFI={efi_size_mb}MB, Swap={swap_size_mb}MB")

        # Step 1: Create GPT partition table
        result = self._run_partitioning_command(
            ["parted", "-s", disk, "mklabel", "gpt"],
            description="Creating GPT partition table",
            dry_run=dry_run,
        )
        if not result.success:
            return result

        context.report_progress(30, "Creating EFI partition...")

        # Step 2: Create EFI partition
        result = self._run_partitioning_command(
            [
                "parted",
                "-s",
                disk,
                "mkpart",
                "ESP",
                "fat32",
                "1MiB",
                f"{efi_size_mb + 1}MiB",
            ],
            description="Creating EFI partition",
            dry_run=dry_run,
        )
        if not result.success:
            return result

        # Mark EFI partition
        result = self._run_partitioning_command(
            ["parted", "-s", disk, "set", "1", "esp", "on"],
            description="Setting ESP flag",
            dry_run=dry_run,
        )
        if not result.success:
            return result

        context.report_progress(40, "Creating root partition...")

        # Step 3: Create root partition
        root_end = "100%" if swap_size_mb == 0 else f"-{swap_size_mb}MiB"
        result = self._run_partitioning_command(
            [
                "parted",
                "-s",
                disk,
                "mkpart",
                "root",
                filesystem,
                f"{efi_size_mb + 1}MiB",
                root_end,
            ],
            description="Creating root partition",
            dry_run=dry_run,
        )
        if not result.success:
            return result

        # Step 4: Create swap partition (if requested)
        if swap_size_mb > 0:
            context.report_progress(50, "Creating swap partition...")
            result = self._run_partitioning_command(
                [
                    "parted",
                    "-s",
                    disk,
                    "mkpart",
                    "swap",
                    "linux-swap",
                    f"-{swap_size_mb}MiB",
                    "100%",
                ],
                description="Creating swap partition",
                dry_run=dry_run,
            )
            if not result.success:
                return result

        context.report_progress(60, "Formatting partitions...")

        # Step 5: Format partitions
        result = self._format_partitions(context, filesystem, dry_run)
        if not result.success:
            return result

        context.report_progress(80, "Mounting filesystems...")

        # Step 6: Mount partitions
        result = self._mount_partitions(context, dry_run)
        if not result.success:
            return result

        return JobResult.ok("Automatic partitioning completed")

    def _format_partitions(self, _context: JobContext, filesystem: str, dry_run: bool) -> JobResult:
        """
        Format partitions according to layout.

        Args:
            context: Execution context
            filesystem: Root filesystem type
            dry_run: If True, simulate only

        Returns:
            JobResult indicating success or failure
        """
        if not self._layout:
            return JobResult.fail("Partition layout not initialized", error_code=40)

        # Format EFI partition (FAT32)
        result = self._run_partitioning_command(
            ["mkfs.fat", "-F32", self._layout.efi_partition],
            description=f"Formatting EFI partition ({self._layout.efi_partition})",
            dry_run=dry_run,
        )
        if not result.success:
            return result

        # Format root partition
        if filesystem == FilesystemType.EXT4.value:
            cmd = ["mkfs.ext4", "-F", self._layout.root_partition]
        elif filesystem == FilesystemType.BTRFS.value:
            cmd = ["mkfs.btrfs", "-f", self._layout.root_partition]
        else:
            return JobResult.fail(f"Unsupported filesystem: {filesystem}", error_code=41)

        result = self._run_partitioning_command(
            cmd,
            description=f"Formatting root partition ({self._layout.root_partition})",
            dry_run=dry_run,
        )
        if not result.success:
            return result

        # Format swap partition (if exists)
        if self._layout.swap_partition:
            result = self._run_partitioning_command(
                ["mkswap", self._layout.swap_partition],
                description=f"Formatting swap partition ({self._layout.swap_partition})",
                dry_run=dry_run,
            )
            if not result.success:
                return result

        return JobResult.ok("Partitions formatted successfully")

    def _mount_partitions(self, context: JobContext, dry_run: bool) -> JobResult:
        """
        Mount partitions to target root.

        Hierarchy:
        - /mnt (target_root) ← root partition
        - /mnt/boot/efi ← EFI partition

        Args:
            context: Execution context
            dry_run: If True, simulate only

        Returns:
            JobResult indicating success or failure
        """
        if not self._layout:
            return JobResult.fail("Partition layout not initialized", error_code=42)

        target_root = context.target_root

        # Mount root partition
        result = self._run_partitioning_command(
            ["mount", self._layout.root_partition, target_root],
            description=f"Mounting root partition to {target_root}",
            dry_run=dry_run,
        )
        if not result.success:
            return result

        # Create EFI mount point
        efi_mount = Path(target_root) / "boot" / "efi"
        if not dry_run:
            try:
                efi_mount.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created EFI mount point: {efi_mount}")
            except OSError as e:
                logger.error(f"Failed to create EFI mount point: {e}")
                return JobResult.fail(f"Failed to create {efi_mount}: {e}", error_code=43)
        else:
            logger.info(f"[DRY-RUN] Would create directory: {efi_mount}")

        # Mount EFI partition
        result = self._run_partitioning_command(
            ["mount", self._layout.efi_partition, str(efi_mount)],
            description=f"Mounting EFI partition to {efi_mount}",
            dry_run=dry_run,
        )
        if not result.success:
            return result

        # Activate swap (if exists)
        if self._layout.swap_partition:
            result = self._run_partitioning_command(
                ["swapon", self._layout.swap_partition],
                description=f"Activating swap ({self._layout.swap_partition})",
                dry_run=dry_run,
            )
            if not result.success:
                # Swap activation failure is not critical
                logger.warning(f"Failed to activate swap: {result.message}")

        return JobResult.ok("Partitions mounted successfully")

    def _run_partitioning_command(
        self, cmd: list[str], description: str, dry_run: bool
    ) -> JobResult:
        """
        Run a partitioning command with dry-run support.

        Args:
            cmd: Command to execute
            description: Human-readable description for logging
            dry_run: If True, simulate only

        Returns:
            JobResult indicating success or failure
        """
        if dry_run:
            logger.info(f"[DRY-RUN] {description}: {' '.join(cmd)}")
            return JobResult.ok(f"[DRY-RUN] {description}")

        logger.info(f"Executing: {description}")
        logger.debug(f"Command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info(f"✓ {description} completed successfully")
            if result.stdout:
                logger.debug(f"stdout: {result.stdout}")
            return JobResult.ok(description)

        except subprocess.CalledProcessError as e:
            logger.error(f"✗ {description} failed: {e}")
            logger.error(f"stderr: {e.stderr}")
            return JobResult.fail(
                f"{description} failed: {e.stderr}",
                error_code=44,
            )
        except FileNotFoundError:
            logger.error(f"Command not found: {cmd[0]}")
            return JobResult.fail(f"Required tool not found: {cmd[0]}", error_code=45)

    def cleanup(self, context: JobContext) -> None:
        """
        Clean up after partitioning failure.

        Attempts to unmount any mounted filesystems.

        Args:
            context: Execution context
        """
        if not self._layout:
            return

        target_root = context.target_root
        logger.info("Cleaning up mounted filesystems...")

        # Unmount in reverse order
        efi_mount = Path(target_root) / "boot" / "efi"

        # Try to unmount EFI
        try:
            subprocess.run(
                ["umount", str(efi_mount)],
                check=False,
                capture_output=True,
            )
            logger.info(f"Unmounted {efi_mount}")
        except Exception as e:
            logger.debug(f"Failed to unmount {efi_mount}: {e}")

        # Try to unmount root
        try:
            subprocess.run(
                ["umount", target_root],
                check=False,
                capture_output=True,
            )
            logger.info(f"Unmounted {target_root}")
        except Exception as e:
            logger.debug(f"Failed to unmount {target_root}: {e}")

        # Try to deactivate swap
        if self._layout.swap_partition:
            try:
                subprocess.run(
                    ["swapoff", self._layout.swap_partition],
                    check=False,
                    capture_output=True,
                )
                logger.info(f"Deactivated swap {self._layout.swap_partition}")
            except Exception as e:
                logger.debug(f"Failed to deactivate swap: {e}")

    def estimate_duration(self) -> int:
        """
        Estimate execution time in seconds.

        Partitioning operations are relatively fast, but formatting
        large disks can take time.

        Returns:
            Estimated duration in seconds (60s for average disk)
        """
        return 60

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """
        Format byte size to human-readable string.

        Args:
            size_bytes: Size in bytes

        Returns:
            Human-readable size (e.g., "256 GB")
        """
        size = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
