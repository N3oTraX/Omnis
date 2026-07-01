"""
Partition Job for Omnis Installer.

CRITICAL SECURITY WARNING:
This job performs DESTRUCTIVE DISK OPERATIONS that can result in IRREVERSIBLE DATA LOSS.
All operations require explicit confirmation and use dry-run mode by default.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from omnis.jobs.base import BaseJob, JobContext, JobResult
from omnis.utils import disk_detector

logger = logging.getLogger(__name__)


def part_path(disk: str, n: int) -> str:
    """
    Build a partition device path, handling the NVMe/eMMC ``p`` separator.

    Block devices whose name ends with a digit (NVMe ``nvme0n1``, eMMC
    ``mmcblk0``, loop ``loop0``) require a ``p`` before the partition number,
    e.g. ``/dev/nvme0n1`` -> ``/dev/nvme0n1p1``. SATA/SCSI devices (``sda``) do
    not, e.g. ``/dev/sda`` -> ``/dev/sda1``.
    """
    base = disk.rsplit("/", 1)[-1]
    sep = "p" if base and base[-1].isdigit() else ""
    return f"{disk}{sep}{n}"


def _detect_ram_mb() -> int:
    """
    Detect total RAM in MiB from ``/proc/meminfo``.

    Returns the rounded MiB value, or ``8192`` when detection is unavailable.
    """
    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemTotal:"):
                    kib = int(line.split()[1])
                    return kib // 1024
    except (OSError, ValueError, IndexError):
        logger.debug("RAM detection failed, defaulting to 8192 MB")
    return 8192


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
    encrypted: bool = False  # True once the root partition is LUKS-wrapped
    luks_mapper_name: str = "cryptroot"  # /dev/mapper name for the LUKS device

    @property
    def root_target(self) -> str:
        """Device to format/mount as root (LUKS mapper if encrypted)."""
        if self.encrypted:
            return f"/dev/mapper/{self.luks_mapper_name}"
        return self.root_partition


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

        # Backward compat: prefer partition_mode, fall back to legacy "mode".
        mode = selections.get("partition_mode", selections.get("mode", "auto"))
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

        # Validate swap size (legacy swap_size partition path)
        swap_size = selections.get("swap_size", 0)
        if not isinstance(swap_size, (int, float)) or swap_size < 0:
            return JobResult.fail("Invalid swap size", error_code=37)

        # Validate swap strategy (current path)
        swap_strategy = selections.get("swap_strategy")
        if swap_strategy is not None and swap_strategy not in ("file", "none", "hibernate"):
            return JobResult.fail(f"Invalid swap strategy: {swap_strategy}", error_code=47)

        # Validate encryption: a passphrase is mandatory when encryption is on.
        # SECURITY: never echo the passphrase in the error message.
        if selections.get("encryption", False):
            passphrase = selections.get("encryption_passphrase", "")
            if not passphrase:
                return JobResult.fail(
                    "Encryption enabled but no passphrase provided",
                    error_code=46,
                )

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
        # Backward compat: prefer partition_mode, fall back to legacy "mode".
        mode = selections.get("partition_mode", selections.get("mode", "auto"))
        filesystem = selections.get("filesystem", "ext4")

        # SECURITY: read the passphrase locally so we can wipe it in finally.
        passphrase = str(selections.get("encryption_passphrase", ""))
        try:
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
                    selections=selections,
                    passphrase=passphrase,
                    dry_run=dry_run,
                )
            elif mode == PartitionMode.MANUAL.value:
                result = self._partition_manual(
                    context=context,
                    disk=disk,
                    selections=selections,
                    dry_run=dry_run,
                )
            else:
                return JobResult.fail(f"Unknown partition mode: {mode}", error_code=39)

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
        finally:
            # SECURITY: clear the passphrase from memory after use.
            passphrase = ""
            del passphrase

    def _list_disks(self) -> list[DiskInfo]:
        """
        List available disks via the unified :mod:`omnis.utils.disk_detector`.

        Adapts the detector's UI-contract dicts into the ``DiskInfo`` /
        ``PartitionInfo`` dataclasses used by :meth:`validate`.

        Returns:
            List of DiskInfo objects
        """
        disks: list[DiskInfo] = []

        for entry in disk_detector.list_disks():
            name = entry.get("name", "")
            size = int(entry.get("sizeBytes", 0))

            partitions: list[PartitionInfo] = []
            for part in entry.get("partitions", []):
                part_name = part.get("name", "")
                part_size = int(part.get("sizeBytes", 0))
                fstype = part.get("fstype", "")
                partitions.append(
                    PartitionInfo(
                        name=part_name,
                        path=f"/dev/{part_name}",
                        size=part_size,
                        size_human=self._format_size(part_size),
                        fstype=fstype,
                        mountpoint="",
                        has_data=bool(fstype),
                    )
                )

            disks.append(
                DiskInfo(
                    name=name,
                    path=f"/dev/{name}",
                    size=size,
                    size_human=str(entry.get("size", self._format_size(size))),
                    model=str(entry.get("model", "")),
                    is_removable=bool(entry.get("removable", False)),
                    has_partitions=bool(partitions),
                    partitions=partitions,
                )
            )

        return disks

    def _partition_auto(
        self,
        context: JobContext,
        disk: str,
        filesystem: str,
        selections: dict[str, Any],
        passphrase: str,
        dry_run: bool,
    ) -> JobResult:
        """
        Automatic partitioning mode: wipe disk and create a GPT layout.

        Layout:
        - Partition 1: EFI System Partition (``efi_size_mb`` MiB, FAT32)
        - Partition 2: Root (remaining space, ext4/btrfs, optionally LUKS)

        Swap is handled by ``swap_strategy`` (swapfile under ``target_root``).
        The legacy ``swap_size`` (GB) still creates a swap PARTITION for
        backward compatibility when ``swap_strategy`` is absent.

        SECURITY: when ``encryption`` is set, the root partition is wrapped in
        LUKS2 before formatting. The passphrase is fed via stdin and never
        logged.

        Args:
            context: Execution context
            disk: Disk path (e.g., "/dev/sda")
            filesystem: Root filesystem type
            selections: Raw user selections (snake_case keys)
            passphrase: LUKS passphrase (empty if encryption disabled)
            dry_run: If True, simulate only

        Returns:
            JobResult indicating success or failure
        """
        context.report_progress(20, "Creating partition table...")

        efi_size_mb = int(selections.get("efi_size_mb", 512))
        encryption = bool(selections.get("encryption", False))

        # Determine swap handling. swap_strategy takes precedence over the
        # legacy swap_size partition path.
        swap_strategy = selections.get("swap_strategy")
        legacy_swap_gb = int(selections.get("swap_size", 0) or 0)
        use_swap_partition = swap_strategy is None and legacy_swap_gb > 0
        swap_size_mb = legacy_swap_gb * 1024 if use_swap_partition else 0

        self._layout = PartitionLayout(
            efi_partition=part_path(disk, 1),
            root_partition=part_path(disk, 2),
            swap_partition=part_path(disk, 3) if use_swap_partition else "",
            efi_size_mb=efi_size_mb,
            swap_size_mb=swap_size_mb,
        )

        logger.info(f"Partition layout: EFI={efi_size_mb}MB, swap_partition={swap_size_mb}MB")

        # Step 0: Wipe any existing signatures/partition tables (idempotent,
        # avoids parted refusing to relabel a disk with stale metadata).
        result = self._run_partitioning_command(
            ["wipefs", "-a", disk],
            description="Wiping filesystem signatures",
            dry_run=dry_run,
        )
        if not result.success:
            return result

        result = self._run_partitioning_command(
            ["sgdisk", "--zap-all", disk],
            description="Zapping GPT/MBR structures",
            dry_run=dry_run,
        )
        if not result.success:
            return result

        # Step 1: Create GPT partition table
        result = self._run_partitioning_command(
            ["parted", "-s", disk, "mklabel", "gpt"],
            description="Creating GPT partition table",
            dry_run=dry_run,
        )
        if not result.success:
            return result

        context.report_progress(30, "Creating EFI partition...")

        # Step 2: Create EFI partition (1MiB alignment via 1MiB start)
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

        # Step 4: Create swap PARTITION (legacy path only)
        if use_swap_partition:
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

        # Step 5: Settle udev BEFORE any mkfs to avoid racing on missing nodes.
        result = self._run_partitioning_command(
            ["partprobe", disk],
            description="Re-reading partition table",
            dry_run=dry_run,
        )
        if not result.success:
            return result

        result = self._run_partitioning_command(
            ["udevadm", "settle"],
            description="Waiting for udev to settle",
            dry_run=dry_run,
        )
        if not result.success:
            return result

        # Step 6: Optionally wrap root in LUKS2 before formatting.
        if encryption:
            context.report_progress(55, "Encrypting root partition...")
            result = self._setup_luks(passphrase, dry_run)
            if not result.success:
                return result

        context.report_progress(60, "Formatting partitions...")

        # Step 7: Format partitions
        result = self._format_partitions(context, filesystem, dry_run)
        if not result.success:
            return result

        context.report_progress(80, "Mounting filesystems...")

        # Step 8: Mount partitions
        result = self._mount_partitions(context, dry_run)
        if not result.success:
            return result

        # Step 9: Configure swap via swapfile under target_root.
        if swap_strategy in ("file", "hibernate"):
            context.report_progress(90, "Configuring swapfile...")
            result = self._setup_swapfile(context, swap_strategy, dry_run)
            if not result.success:
                return result

        return JobResult.ok("Automatic partitioning completed")

    def _partition_manual(
        self,
        context: JobContext,
        disk: str,
        selections: dict[str, Any],
        dry_run: bool,
    ) -> JobResult:
        """
        Manual partitioning: assign existing partitions (mount point + format).

        Does NOT create, delete or resize partitions; it optionally reformats
        the partitions the user flagged and mounts them under ``target_root``.
        Exactly one partition must be mounted at ``/``.

        Args:
            context: Execution context
            disk: Target disk path (informational; not wiped in this mode)
            selections: Raw user selections; reads ``partition_assignments``
            dry_run: If True, simulate only

        Returns:
            JobResult indicating success or failure
        """
        logger.info(f"Manual partitioning on {disk} (existing partitions preserved)")

        assignments = selections.get("partition_assignments", [])
        used = [a for a in assignments if a.get("mountpoint") or a.get("format")]
        if not used:
            return JobResult.fail("No partition assignment provided", error_code=48)

        roots = [a for a in used if a.get("mountpoint") == "/"]
        if len(roots) != 1:
            return JobResult.fail(
                "Manual mode requires exactly one partition mounted at /",
                error_code=49,
            )

        mounts = [a["mountpoint"] for a in used if a.get("mountpoint")]
        if len(mounts) != len(set(mounts)):
            return JobResult.fail("Duplicate mount point in manual plan", error_code=50)

        # Record layout for the summary; the EFI slot is whatever lands on /boot*.
        efi = next((a for a in used if a.get("mountpoint") in ("/boot", "/boot/efi")), None)
        self._layout = PartitionLayout(
            efi_partition=str(efi["path"]) if efi else "",
            root_partition=str(roots[0]["path"]),
        )

        context.report_progress(30, "Formatting assigned partitions...")

        for assignment in used:
            if not assignment.get("format"):
                continue
            path = str(assignment["path"])
            fstype = str(assignment.get("fstype") or "ext4")
            cmd = self._mkfs_command(fstype, path)
            if cmd is None:
                return JobResult.fail(
                    f"Unsupported filesystem for {path}: {fstype}", error_code=51
                )
            result = self._run_partitioning_command(
                cmd, description=f"Formatting {path} ({fstype})", dry_run=dry_run
            )
            if not result.success:
                return result

        context.report_progress(70, "Mounting assigned filesystems...")
        return self._mount_manual(context, used, dry_run)

    @staticmethod
    def _mkfs_command(fstype: str, path: str) -> list[str] | None:
        """Return the mkfs command for a filesystem, or None if unsupported."""
        fs = fstype.lower()
        if fs == "ext4":
            return ["mkfs.ext4", "-F", path]
        if fs == "btrfs":
            return ["mkfs.btrfs", "-f", path]
        if fs in ("vfat", "fat", "fat32"):
            return ["mkfs.fat", "-F32", path]
        if fs == "swap":
            return ["mkswap", path]
        return None

    def _mount_manual(
        self,
        context: JobContext,
        assignments: list[dict[str, Any]],
        dry_run: bool,
    ) -> JobResult:
        """Mount manually-assigned filesystems under target_root (parents first)."""
        target_root = context.target_root

        fs_mounts = [a for a in assignments if a.get("mountpoint") and a["mountpoint"] != "swap"]
        # Shallowest path first so a parent mount exists before its children.
        fs_mounts.sort(key=lambda a: 0 if a["mountpoint"] == "/" else a["mountpoint"].count("/"))

        for assignment in fs_mounts:
            mountpoint = assignment["mountpoint"]
            dest = Path(target_root)
            if mountpoint != "/":
                dest = dest / mountpoint.lstrip("/")
            if not dry_run:
                try:
                    dest.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    return JobResult.fail(f"Failed to create {dest}: {e}", error_code=52)
            else:
                logger.info(f"[DRY-RUN] Would create directory: {dest}")
            result = self._run_partitioning_command(
                ["mount", str(assignment["path"]), str(dest)],
                description=f"Mounting {assignment['path']} at {dest}",
                dry_run=dry_run,
            )
            if not result.success:
                return result

        for assignment in assignments:
            if assignment.get("mountpoint") == "swap":
                result = self._run_partitioning_command(
                    ["swapon", str(assignment["path"])],
                    description=f"Enabling swap on {assignment['path']}",
                    dry_run=dry_run,
                )
                if not result.success:
                    logger.warning(f"Failed to activate swap: {result.message}")

        return JobResult.ok("Manual partitions mounted")

    def _setup_luks(self, passphrase: str, dry_run: bool) -> JobResult:
        """
        Wrap the root partition in a LUKS2 container.

        SECURITY: the passphrase is fed through stdin and is never logged, nor
        included in any logged command line.

        # TODO(phase2/nixos job): inject
        #   boot.initrd.luks.devices."<mapper>".device = <root_part>

        Args:
            passphrase: LUKS passphrase (must be non-empty in real runs)
            dry_run: If True, simulate only

        Returns:
            JobResult indicating success or failure
        """
        if not self._layout:
            return JobResult.fail("Partition layout not initialized", error_code=40)

        root_part = self._layout.root_partition
        mapper_name = self._layout.luks_mapper_name

        if dry_run:
            logger.info(f"[DRY-RUN] Would LUKS-format and open {root_part} as {mapper_name}")
            self._layout.encrypted = True
            return JobResult.ok("[DRY-RUN] LUKS setup")

        if not passphrase:
            return JobResult.fail("LUKS passphrase missing", error_code=46)

        fmt = self._run_secret_command(
            ["cryptsetup", "luksFormat", "--type", "luks2", "--batch-mode", root_part],
            passphrase=passphrase,
            description="LUKS formatting root partition",
        )
        if not fmt.success:
            return fmt

        opened = self._run_secret_command(
            ["cryptsetup", "luksOpen", root_part, mapper_name],
            passphrase=passphrase,
            description="Opening LUKS container",
        )
        if not opened.success:
            return opened

        self._layout.encrypted = True
        return JobResult.ok("LUKS container ready")

    def _setup_swapfile(self, context: JobContext, strategy: str, dry_run: bool) -> JobResult:
        """
        Create and activate a swapfile under ``target_root``.

        - ``file``: size = min(RAM, 8192 MB), default 4096 MB if RAM unknown.
        - ``hibernate``: size >= RAM (so the image fits), default 8192 MB.

        Args:
            context: Execution context (provides target_root)
            strategy: "file" or "hibernate"
            dry_run: If True, simulate only

        Returns:
            JobResult indicating success or failure
        """
        ram_mb = _detect_ram_mb()
        if strategy == "hibernate":
            size_mb = max(ram_mb, 8192)
        else:  # "file"
            size_mb = min(ram_mb, 8192) if ram_mb else 4096

        swapfile = f"{context.target_root}/swapfile"
        logger.info(f"Swapfile strategy={strategy}, size={size_mb}MB at {swapfile}")

        steps = [
            (
                ["dd", "if=/dev/zero", f"of={swapfile}", "bs=1M", f"count={size_mb}"],
                "Allocating swapfile",
            ),
            (["chmod", "600", swapfile], "Securing swapfile permissions"),
            (["mkswap", swapfile], "Formatting swapfile"),
            (["swapon", swapfile], "Activating swapfile"),
        ]
        for cmd, description in steps:
            result = self._run_partitioning_command(cmd, description=description, dry_run=dry_run)
            if not result.success:
                return result

        return JobResult.ok("Swapfile configured")

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

        # Format root target (the LUKS mapper when encryption is enabled).
        root_target = self._layout.root_target
        if filesystem == FilesystemType.EXT4.value:
            cmd = ["mkfs.ext4", "-F", root_target]
        elif filesystem == FilesystemType.BTRFS.value:
            # btrfs is created "flat" (single subvolume).
            # TODO(v0.5): btrfs subvolumes (@/@home/@nix, compress=zstd, noatime)
            cmd = ["mkfs.btrfs", "-f", root_target]
        else:
            return JobResult.fail(f"Unsupported filesystem: {filesystem}", error_code=41)

        result = self._run_partitioning_command(
            cmd,
            description=f"Formatting root partition ({root_target})",
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
        - /mnt (target_root) ← root partition (or LUKS mapper)
        - /mnt/boot ← EFI partition (NixOS systemd-boot expects the ESP on /boot)

        Args:
            context: Execution context
            dry_run: If True, simulate only

        Returns:
            JobResult indicating success or failure
        """
        if not self._layout:
            return JobResult.fail("Partition layout not initialized", error_code=42)

        target_root = context.target_root

        # Mount root target (LUKS mapper when encrypted)
        result = self._run_partitioning_command(
            ["mount", self._layout.root_target, target_root],
            description=f"Mounting root partition to {target_root}",
            dry_run=dry_run,
        )
        if not result.success:
            return result

        # Create EFI mount point: ESP lives on /boot for NixOS systemd-boot.
        efi_mount = Path(target_root) / "boot"
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

    def _run_secret_command(self, cmd: list[str], passphrase: str, description: str) -> JobResult:
        """
        Run a command that consumes a secret via stdin.

        SECURITY: neither the passphrase nor the full command line is logged.
        Only the human-readable description is emitted. This is used for
        ``cryptsetup luksFormat`` / ``luksOpen`` where the passphrase is piped
        in rather than passed as an argument.

        Args:
            cmd: Command to execute (must NOT contain the passphrase)
            passphrase: Secret fed to the process stdin
            description: Human-readable description for logging

        Returns:
            JobResult indicating success or failure
        """
        logger.info(f"Executing: {description}")

        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                input=passphrase,
            )
            logger.info(f"✓ {description} completed successfully")
            return JobResult.ok(description)
        except subprocess.CalledProcessError as e:
            # SECURITY: log stderr only; cryptsetup does not echo the passphrase.
            logger.error(f"✗ {description} failed: {e.stderr}")
            return JobResult.fail(f"{description} failed", error_code=44)
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

        # Unmount in reverse order (ESP is mounted on /boot)
        efi_mount = Path(target_root) / "boot"

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

        # Try to deactivate swap partition (legacy path)
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

        # Try to close the LUKS mapper if it was opened
        if self._layout.encrypted:
            try:
                subprocess.run(
                    ["cryptsetup", "luksClose", self._layout.luks_mapper_name],
                    check=False,
                    capture_output=True,
                )
                logger.info(f"Closed LUKS mapper {self._layout.luks_mapper_name}")
            except Exception as e:
                logger.debug(f"Failed to close LUKS mapper: {e}")

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
