"""
Users Job for Omnis Installer.

Creates user accounts, sets passwords securely, and configures hostname.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Any

from omnis.jobs.base import BaseJob, JobContext, JobResult

logger = logging.getLogger(__name__)


class UsersJob(BaseJob):
    """
    User account and hostname configuration job.

    Responsibilities:
    - Create primary user account with appropriate groups
    - Set user password securely (using chpasswd, never logging passwords)
    - Configure user shell and home directory
    - Set system hostname
    - Optionally configure sudo access

    SECURITY: This job handles sensitive data (passwords). All password operations
    are implemented with security best practices:
    - Never log passwords (not even in debug mode)
    - Use secure methods (chpasswd) for password setting
    - Clear password from memory as soon as possible
    """

    name = "users"
    description = "User account and hostname configuration"

    # Default groups for the primary user
    DEFAULT_GROUPS = ["wheel", "audio", "video", "network", "storage", "optical"]

    # Valid username pattern (lowercase letters, digits, underscore, hyphen)
    USERNAME_PATTERN = re.compile(r"^[a-z_][a-z0-9_-]*$")

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the users job."""
        super().__init__(config)

    def validate(self, context: JobContext) -> JobResult:
        """
        Validate user configuration before execution.

        Args:
            context: Execution context with user selections

        Returns:
            JobResult indicating if configuration is valid
        """
        username = context.selections.get("username", "").strip()
        password = context.selections.get("password", "")
        hostname = context.selections.get("hostname", "").strip()

        # Validate username
        if not username:
            return JobResult.fail("Username is required", error_code=10)

        if not self._validate_username(username):
            return JobResult.fail(
                f"Invalid username '{username}'. Must start with lowercase letter or underscore, "
                "and contain only lowercase letters, digits, underscores, or hyphens.",
                error_code=11,
            )

        # Validate password (must not be empty, but we don't log it)
        if not password:
            return JobResult.fail("Password is required", error_code=12)

        # Validate hostname (optional but if provided must be valid)
        if hostname and not self._validate_hostname(hostname):
            return JobResult.fail(
                f"Invalid hostname '{hostname}'. Must contain only lowercase letters, digits, "
                "and hyphens, and cannot start/end with hyphen.",
                error_code=13,
            )

        return JobResult.ok("User configuration is valid")

    def run(self, context: JobContext) -> JobResult:
        """
        Execute user account creation and configuration.

        Args:
            context: Execution context

        Returns:
            JobResult indicating success or failure
        """
        context.report_progress(0, "Starting user configuration...")

        # Validate first
        validation = self.validate(context)
        if not validation.success:
            return validation

        # Extract configuration
        username = context.selections.get("username", "").strip()
        password = context.selections.get("password", "")  # NEVER LOG THIS
        fullname = context.selections.get("fullname", "").strip()
        is_admin = context.selections.get("is_admin", True)
        hostname = context.selections.get("hostname", "").strip()
        shell = context.selections.get("shell", "/bin/bash")
        target_root = context.target_root

        try:
            # Step 1: Create user account
            context.report_progress(20, f"Creating user account '{username}'...")
            create_result = self._create_user(
                target_root=target_root,
                username=username,
                fullname=fullname,
                shell=shell,
                is_admin=is_admin,
            )
            if not create_result.success:
                return create_result

            # Step 2: Set user password (SECURE - never log password)
            context.report_progress(50, "Setting user password...")
            password_result = self._set_password(
                target_root=target_root,
                username=username,
                password=password,
            )
            if not password_result.success:
                return password_result

            # Clear password from memory
            password = ""

            # Step 3: Configure hostname (if provided)
            if hostname:
                context.report_progress(80, f"Setting hostname '{hostname}'...")
                hostname_result = self._set_hostname(target_root, hostname)
                if not hostname_result.success:
                    return hostname_result

            context.report_progress(100, "User configuration complete")

            return JobResult.ok(
                f"User '{username}' created successfully",
                data={
                    "username": username,
                    "is_admin": is_admin,
                    "hostname": hostname or "not_set",
                },
            )

        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {e.cmd} (exit code: {e.returncode})")
            return JobResult.fail(
                f"User configuration failed: {e}",
                error_code=20,
            )
        except Exception as e:
            logger.exception("Unexpected error during user configuration")
            return JobResult.fail(
                f"Unexpected error: {e}",
                error_code=21,
            )

    def _create_user(
        self,
        target_root: str,
        username: str,
        fullname: str,
        shell: str,
        is_admin: bool,
    ) -> JobResult:
        """
        Create user account with appropriate groups.

        Args:
            target_root: Target root directory
            username: Username to create
            fullname: Full name (GECOS field)
            shell: Login shell path
            is_admin: Whether to add to admin group (wheel/sudo)

        Returns:
            JobResult indicating success or failure
        """
        # Build groups list
        groups = self.DEFAULT_GROUPS.copy()

        # Add admin group if requested
        if is_admin:
            # Check which admin group exists (wheel for Arch, sudo for Debian)
            group_file = Path(target_root) / "etc" / "group"
            if group_file.exists():
                group_content = group_file.read_text()
                # Use sudo group for Debian-based systems if wheel doesn't exist
                if (
                    "wheel:" not in group_content
                    and "sudo:" in group_content
                    and "sudo" not in groups
                ):
                    groups.append("sudo")
            # Ensure wheel is in groups (default for Arch)
            if "wheel" not in groups:
                groups.insert(0, "wheel")

        groups_str = ",".join(groups)

        # Build useradd command
        cmd = [
            "arch-chroot",
            target_root,
            "useradd",
            "-m",  # Create home directory
            "-G",
            groups_str,  # Supplementary groups
            "-s",
            shell,  # Login shell
        ]

        # Add GECOS field if fullname provided
        if fullname:
            cmd.extend(["-c", fullname])

        cmd.append(username)

        try:
            logger.info(f"Creating user '{username}' with groups: {groups_str}")
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            return JobResult.ok(f"User '{username}' created")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create user: {e.stderr}")
            return JobResult.fail(
                f"Failed to create user '{username}': {e.stderr}",
                error_code=22,
            )

    def _set_password(
        self,
        target_root: str,
        username: str,
        password: str,
    ) -> JobResult:
        """
        Set user password securely using chpasswd.

        SECURITY CRITICAL:
        - Password is passed via stdin to chpasswd (not command line)
        - Password is never logged (not even in debug mode)
        - Uses subprocess.PIPE to avoid shell exposure

        Args:
            target_root: Target root directory
            username: Username
            password: Password (NEVER LOGGED)

        Returns:
            JobResult indicating success or failure
        """
        # Format: username:password
        # SECURITY: Do NOT log this string
        password_input = f"{username}:{password}"

        cmd = ["arch-chroot", target_root, "chpasswd"]

        try:
            # SECURITY: Pass password via stdin, never via command line
            subprocess.run(
                cmd,
                input=password_input,
                text=True,
                capture_output=True,
                check=True,
            )

            # Clear password from memory immediately
            password_input = ""

            # SECURITY: Do NOT log that password was set successfully with any details
            logger.info(f"Password configured for user '{username}'")
            return JobResult.ok("Password set")

        except subprocess.CalledProcessError as e:
            # SECURITY: Do NOT include password or password_input in error messages
            logger.error(f"Failed to set password: {e.stderr}")
            return JobResult.fail(
                "Failed to set user password",
                error_code=23,
            )

    def _set_hostname(self, target_root: str, hostname: str) -> JobResult:
        """
        Configure system hostname.

        Args:
            target_root: Target root directory
            hostname: Hostname to set

        Returns:
            JobResult indicating success or failure
        """
        try:
            # Write /etc/hostname
            hostname_file = Path(target_root) / "etc" / "hostname"
            hostname_file.write_text(f"{hostname}\n")

            # Update /etc/hosts
            hosts_file = Path(target_root) / "etc" / "hosts"
            hosts_content = f"""# Generated by Omnis installer
127.0.0.1   localhost
::1         localhost
127.0.1.1   {hostname}.localdomain {hostname}
"""
            hosts_file.write_text(hosts_content)

            logger.info(f"Hostname set to '{hostname}'")
            return JobResult.ok(f"Hostname set to '{hostname}'")

        except OSError as e:
            logger.error(f"Failed to set hostname: {e}")
            return JobResult.fail(
                f"Failed to set hostname: {e}",
                error_code=24,
            )

    def _validate_username(self, username: str) -> bool:
        """
        Validate username format.

        Rules:
        - Must start with lowercase letter or underscore
        - Can contain lowercase letters, digits, underscores, hyphens
        - Typical Linux username restrictions

        Args:
            username: Username to validate

        Returns:
            True if valid, False otherwise
        """
        if not username or len(username) > 32:
            return False
        return bool(self.USERNAME_PATTERN.match(username))

    def _validate_hostname(self, hostname: str) -> bool:
        """
        Validate hostname format.

        Rules:
        - Can contain lowercase letters, digits, hyphens
        - Cannot start or end with hyphen
        - Maximum 63 characters per label

        Args:
            hostname: Hostname to validate

        Returns:
            True if valid, False otherwise
        """
        if not hostname or len(hostname) > 253:
            return False

        # Check each label (parts separated by dots)
        labels = hostname.split(".")
        for label in labels:
            if not label or len(label) > 63:
                return False
            if label.startswith("-") or label.endswith("-"):
                return False
            if not re.match(r"^[a-z0-9-]+$", label):
                return False

        return True

    def estimate_duration(self) -> int:
        """
        Estimate execution time in seconds.

        Returns:
            Estimated duration (user creation is fast)
        """
        return 10
