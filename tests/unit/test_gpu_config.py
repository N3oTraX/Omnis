"""
Unit tests for the GPU inventory / configuration.nix snippet generation (kept in
sync with the GLF Calamares nixos module). Every machine is a synthetic
``/sys/bus/pci/devices`` tree, so no hardware is needed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from omnis.jobs import gpu_config
from omnis.jobs.gpu_config import GpuDevice

NVIDIA = "NVIDIA Corporation GA104 [GeForce RTX 3070] (rev a1)"
NVIDIA_MOBILE = "NVIDIA Corporation GA106M [GeForce RTX 3060 Mobile / Max-Q] (rev a1)"
INTEL_IGPU = "Intel Corporation AlderLake-P GT2 [Iris Xe Graphics] (rev 0c)"
INTEL_LUNARLAKE = "Intel Corporation Lunar Lake [Arc Graphics 140V] (rev 04)"
INTEL_ARC = "Intel Corporation Battlemage G21 [Arc B580]"
AMD_RX = "Advanced Micro Devices, Inc. [AMD/ATI] Navi 22 [Radeon RX 6700 XT] (rev c1)"
AMD_RX_MOBILE = "Advanced Micro Devices, Inc. [AMD/ATI] Navi 23 [Radeon RX 6600M]"
AMD_APU = "Advanced Micro Devices, Inc. [AMD/ATI] Cezanne [Radeon Vega Series]"
AMD_LEGACY = "Advanced Micro Devices, Inc. [AMD/ATI] RV710 [Radeon HD 4350/4550]"

VGA = "0x030000"
CONTROLLER_3D = "0x030200"
DISPLAY = "0x038000"


class FakePci:
    """Builds a throwaway /sys/bus/pci/devices tree."""

    def __init__(self, root: Path) -> None:
        self.root = root / "pci"
        self.root.mkdir()
        self._drivers = root / "drivers"
        self.descriptions: dict[str, str] = {}

    def add(
        self,
        slot: str,
        pci_class: str,
        vendor: str,
        desc: str = "",
        driver: str = "",
        boot_vga: bool | None = None,
    ) -> FakePci:
        path = self.root / slot
        path.mkdir()
        (path / "class").write_text(pci_class + "\n")
        (path / "vendor").write_text(vendor + "\n")
        if boot_vga is not None:
            (path / "boot_vga").write_text("1\n" if boot_vga else "0\n")
        if driver:
            target = self._drivers / driver
            target.mkdir(parents=True, exist_ok=True)
            (path / "driver").symlink_to(target)
        self.descriptions[slot] = desc
        return self

    def devices(self) -> list[GpuDevice]:
        return gpu_config.read_gpu_devices(self.root, self.descriptions)


@pytest.fixture
def pci(tmp_path: Path) -> FakePci:
    return FakePci(tmp_path)


def _classify(
    desc: str, vendor_id: str, slot: str = "0000:01:00.0", driver: str = ""
) -> tuple[str, str, str]:
    gpu = gpu_config.classify_gpu(GpuDevice(slot, vendor_id, bound_driver=driver, desc=desc))
    assert gpu is not None
    return (gpu.vendor, gpu.kind, gpu.driver)


class TestClassification:
    def test_nvidia_is_discrete(self) -> None:
        assert _classify(NVIDIA, "0x10de") == ("nvidia", "discrete", "nvidia")

    def test_amd_rx_is_amdgpu_discrete(self) -> None:
        assert _classify(AMD_RX, "0x1002") == ("amd", "discrete", "amdgpu")

    def test_amd_apu_is_integrated(self) -> None:
        assert _classify(AMD_APU, "0x1002") == ("amd", "integrated", "amdgpu")

    def test_amd_legacy_uses_radeon(self) -> None:
        assert _classify(AMD_LEGACY, "0x1002") == ("amd", "discrete", "radeon")

    def test_intel_igpu_is_i915(self) -> None:
        assert _classify(INTEL_IGPU, "0x8086", "0000:00:02.0") == ("intel", "integrated", "i915")

    def test_intel_lunarlake_is_xe_integrated(self) -> None:
        assert _classify(INTEL_LUNARLAKE, "0x8086", "0000:00:02.0") == ("intel", "integrated", "xe")

    def test_intel_card_is_discrete(self) -> None:
        assert _classify(INTEL_ARC, "0x8086", "0000:03:00.0") == ("intel", "discrete", "xe")

    def test_bound_driver_wins_over_name_hints(self) -> None:
        assert _classify(INTEL_LUNARLAKE, "0x8086", "0000:00:02.0", "i915")[2] == "i915"
        assert _classify(AMD_RX, "0x1002", driver="radeon")[2] == "radeon"

    def test_vendor_comes_from_the_pci_id_not_the_name(self) -> None:
        assert _classify("", "0x10de") == ("nvidia", "discrete", "nvidia")

    def test_virtual_gpu_is_ignored(self) -> None:
        virtio = GpuDevice("0000:00:01.0", "0x1af4", desc="Red Hat, Inc. Virtio GPU")
        assert gpu_config.classify_gpu(virtio) is None


class TestSysfs:
    def test_reads_display_controllers_only(self, pci: FakePci) -> None:
        pci.add("0000:00:02.0", VGA, "0x8086", INTEL_IGPU, driver="i915", boot_vga=True)
        pci.add("0000:01:00.0", CONTROLLER_3D, "0x10de", NVIDIA_MOBILE)
        pci.add("0000:00:1f.3", "0x040300", "0x8086", "Intel Corporation Audio")
        assert pci.devices() == [
            GpuDevice("0000:00:02.0", "0x8086", True, "i915", INTEL_IGPU),
            GpuDevice("0000:01:00.0", "0x10de", False, "", NVIDIA_MOBILE),
        ]

    def test_sees_a_dgpu_exposed_as_display_controller(self, pci: FakePci) -> None:
        pci.add("0000:03:00.0", DISPLAY, "0x1002", AMD_RX_MOBILE, driver="amdgpu")
        assert [d.slot for d in pci.devices()] == ["0000:03:00.0"]

    def test_missing_sysfs_is_not_fatal(self, tmp_path: Path) -> None:
        assert gpu_config.read_gpu_devices(tmp_path / "absent") == []

    def test_lspci_descriptions(self) -> None:
        out = f"0000:01:00.0 VGA compatible controller: {NVIDIA}\n0000:00:1f.0 ISA bridge\n"
        assert gpu_config.parse_lspci_descriptions(out) == {"0000:01:00.0": NVIDIA}

    def test_convert_pci_format(self) -> None:
        assert gpu_config.convert_to_pci_format("00:02.0") == "PCI:0:2:0"
        assert gpu_config.convert_to_pci_format("0000:0a:00.1") == "PCI:10:0:1"
        assert gpu_config.convert_to_pci_format("garbage") == ""


class TestRender:
    def test_nvidia_only(self, pci: FakePci) -> None:
        pci.add("0000:01:00.0", VGA, "0x10de", NVIDIA, boot_vga=True)
        out = gpu_config.render(pci.devices(), chassis_type="3")
        assert "glf.nvidia_config" in out
        assert "laptop = false;" in out
        assert 'nvidiaBusId = "PCI:1:0:0";' in out
        # No AMD hardware -> amdgpu explicitly disabled.
        assert "glf.amdgpu_config.enable = false;" in out
        assert (
            '{ vendor = "nvidia"; kind = "discrete"; driver = "nvidia"; '
            'busId = "PCI:1:0:0"; bootVga = true; }'
        ) in out

    def test_nvidia_intel_hybrid_laptop_prime(self, pci: FakePci) -> None:
        pci.add("0000:00:02.0", VGA, "0x8086", INTEL_IGPU, driver="i915", boot_vga=True)
        pci.add("0000:01:00.0", CONTROLLER_3D, "0x10de", NVIDIA)
        out = gpu_config.render(pci.devices(), chassis_type="10")
        assert "laptop = true;" in out  # DMI chassis, the name says nothing here
        assert 'intelBusId = "PCI:0:2:0";' in out
        assert 'nvidiaBusId = "PCI:1:0:0";' in out
        assert "glf.intel_config.enable = true;" in out

    def test_laptop_name_fallback_without_dmi(self, pci: FakePci) -> None:
        pci.add("0000:01:00.0", CONTROLLER_3D, "0x10de", NVIDIA_MOBILE)
        assert "laptop = true;" in gpu_config.render(pci.devices())

    def test_two_nvidia_cards_emit_a_single_bus_id(self, pci: FakePci) -> None:
        pci.add("0000:01:00.0", VGA, "0x10de", NVIDIA, boot_vga=True)
        pci.add("0000:02:00.0", VGA, "0x10de", NVIDIA)
        out = gpu_config.render(pci.devices(), chassis_type="3")
        assert out.count("nvidiaBusId") == 1
        assert out.count("vendor =") == 2

    def test_prime_prefers_the_integrated_gpu(self, pci: FakePci) -> None:
        pci.add("0000:00:02.0", VGA, "0x8086", INTEL_IGPU, driver="i915")
        pci.add("0000:03:00.0", VGA, "0x8086", INTEL_ARC, driver="xe")
        pci.add("0000:04:00.0", VGA, "0x10de", NVIDIA)
        out = gpu_config.render(pci.devices())
        assert out.count("intelBusId") == 1
        assert 'intelBusId = "PCI:0:2:0";' in out

    def test_amd_rx_enables_amdgpu(self, pci: FakePci) -> None:
        pci.add("0000:03:00.0", VGA, "0x1002", AMD_RX, driver="amdgpu", boot_vga=True)
        out = gpu_config.render(pci.devices())
        assert "glf.amdgpu_config.enable = true;" in out
        assert "legacy" not in out
        assert "glf.nvidia_config" not in out

    def test_amd_legacy_enables_legacy(self, pci: FakePci) -> None:
        pci.add("0000:01:00.0", VGA, "0x1002", AMD_LEGACY, driver="radeon")
        out = gpu_config.render(pci.devices())
        assert "glf.amdgpu_config.enable = true;" in out
        assert "glf.amdgpu_config.legacy = true;" in out

    def test_amd_igpu_with_intel_card_keeps_both_kinds(self, pci: FakePci) -> None:
        pci.add("0000:03:00.0", VGA, "0x8086", INTEL_ARC, driver="xe", boot_vga=True)
        pci.add("0000:0c:00.0", VGA, "0x1002", AMD_APU, driver="amdgpu")
        out = gpu_config.render(pci.devices())
        assert 'vendor = "intel"; kind = "discrete"; driver = "xe";' in out
        assert 'vendor = "amd"; kind = "integrated"; driver = "amdgpu";' in out
        assert 'glf.intel_config.driver = "xe";' in out

    def test_virtual_only_emits_nothing(self, pci: FakePci) -> None:
        pci.add("0000:00:01.0", VGA, "0x1af4", "Red Hat, Inc. Virtio GPU", driver="virtio-pci")
        assert gpu_config.render(pci.devices()) == ""

    def test_no_gpu_emits_nothing(self) -> None:
        assert gpu_config.render([]) == ""
