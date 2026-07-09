"""
NixOS Install Job for the Omnis Installer.

This job makes GLF OS (a NixOS-based distribution) actually installable. It is
the Phase 2 core step and is faithfully modelled on the GLF Calamares module
``patches/calamares-nixos-extensions/modules/nixos/main.py``.

High-level sequence (executed on an already-mounted ``target_root``):

1. Assemble ``configuration.nix`` from templates (head, bootloader, network,
   locale, keymap, users, autologin, tail) plus the GLF-specific
   ``glf.environment.type`` / ``glf.environment.edition`` options. User and
   root passwords are set DECLARATIVELY via ``users.users.<name>.hashedPassword``
   (SHA-512 crypt, computed with ``mkpasswd``/``openssl`` — never chpasswd,
   which is unsuited to NixOS).
2. Run ``nixos-generate-config --root <target>`` to produce
   ``hardware-configuration.nix``.
3. Write ``configuration.nix`` and copy the GLF flake files
   (``flake.nix``, ``flake.lock``, ``customConfig``, ``customized.nix``) into
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

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from omnis.jobs import gpu_config
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
  # earlySetup pushes the console keymap into the initrd so the LUKS passphrase
  # prompt (stage-1 boot) follows the chosen layout — without it, useXkbConfig
  # only applies to the stage-2 console and the LUKS prompt stays QWERTY/US.
  console.earlySetup = true;
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
    extraGroups = [ {groups} ];{hashed_password}
  }};

"""

# Injected inside CFG_USERS when a user password is provided. The leading
# newline + indentation keep the generated Nix readable. SECURITY: the value
# is a SHA-512 crypt hash (``$6$...``), never a plaintext password.
CFG_USER_HASHED_PASSWORD = """
    hashedPassword = "{hash}";"""

# Emitted as a standalone block for the root account when a root password
# (or ``root_same_as_user``) is provided.
CFG_ROOT_HASHED_PASSWORD = """  # Root account password (declarative, NixOS way).
  users.users.root.hashedPassword = "{hash}";

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
ERR_HASH_FAILED = 70


class _NixProgress:
    """Fraction 0..1 depuis les events nix internal-json (builds type 104 + copyPaths 103)."""

    _ACT_COPY_PATHS = 103
    _ACT_BUILDS = 104
    _RES_PROGRESS = 105

    def __init__(self) -> None:
        self._kind: dict[int, str] = {}
        self._done: dict[int, int] = {}
        self._expected: dict[int, int] = {}
        self._fraction = 0.0

    def feed(self, line: str) -> float | None:
        if not line.startswith("@nix "):
            return None
        try:
            event = json.loads(line[5:])
        except ValueError:
            return None
        action = event.get("action")
        if action == "start":
            act_type = event.get("type")
            if act_type == self._ACT_BUILDS:
                self._kind[event.get("id")] = "build"
            elif act_type == self._ACT_COPY_PATHS:
                self._kind[event.get("id")] = "copy"
        elif action == "result" and event.get("type") == self._RES_PROGRESS:
            rid = event.get("id")
            if rid in self._kind:
                fields = event.get("fields") or []
                self._done[rid] = int(fields[0]) if len(fields) > 0 else 0
                self._expected[rid] = int(fields[1]) if len(fields) > 1 else 0
        expected = sum(self._expected.values())
        if expected <= 0:
            return None
        fraction = min(1.0, sum(self._done.values()) / expected)
        if fraction <= self._fraction:
            return None
        self._fraction = fraction
        return fraction

    def _totals(self, kind: str) -> tuple[int, int]:
        done = sum(v for i, v in self._done.items() if self._kind.get(i) == kind)
        exp = sum(v for i, v in self._expected.items() if self._kind.get(i) == kind)
        return done, exp

    def message(self) -> str:
        parts = []
        b_done, b_exp = self._totals("build")
        if b_exp:
            parts.append(f"{b_done}/{b_exp} built")
        c_done, c_exp = self._totals("copy")
        if c_exp:
            parts.append(f"{c_done}/{c_exp} copied")
        return "Installing NixOS: " + ", ".join(parts) if parts else "Installing NixOS..."


@dataclass(frozen=True)
class PasswordHashes:
    """
    Pre-computed SHA-512 crypt hashes for the declarative NixOS config.

    Both fields hold ``$6$...`` crypt strings (or empty when no password is
    provided for that account). They are NEVER plaintext and are wiped by
    :meth:`NixosJob.run` after the configuration has been rendered.
    """

    user: str = ""
    root: str = ""


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

    def _build_configuration(
        self, context: JobContext, hashes: PasswordHashes | None = None
    ) -> str:
        """
        Assemble the ``configuration.nix`` contents from user selections.

        Mirrors the template assembly order of the Calamares nixos module:
        head → environment → bootloader → network → time → locale → keymap →
        users → autologin → tail. LUKS device injection is appended separately
        by :meth:`_luks_config` (before the tail) when encryption is enabled.

        Password hashes are computed upstream (in :meth:`run`) and passed in via
        ``hashes`` so this method NEVER hashes (and never crashes on a missing
        hashing tool). When ``hashes`` is ``None`` (e.g. unit tests exercising
        the pure template assembly), no ``hashedPassword`` line is emitted.

        SECURITY: the injected values are SHA-512 crypt hashes (``$6$...``),
        never plaintext passwords. See :meth:`_hash_password` for the escaping
        rationale in a double-quoted Nix string.

        Args:
            context: Execution context (reads ``selections``)
            hashes: Pre-computed user/root password hashes (optional)

        Returns:
            The full ``configuration.nix`` text.
        """
        s = context.selections
        hashes = hashes or PasswordHashes()
        cfg = CFG_HEAD

        # GLF environment/edition (the defining GLF-OS options).
        environment = self._map_environment(str(s.get("desktop_environment", "gnome")))
        edition = self._map_edition(str(s.get("edition", "standard")))
        cfg += CFG_ENVIRONMENT.format(environment=environment, edition=edition)
        cfg += self._gpu_config()
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
            # Inject ``hashedPassword`` inside the user block only when a hash
            # was computed for the user account (i.e. a password was provided).
            hashed = CFG_USER_HASHED_PASSWORD.format(hash=hashes.user) if hashes.user else ""
            cfg += CFG_USERS.format(
                username=username,
                fullname=fullname,
                groups=groups,
                hashed_password=hashed,
            )
            if bool(s.get("auto_login", False)):
                cfg += CFG_AUTOLOGIN.format(username=username)

        # Root account password (declarative). Emitted whenever a root hash was
        # computed (root_password provided, or root_same_as_user reusing the
        # user hash). On NixOS this is the ONLY place the root password is set.
        if hashes.root:
            cfg += CFG_ROOT_HASHED_PASSWORD.format(hash=hashes.root)

        # Tail (stateVersion).
        cfg += CFG_TAIL.format(nixos_version=self._detect_state_version())
        return cfg

    @staticmethod
    def _gpu_config() -> str:
        """Snippet GPU configuration.nix via lspci (vide si lspci absent)."""
        try:
            proc = subprocess.run(["lspci"], capture_output=True, text=True, check=False)
        except (FileNotFoundError, OSError) as exc:
            logger.warning("lspci unavailable, skipping GPU config: %s", exc)
            return ""
        output = proc.stdout if isinstance(proc.stdout, str) else ""
        return gpu_config.render(output)

    def _luks_config(self, _context: JobContext) -> str:
        """
        Root LUKS is owned by ``nixos-generate-config`` — emit nothing here.

        The partition job opens the LUKS-wrapped root as the ``cryptroot`` mapper
        and mounts it BEFORE the nixos job runs. ``nixos-generate-config`` then
        detects the underlying LUKS container and writes
        ``boot.initrd.luks.devices."cryptroot".device = "/dev/disk/by-uuid/…";``
        (a stable by-uuid path) into ``hardware-configuration.nix``.

        Emitting our own ``boot.initrd.luks.devices.<mapper>.device`` (pointing at
        the raw ``/dev/vdaX``) produced a SECOND definition of the same option, so
        ``nixos-install`` aborted with "The option
        `boot.initrd.luks.devices.cryptroot.device' has conflicting definition
        values". This mirrors the GLF Calamares module, which only injects LUKS
        for *swap* and lets ``nixos-generate-config`` own the root device.

        Returns an empty string in all cases (kept as the injection point for a
        future encrypted-swap block).
        """
        return ""

    # -------------------------------------------------------------------------
    # Password hashing (declarative NixOS approach)
    # -------------------------------------------------------------------------

    def _hash_password(self, password: str) -> str:
        """
        Hash ``password`` into a SHA-512 crypt string (``$6$salt$hash``).

        SECURITY:
        - The plaintext is fed via STDIN, NEVER as an argv element (argv is
          world-readable via ``/proc/<pid>/cmdline``) and NEVER logged.
        - Prefers ``mkpasswd -m sha-512`` (from the ``whois``/``mkpasswd``
          package, standard on NixOS ISOs); falls back to
          ``openssl passwd -6 -stdin`` when ``mkpasswd`` is absent.

        Nix-escaping rationale:
        The returned value is embedded verbatim in a double-quoted Nix string
        (``hashedPassword = "<hash>";``). Nix only interpolates ``${...}`` — the
        ``$`` in a crypt hash is always followed by a digit (``$6$``) or a
        salt/hash character, NEVER by ``{``, so no escaping is required. The
        salt/hash alphabet is ``[A-Za-z0-9./]`` plus ``$`` separators, none of
        which are Nix string metacharacters. We still assert the ``$6$`` prefix
        as a robustness check.

        Args:
            password: Plaintext password (NEVER LOGGED)

        Returns:
            The SHA-512 crypt hash.

        Raises:
            RuntimeError: If neither hashing tool is available or both fail.
        """
        # (command, needs the "-6"/"sha-512" already baked in) candidates.
        candidates: list[list[str]] = []
        if shutil.which("mkpasswd"):
            candidates.append(["mkpasswd", "-m", "sha-512", "--stdin"])
        if shutil.which("openssl"):
            candidates.append(["openssl", "passwd", "-6", "-stdin"])

        if not candidates:
            raise RuntimeError("No password hashing tool found (need 'mkpasswd' or 'openssl')")

        last_error = ""
        for cmd in candidates:
            try:
                # SECURITY: plaintext via STDIN only, output captured, never
                # echoed to logs. ``check=True`` surfaces non-zero exits.
                completed = subprocess.run(
                    cmd,
                    input=password,
                    text=True,
                    capture_output=True,
                    check=True,
                )
            except (subprocess.CalledProcessError, OSError):
                # SECURITY: log only the tool name, never stderr (which could
                # conceivably echo input) and never the password.
                last_error = f"{cmd[0]} failed"
                logger.warning("Password hashing tool '%s' failed", cmd[0])
                continue

            digest = completed.stdout.strip()
            if digest.startswith("$6$"):
                return digest
            # An unexpected format is treated as a failure (never logged).
            last_error = f"{cmd[0]} returned an unexpected hash format"
            logger.warning("Password hashing tool '%s' returned unexpected output", cmd[0])

        raise RuntimeError(f"Password hashing failed: {last_error}")

    def _compute_password_hashes(self, context: JobContext) -> PasswordHashes:
        """
        Compute the user/root SHA-512 crypt hashes from the selections.

        Rules (keys are snake_case, normalised by the GUI bridge):
        - ``password``            → user account hash (empty ⇒ no user hash).
        - ``root_same_as_user``   → root REUSES the user hash (no re-hash).
        - ``root_password``       → root hash when root differs from the user.
        - No user password + no root password ⇒ both hashes empty.

        The hash for a given plaintext is computed EXACTLY ONCE (root sharing
        the user password does not trigger a second ``mkpasswd`` call).

        Args:
            context: Execution context (reads ``selections``)

        Returns:
            A :class:`PasswordHashes` with the computed values.

        Raises:
            RuntimeError: Propagated from :meth:`_hash_password` on tool failure.
        """
        s = context.selections
        user_password = str(s.get("password", "") or "")
        root_password = str(s.get("root_password", "") or "")
        root_same = bool(s.get("root_same_as_user", False))

        user_hash = self._hash_password(user_password) if user_password else ""

        if root_same or not root_password:
            # Root mirrors the user account: reuse the already-computed hash
            # (single hashing operation). When neither is set, root stays empty.
            root_hash = user_hash if root_same else ""
        else:
            root_hash = self._hash_password(root_password)

        return PasswordHashes(user=user_hash, root=root_hash)

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
        hashes = PasswordHashes()
        try:
            if dry_run:
                logger.info("DRY-RUN MODE: simulating NixOS install (no changes)")
            else:
                logger.warning("EXECUTING REAL NIXOS INSTALL on %s", target_root)

            # Step 0: compute password hashes ONCE, upstream of the template
            # assembly, so hashing failures surface as a clean JobResult and
            # ``_build_configuration`` never has to hash (and never crashes).
            context.report_progress(8, "Preparing account credentials...")
            try:
                hashes = self._compute_password_hashes(context)
            except RuntimeError as exc:
                logger.error("Password hashing failed: %s", exc)
                return JobResult.fail(
                    f"Failed to hash account password(s): {exc}",
                    error_code=ERR_HASH_FAILED,
                )

            # Step 1: build configuration.nix contents.
            context.report_progress(10, "Assembling configuration.nix...")
            cfg = self._build_configuration(context, hashes)

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

            context.report_progress(50, "Copying network configuration...")
            self._copy_network_config(target_root, dry_run)

            context.report_progress(55, "Securing Nix build directories...")
            secure_tmpdir = self._harden_target(target_root, dry_run)

            context.report_progress(60, "Installing NixOS (this can take a while)...")
            result = self._nixos_install(target_root, dry_run, context, secure_tmpdir)
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
            # SECURITY: wipe secrets (plaintext AND derived hashes) from memory.
            passphrase = ""
            password = ""
            root_password = ""
            hashes = PasswordHashes()
            del passphrase, password, root_password, hashes

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

        # Copy GLF flake files, preserving hardware-configuration.nix. The GLF
        # target flake (iso-cfg/flake.nix) imports ./configuration.nix (written
        # above), ./customized.nix (glf-customizer managed) and
        # glf.nixosModules.default, so customized.nix must be copied too or the
        # flake fails to evaluate at nixos-install time.
        flake_source = Path(self._flake_source())
        for item in ("flake.nix", "flake.lock", "customConfig", "customized.nix"):
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

    def _copy_network_config(self, target_root: str, dry_run: bool) -> None:
        """Recopie les connexions NetworkManager (wifi + filaire) vers la cible."""
        src = Path("/etc/NetworkManager/system-connections")
        if not src.is_dir():
            return
        dest = Path(target_root) / "etc/NetworkManager/system-connections"
        if dry_run:
            logger.info("[DRY-RUN] would copy NetworkManager connections to %s", dest)
            return
        try:
            dest.mkdir(parents=True, exist_ok=True)
            os.chmod(dest, 0o700)
        except OSError as exc:
            logger.warning("Could not prepare %s: %s", dest, exc)
            return
        for conn in sorted(src.glob("*.nmconnection")):
            try:
                target = dest / conn.name
                target.write_bytes(conn.read_bytes())
                os.chmod(target, 0o600)
                os.chown(target, 0, 0)
                logger.info("Copied NetworkManager connection: %s", conn.name)
            except OSError as exc:
                logger.warning("Could not copy %s: %s", conn.name, exc)

    def _harden_target(self, target_root: str, dry_run: bool) -> str:
        """Securise les repertoires de build nix (root:root) et renvoie le TMPDIR dedie."""
        secure_tmpdir = os.path.join(target_root, "var/tmp/nix-installer")
        if dry_run:
            logger.info("[DRY-RUN] would secure Nix build dirs under %s", target_root)
            return secure_tmpdir
        entries = [
            (target_root, 0o755),
            (secure_tmpdir, 0o700),
            (os.path.join(target_root, "nix"), 0o755),
            (os.path.join(target_root, "nix/var"), 0o755),
            (os.path.join(target_root, "nix/var/nix"), 0o755),
            (os.path.join(target_root, "nix/var/nix/builds"), 0o755),
            (os.path.join(target_root, "nix/var/nix/db"), 0o755),
            (os.path.join(target_root, "nix/var/nix/profiles"), 0o755),
        ]
        for path, mode in entries:
            try:
                os.makedirs(path, exist_ok=True)
                os.chmod(path, mode)
                os.chown(path, 0, 0)
            except OSError as exc:
                logger.warning("Could not secure %s: %s", path, exc)
        return secure_tmpdir

    def _nixos_install(
        self,
        target_root: str,
        dry_run: bool,
        context: JobContext | None = None,
        tmpdir: str | None = None,
    ) -> JobResult:
        """
        Run ``nixos-install`` against the GLF flake attribute.

        Command (faithful to the Calamares nixos module)::

            nixos-install --no-root-passwd \
                --option sandbox false \
                --option build-users-group "" \
                --flake <target>/etc/nixos#GLF-OS \
                --root <target>

        Streame pour faire avancer la barre pendant le build (voir
        :meth:`_run_install_streamed`).
        """
        # Progress is split across the two phases that actually take time, each
        # driven by ``nix``'s internal-json activity stream (best-effort, so a
        # failure here never breaks the install — nixos-install still runs):
        #   1) build/fetch the closure into the LIVE store           (60 → 70 %)
        #   2) copy the closure onto the TARGET disk (the slow part) (70 → 96 %)
        # nixos-install then finds everything already present and only registers
        # the profile + bootloader + activation                     (96 → 100 %)
        self._prebuild_system(target_root, dry_run, context, tmpdir)
        self._copy_system_to_target(target_root, dry_run, context, tmpdir)

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
        return self._run_install_streamed(
            cmd,
            "Running nixos-install",
            dry_run,
            context,
            tmpdir,
            pct_start=96,
            pct_end=100,
        )

    def _copy_system_to_target(
        self,
        target_root: str,
        dry_run: bool,
        context: JobContext | None = None,
        tmpdir: str | None = None,
    ) -> None:
        """Best-effort ``nix copy`` of the system closure onto the target disk.

        This is the phase that actually takes minutes (copying the whole system
        closure to ``/mnt/target``), and — unlike the ``nixos-install`` wrapper —
        ``nix copy`` emits the internal-json ``@nix`` activity stream, so the
        progress bar advances smoothly as each path is copied. nixos-install then
        finds the paths already present in the target store and skips its own
        copy. Failures are swallowed: nixos-install still performs the copy.
        """
        if dry_run:
            return
        attr = self._flake_attr()
        toplevel = (
            f"{target_root}/etc/nixos#nixosConfigurations.{attr}.config.system.build.toplevel"
        )
        cmd = [
            "nix",
            "copy",
            "--no-check-sigs",
            "--log-format",
            "internal-json",
            "--extra-experimental-features",
            "nix-command flakes",
            "--to",
            target_root,
            toplevel,
        ]
        try:
            result = self._run_install_streamed(
                cmd,
                "Copying system to target disk",
                dry_run,
                context,
                tmpdir,
                pct_start=70,
                pct_end=96,
            )
            if not result.success:
                logger.warning("Target copy failed (non-fatal); nixos-install will copy instead")
        except Exception as exc:  # pragma: no cover - defensive, never break install
            logger.warning("Target copy error (non-fatal): %s", exc)

    def _prebuild_system(
        self,
        target_root: str,
        dry_run: bool,
        context: JobContext | None = None,
        tmpdir: str | None = None,
    ) -> None:
        """Best-effort ``nix build`` of the system toplevel to drive real progress.

        Unlike the ``nixos-install`` wrapper, ``nix build`` emits the
        internal-json activity stream, so the progress bar reflects each
        derivation copied from the binary cache or built. Any failure here is
        logged and swallowed: ``nixos-install`` re-evaluates the identical
        (now-cached) closure immediately after, so this step is purely cosmetic.
        """
        if dry_run:
            return
        attr = self._flake_attr()
        toplevel = (
            f"{target_root}/etc/nixos#nixosConfigurations.{attr}.config.system.build.toplevel"
        )
        cmd = [
            "nix",
            "build",
            "--no-link",
            # ``log-format`` is a CLI-only option — it is NOT honoured via
            # NIX_CONFIG/nix.conf. Passing it here is what makes ``nix build``
            # emit the ``@nix`` internal-json activity stream that _NixProgress
            # parses to advance the bar. Without it, no @nix lines are produced
            # and the bar stays frozen.
            "--log-format",
            "internal-json",
            "--extra-experimental-features",
            "nix-command flakes",
            "--option",
            "sandbox",
            "false",
            "--option",
            "build-users-group",
            "",
            toplevel,
        ]
        try:
            result = self._run_install_streamed(
                cmd,
                "Building system closure",
                dry_run,
                context,
                tmpdir,
                pct_start=60,
                pct_end=70,
            )
            if not result.success:
                logger.warning("System prebuild failed (non-fatal); continuing to nixos-install")
        except Exception as exc:  # pragma: no cover - defensive, never break install
            logger.warning("System prebuild error (non-fatal): %s", exc)

    def _run_install_streamed(
        self,
        cmd: list[str],
        description: str,
        dry_run: bool,
        context: JobContext | None,
        tmpdir: str | None = None,
        pct_start: int = 60,
        pct_end: int = 98,
    ) -> JobResult:
        """Run a nix/nixos-install command, driving the progress bar from the
        internal-json activity stream over the ``pct_start``..``pct_end`` range.

        Progress comes from the ``@nix`` build/copyPaths events (see
        :class:`_NixProgress`), which only ``nix build`` emits reliably — the
        ``nixos-install`` wrapper prints its own human-readable output, so the
        bulk of real progress is driven by the ``nix build`` prebuild step (see
        :meth:`_prebuild_system`).
        """
        if dry_run:
            logger.info("[DRY-RUN] %s: %s", description, " ".join(cmd))
            return JobResult.ok(f"[DRY-RUN] {description}")

        # NOTE: internal-json progress is enabled via the ``--log-format
        # internal-json`` CLI flag on the ``nix build`` prebuild (see
        # _prebuild_system) — NOT via NIX_CONFIG, which does not honour
        # ``log-format``. The nixos-install wrapper doesn't accept the flag, so
        # its call simply won't stream @nix events (the prebuild already did).
        env = dict(os.environ)
        if tmpdir:
            env["TMPDIR"] = tmpdir

        logger.info("Executing: %s", description)
        logger.debug("Command: %s", " ".join(cmd))
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )
        except FileNotFoundError:
            logger.error("Command not found: %s", cmd[0])
            return JobResult.fail(
                f"Required tool not found: {cmd[0]}", error_code=ERR_TOOL_NOT_FOUND
            )

        span = max(0, pct_end - pct_start)
        progress = _NixProgress()
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            fraction = progress.feed(line)
            if fraction is not None and context is not None:
                pct = pct_start + round(span * fraction)
                context.report_progress(min(pct_end, pct), progress.message())
            elif not line.startswith("@nix "):
                logger.debug("nixos-install: %s", line)

        code = proc.wait()
        if code != 0:
            logger.error("FAILED: %s (exit %s)", description, code)
            return JobResult.fail(
                f"{description} failed (exit code {code})", error_code=ERR_INSTALL
            )
        logger.info("OK: %s", description)
        return JobResult.ok(description)

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
