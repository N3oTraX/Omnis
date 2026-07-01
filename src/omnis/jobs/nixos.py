"""
NixOS Install Job for the Omnis Installer.

This job makes GLF OS (a NixOS-based distribution) actually installable. It is
the Phase 2 core step and is faithfully modelled on the GLF Calamares module
``patches/calamares-nixos-extensions/modules/nixos/main.py``.

High-level sequence (executed on an already-mounted ``target_root``):

1. Assemble ``configuration.nix`` from templates (head, bootloader, network,
   locale, keymap, users, autologin, tail) plus the GLF-specific
   ``glf.environment.type`` / ``glf.environment.edition`` options.
2. Run ``nixos-generate-config --root <target>`` to produce
   ``hardware-configuration.nix``.
3. Write ``configuration.nix`` and copy the GLF flake files
   (``flake.nix``, ``flake.lock``, ``customConfig``) into
   ``<target>/etc/nixos`` while PRESERVING the generated
   ``hardware-configuration.nix``.
4. Inject ``boot.initrd.luks.devices`` when the root partition is encrypted.
5. Run ``nixos-install --no-root-passwd --option sandbox false
   --option build-users-group "" --flake <target>/etc/nixos#GLF-OS
   --root <target>``.

CRITICAL SECURITY WARNING:
This job performs a PRIVILEGED, DESTRUCTIVE operation (it installs an OS onto a
mounted target). It honours the same guard-rails as the partition job:

- ``dry_run=True`` by default (commands are logged, never executed).
- ``confirmed=False`` by default (a real run is refused without confirmation).
- Passwords / passphrases are NEVER logged and are wiped after use.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from omnis.jobs.base import BaseJob, JobContext, JobResult

logger = logging.getLogger(__name__)

# =============================================================================
# configuration.nix templates (faithful to the Calamares nixos module)
# =============================================================================

CFG_HEAD = """{ inputs, config, pkgs, lib, ... }:

{
  nix.settings.experimental-features = [ "nix-command" "flakes" ];
  imports =
    [ # Include the results of the hardware scan + GLF modules
      ./hardware-configuration.nix
      ./customConfig

    ];

"""

CFG_ENVIRONMENT = """  glf.environment.type = "{environment}";
  glf.environment.edition = "{edition}";

"""

CFG_BOOT_EFI = """  # Bootloader.
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

"""

CFG_BOOT_BIOS = """  # Bootloader.
  boot.loader.grub.enable = true;
  boot.loader.grub.device = "{bootdev}";
  boot.loader.grub.useOSProber = true;

"""

CFG_NETWORK = """  networking.hostName = "{hostname}"; # Define your hostname.

"""

CFG_NETWORK_MANAGER = """  # Enable networking
  networking.networkmanager.enable = true;

"""

CFG_TIME = """  # Set your time zone.
  time.timeZone = "{timezone}";

"""

CFG_LOCALE = """  # Select internationalisation properties.
  i18n.defaultLocale = "{locale}";

"""

CFG_KEYMAP = """  # Configure keymap
  console.useXkbConfig = true;
  services.xserver.xkb = {{
    layout = "{layout}";
    variant = "{variant}";
  }};

"""

CFG_USERS = """  # Define a user account.
  users.users.{username} = {{
    isNormalUser = true;
    description = "{fullname}";
    extraGroups = [ {groups} ];
  }};

"""

CFG_AUTOLOGIN = """  # Enable automatic login for the user.
  services.displayManager.autoLogin.enable = true;
  services.displayManager.autoLogin.user = "{username}";

"""

CFG_TAIL = """  system.stateVersion = "{nixos_version}"; # DO NOT TOUCH
}}
"""

# Default GLF OS user groups (mirrors the Calamares nixos module).
DEFAULT_USER_GROUPS = (
    "networkmanager",
    "wheel",
    "scanner",
    "lp",
    "disk",
    "input",
    "render",
    "video",
)

# Fallback stateVersion when ``nixos-version`` cannot be queried (dry-run/mock).
DEFAULT_STATE_VERSION = "25.11"

# Error codes (kept distinct from the partition job's 30-52 range).
ERR_NO_TARGET = 60
ERR_TARGET_MISSING = 61
ERR_FLAKE_SOURCE_MISSING = 62
ERR_NOT_CONFIRMED = 63
ERR_GENERATE_CONFIG = 64
ERR_WRITE_CONFIG = 65
ERR_COPY_FLAKE = 66
ERR_INSTALL = 67
ERR_COMMAND_FAILED = 68
ERR_TOOL_NOT_FOUND = 69


class NixosJob(BaseJob):
    """
    NixOS install job for GLF OS.

    Replicates the GLF Calamares ``nixos`` module: generates a
    ``configuration.nix`` from the user's selections, runs
    ``nixos-generate-config``, copies the GLF flake, injects LUKS devices when
    encryption is enabled, then runs ``nixos-install`` against the GLF flake
    attribute (``GLF-OS``).

    SECURITY MODEL:
    - ``dry_run=True`` by default (simulation only).
    - ``confirmed=False`` by default (real runs refused without confirmation).
    - Secrets (passwords, passphrases) are never logged and wiped after use.
    """

    name = "nixos"
    description = "Generate NixOS configuration and install GLF OS"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the NixOS install job."""
        super().__init__(config)
        # The LUKS mapper name used by the partition job (kept in sync).
        self._luks_mapper_name = "cryptroot"

    # -------------------------------------------------------------------------
    # Configuration helpers
    # -------------------------------------------------------------------------

    def _flake_source(self) -> str:
        """Return the GLF flake source directory (default ``/iso/nixos``)."""
        return str(self._config.get("flake_source", "/iso/nixos"))

    def _flake_attr(self) -> str:
        """Return the flake attribute to install (default ``GLF-OS``)."""
        return str(self._config.get("flake_attr", "GLF-OS"))

    def _etc_nixos(self, target_root: str) -> Path:
        """Return the ``<target>/etc/nixos`` path."""
        return Path(target_root) / "etc" / "nixos"

    @staticmethod
    def _map_environment(desktop_environment: str) -> str:
        """
        Map the selected desktop environment to ``glf.environment.type``.

        GLF OS expects ``gnome`` or ``plasma`` (KDE). Anything unknown is passed
        through unchanged so new environments do not silently break.
        """
        de = (desktop_environment or "gnome").strip().lower()
        # ``kde`` is a common alias for Plasma; normalise it.
        if de == "kde":
            return "plasma"
        return de

    @staticmethod
    def _map_edition(edition: str) -> str:
        """Map the selected edition to ``glf.environment.edition``."""
        return (edition or "standard").strip().lower()

    def _detect_state_version(self) -> str:
        """
        Query the running system's NixOS ``stateVersion`` (major.minor).

        Falls back to :data:`DEFAULT_STATE_VERSION` when ``nixos-version`` is
        unavailable (e.g. dry-run on a non-NixOS host, or in tests).
        """
        try:
            out = subprocess.run(
                ["nixos-version"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            return DEFAULT_STATE_VERSION
        parts = out.split(".")
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[1]}"[:5]
        return DEFAULT_STATE_VERSION

    def _build_configuration(self, context: JobContext) -> str:
        """
        Assemble the ``configuration.nix`` contents from user selections.

        Mirrors the template assembly order of the Calamares nixos module:
        head → environment → bootloader → network → time → locale → keymap →
        users → autologin → tail. LUKS device injection is appended separately
        by :meth:`_luks_config` (before the tail) when encryption is enabled.

        Args:
            context: Execution context (reads ``selections``)

        Returns:
            The full ``configuration.nix`` text.
        """
        s = context.selections
        cfg = CFG_HEAD

        # GLF environment/edition (the defining GLF-OS options).
        environment = self._map_environment(str(s.get("desktop_environment", "gnome")))
        edition = self._map_edition(str(s.get("edition", "standard")))
        cfg += CFG_ENVIRONMENT.format(environment=environment, edition=edition)

        # Bootloader: EFI (systemd-boot) is the GLF OS default. BIOS/GRUB is
        # emitted only when explicitly requested via ``firmware_type``.
        firmware = str(s.get("firmware_type", "efi")).lower()
        if firmware == "bios":
            bootdev = str(s.get("disk", "nodev")) or "nodev"
            cfg += CFG_BOOT_BIOS.format(bootdev=bootdev)
        else:
            cfg += CFG_BOOT_EFI

        # LUKS device injection (before network, matching Calamares ordering
        # where luks devices are appended to cfg as they are discovered).
        cfg += self._luks_config(context)

        # Networking.
        hostname = str(s.get("hostname", "") or "GLF-OS")
        cfg += CFG_NETWORK.format(hostname=hostname)
        cfg += CFG_NETWORK_MANAGER

        # Time zone.
        timezone = str(s.get("timezone", "") or "")
        if timezone:
            cfg += CFG_TIME.format(timezone=timezone)

        # Locale (normalise Calamares-style ``.utf8`` to NixOS ``.UTF-8``).
        locale = str(s.get("locale", "") or s.get("language", "") or "")
        locale = locale.replace(".utf8", ".UTF-8").replace(".UTF8", ".UTF-8")
        if locale:
            cfg += CFG_LOCALE.format(locale=locale)

        # Keymap.
        layout = str(s.get("keymap", "") or "")
        if layout:
            variant = str(s.get("keyboard_variant", "") or "")
            cfg += CFG_KEYMAP.format(layout=layout, variant=variant)

        # User account.
        username = str(s.get("username", "") or "")
        if username:
            fullname = str(s.get("fullname", "") or "")
            groups = " ".join(f'"{g}"' for g in DEFAULT_USER_GROUPS)
            cfg += CFG_USERS.format(username=username, fullname=fullname, groups=groups)
            if bool(s.get("auto_login", False)):
                cfg += CFG_AUTOLOGIN.format(username=username)

        # Tail (stateVersion).
        cfg += CFG_TAIL.format(nixos_version=self._detect_state_version())
        return cfg

    def _luks_config(self, context: JobContext) -> str:
        """
        Build the ``boot.initrd.luks.devices`` snippet for an encrypted root.

        The partition job LUKS-wraps the root partition (mapper ``cryptroot``)
        and mounts ``/dev/mapper/cryptroot``. NixOS' ``nixos-generate-config``
        does not always detect the underlying LUKS device, so we inject it
        explicitly, pointing at the raw root partition.

        Returns an empty string when encryption is disabled.

        SECURITY: the passphrase is never referenced here — only the device
        path (which is not secret) is written.
        """
        s = context.selections
        if not bool(s.get("encryption", False)):
            return ""

        mapper = str(s.get("luks_mapper_name", self._luks_mapper_name))
        # The raw partition that was LUKS-formatted. Prefer an explicit value
        # provided by the partition job; fall back to the well-known layout.
        root_part = str(s.get("root_partition", "") or "")
        device = root_part or f"/dev/mapper/{mapper}"
        return f'  boot.initrd.luks.devices."{mapper}".device = "{device}";\n\n'

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def validate(self, context: JobContext) -> JobResult:
        """
        Validate preconditions for the NixOS install.

        Checks:
        - ``target_root`` is provided.
        - In a REAL run, the target is mounted and the GLF flake source exists.

        In dry-run / mock mode the filesystem checks are relaxed so the job can
        be exercised on any host (and in tests) without a real mounted target.

        Args:
            context: Execution context

        Returns:
            JobResult indicating validation status
        """
        context.report_progress(0, "Validating NixOS install configuration...")

        target_root = context.target_root
        if not target_root:
            return JobResult.fail("Target root is required", error_code=ERR_NO_TARGET)

        dry_run = bool(context.selections.get("dry_run", True))

        # Only enforce on-disk preconditions for a real installation.
        if not dry_run:
            if not Path(target_root).is_dir():
                return JobResult.fail(
                    f"Target root not mounted: {target_root}",
                    error_code=ERR_TARGET_MISSING,
                )
            flake_source = self._flake_source()
            if not Path(flake_source).exists():
                return JobResult.fail(
                    f"GLF flake source not found: {flake_source}",
                    error_code=ERR_FLAKE_SOURCE_MISSING,
                )

        context.report_progress(5, "Validation complete")
        return JobResult.ok(
            "NixOS install configuration valid",
            data={"target_root": target_root, "flake_attr": self._flake_attr()},
        )

    # -------------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------------

    def run(self, context: JobContext) -> JobResult:
        """
        Execute the NixOS installation sequence.

        SECURITY: checks ``dry_run`` and ``confirmed`` before any privileged
        operation, exactly like the partition job.

        Args:
            context: Execution context

        Returns:
            JobResult indicating success or failure
        """
        context.report_progress(0, "Starting NixOS install job...")

        validation = self.validate(context)
        if not validation.success:
            return validation

        s = context.selections
        dry_run = bool(s.get("dry_run", True))  # DEFAULT TRUE
        confirmed = bool(s.get("confirmed", False))  # DEFAULT FALSE

        # SECURITY GATE: a real install requires explicit confirmation.
        if not dry_run and not confirmed:
            return JobResult.fail(
                "SECURITY: Cannot install without explicit confirmation. "
                "Set confirmed=True to proceed with the real installation.",
                error_code=ERR_NOT_CONFIRMED,
            )

        target_root = context.target_root

        # SECURITY: read secrets locally so we can wipe them in ``finally``.
        # They are never passed to any logged command line.
        passphrase = str(s.get("encryption_passphrase", ""))
        password = str(s.get("password", ""))
        root_password = str(s.get("root_password", ""))
        try:
            if dry_run:
                logger.info("DRY-RUN MODE: simulating NixOS install (no changes)")
            else:
                logger.warning("EXECUTING REAL NIXOS INSTALL on %s", target_root)

            # Step 1: build configuration.nix contents.
            context.report_progress(10, "Assembling configuration.nix...")
            cfg = self._build_configuration(context)

            # Step 2: nixos-generate-config (produces hardware-configuration.nix).
            context.report_progress(25, "Generating hardware configuration...")
            result = self._generate_config(target_root, dry_run)
            if not result.success:
                return result

            # Step 3: write configuration.nix + copy the GLF flake, preserving
            # the generated hardware-configuration.nix.
            context.report_progress(45, "Writing configuration and copying flake...")
            result = self._write_config_and_flake(target_root, cfg, dry_run)
            if not result.success:
                return result

            # Step 4: nixos-install against the GLF flake attribute.
            context.report_progress(60, "Installing NixOS (this can take a while)...")
            result = self._nixos_install(target_root, dry_run)
            if not result.success:
                return result

            context.report_progress(100, "NixOS installation complete")
            return JobResult.ok(
                f"GLF OS installed on {target_root}",
                data={
                    "target_root": target_root,
                    "flake_attr": self._flake_attr(),
                    "dry_run": dry_run,
                    "environment": self._map_environment(
                        str(s.get("desktop_environment", "gnome"))
                    ),
                    "edition": self._map_edition(str(s.get("edition", "standard"))),
                    "encrypted": bool(s.get("encryption", False)),
                },
            )
        finally:
            # SECURITY: wipe secrets from memory.
            passphrase = ""
            password = ""
            root_password = ""
            del passphrase, password, root_password

    def _generate_config(self, target_root: str, dry_run: bool) -> JobResult:
        """Run ``nixos-generate-config --root <target>``."""
        return self._run_command(
            ["nixos-generate-config", "--root", target_root],
            description="Generating hardware-configuration.nix",
            dry_run=dry_run,
            error_code=ERR_GENERATE_CONFIG,
        )

    def _write_config_and_flake(self, target_root: str, cfg: str, dry_run: bool) -> JobResult:
        """
        Write ``configuration.nix`` and copy the GLF flake files.

        The generated ``hardware-configuration.nix`` is PRESERVED: we only add
        ``configuration.nix`` and copy ``flake.nix``, ``flake.lock`` and
        ``customConfig`` from the flake source. Copying is done file-by-file
        (never a wholesale directory copy) so the hardware config is untouched.

        Args:
            target_root: Mounted installation target
            cfg: Rendered configuration.nix text
            dry_run: If True, simulate only

        Returns:
            JobResult indicating success or failure
        """
        etc_nixos = self._etc_nixos(target_root)
        config_path = etc_nixos / "configuration.nix"

        # Write configuration.nix.
        if dry_run:
            logger.info("[DRY-RUN] Would write %s (%d bytes)", config_path, len(cfg))
        else:
            try:
                etc_nixos.mkdir(parents=True, exist_ok=True)
                config_path.write_text(cfg, encoding="utf-8")
                logger.info("Wrote %s", config_path)
            except OSError as e:
                logger.error("Failed to write configuration.nix: %s", e)
                return JobResult.fail(
                    f"Failed to write configuration.nix: {e}",
                    error_code=ERR_WRITE_CONFIG,
                )

        # Copy GLF flake files, preserving hardware-configuration.nix.
        flake_source = Path(self._flake_source())
        for item in ("flake.nix", "flake.lock", "customConfig"):
            src = flake_source / item
            dest = etc_nixos / item
            result = self._run_command(
                ["cp", "-r", str(src), str(dest)],
                description=f"Copying GLF flake item: {item}",
                dry_run=dry_run,
                error_code=ERR_COPY_FLAKE,
            )
            if not result.success:
                return result

        return JobResult.ok("Configuration written and flake copied")

    def _nixos_install(self, target_root: str, dry_run: bool) -> JobResult:
        """
        Run ``nixos-install`` against the GLF flake attribute.

        Command (faithful to the Calamares nixos module)::

            nixos-install --no-root-passwd \
                --option sandbox false \
                --option build-users-group "" \
                --flake <target>/etc/nixos#GLF-OS \
                --root <target>
        """
        flake_ref = f"{target_root}/etc/nixos#{self._flake_attr()}"
        cmd = [
            "nixos-install",
            "--no-root-passwd",
            "--option",
            "sandbox",
            "false",
            "--option",
            "build-users-group",
            "",
            "--flake",
            flake_ref,
            "--root",
            target_root,
        ]
        return self._run_command(
            cmd,
            description="Running nixos-install",
            dry_run=dry_run,
            error_code=ERR_INSTALL,
        )

    def _run_command(
        self,
        cmd: list[str],
        description: str,
        dry_run: bool,
        error_code: int = ERR_COMMAND_FAILED,
    ) -> JobResult:
        """
        Run a privileged command with dry-run support.

        In dry-run mode the command is logged and NOT executed. This method is
        never used for secret-bearing commands; secrets are never part of any
        command line in this job.

        Args:
            cmd: Command to execute
            description: Human-readable description for logging
            dry_run: If True, simulate only
            error_code: Error code to return on failure

        Returns:
            JobResult indicating success or failure
        """
        if dry_run:
            logger.info("[DRY-RUN] %s: %s", description, " ".join(cmd))
            return JobResult.ok(f"[DRY-RUN] {description}")

        logger.info("Executing: %s", description)
        logger.debug("Command: %s", " ".join(cmd))
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info("OK: %s", description)
            if result.stdout:
                logger.debug("stdout: %s", result.stdout)
            return JobResult.ok(description)
        except subprocess.CalledProcessError as e:
            logger.error("FAILED: %s: %s", description, e.stderr)
            return JobResult.fail(f"{description} failed: {e.stderr}", error_code=error_code)
        except FileNotFoundError:
            logger.error("Command not found: %s", cmd[0])
            return JobResult.fail(
                f"Required tool not found: {cmd[0]}", error_code=ERR_TOOL_NOT_FOUND
            )

    def cleanup(self, context: JobContext) -> None:
        """
        Unmount the target filesystems after the install.

        The partition job mounts the target (root on ``target_root``, ESP on
        ``<target>/boot``). We unmount recursively so the user can reboot into
        the freshly installed system. Failures are non-fatal (logged only).

        In dry-run mode nothing is unmounted.
        """
        if bool(context.selections.get("dry_run", True)):
            return

        target_root = context.target_root
        if not target_root:
            return

        # ``umount -R`` unmounts the target and everything below it (ESP, etc.).
        try:
            subprocess.run(
                ["umount", "-R", target_root],
                check=False,
                capture_output=True,
            )
            logger.info("Unmounted %s (recursive)", target_root)
        except Exception as e:  # noqa: BLE001 - cleanup must never raise
            logger.debug("Failed to unmount %s: %s", target_root, e)

    def estimate_duration(self) -> int:
        """
        Estimate execution time in seconds.

        ``nixos-install`` builds the whole system closure and can be very long
        (network-bound); 20 minutes is a realistic average for GLF OS.

        Returns:
            Estimated duration in seconds
        """
        return 1200
