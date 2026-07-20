"""Unit tests for the per-disk storage requirement check."""

from typing import Any
from unittest.mock import patch

import pytest

try:
    from omnis.jobs.requirements import RequirementStatus, SystemRequirementsChecker

    HAS_REQUIREMENTS = True
except ImportError:
    HAS_REQUIREMENTS = False

pytestmark = pytest.mark.skipif(not HAS_REQUIREMENTS, reason="requirements not available")


def _disk(name: str, size_gb: float, model: str = "", disk_type: str = "SSD") -> dict[str, Any]:
    """Build a disk_detector-shaped dict for the given size."""
    size_bytes = int(size_gb * 1024**3)
    return {
        "name": name,
        "model": model,
        "size": f"{size_gb:.1f} GB",
        "sizeBytes": size_bytes,
        "type": disk_type,
        "removable": False,
        "partitions": [],
    }


def _check(disks: list[dict[str, Any]], **cfg: Any) -> Any:
    """Run the disk check against a mocked disk list."""
    config = {"disk": {"enabled": True, "min_gb": 60, "recommended_gb": 120, **cfg}}
    checker = SystemRequirementsChecker(config)
    with patch("omnis.jobs.requirements.list_disks", return_value=disks):
        return checker._check_disk_space()


class TestDiskStatus:
    """Global status is driven by the best disk, not by a single scalar."""

    def test_passes_when_one_disk_is_large_enough(self) -> None:
        result = _check([_disk("sda", 20.0), _disk("nvme0n1", 500.0)])
        assert result.status == RequirementStatus.PASS

    def test_fails_when_no_disk_reaches_minimum(self) -> None:
        result = _check([_disk("sda", 20.0), _disk("sdb", 40.0)])
        assert result.status == RequirementStatus.FAIL
        assert result.is_critical is True

    def test_warns_when_minimum_met_but_not_recommended(self) -> None:
        result = _check([_disk("sda", 80.0)])
        assert result.status == RequirementStatus.WARN
        assert result.passed is True

    def test_fails_when_no_disk_detected(self) -> None:
        result = _check([])
        assert result.status == RequirementStatus.FAIL
        assert result.data["disks"] == []

    def test_skips_when_enumeration_raises(self) -> None:
        checker = SystemRequirementsChecker({"disk": {"enabled": True}})
        with patch("omnis.jobs.requirements.list_disks", side_effect=OSError("lsblk exploded")):
            result = checker._check_disk_space()
        assert result.status == RequirementStatus.SKIP


class TestDiskDetail:
    """Every disk must be reported individually."""

    def test_detail_contains_every_disk(self) -> None:
        result = _check([_disk("nvme0n1", 500.0), _disk("sda", 2048.0), _disk("sdb", 30.0)])
        names = [entry["name"] for entry in result.data["disks"]]
        assert names == ["nvme0n1", "sda", "sdb"]

    def test_detail_flags_per_disk_eligibility(self) -> None:
        result = _check([_disk("nvme0n1", 500.0), _disk("sdb", 30.0)])
        eligibility = {entry["name"]: entry["meetsMinimum"] for entry in result.data["disks"]}
        assert eligibility == {"nvme0n1": True, "sdb": False}

    def test_detail_reports_size_and_model(self) -> None:
        result = _check([_disk("nvme0n1", 500.0, model="Samsung 990 PRO")])
        entry = result.data["disks"][0]
        assert entry["model"] == "Samsung 990 PRO"
        assert entry["sizeGb"] == pytest.approx(500.0)
        assert entry["size"] == "500.0 GB"

    def test_smaller_nvme_stays_visible_next_to_a_larger_hdd(self) -> None:
        """The reported bug: a smaller NVMe was hidden by a larger secondary HDD."""
        result = _check(
            [
                _disk("nvme0n1", 500.0, model="NVMe SSD"),
                _disk("sda", 4096.0, model="Seagate HDD", disk_type="HDD"),
            ]
        )
        names = [entry["name"] for entry in result.data["disks"]]
        assert "nvme0n1" in names
        assert "sda" in names
        assert "nvme0n1" in result.current_value
        assert "sda" in result.current_value

    def test_larger_hdd_stays_visible_next_to_a_smaller_nvme(self) -> None:
        result = _check([_disk("nvme0n1", 4096.0), _disk("sda", 500.0, disk_type="HDD")])
        names = [entry["name"] for entry in result.data["disks"]]
        assert names == ["nvme0n1", "sda"]


class TestDiskSummary:
    """current_value stays a short string the QML can render as-is."""

    def test_summary_lists_each_disk(self) -> None:
        result = _check([_disk("nvme0n1", 500.0), _disk("sda", 1024.0)])
        assert result.current_value == "nvme0n1 500.0 GB, sda 1024.0 GB"

    def test_summary_collapses_beyond_three_disks(self) -> None:
        disks = [_disk(f"sd{letter}", 500.0) for letter in "abcde"]
        result = _check(disks)
        assert result.current_value.endswith("(+2)")
        assert "sdd" not in result.current_value

    def test_required_and_recommended_values_are_preserved(self) -> None:
        result = _check([_disk("sda", 500.0)], min_gb=60, recommended_gb=120)
        assert result.required_value == "60 GB"
        assert result.recommended_value == "120 GB (SSD recommended)"

    def test_check_all_still_includes_the_disk_check(self) -> None:
        checker = SystemRequirementsChecker({"disk": {"enabled": True, "min_gb": 1}})
        with patch("omnis.jobs.requirements.list_disks", return_value=[_disk("sda", 500.0)]):
            result = checker.check_all()
        disk_checks = [check for check in result.checks if check.name == "disk"]
        assert len(disk_checks) == 1
        assert disk_checks[0].data["disks"][0]["name"] == "sda"
