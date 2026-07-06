"""GPU classification et snippet configuration.nix (porte du module Calamares GLF)."""

from __future__ import annotations

import re

CFG_NVIDIA = """  glf.nvidia_config = {{
    enable = true;
    laptop = {has_laptop};
{prime_busids}  }};

"""

AMD_LEGACY_RADEON_HINTS = (
    "hd 2", "hd 3", "hd 4", "hd 5", "hd 6",
    "rv6", "rv7", "rs6", "rs7", "rs8", "rs9",
    "r600", "r700", "r800", "r900",
    "tera-scale", "terascale",
)
AMD_DISCRETE_HINTS = ("rx ", "radeon pro", "instinct", "firepro")
AMD_IGPU_HINTS = (
    "radeon graphics",
    "vega 3", "vega 6", "vega 7", "vega 8", "vega 11",
    "rembrandt", "phoenix", "raphael", "barcelo",
    "cezanne", "renoir", "lucienne", "picasso",
    "raven ridge",
)
INTEL_I915_DISCRETE_HINTS = (
    "dg2",
    "a380", "a580", "a750", "a770",
    "a310", "a350m", "a370m", "a550m", "a570m", "a730m", "a770m",
)
INTEL_XE_DISCRETE_HINTS = ("battlemage", "bmg", "b580", "b770")
INTEL_XE_INTEGRATED_HINTS = (
    "lunar lake", "lnl",
    "panther lake", "ptl",
    "arrow lake", "arl",
)
VIRTUAL_GPU_HINTS = ("qxl", "virtio", "vmware", "vmwgfx", "cirrus", "bochs", "innotek", "virtualbox")

_VGA_KEYWORDS = (" VGA compatible controller: ", " 3D controller: ")


def parse_vga_devices(lspci_output: str) -> list[tuple[str, str]]:
    devices: list[tuple[str, str]] = []
    for line in lspci_output.strip().splitlines():
        for keyword in _VGA_KEYWORDS:
            if keyword in line:
                address, description = line.split(keyword, 1)
                pci_address = convert_to_pci_format(address)
                if pci_address:
                    devices.append((pci_address, description))
                break
    return devices


def convert_to_pci_format(address: str) -> str:
    devid = re.split(r"[:.]", address)
    if len(devid) < 3:
        return ""
    bus, device, function = devid[-3], devid[-2], devid[-1]
    try:
        return f"PCI:{int(bus, 16)}:{int(device, 16)}:{int(function)}"
    except ValueError:
        return ""


def has_nvidia_device(devices: list[tuple[str, str]]) -> bool:
    return any("nvidia" in desc.lower() for _addr, desc in devices)


def has_nvidia_laptop(devices: list[tuple[str, str]]) -> bool:
    pattern = re.compile(r"\b\d{3}M\b")
    for _addr, description in devices:
        low = description.lower()
        if "nvidia" not in low:
            continue
        if any(k in low for k in ("laptop", "mobile")) or pattern.search(description):
            return True
    return False


def generate_prime_entries(devices: list[tuple[str, str]]) -> str:
    lines = ""
    for pci_address, description in devices:
        low = description.lower()
        if "intel" in low:
            var_name = "intelBusId"
        elif "nvidia" in low:
            var_name = "nvidiaBusId"
        elif "amd" in low:
            var_name = "amdgpuBusId"
        else:
            continue
        lines += f"    # {description}\n"
        lines += f'    {var_name} = "{pci_address}";\n'
    return lines


def classify_gpu(description: str) -> dict[str, str | None]:
    d = description.lower()
    if any(k in d for k in VIRTUAL_GPU_HINTS):
        return {"vendor": "virtual", "kind": "virtual", "driver": None}
    if "nvidia" in d:
        return {"vendor": "nvidia", "kind": "discrete", "driver": "nvidia"}
    if "amd" in d or "ati " in d or "advanced micro devices" in d:
        if any(k in d for k in AMD_LEGACY_RADEON_HINTS):
            return {"vendor": "amd", "kind": "discrete", "driver": "radeon"}
        if any(k in d for k in AMD_DISCRETE_HINTS):
            return {"vendor": "amd", "kind": "discrete", "driver": "amdgpu"}
        if any(k in d for k in AMD_IGPU_HINTS):
            return {"vendor": "amd", "kind": "integrated", "driver": "amdgpu"}
        return {"vendor": "amd", "kind": "discrete", "driver": "amdgpu"}
    if "intel" in d:
        if any(k in d for k in INTEL_XE_INTEGRATED_HINTS):
            return {"vendor": "intel", "kind": "integrated", "driver": "xe"}
        if any(k in d for k in INTEL_XE_DISCRETE_HINTS):
            return {"vendor": "intel", "kind": "discrete", "driver": "xe"}
        if any(k in d for k in INTEL_I915_DISCRETE_HINTS):
            return {"vendor": "intel", "kind": "discrete", "driver": "i915"}
        return {"vendor": "intel", "kind": "integrated", "driver": "i915"}
    return {"vendor": "other", "kind": "unknown", "driver": None}


def classify_gpus(devices: list[tuple[str, str]]) -> list[dict[str, str | None]]:
    return [
        {"addr": pci_address, "desc": description.strip(), **classify_gpu(description)}
        for pci_address, description in devices
    ]


def pick_primary_gpu(
    classified: list[dict[str, str | None]],
) -> dict[str, str | None] | None:
    discrete = [g for g in classified if g["kind"] == "discrete"]
    if discrete:
        prio = {"nvidia": 0, "amd": 1, "intel": 2}
        return sorted(discrete, key=lambda g: prio.get(str(g["vendor"]), 99))[0]
    integrated = [g for g in classified if g["kind"] == "integrated"]
    if integrated:
        prio = {"amd": 0, "intel": 1}
        return sorted(integrated, key=lambda g: prio.get(str(g["vendor"]), 99))[0]
    return None


def emit_gpu_config(
    classified: list[dict[str, str | None]],
    primary: dict[str, str | None] | None,
) -> str:
    if primary is None:
        return ""

    lines: list[str] = []
    seen: set[str] = set()
    for gpu in classified:
        desc = str(gpu["desc"])
        if desc in seen:
            continue
        seen.add(desc)
        lines.append(f"  # Detected GPU: {desc} (driver: {gpu['driver'] or 'none'})")

    enable_amdgpu = any(g["vendor"] == "amd" and g["driver"] == "amdgpu" for g in classified)
    enable_amdgpu_legacy = any(g["vendor"] == "amd" and g["driver"] == "radeon" for g in classified)
    enable_intel = any(g["vendor"] == "intel" for g in classified)
    intel_driver = next((g["driver"] for g in classified if g["vendor"] == "intel"), "i915")

    if enable_amdgpu or enable_amdgpu_legacy:
        lines.append("  glf.amdgpu_config.enable = true;")
        if enable_amdgpu_legacy and not enable_amdgpu:
            lines.append("  glf.amdgpu_config.legacy = true;")
    else:
        lines.append("  glf.amdgpu_config.enable = false;")

    if enable_intel:
        lines.append("  glf.intel_config.enable = true;")
        if intel_driver == "xe":
            lines.append('  glf.intel_config.driver = "xe";')

    return "\n".join(lines) + "\n\n"


def render(lspci_output: str) -> str:
    devices = parse_vga_devices(lspci_output)
    if not devices:
        return ""
    classified = classify_gpus(devices)
    primary = pick_primary_gpu(classified)
    cfg = ""
    if has_nvidia_device(devices):
        cfg += CFG_NVIDIA.format(
            has_laptop=str(has_nvidia_laptop(devices)).lower(),
            prime_busids=generate_prime_entries(devices),
        )
    cfg += emit_gpu_config(classified, primary)
    return cfg
