"""
Locale Job - System locale, timezone and keyboard configuration.

Configures the target system's locale settings, timezone, and keyboard layout.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from omnis.jobs.base import BaseJob, JobContext, JobResult

logger = logging.getLogger(__name__)


class LocaleJob(BaseJob):
    """
    System locale, timezone and keyboard configuration.

    Responsibilities:
    - Configure system locale (language, character encoding)
    - Set system timezone with hardware clock sync
    - Configure console and X11 keyboard layouts
    """

    name = "locale"
    description = "System locale, timezone and keyboard configuration"

    # Common locales available on most Linux systems
    COMMON_LOCALES = [
        "en_US.UTF-8",
        "en_GB.UTF-8",
        "fr_FR.UTF-8",
        "de_DE.UTF-8",
        "es_ES.UTF-8",
        "it_IT.UTF-8",
        "pt_BR.UTF-8",
        "ru_RU.UTF-8",
        "zh_CN.UTF-8",
        "ja_JP.UTF-8",
    ]

    # Common keyboard layouts
    COMMON_KEYMAPS = [
        "us",
        "uk",
        "fr",
        "de",
        "es",
        "it",
        "pt",
        "ru",
        "dvorak",
    ]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the locale job."""
        super().__init__(config)

    def _get_available_timezones(self) -> list[str]:
        """
        Get list of available timezones from the system.

        Returns:
            List of timezone names (e.g., "Europe/Paris")
        """
        zoneinfo_path = Path("/usr/share/zoneinfo")
        if not zoneinfo_path.exists():
            logger.warning("Zoneinfo directory not found, using fallback list")
            return [
                "UTC",
                "Europe/Paris",
                "Europe/London",
                "America/New_York",
                "America/Los_Angeles",
            ]

        timezones = []
        # Scan common timezone directories
        for region_dir in zoneinfo_path.iterdir():
            if region_dir.is_dir() and region_dir.name[0].isupper():
                for zone_file in region_dir.iterdir():
                    if zone_file.is_file():
                        timezones.append(f"{region_dir.name}/{zone_file.name}")

        return sorted(timezones) if timezones else ["UTC"]

    def _validate_locale(self, locale: str) -> bool:
        """
        Validate locale format.

        Args:
            locale: Locale string (e.g., "fr_FR.UTF-8")

        Returns:
            True if locale format is valid
        """
        if not locale:
            return False

        # Basic format validation: xx_YY.UTF-8
        parts = locale.split(".")
        if len(parts) != 2:
            return False

        lang_country = parts[0]
        encoding = parts[1]

        # Check encoding
        if encoding.upper() not in ["UTF-8", "UTF8"]:
            logger.warning(f"Non-UTF-8 encoding detected: {encoding}")

        # Check language_COUNTRY format
        return "_" in lang_country and len(lang_country) >= 5

    def _validate_timezone(self, timezone: str) -> bool:
        """
        Validate timezone exists in zoneinfo.

        Args:
            timezone: Timezone name (e.g., "Europe/Paris")

        Returns:
            True if timezone is valid
        """
        if not timezone:
            return False

        zoneinfo_path = Path("/usr/share/zoneinfo") / timezone
        return zoneinfo_path.exists() and zoneinfo_path.is_file()

    def _validate_keymap(self, keymap: str) -> bool:
        """
        Validate keyboard layout.

        Args:
            keymap: Keyboard layout name (e.g., "fr")

        Returns:
            True if keymap is valid
        """
        if not keymap:
            return False

        # Accept common keymaps or any alphanumeric layout name
        return keymap in self.COMMON_KEYMAPS or keymap.isalnum()

    def _configure_locale(self, context: JobContext) -> JobResult:
        """
        Configure system locale.

        Args:
            context: Execution context with target_root and selections

        Returns:
            JobResult indicating success or failure
        """
        locale = context.selections.get("locale", "en_US.UTF-8")

        if not self._validate_locale(locale):
            return JobResult.fail(f"Invalid locale format: {locale}", error_code=20)

        context.report_progress(10, f"Configuring locale: {locale}")

        target_root = Path(context.target_root)
        locale_gen_path = target_root / "etc" / "locale.gen"
        locale_conf_path = target_root / "etc" / "locale.conf"

        try:
            # Ensure /etc directory exists
            locale_conf_path.parent.mkdir(parents=True, exist_ok=True)

            # Write locale.conf
            locale_conf_content = f"LANG={locale}\n"
            locale_conf_path.write_text(locale_conf_content, encoding="utf-8")
            logger.info(f"Written {locale_conf_path}")

            # If locale.gen exists, uncomment the selected locale
            if locale_gen_path.exists():
                locale_gen_content = locale_gen_path.read_text(encoding="utf-8")
                # Uncomment the locale line
                updated_content = locale_gen_content.replace(f"#{locale}", locale).replace(
                    f"# {locale}", locale
                )
                locale_gen_path.write_text(updated_content, encoding="utf-8")
                logger.info(f"Updated {locale_gen_path}")

                # Generate locale (using chroot)
                try:
                    subprocess.run(
                        ["arch-chroot", str(target_root), "locale-gen"],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    logger.info("locale-gen executed successfully")
                except subprocess.CalledProcessError as e:
                    logger.warning(f"locale-gen failed: {e.stderr}")
                    # Non-critical: continue even if locale-gen fails
                except FileNotFoundError:
                    logger.warning("arch-chroot not found, skipping locale-gen")

            return JobResult.ok(f"Locale configured: {locale}")

        except OSError as e:
            return JobResult.fail(f"Failed to configure locale: {e}", error_code=21)

    def _configure_timezone(self, context: JobContext) -> JobResult:
        """
        Configure system timezone.

        Args:
            context: Execution context with target_root and selections

        Returns:
            JobResult indicating success or failure
        """
        timezone = context.selections.get("timezone", "UTC")

        if not self._validate_timezone(timezone):
            return JobResult.fail(f"Invalid timezone: {timezone}", error_code=22)

        context.report_progress(40, f"Configuring timezone: {timezone}")

        target_root = Path(context.target_root)
        localtime_link = target_root / "etc" / "localtime"
        timezone_file = target_root / "etc" / "timezone"

        try:
            # Ensure /etc directory exists
            localtime_link.parent.mkdir(parents=True, exist_ok=True)

            # Remove existing symlink if present
            if localtime_link.exists() or localtime_link.is_symlink():
                localtime_link.unlink()

            # Create symlink to zoneinfo
            zoneinfo_target = Path("/usr/share/zoneinfo") / timezone
            localtime_link.symlink_to(zoneinfo_target)
            logger.info(f"Created symlink: {localtime_link} -> {zoneinfo_target}")

            # Write timezone file
            timezone_file.write_text(f"{timezone}\n", encoding="utf-8")
            logger.info(f"Written {timezone_file}")

            # Sync hardware clock (using chroot)
            try:
                subprocess.run(
                    ["arch-chroot", str(target_root), "hwclock", "--systohc"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                logger.info("Hardware clock synchronized")
            except subprocess.CalledProcessError as e:
                logger.warning(f"hwclock failed: {e.stderr}")
                # Non-critical: continue even if hwclock fails
            except FileNotFoundError:
                logger.warning("arch-chroot not found, skipping hwclock")

            return JobResult.ok(f"Timezone configured: {timezone}")

        except OSError as e:
            return JobResult.fail(f"Failed to configure timezone: {e}", error_code=23)

    def _configure_keyboard(self, context: JobContext) -> JobResult:
        """
        Configure keyboard layout.

        Args:
            context: Execution context with target_root and selections

        Returns:
            JobResult indicating success or failure
        """
        keymap = context.selections.get("keymap", "us")

        if not self._validate_keymap(keymap):
            return JobResult.fail(f"Invalid keyboard layout: {keymap}", error_code=24)

        context.report_progress(70, f"Configuring keyboard: {keymap}")

        target_root = Path(context.target_root)
        vconsole_conf = target_root / "etc" / "vconsole.conf"
        xorg_kbd_conf = target_root / "etc" / "X11" / "xorg.conf.d" / "00-keyboard.conf"

        try:
            # Ensure /etc directory exists
            vconsole_conf.parent.mkdir(parents=True, exist_ok=True)

            # Write vconsole.conf (for console)
            vconsole_content = f"KEYMAP={keymap}\n"
            vconsole_conf.write_text(vconsole_content, encoding="utf-8")
            logger.info(f"Written {vconsole_conf}")

            # Write X11 keyboard config (for graphical environment)
            xorg_kbd_conf.parent.mkdir(parents=True, exist_ok=True)
            xorg_content = f"""# Keyboard configuration for X11
Section "InputClass"
    Identifier "system-keyboard"
    MatchIsKeyboard "on"
    Option "XkbLayout" "{keymap}"
EndSection
"""
            xorg_kbd_conf.write_text(xorg_content, encoding="utf-8")
            logger.info(f"Written {xorg_kbd_conf}")

            return JobResult.ok(f"Keyboard configured: {keymap}")

        except OSError as e:
            return JobResult.fail(f"Failed to configure keyboard: {e}", error_code=25)

    def validate(self, context: JobContext) -> JobResult:
        """
        Validate that locale configuration can proceed.

        Args:
            context: Execution context

        Returns:
            JobResult indicating if selections are valid
        """
        errors = []

        # Validate locale
        locale = context.selections.get("locale")
        if locale and not self._validate_locale(locale):
            errors.append(f"Invalid locale: {locale}")

        # Validate timezone
        timezone = context.selections.get("timezone")
        if timezone and not self._validate_timezone(timezone):
            errors.append(f"Invalid timezone: {timezone}")

        # Validate keymap
        keymap = context.selections.get("keymap")
        if keymap and not self._validate_keymap(keymap):
            errors.append(f"Invalid keyboard layout: {keymap}")

        if errors:
            return JobResult.fail(
                message=f"Validation errors: {', '.join(errors)}",
                error_code=19,
                data={"errors": errors},
            )

        return JobResult.ok("Locale configuration validated")

    def run(self, context: JobContext) -> JobResult:
        """
        Execute the locale configuration job.

        Args:
            context: Execution context

        Returns:
            JobResult indicating success or failure
        """
        context.report_progress(0, "Starting locale configuration...")

        # Validate first
        validation = self.validate(context)
        if not validation.success:
            return validation

        # Configure locale
        locale_result = self._configure_locale(context)
        if not locale_result.success:
            return locale_result

        # Configure timezone
        timezone_result = self._configure_timezone(context)
        if not timezone_result.success:
            return timezone_result

        # Configure keyboard
        keyboard_result = self._configure_keyboard(context)
        if not keyboard_result.success:
            return keyboard_result

        context.report_progress(100, "Locale configuration complete")

        return JobResult.ok(
            "Locale, timezone and keyboard configured successfully",
            data={
                "locale": context.selections.get("locale", "en_US.UTF-8"),
                "timezone": context.selections.get("timezone", "UTC"),
                "keymap": context.selections.get("keymap", "us"),
            },
        )

    def estimate_duration(self) -> int:
        """
        Estimate execution time in seconds.

        Returns:
            Estimated duration (locale configuration is quick)
        """
        return 15
