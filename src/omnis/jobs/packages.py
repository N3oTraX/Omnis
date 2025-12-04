"""
Packages Job - System package installation.

Handles package installation for the target system with support for multiple
package managers, installation modes, and error recovery.
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path
from typing import Any

from omnis.jobs.base import BaseJob, JobContext, JobResult

logger = logging.getLogger(__name__)


class PackagesJob(BaseJob):
    """
    System package installation job.

    Responsibilities:
    - Install essential system packages
    - Configure package repositories
    - Support multiple installation modes (essential, desktop, custom)
    - Handle installation errors with retry logic
    - Track installation progress
    """

    name = "packages"
    description = "System package installation"

    # Package installation modes
    MODE_ESSENTIAL = "essential"
    MODE_DESKTOP = "desktop"
    MODE_CUSTOM = "custom"

    # Essential packages for minimal system
    ESSENTIAL_PACKAGES = [
        "base",
        "linux",
        "linux-firmware",
        "networkmanager",
        "sudo",
        "nano",
        "vim",
    ]

    # Desktop environment packages
    DESKTOP_PACKAGES = [
        "xorg",
        "plasma",
        "kde-applications",
        "firefox",
        "konsole",
        "dolphin",
        "sddm",
    ]

    # Supported package managers
    SUPPORTED_PACKAGE_MANAGERS = ["pacman", "apt"]

    # Retry configuration for network failures
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # seconds

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the packages job."""
        super().__init__(config)
        self._packages_installed: list[str] = []
        self._packages_failed: list[str] = []

    def _get_package_manager(self, context: JobContext) -> str:
        """
        Determine which package manager to use.

        Args:
            context: Execution context with selections

        Returns:
            Package manager name ('pacman' or 'apt')
        """
        return context.selections.get("package_manager", "pacman")

    def _get_installation_mode(self, context: JobContext) -> str:
        """
        Get installation mode from context.

        Args:
            context: Execution context with selections

        Returns:
            Installation mode (essential, desktop, custom)
        """
        return context.selections.get("mode", self.MODE_ESSENTIAL)

    def _get_package_list(self, context: JobContext) -> list[str]:
        """
        Build package list based on installation mode.

        Args:
            context: Execution context with selections

        Returns:
            List of package names to install
        """
        mode = self._get_installation_mode(context)

        if mode == self.MODE_ESSENTIAL:
            return self.ESSENTIAL_PACKAGES.copy()

        if mode == self.MODE_DESKTOP:
            packages = self.ESSENTIAL_PACKAGES.copy()
            packages.extend(self.DESKTOP_PACKAGES)
            return packages

        if mode == self.MODE_CUSTOM:
            custom_packages = context.selections.get("packages", [])
            if not custom_packages:
                logger.warning("Custom mode selected but no packages specified")
                return self.ESSENTIAL_PACKAGES.copy()
            return custom_packages

        logger.warning(f"Unknown mode '{mode}', using essential packages")
        return self.ESSENTIAL_PACKAGES.copy()

    def _validate_package_names(self, packages: list[str]) -> JobResult:
        """
        Validate package names format.

        Args:
            packages: List of package names

        Returns:
            JobResult indicating validation success or failure
        """
        if not packages:
            return JobResult.fail("Package list is empty", error_code=30)

        invalid_packages = []
        for pkg in packages:
            # Basic validation: alphanumeric, dash, underscore
            if not pkg or not all(c.isalnum() or c in "-_." for c in pkg):
                invalid_packages.append(pkg)

        if invalid_packages:
            return JobResult.fail(
                f"Invalid package names: {invalid_packages}",
                error_code=31,
                data={"invalid_packages": invalid_packages},
            )

        return JobResult.ok("Package names validated")

    def _update_repositories(self, context: JobContext) -> JobResult:
        """
        Update package repositories/mirrors before installation.

        Args:
            context: Execution context

        Returns:
            JobResult indicating success or failure
        """
        pkg_manager = self._get_package_manager(context)
        target_root = context.target_root

        context.report_progress(5, "Updating package repositories...")
        logger.info(f"Updating {pkg_manager} repositories")

        try:
            if pkg_manager == "pacman":
                cmd = ["arch-chroot", target_root, "pacman", "-Syy"]
            elif pkg_manager == "apt":
                cmd = ["arch-chroot", target_root, "apt-get", "update"]
            else:
                return JobResult.fail(
                    f"Unsupported package manager: {pkg_manager}",
                    error_code=32,
                )

            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes timeout
            )

            logger.info("Repository update successful")
            logger.debug(f"Update output: {result.stdout}")
            return JobResult.ok("Repositories updated")

        except subprocess.CalledProcessError as e:
            logger.error(f"Repository update failed: {e.stderr}")
            return JobResult.fail(
                f"Failed to update repositories: {e.stderr}",
                error_code=33,
            )
        except subprocess.TimeoutExpired:
            return JobResult.fail(
                "Repository update timed out",
                error_code=34,
            )
        except FileNotFoundError:
            return JobResult.fail(
                "arch-chroot not found. Cannot access target system.",
                error_code=35,
            )

    def _install_packages_pacman(
        self,
        packages: list[str],
        target_root: str,
        context: JobContext,
    ) -> JobResult:
        """
        Install packages using pacman.

        Args:
            packages: List of package names
            target_root: Target root directory
            context: Execution context for progress reporting

        Returns:
            JobResult indicating success or failure
        """
        logger.info(f"Installing {len(packages)} packages with pacman")

        cmd = [
            "arch-chroot",
            target_root,
            "pacman",
            "-S",
            "--noconfirm",
            "--needed",  # Skip already installed packages
        ]
        cmd.extend(packages)

        try:
            # Run pacman with real-time output parsing
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            installed_count = 0
            total_packages = len(packages)

            for line in process.stdout:  # type: ignore
                line = line.strip()
                logger.debug(f"pacman: {line}")

                # Track installation progress
                if "installing" in line.lower():
                    installed_count += 1
                    percent = 20 + int((installed_count / total_packages) * 70)
                    context.report_progress(
                        percent,
                        f"Installing packages... ({installed_count}/{total_packages})",
                    )

            return_code = process.wait()

            if return_code != 0:
                return JobResult.fail(
                    f"pacman failed with exit code {return_code}",
                    error_code=36,
                    data={"return_code": return_code},
                )

            self._packages_installed.extend(packages)
            return JobResult.ok(
                f"Installed {len(packages)} packages",
                data={"packages": packages},
            )

        except FileNotFoundError:
            return JobResult.fail(
                "pacman or arch-chroot not found",
                error_code=35,
            )
        except Exception as e:
            logger.exception("Unexpected error during package installation")
            return JobResult.fail(
                f"Package installation failed: {e}",
                error_code=37,
                data={"exception": str(e)},
            )

    def _install_packages_apt(
        self,
        packages: list[str],
        target_root: str,
        context: JobContext,
    ) -> JobResult:
        """
        Install packages using apt.

        Args:
            packages: List of package names
            target_root: Target root directory
            context: Execution context for progress reporting

        Returns:
            JobResult indicating success or failure
        """
        logger.info(f"Installing {len(packages)} packages with apt")

        cmd = [
            "arch-chroot",
            target_root,
            "apt-get",
            "install",
            "-y",
            "--no-install-recommends",
        ]
        cmd.extend(packages)

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            installed_count = 0
            total_packages = len(packages)

            for line in process.stdout:  # type: ignore
                line = line.strip()
                logger.debug(f"apt: {line}")

                # Track installation progress
                if "setting up" in line.lower():
                    installed_count += 1
                    percent = 20 + int((installed_count / total_packages) * 70)
                    context.report_progress(
                        percent,
                        f"Installing packages... ({installed_count}/{total_packages})",
                    )

            return_code = process.wait()

            if return_code != 0:
                return JobResult.fail(
                    f"apt-get failed with exit code {return_code}",
                    error_code=38,
                    data={"return_code": return_code},
                )

            self._packages_installed.extend(packages)
            return JobResult.ok(
                f"Installed {len(packages)} packages",
                data={"packages": packages},
            )

        except FileNotFoundError:
            return JobResult.fail(
                "apt-get or arch-chroot not found",
                error_code=35,
            )
        except Exception as e:
            logger.exception("Unexpected error during package installation")
            return JobResult.fail(
                f"Package installation failed: {e}",
                error_code=37,
                data={"exception": str(e)},
            )

    def _install_packages_with_retry(
        self,
        packages: list[str],
        context: JobContext,
    ) -> JobResult:
        """
        Install packages with retry logic for network failures.

        Args:
            packages: List of package names
            context: Execution context

        Returns:
            JobResult indicating success or failure
        """
        pkg_manager = self._get_package_manager(context)
        target_root = context.target_root

        last_result = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            logger.info(f"Installation attempt {attempt}/{self.MAX_RETRIES}")

            if pkg_manager == "pacman":
                result = self._install_packages_pacman(packages, target_root, context)
            elif pkg_manager == "apt":
                result = self._install_packages_apt(packages, target_root, context)
            else:
                return JobResult.fail(
                    f"Unsupported package manager: {pkg_manager}",
                    error_code=32,
                )

            if result.success:
                return result

            last_result = result

            # Check if error is network-related and retry possible
            if result.error_code in (33, 34, 36, 38) and attempt < self.MAX_RETRIES:
                logger.warning(
                    f"Installation failed (attempt {attempt}), retrying in {self.RETRY_DELAY}s..."
                )
                context.report_progress(
                    15,
                    f"Installation failed, retrying... (attempt {attempt + 1}/{self.MAX_RETRIES})",
                )
                time.sleep(self.RETRY_DELAY)
                continue

            # Non-network error - don't retry
            if result.error_code not in (33, 34, 36, 38):
                return result

        # Max retries reached
        return JobResult.fail(
            f"Package installation failed after {self.MAX_RETRIES} attempts",
            error_code=39,
            data={
                "attempts": self.MAX_RETRIES,
                "packages_failed": packages,
                "last_error": last_result.message if last_result else "Unknown",
            },
        )

    def validate(self, context: JobContext) -> JobResult:
        """
        Validate package installation prerequisites.

        Checks:
        - Package manager is supported
        - Installation mode is valid
        - Package list is valid
        - Target is accessible
        - Required tools are available

        Args:
            context: Execution context

        Returns:
            JobResult indicating validation success or failure
        """
        errors = []

        # Validate package manager
        pkg_manager = self._get_package_manager(context)
        if pkg_manager not in self.SUPPORTED_PACKAGE_MANAGERS:
            errors.append(
                f"Unsupported package manager: {pkg_manager}. "
                f"Supported: {self.SUPPORTED_PACKAGE_MANAGERS}"
            )

        # Validate installation mode
        mode = self._get_installation_mode(context)
        valid_modes = [self.MODE_ESSENTIAL, self.MODE_DESKTOP, self.MODE_CUSTOM]
        if mode not in valid_modes:
            errors.append(f"Invalid mode: {mode}. Valid modes: {valid_modes}")

        # Validate custom packages if in custom mode
        if mode == self.MODE_CUSTOM:
            packages = context.selections.get("packages", [])
            if not packages:
                errors.append("Custom mode requires 'packages' list in selections")
            else:
                validation = self._validate_package_names(packages)
                if not validation.success:
                    errors.append(validation.message)

        # Validate target root exists
        target_path = Path(context.target_root)
        if not target_path.exists():
            errors.append(f"Target directory not found: {context.target_root}")
        elif not target_path.is_dir():
            errors.append(f"Target path is not a directory: {context.target_root}")

        if errors:
            return JobResult.fail(
                message=f"Validation errors: {'; '.join(errors)}",
                error_code=40,
                data={"errors": errors},
            )

        logger.info("Package installation prerequisites validated")
        return JobResult.ok("Package installation validated")

    def run(self, context: JobContext) -> JobResult:
        """
        Execute package installation job.

        Args:
            context: Execution context

        Returns:
            JobResult indicating success or failure
        """
        context.report_progress(0, "Starting package installation...")

        # Validate first
        validation = self.validate(context)
        if not validation.success:
            return validation

        # Get package list
        packages = self._get_package_list(context)
        mode = self._get_installation_mode(context)

        logger.info(f"Installing packages in {mode} mode: {packages}")
        context.report_progress(2, f"Installing {len(packages)} packages...")

        # Update repositories
        update_result = self._update_repositories(context)
        if not update_result.success:
            logger.warning("Repository update failed, continuing with installation...")
            # Non-critical: continue with installation

        context.report_progress(10, "Repositories updated")

        # Install packages with retry
        install_result = self._install_packages_with_retry(packages, context)
        if not install_result.success:
            return install_result

        context.report_progress(95, "Package installation complete")
        logger.info(f"Successfully installed {len(self._packages_installed)} packages")

        context.report_progress(100, "Package installation finished")

        return JobResult.ok(
            "Packages installed successfully",
            data={
                "mode": mode,
                "packages_installed": self._packages_installed,
                "packages_failed": self._packages_failed,
                "total_packages": len(self._packages_installed),
            },
        )

    def estimate_duration(self) -> int:
        """
        Estimate execution time in seconds.

        Estimation varies based on:
        - Number of packages
        - Network speed
        - Package size
        - System resources

        Returns:
            Estimated duration in seconds
        """
        # Base estimate: 5 minutes for essential packages
        # Desktop mode: 15 minutes (more packages)
        base_estimate = 300

        if hasattr(self, "_config") and self._config:
            mode = self._config.get("mode", self.MODE_ESSENTIAL)
            if mode == self.MODE_DESKTOP:
                return 900  # 15 minutes
            if mode == self.MODE_CUSTOM:
                packages = self._config.get("packages", [])
                # Estimate ~10 seconds per package
                return max(base_estimate, len(packages) * 10)

        return base_estimate

    def cleanup(self, _context: JobContext) -> None:
        """
        Clean up after package installation.

        Clears package cache if needed.

        Args:
            _context: Execution context (unused)
        """
        logger.debug("PackagesJob cleanup - package cache retained")
