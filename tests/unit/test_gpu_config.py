"""
Unit tests for the GPU classification / configuration.nix snippet generation
(ported from the GLF Calamares nixos module). All inputs are synthetic ``lspci``
text so no hardware is needed.
"""

from __future__ import annotations

from omnis.jobs import gpu_config

NVIDIA = "01:00.0 VGA compatible controller: NVIDIA Corporation GA104 [GeForce RTX 3070] (rev a1)"
NVIDIA_MOBILE = (
    "01:00.0 VGA compatible controller: NVIDIA Corporation "
    "GA106M [GeForce RTX 3060 Mobile / Max-Q] (rev a1)"
)
INTEL_IGPU = (
    "00:02.0 VGA compatible controller: Intel Corporation "
    "AlderLake-P GT2 [Iris Xe Graphics] (rev 0c)"
)
INTEL_LUNARLAKE = (
    "00:02.0 VGA compatible controller: Intel Corporation Lunar Lake [Arc Graphics 140V] (rev 04)"
)
AMD_RX = (
    "03:00.0 VGA compatible controller: Advanced Micro Devices, Inc. "
    "[AMD/ATI] Navi 22 [Radeon RX 6700 XT] (rev c1)"
)
AMD_LEGACY = (
    "01:00.0 VGA compatible controller: Advanced Micro Devices, Inc. "
    "[AMD/ATI] RV710 [Radeon HD 4350/4550]"
)
VIRTIO = "00:01.0 VGA compatible controller: Red Hat, Inc. Virtio GPU"


class TestClassification:
    def test_nvidia_is_discrete(self) -> None:
        assert gpu_config.classify_gpu(NVIDIA) == {
            "vendor": "nvidia",
            "kind": "discrete",
            "driver": "nvidia",
        }

    def test_amd_rx_is_amdgpu_discrete(self) -> None:
        info = gpu_config.classify_gpu(AMD_RX)
        assert info["vendor"] == "amd"
        assert info["driver"] == "amdgpu"

    def test_amd_legacy_uses_radeon(self) -> None:
        assert gpu_config.classify_gpu(AMD_LEGACY)["driver"] == "radeon"

    def test_intel_igpu_is_i915(self) -> None:
        info = gpu_config.classify_gpu(INTEL_IGPU)
        assert info == {"vendor": "intel", "kind": "integrated", "driver": "i915"}

    def test_intel_lunarlake_is_xe_integrated(self) -> None:
        assert gpu_config.classify_gpu(INTEL_LUNARLAKE) == {
            "vendor": "intel",
            "kind": "integrated",
            "driver": "xe",
        }

    def test_virtio_is_virtual(self) -> None:
        assert gpu_config.classify_gpu(VIRTIO)["kind"] == "virtual"


class TestPciParsing:
    def test_parse_extracts_address_and_desc(self) -> None:
        devices = gpu_config.parse_vga_devices(NVIDIA)
        assert devices == [("PCI:1:0:0", NVIDIA.split(": ", 1)[1])]

    def test_convert_pci_format(self) -> None:
        assert gpu_config.convert_to_pci_format("00:02.0") == "PCI:0:2:0"
        assert gpu_config.convert_to_pci_format("0a:00.1") == "PCI:10:0:1"


class TestRender:
    def test_nvidia_only(self) -> None:
        out = gpu_config.render(NVIDIA)
        assert "glf.nvidia_config" in out
        assert "enable = true;" in out
        assert "laptop = false;" in out
        assert 'nvidiaBusId = "PCI:1:0:0";' in out
        # No AMD hardware -> amdgpu explicitly disabled.
        assert "glf.amdgpu_config.enable = false;" in out

    def test_nvidia_intel_hybrid_laptop_prime(self) -> None:
        out = gpu_config.render(NVIDIA_MOBILE + "\n" + INTEL_IGPU)
        assert "glf.nvidia_config" in out
        assert "laptop = true;" in out  # "Mobile" marks a laptop
        assert 'intelBusId = "PCI:0:2:0";' in out
        assert 'nvidiaBusId = "PCI:1:0:0";' in out
        assert "glf.intel_config.enable = true;" in out

    def test_amd_rx_enables_amdgpu(self) -> None:
        out = gpu_config.render(AMD_RX)
        assert "glf.amdgpu_config.enable = true;" in out
        assert "legacy" not in out
        assert "glf.nvidia_config" not in out

    def test_amd_legacy_enables_legacy(self) -> None:
        out = gpu_config.render(AMD_LEGACY)
        assert "glf.amdgpu_config.enable = true;" in out
        assert "glf.amdgpu_config.legacy = true;" in out

    def test_intel_xe_sets_driver(self) -> None:
        out = gpu_config.render(INTEL_LUNARLAKE)
        assert 'glf.intel_config.driver = "xe";' in out

    def test_virtual_only_emits_nothing(self) -> None:
        assert gpu_config.render(VIRTIO) == ""

    def test_no_gpu_emits_nothing(self) -> None:
        assert gpu_config.render("") == ""
        assert gpu_config.render("00:1f.0 ISA bridge: Intel Corporation") == ""
