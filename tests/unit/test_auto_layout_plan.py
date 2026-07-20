"""Tests for the automatic-mode layout planner used by the disk preview."""

from __future__ import annotations

import pytest

from omnis.jobs.partition import plan_auto_layout, swapfile_size_mb

# 256 GB disk expressed in 512-byte sectors.
DISK_SECTORS = (256 * 1024**3) // 512


def _by_type(planned: list[dict], part_type: str) -> dict:
    return next(entry for entry in planned if entry["partType"] == part_type)


class TestSwapfileSize:
    """The preview must announce the size the job would really create."""

    def test_hibernate_covers_memory_image(self) -> None:
        assert swapfile_size_mb("hibernate", ram_mb=16384) == 16384

    def test_hibernate_has_a_floor(self) -> None:
        assert swapfile_size_mb("hibernate", ram_mb=2048) == 8192

    def test_plain_file_is_capped(self) -> None:
        assert swapfile_size_mb("file", ram_mb=32768) == 8192

    def test_plain_file_follows_small_memory(self) -> None:
        assert swapfile_size_mb("file", ram_mb=4096) == 4096

    def test_no_swap_strategy_means_no_file(self) -> None:
        assert swapfile_size_mb("none", ram_mb=8192) == 0


class TestPlanAutoLayout:
    """Geometry mirrors _partition_auto without touching any disk."""

    def test_creates_esp_and_root(self) -> None:
        planned = plan_auto_layout(DISK_SECTORS, ram_mb=8192)
        assert [entry["partType"] for entry in planned] == ["efi", "linux"]

    def test_esp_honours_requested_size(self) -> None:
        planned = plan_auto_layout(DISK_SECTORS, efi_size_mb=1024, ram_mb=8192)
        assert _by_type(planned, "efi")["sizeBytes"] == 1024 * 1024 * 1024

    def test_root_carries_the_chosen_filesystem(self) -> None:
        planned = plan_auto_layout(DISK_SECTORS, filesystem="btrfs", ram_mb=8192)
        assert _by_type(planned, "linux")["fstype"] == "btrfs"

    def test_root_reports_encryption(self) -> None:
        planned = plan_auto_layout(DISK_SECTORS, encryption=True, ram_mb=8192)
        assert _by_type(planned, "linux")["encrypted"] is True

    def test_segments_do_not_overlap_and_stay_on_disk(self) -> None:
        planned = plan_auto_layout(DISK_SECTORS, legacy_swap_gb=4, swap_strategy="", ram_mb=8192)
        ordered = sorted(planned, key=lambda entry: entry["startSector"])
        for previous, following in zip(ordered, ordered[1:], strict=False):
            assert previous["endSector"] < following["startSector"]
        assert ordered[-1]["endSector"] < DISK_SECTORS

    def test_legacy_swap_size_creates_a_partition(self) -> None:
        planned = plan_auto_layout(DISK_SECTORS, swap_strategy="", legacy_swap_gb=4, ram_mb=8192)
        assert _by_type(planned, "swap")["sizeBytes"] == pytest.approx(4 * 1024**3, rel=0.01)

    def test_swapfile_strategies_create_no_partition(self) -> None:
        planned = plan_auto_layout(DISK_SECTORS, swap_strategy="hibernate", ram_mb=8192)
        assert all(entry["partType"] != "swap" for entry in planned)

    def test_swapfile_is_reported_on_root(self) -> None:
        """Without this the preview stayed identical when picking hibernation."""
        planned = plan_auto_layout(DISK_SECTORS, swap_strategy="hibernate", ram_mb=16384)
        assert _by_type(planned, "linux")["swapfileBytes"] == 16384 * 1024 * 1024

    def test_disabling_swap_reports_no_swapfile(self) -> None:
        planned = plan_auto_layout(DISK_SECTORS, swap_strategy="none", ram_mb=8192)
        assert _by_type(planned, "linux")["swapfileBytes"] == 0

    def test_options_actually_change_the_plan(self) -> None:
        """The reported bug: the preview never reflected any chosen option."""
        base = plan_auto_layout(DISK_SECTORS, filesystem="ext4", swap_strategy="none", ram_mb=8192)
        variant = plan_auto_layout(
            DISK_SECTORS,
            filesystem="btrfs",
            swap_strategy="hibernate",
            encryption=True,
            ram_mb=8192,
        )
        assert base != variant

    def test_tiny_disk_does_not_produce_negative_geometry(self) -> None:
        planned = plan_auto_layout(2048 * 64, ram_mb=8192)
        assert all(entry["sizeSectors"] >= 0 for entry in planned)
