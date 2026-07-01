"""Unit tests for the unified disk_detector module."""

import json
from unittest.mock import MagicMock, patch

import pytest

try:
    from omnis.utils import disk_detector

    HAS_DETECTOR = True
except ImportError:
    HAS_DETECTOR = False

pytestmark = pytest.mark.skipif(not HAS_DETECTOR, reason="disk_detector not available")


def _lsblk_result(payload: dict[str, object]) -> MagicMock:
    return MagicMock(returncode=0, stdout=json.dumps(payload), stderr="")


def _findmnt_result(source: str, returncode: int = 0) -> MagicMock:
    return MagicMock(returncode=returncode, stdout=source + "\n", stderr="")


def _make_run(lsblk_payload: dict[str, object], live_source: str) -> MagicMock:
    """Build a subprocess.run side_effect dispatching on the binary name."""

    def _side_effect(cmd: list[str], **_kwargs: object) -> MagicMock:
        if cmd[0] == "lsblk":
            return _lsblk_result(lsblk_payload)
        if cmd[0] == "findmnt":
            return _findmnt_result(live_source)
        return MagicMock(returncode=0, stdout="", stderr="")

    return MagicMock(side_effect=_side_effect)


class TestCoerceBool:
    """Tests for the robust bool coercion helper."""

    def test_truthy_forms(self) -> None:
        assert disk_detector._coerce_bool(1) is True
        assert disk_detector._coerce_bool("1") is True
        assert disk_detector._coerce_bool(True) is True

    def test_falsy_forms(self) -> None:
        assert disk_detector._coerce_bool(0) is False
        assert disk_detector._coerce_bool("0") is False
        assert disk_detector._coerce_bool(False) is False
        assert disk_detector._coerce_bool(None) is False


class TestClassifyPartType:
    """Tests for partType deduction rules."""

    def test_efi_from_vfat_and_parttypename(self) -> None:
        assert disk_detector._classify_part_type("vfat", "EFI System") == "efi"

    def test_vfat_without_efi_is_other(self) -> None:
        assert disk_detector._classify_part_type("vfat", "") == "other"

    def test_windows_from_ntfs(self) -> None:
        assert disk_detector._classify_part_type("ntfs", "") == "windows"

    def test_windows_from_parttypename(self) -> None:
        assert disk_detector._classify_part_type("", "Microsoft basic data") == "windows"

    def test_swap(self) -> None:
        assert disk_detector._classify_part_type("swap", "") == "swap"
        assert disk_detector._classify_part_type("", "Linux swap") == "swap"

    def test_linux_filesystems(self) -> None:
        assert disk_detector._classify_part_type("ext4", "") == "linux"
        assert disk_detector._classify_part_type("btrfs", "") == "linux"
        assert disk_detector._classify_part_type("xfs", "") == "linux"

    def test_other(self) -> None:
        assert disk_detector._classify_part_type("", "") == "other"


class TestListDisks:
    """Tests for list_disks() parsing and contract."""

    @patch("omnis.utils.disk_detector.subprocess.run")
    def test_parses_disk_and_partitions(self, mock_run: MagicMock) -> None:
        payload = {
            "blockdevices": [
                {
                    "name": "nvme0n1",
                    "size": 500 * 1024**3,
                    "type": "disk",
                    "model": "  WD Black  ",
                    "rm": False,
                    "hotplug": False,
                    "rota": False,
                    "children": [
                        {
                            "name": "nvme0n1p1",
                            "size": 512 * 1024**2,
                            "type": "part",
                            "fstype": "vfat",
                            "parttypename": "EFI System",
                        },
                        {
                            "name": "nvme0n1p2",
                            "size": 499 * 1024**3,
                            "type": "part",
                            "fstype": "ext4",
                            "parttypename": "Linux filesystem",
                        },
                    ],
                }
            ]
        }
        # Live root is an overlay -> exclude nothing.
        mock_run.side_effect = _make_run(payload, "overlay").side_effect

        disks = disk_detector.list_disks()

        assert len(disks) == 1
        disk = disks[0]
        assert disk["name"] == "nvme0n1"
        assert disk["model"] == "WD Black"  # stripped
        assert disk["sizeBytes"] == 500 * 1024**3
        assert disk["size"] == "500.0 GB"
        assert disk["type"] == "SSD"  # rota False
        assert disk["removable"] is False
        assert len(disk["partitions"]) == 2
        assert disk["partitions"][0]["partType"] == "efi"
        assert disk["partitions"][1]["partType"] == "linux"

    @patch("omnis.utils.disk_detector.subprocess.run")
    def test_hdd_and_removable_flags(self, mock_run: MagicMock) -> None:
        payload = {
            "blockdevices": [
                {
                    "name": "sdb",
                    "size": 64 * 1024**3,
                    "type": "disk",
                    "model": "USB Stick",
                    "rm": True,
                    "hotplug": True,
                    "rota": True,
                }
            ]
        }
        mock_run.side_effect = _make_run(payload, "overlay").side_effect

        disks = disk_detector.list_disks()
        assert len(disks) == 1
        assert disks[0]["type"] == "HDD"  # rota True
        assert disks[0]["removable"] is True

    @patch("omnis.utils.disk_detector.subprocess.run")
    def test_filters_non_disk_devices(self, mock_run: MagicMock) -> None:
        payload = {
            "blockdevices": [
                {"name": "loop0", "size": 1024, "type": "loop"},
                {"name": "sr0", "size": 1024, "type": "rom"},
                {
                    "name": "sda",
                    "size": 256 * 1024**3,
                    "type": "disk",
                    "rota": False,
                },
            ]
        }
        mock_run.side_effect = _make_run(payload, "overlay").side_effect

        disks = disk_detector.list_disks()
        assert [d["name"] for d in disks] == ["sda"]

    @patch("omnis.utils.disk_detector.subprocess.run")
    def test_excludes_live_disk(self, mock_run: MagicMock) -> None:
        payload = {
            "blockdevices": [
                {
                    "name": "sda",
                    "size": 256 * 1024**3,
                    "type": "disk",
                    "rota": False,
                    "children": [
                        {"name": "sda1", "size": 512 * 1024**2, "type": "part"},
                        {"name": "sda2", "size": 255 * 1024**3, "type": "part"},
                    ],
                },
                {
                    "name": "nvme0n1",
                    "size": 1024**4,
                    "type": "disk",
                    "rota": False,
                    "children": [],
                },
            ]
        }
        # Live root sits on /dev/sda2 -> sda excluded, nvme0n1 kept.
        mock_run.side_effect = _make_run(payload, "/dev/sda2").side_effect

        disks = disk_detector.list_disks()
        names = [d["name"] for d in disks]
        assert "sda" not in names
        assert "nvme0n1" in names

    @patch("omnis.utils.disk_detector.subprocess.run")
    def test_non_block_live_source_excludes_nothing(self, mock_run: MagicMock) -> None:
        payload = {
            "blockdevices": [
                {
                    "name": "sda",
                    "size": 256 * 1024**3,
                    "type": "disk",
                    "rota": False,
                    "children": [{"name": "sda2", "size": 1024, "type": "part"}],
                }
            ]
        }
        # airootfs (live ISO) is not a block device.
        mock_run.side_effect = _make_run(payload, "airootfs").side_effect

        disks = disk_detector.list_disks()
        assert [d["name"] for d in disks] == ["sda"]

    @patch("omnis.utils.disk_detector.subprocess.run")
    def test_fallback_on_lsblk_missing(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError()

        disks = disk_detector.list_disks()
        # Mock list follows the same contract.
        assert len(disks) == 2
        names = {d["name"] for d in disks}
        assert names == {"sda", "nvme0n1"}
        for disk in disks:
            assert set(disk.keys()) == {
                "name",
                "model",
                "size",
                "sizeBytes",
                "type",
                "removable",
                "partitions",
            }

    @patch("omnis.utils.disk_detector.subprocess.run")
    def test_fallback_on_bad_json(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="not json", stderr="")

        disks = disk_detector.list_disks()
        assert len(disks) == 2  # mock fallback

    @patch("omnis.utils.disk_detector.subprocess.run")
    def test_fallback_on_nonzero_exit(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="boom")

        disks = disk_detector.list_disks()
        assert len(disks) == 2  # mock fallback
