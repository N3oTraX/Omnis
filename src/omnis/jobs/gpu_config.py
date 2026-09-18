"""GPU inventory and configuration.nix snippet (kept in sync with the GLF Calamares module)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

CFG_NVIDIA = """  glf.nvidia_config = {{
    enable = true;
    laptop = {has_laptop};
{prime_busids}  }};

"""

PCI_DEVICES_DIR = Path("/sys/bus/pci/devices")
DMI_CHASSIS_TYPE = Path("/sys/class/dmi/id/chassis_type")

# VGA, 3D and "other display" controllers. Hybrid laptops often expose the AMD
# dGPU as 0x0380, which a "VGA"/"3D controller" text match never sees.
PCI_DISPLAY_CLASSES = ("0x0300", "0x0302", "0x0380")
PCI_GPU_VENDORS = {"0x10de": "nvidia", "0x1002": "amd", "0x8086": "intel"}

# SMBIOS portable chassis types.
LAPTOP_CHASSIS_TYPES = frozenset({"8", "9", "10", "11", "14", "30", "31", "32"})

# Name hints only settle what sysfs cannot tell: an AMD APU from an AMD card, and
# the driver of a GPU the live kernel did not bind.
AMD_LEGACY_RADEON_HINTS = (
    "hd 2",
    "hd 3",
    "hd 4",
    "hd 5",
    "hd 6",
    "rv6",
    "rv7",
    "rs6",
    "rs7",
    "rs8",
    "rs9",
    "r600",
    "r700",
    "r800",
    "r900",
    "tera-scale",
    "terascale",
)
AMD_DISCRETE_HINTS = ("rx ", "radeon pro", "instinct", "firepro")
AMD_IGPU_HINTS = (
    "radeon graphics",
    "vega 3",
    "vega 6",
    "vega 7",
    "vega 8",
    "vega 11",
    "rembrandt",
    "phoenix",
    "raphael",
    "barcelo",
    "cezanne",
    "renoir",
    "lucienne",
    "picasso",
    "raven ridge",
)
# Intel families driven by xe, for a GPU the live kernel did not bind.
INTEL_XE_HINTS = ("battlemage", "bmg", "b580", "b770", "lunar lake", "lnl", "panther lake", "ptl")

_PRIME_VARS = (("nvidiaBusId", "nvidia"), ("intelBusId", "intel"), ("amdgpuBusId", "amd"))


@dataclass(frozen=True)
class GpuDevice:
    """A display controller as seen in /sys/bus/pci/devices."""

    slot: str
    vendor_id: str
    boot_vga: bool = False
    bound_driver: str = ""
    desc: str = ""

    @property
    def bus_id(self) -> str:
        return convert_to_pci_format(self.slot)

    @property
    def label(self) -> str:
        return self.desc or self.slot


@dataclass(frozen=True)
class ClassifiedGpu:
    device: GpuDevice
    vendor: str
    kind: str
    driver: str


def convert_to_pci_format(address: str) -> str:
    devid = re.split(r"[:.]", address)
    if len(devid) < 3:
        return ""
    try:
        return f"PCI:{int(devid[-3], 16)}:{int(devid[-2], 16)}:{int(devid[-1])}"
    except ValueError:
        return ""


def _read(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def read_chassis_type(path: Path = DMI_CHASSIS_TYPE) -> str:
    return _read(path)


def parse_lspci_descriptions(lspci_output: str) -> dict[str, str]:
    """Map a ``lspci -D`` slot ("0000:01:00.0") to its pci.ids name."""
    descriptions: dict[str, str] = {}
    for line in lspci_output.splitlines():
        slot, _, rest = line.partition(" ")
        description = rest.partition(": ")[2].strip()
        if description:
            descriptions[slot] = description
    return descriptions


def read_gpu_devices(
    pci_root: Path = PCI_DEVICES_DIR,
    descriptions: Mapping[str, str] | None = None,
) -> list[GpuDevice]:
    """Enumerate display controllers from sysfs: needs no bound driver and no pci.ids."""
    names = descriptions or {}
    try:
        slots = sorted(entry.name for entry in pci_root.iterdir())
    except OSError:
        return []
    devices: list[GpuDevice] = []
    for slot in slots:
        path = pci_root / slot
        if not _read(path / "class").startswith(PCI_DISPLAY_CLASSES):
            continue
        driver = path / "driver"
        devices.append(
            GpuDevice(
                slot=slot,
                vendor_id=_read(path / "vendor"),
                boot_vga=_read(path / "boot_vga") == "1",
                bound_driver=driver.resolve().name if driver.exists() else "",
                desc=names.get(slot, ""),
            )
        )
    return devices


def classify_gpu(device: GpuDevice) -> ClassifiedGpu | None:
    """Vendor, kind and KMS driver of a GPU, or None for a virtual or unknown one."""
    vendor = PCI_GPU_VENDORS.get(device.vendor_id)
    bound = device.bound_driver
    d = device.desc.lower()

    if vendor == "nvidia":
        return ClassifiedGpu(device, vendor, "discrete", "nvidia")

    if vendor == "amd":
        if bound in ("amdgpu", "radeon"):
            driver = bound
        elif any(k in d for k in AMD_LEGACY_RADEON_HINTS):
            driver = "radeon"
        else:
            driver = "amdgpu"
        integrated = (
            driver == "amdgpu"
            and not any(k in d for k in AMD_DISCRETE_HINTS)
            and any(k in d for k in AMD_IGPU_HINTS)
        )
        return ClassifiedGpu(device, vendor, "integrated" if integrated else "discrete", driver)

    if vendor == "intel":
        if bound in ("i915", "xe"):
            driver = bound
        elif any(k in d for k in INTEL_XE_HINTS):
            driver = "xe"
        else:
            driver = "i915"
        # The Intel iGPU always sits at 00:02.0 (same rule as switcheroo-control).
        kind = "integrated" if device.slot.endswith(":00:02.0") else "discrete"
        return ClassifiedGpu(device, vendor, kind, driver)

    return None


def classify_gpus(devices: list[GpuDevice]) -> list[ClassifiedGpu]:
    return [gpu for gpu in map(classify_gpu, devices) if gpu is not None]


def has_nvidia_laptop(classified: list[ClassifiedGpu], chassis_type: str = "") -> bool:
    nvidia = [gpu for gpu in classified if gpu.vendor == "nvidia"]
    if not nvidia:
        return False
    if chassis_type in LAPTOP_CHASSIS_TYPES:
        return True
    # Some firmwares report no usable chassis type: fall back on the name.
    pattern = re.compile(r"\b\d{3}M\b")
    for gpu in nvidia:
        low = gpu.device.desc.lower()
        if "laptop" in low or "mobile" in low or pattern.search(gpu.device.desc):
            return True
    return False


def generate_prime_entries(classified: list[ClassifiedGpu]) -> str:
    """One bus ID per vendor: a repeated attribute would not even parse."""
    out = ""
    for var_name, vendor in _PRIME_VARS:
        candidates = [gpu for gpu in classified if gpu.vendor == vendor]
        if vendor != "nvidia":
            # PRIME pairs the NVIDIA GPU with the integrated one.
            candidates = [gpu for gpu in candidates if gpu.kind == "integrated"] or candidates
        if not candidates:
            continue
        gpu = candidates[0]
        out += f"    # {gpu.device.label}\n"
        out += f'    {var_name} = "{gpu.device.bus_id}";\n'
    return out


def emit_gpu_config(classified: list[ClassifiedGpu]) -> str:
    """
    glf.{amdgpu,intel}_config switches plus the glf.gpu.devices inventory.

    The switches only select kernel drivers. Which GPU runs compute workloads is
    derived from the inventory by glf-os (modules/default/gpu.nix).
    """
    if not classified:
        return ""

    lines = [f"  # Detected GPU: {gpu.device.label} (driver: {gpu.driver})" for gpu in classified]

    enable_amdgpu = any(gpu.driver == "amdgpu" for gpu in classified)
    enable_amdgpu_legacy = any(gpu.driver == "radeon" for gpu in classified)
    intel_driver = next((gpu.driver for gpu in classified if gpu.vendor == "intel"), None)

    if enable_amdgpu or enable_amdgpu_legacy:
        lines.append("  glf.amdgpu_config.enable = true;")
        if enable_amdgpu_legacy and not enable_amdgpu:
            lines.append("  glf.amdgpu_config.legacy = true;")
    else:
        lines.append("  glf.amdgpu_config.enable = false;")

    if intel_driver is not None:
        lines.append("  glf.intel_config.enable = true;")
        if intel_driver == "xe":
            lines.append('  glf.intel_config.driver = "xe";')

    lines.append("  glf.gpu.devices = [")
    for gpu in classified:
        lines.append(
            f'    {{ vendor = "{gpu.vendor}"; kind = "{gpu.kind}"; driver = "{gpu.driver}"; '
            f'busId = "{gpu.device.bus_id}"; bootVga = {str(gpu.device.boot_vga).lower()}; }}'
        )
    lines.append("  ];")

    return "\n".join(lines) + "\n\n"


def render(devices: list[GpuDevice], chassis_type: str = "") -> str:
    classified = classify_gpus(devices)
    if not classified:
        return ""
    cfg = ""
    if any(gpu.vendor == "nvidia" for gpu in classified):
        cfg += CFG_NVIDIA.format(
            has_laptop=str(has_nvidia_laptop(classified, chassis_type)).lower(),
            prime_busids=generate_prime_entries(classified),
        )
    cfg += emit_gpu_config(classified)
    return cfg
