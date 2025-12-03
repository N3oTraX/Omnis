"""
System Requirements Checker for Omnis Installer.

Provides hardware and system requirement validation before installation.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

from omnis.jobs.gpu import GPUDetector

logger = logging.getLogger(__name__)


class RequirementStatus(Enum):
    """Status of a requirement check."""

    PASS = auto()  # Requirement met
    WARN = auto()  # Recommendation not met (can continue)
    FAIL = auto()  # Requirement not met (cannot continue)
    SKIP = auto()  # Check skipped (not applicable)


@dataclass
class RequirementCheck:
    """Result of a single requirement check."""

    name: str
    description: str
    status: RequirementStatus
    current_value: str = ""
    required_value: str = ""
    recommended_value: str = ""
    details: str = ""

    @property
    def passed(self) -> bool:
        """Check if requirement is met (PASS or WARN)."""
        return self.status in (
            RequirementStatus.PASS,
            RequirementStatus.WARN,
            RequirementStatus.SKIP,
        )

    @property
    def is_critical(self) -> bool:
        """Check if this is a critical failure."""
        return self.status == RequirementStatus.FAIL


@dataclass
class RequirementsResult:
    """Result of all requirement checks."""

    checks: list[RequirementCheck] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        """Check if all requirements are met."""
        return all(check.passed for check in self.checks)

    @property
    def can_continue(self) -> bool:
        """Check if installation can continue (no critical failures)."""
        return not any(check.is_critical for check in self.checks)

    @property
    def failures(self) -> list[RequirementCheck]:
        """Get all failed checks."""
        return [c for c in self.checks if c.status == RequirementStatus.FAIL]

    @property
    def warnings(self) -> list[RequirementCheck]:
        """Get all warning checks."""
        return [c for c in self.checks if c.status == RequirementStatus.WARN]

    @property
    def passed_checks(self) -> list[RequirementCheck]:
        """Get all passed checks."""
        return [c for c in self.checks if c.status == RequirementStatus.PASS]


class SystemRequirementsChecker:
    """
    Checks system requirements for installation.

    Validates hardware, boot mode, connectivity, and other prerequisites.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """
        Initialize the requirements checker.

        Args:
            config: Requirements configuration from omnis.yaml
        """
        self.config = config or {}

    def check_all(self) -> RequirementsResult:
        """
        Run all requirement checks.

        Returns:
            RequirementsResult with all check results
        """
        result = RequirementsResult()

        # Hardware checks
        result.checks.append(self._check_ram())
        result.checks.append(self._check_disk_space())
        result.checks.append(self._check_cpu_architecture())

        # Boot checks
        result.checks.append(self._check_efi_mode())
        result.checks.append(self._check_secure_boot())

        # Connectivity checks
        result.checks.append(self._check_internet())

        # Power checks
        result.checks.append(self._check_power_source())
        result.checks.append(self._check_battery_level())

        # GPU check (optional for gaming)
        result.checks.append(self._check_gpu())

        return result

    def _check_ram(self) -> RequirementCheck:
        """
        Check available RAM.

        Thresholds:
        - Below min_ram_gb: FAIL
        - Between min_ram_gb and warn_ram_gb: WARN
        - Above warn_ram_gb: PASS
        """
        min_gb = self.config.get("min_ram_gb", 8)
        warn_gb = self.config.get("warn_ram_gb", 16)
        recommended_gb = self.config.get("recommended_ram_gb", 16)

        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        # Parse KB value and convert to GB
                        kb = int(line.split()[1])
                        current_gb = kb / (1024 * 1024)
                        break
                else:
                    current_gb = 0

            # Determine status based on thresholds
            if current_gb < min_gb:
                status = RequirementStatus.FAIL
                details = f"Insufficient RAM ({current_gb:.1f} GB < {min_gb} GB minimum)"
            elif current_gb < warn_gb:
                status = RequirementStatus.WARN
                details = f"RAM below recommended ({current_gb:.1f} GB < {warn_gb} GB)"
            else:
                status = RequirementStatus.PASS
                details = "Sufficient RAM for optimal performance"

            return RequirementCheck(
                name="ram",
                description="Memory (RAM)",
                status=status,
                current_value=f"{current_gb:.1f} GB",
                required_value=f"{min_gb} GB",
                recommended_value=f"{recommended_gb} GB",
                details=details,
            )

        except Exception as e:
            logger.warning(f"Could not check RAM: {e}")
            return RequirementCheck(
                name="ram",
                description="Memory (RAM)",
                status=RequirementStatus.SKIP,
                details=f"Could not check RAM: {e}",
            )

    def _check_disk_space(self) -> RequirementCheck:
        """
        Check available disk space.

        Finds the largest block device and checks against requirements.
        """
        min_gb = self.config.get("min_disk_gb", 60)
        recommended_gb = self.config.get("recommended_disk_gb", 120)

        try:
            # Check available space on largest block device
            max_space_gb = 0.0

            # Check /sys/block for disk sizes
            block_path = Path("/sys/block")
            if block_path.exists():
                for device in block_path.iterdir():
                    name = device.name
                    # Skip loop, ram, and virtual devices
                    if name.startswith(("loop", "ram", "dm-", "sr", "zram")):
                        continue

                    size_file = device / "size"
                    if size_file.exists():
                        # Size is in 512-byte sectors
                        sectors = int(size_file.read_text().strip())
                        size_gb = (sectors * 512) / (1024**3)
                        max_space_gb = max(max_space_gb, size_gb)

            # Determine status
            if max_space_gb < min_gb:
                status = RequirementStatus.FAIL
                details = f"Insufficient disk space ({max_space_gb:.0f} GB < {min_gb} GB)"
            elif max_space_gb < recommended_gb:
                status = RequirementStatus.WARN
                details = f"Disk space below recommended ({max_space_gb:.0f} GB)"
            else:
                status = RequirementStatus.PASS
                details = "Sufficient storage space available"

            return RequirementCheck(
                name="disk",
                description="Storage Space",
                status=status,
                current_value=f"{max_space_gb:.0f} GB",
                required_value=f"{min_gb} GB",
                recommended_value=f"{recommended_gb} GB (SSD recommended)",
                details=details,
            )

        except Exception as e:
            logger.warning(f"Could not check disk space: {e}")
            return RequirementCheck(
                name="disk",
                description="Storage Space",
                status=RequirementStatus.SKIP,
                details=f"Could not check disk space: {e}",
            )

    def _check_cpu_architecture(self) -> RequirementCheck:
        """Check CPU architecture."""
        require_x86_64 = self.config.get("require_x86_64", True)

        try:
            arch = os.uname().machine

            if arch == "x86_64":
                status = RequirementStatus.PASS
            elif require_x86_64:
                status = RequirementStatus.FAIL
            else:
                status = RequirementStatus.WARN

            return RequirementCheck(
                name="cpu_arch",
                description="CPU Architecture",
                status=status,
                current_value=arch,
                required_value="x86_64" if require_x86_64 else "Any",
                details="64-bit processor required for modern Linux gaming",
            )

        except Exception as e:
            return RequirementCheck(
                name="cpu_arch",
                description="CPU Architecture",
                status=RequirementStatus.SKIP,
                details=f"Could not check architecture: {e}",
            )

    def _check_efi_mode(self) -> RequirementCheck:
        """Check if booted in EFI mode."""
        require_efi = self.config.get("require_efi", False)

        efi_path = Path("/sys/firmware/efi")
        is_efi = efi_path.exists()

        if is_efi:
            status = RequirementStatus.PASS
            current = "UEFI"
        elif require_efi:
            status = RequirementStatus.FAIL
            current = "Legacy BIOS"
        else:
            status = RequirementStatus.WARN
            current = "Legacy BIOS"

        return RequirementCheck(
            name="efi",
            description="Boot Mode",
            status=status,
            current_value=current,
            required_value="UEFI" if require_efi else "UEFI (recommended)",
            details="UEFI boot mode recommended for modern installations",
        )

    def _check_secure_boot(self) -> RequirementCheck:
        """Check Secure Boot status."""
        require_disabled = self.config.get("require_secure_boot_disabled", False)

        try:
            # Check mokutil if available
            if shutil.which("mokutil"):
                result = subprocess.run(
                    ["mokutil", "--sb-state"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                is_enabled = "SecureBoot enabled" in result.stdout
            else:
                # Check via efivar
                sb_path = Path(
                    "/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c"
                )
                if sb_path.exists():
                    data = sb_path.read_bytes()
                    # Last byte indicates state (1 = enabled)
                    is_enabled = len(data) > 4 and data[-1] == 1
                else:
                    # Can't determine, assume disabled
                    is_enabled = False

            if is_enabled:
                status = RequirementStatus.FAIL if require_disabled else RequirementStatus.WARN
                current = "Enabled"
            else:
                status = RequirementStatus.PASS
                current = "Disabled"

            return RequirementCheck(
                name="secure_boot",
                description="Secure Boot",
                status=status,
                current_value=current,
                required_value="Disabled" if require_disabled else "Any",
                details="Secure Boot may need to be disabled for some drivers",
            )

        except Exception as e:
            return RequirementCheck(
                name="secure_boot",
                description="Secure Boot",
                status=RequirementStatus.SKIP,
                details=f"Could not check Secure Boot: {e}",
            )

    def _check_internet(self) -> RequirementCheck:
        """Check internet connectivity."""
        require_internet = self.config.get("require_internet", False)
        recommend_internet = self.config.get("recommend_internet", True)

        try:
            # Try to reach a known host
            if shutil.which("ping"):
                result = subprocess.run(
                    ["ping", "-c", "1", "-W", "3", "1.1.1.1"],
                    capture_output=True,
                    timeout=5,
                )
                has_internet = result.returncode == 0
            else:
                # Fallback: check if we can resolve DNS
                import socket

                try:
                    socket.getaddrinfo("cloudflare.com", 443, socket.AF_INET, socket.SOCK_STREAM)
                    has_internet = True
                except socket.gaierror:
                    has_internet = False

            if has_internet:
                status = RequirementStatus.PASS
                current = "Connected"
            elif require_internet:
                status = RequirementStatus.FAIL
                current = "Not connected"
            elif recommend_internet:
                status = RequirementStatus.WARN
                current = "Not connected"
            else:
                status = RequirementStatus.PASS
                current = "Not connected"

            return RequirementCheck(
                name="internet",
                description="Internet Connection",
                status=status,
                current_value=current,
                required_value="Required"
                if require_internet
                else "Recommended"
                if recommend_internet
                else "Optional",
                details="Internet may be needed for package updates",
            )

        except Exception as e:
            return RequirementCheck(
                name="internet",
                description="Internet Connection",
                status=RequirementStatus.SKIP,
                details=f"Could not check internet: {e}",
            )

    def _check_power_source(self) -> RequirementCheck:
        """Check if running on AC power."""
        require_ac = self.config.get("require_ac_power", False)
        recommend_ac = self.config.get("recommend_ac_power", True)

        try:
            # Check power supply status
            power_supply = Path("/sys/class/power_supply")

            if not power_supply.exists():
                # Desktop without battery - assume AC
                return RequirementCheck(
                    name="power",
                    description="Power Source",
                    status=RequirementStatus.PASS,
                    current_value="AC Power",
                    details="Desktop system detected",
                )

            # Look for AC adapter
            on_ac = False
            has_battery = False

            for supply in power_supply.iterdir():
                type_file = supply / "type"
                if not type_file.exists():
                    continue

                supply_type = type_file.read_text().strip()

                if supply_type == "Mains":
                    online_file = supply / "online"
                    if online_file.exists():
                        on_ac = online_file.read_text().strip() == "1"
                elif supply_type == "Battery":
                    has_battery = True

            if not has_battery:
                # Desktop
                status = RequirementStatus.PASS
                current = "AC Power (Desktop)"
            elif on_ac:
                status = RequirementStatus.PASS
                current = "AC Power"
            elif require_ac:
                status = RequirementStatus.FAIL
                current = "Battery"
            elif recommend_ac:
                status = RequirementStatus.WARN
                current = "Battery"
            else:
                status = RequirementStatus.PASS
                current = "Battery"

            return RequirementCheck(
                name="power",
                description="Power Source",
                status=status,
                current_value=current,
                required_value="AC Power" if require_ac else "AC Power (recommended)",
                details="AC power recommended to prevent interruption",
            )

        except Exception as e:
            return RequirementCheck(
                name="power",
                description="Power Source",
                status=RequirementStatus.SKIP,
                details=f"Could not check power: {e}",
            )

    def _check_battery_level(self) -> RequirementCheck:
        """Check battery level if on battery power."""
        min_percent = self.config.get("min_battery_percent", 20)

        try:
            power_supply = Path("/sys/class/power_supply")

            if not power_supply.exists():
                return RequirementCheck(
                    name="battery",
                    description="Battery Level",
                    status=RequirementStatus.SKIP,
                    details="No battery detected",
                )

            # Find battery
            for supply in power_supply.iterdir():
                type_file = supply / "type"
                if not type_file.exists():
                    continue

                if type_file.read_text().strip() == "Battery":
                    capacity_file = supply / "capacity"
                    if capacity_file.exists():
                        capacity = int(capacity_file.read_text().strip())

                        if capacity >= min_percent:
                            status = RequirementStatus.PASS
                        else:
                            status = RequirementStatus.WARN

                        return RequirementCheck(
                            name="battery",
                            description="Battery Level",
                            status=status,
                            current_value=f"{capacity}%",
                            required_value=f">{min_percent}%",
                            details="Minimum battery level for safe installation",
                        )

            return RequirementCheck(
                name="battery",
                description="Battery Level",
                status=RequirementStatus.SKIP,
                details="No battery detected",
            )

        except Exception as e:
            return RequirementCheck(
                name="battery",
                description="Battery Level",
                status=RequirementStatus.SKIP,
                details=f"Could not check battery: {e}",
            )

    def _check_gpu(self) -> RequirementCheck:
        """
        Check GPU compatibility with vendor and model overrides.

        Uses the GPUDetector to:
        - Detect all GPUs in the system
        - Check against configured availability list (AMD, INTEL, NVIDIA)
        - Validate against minimum model overrides if configured
        - Distinguish between dedicated and integrated GPUs
        """
        gpu_config = self.config.get("gpu", {})

        # Get configuration values
        availability = gpu_config.get("availability", ["AMD", "INTEL", "NVIDIA"])
        require_dedicated = gpu_config.get("require_dedicated", False)
        overrides = gpu_config.get("overrides", {})

        try:
            detector = GPUDetector()
            result = detector.check_compatibility(
                allowed_vendors=availability,
                require_dedicated=require_dedicated,
                nvidia_min=overrides.get("nvidia", ""),
                amd_min=overrides.get("amd", ""),
                intel_min=overrides.get("intel", ""),
            )

            # Build GPU list string for display
            detected_gpus = detector.detected_gpus
            if detected_gpus:
                gpu_names = []
                for gpu in detected_gpus:
                    if gpu.model:
                        gpu_names.append(f"{gpu.vendor.value} {gpu.model}")
                    else:
                        gpu_names.append(gpu.vendor.value)
                gpu_list = ", ".join(gpu_names)
            else:
                gpu_list = "None detected"

            # Determine status based on result
            if result["status"] == "pass":
                status = RequirementStatus.PASS
                details = result.get("message", "Compatible GPU detected")
            elif result["status"] == "warn":
                status = RequirementStatus.WARN
                details = result.get("message", "GPU compatibility warning")
            else:  # fail
                status = RequirementStatus.FAIL
                details = result.get("message", "GPU not compatible")

            # Build recommended value string
            if require_dedicated:
                rec_value = "Dedicated GPU required"
            else:
                rec_parts = []
                if "NVIDIA" in availability:
                    nvidia_min = overrides.get("nvidia", "")
                    rec_parts.append(f"NVIDIA{' >=' + nvidia_min if nvidia_min else ''}")
                if "AMD" in availability:
                    amd_min = overrides.get("amd", "")
                    rec_parts.append(f"AMD{' >=' + amd_min if amd_min else ''}")
                if "INTEL" in availability:
                    intel_min = overrides.get("intel", "")
                    rec_parts.append(f"Intel{' >=' + intel_min if intel_min else ''}")
                rec_value = " / ".join(rec_parts) if rec_parts else "Any GPU"

            return RequirementCheck(
                name="gpu",
                description="Graphics (GPU)",
                status=status,
                current_value=gpu_list,
                recommended_value=rec_value,
                details=details,
            )

        except Exception as e:
            logger.warning(f"Could not check GPU: {e}")
            return RequirementCheck(
                name="gpu",
                description="Graphics (GPU)",
                status=RequirementStatus.SKIP,
                details=f"Could not check GPU: {e}",
            )
