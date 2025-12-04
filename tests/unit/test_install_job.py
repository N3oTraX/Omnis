"""Unit tests for InstallJob."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

try:
    from omnis.jobs.base import JobContext, JobResult, JobStatus
    from omnis.jobs.install import InstallJob

    HAS_INSTALL_JOB = True
except ImportError:
    HAS_INSTALL_JOB = False

# Skip entire module if omnis is not available
pytestmark = pytest.mark.skipif(not HAS_INSTALL_JOB, reason="InstallJob not available")


class TestInstallJob:
    """Tests for InstallJob basic functionality."""

    def test_init_defaults(self) -> None:
        """InstallJob should have correct defaults."""
        job = InstallJob()
        assert job.name == "install"
        assert job.description == "System installation - copy files to target"
        assert job.status == JobStatus.PENDING
        assert job._source_size_bytes == 0
        assert job._bytes_copied == 0

    def test_estimate_duration_default(self) -> None:
        """estimate_duration should return default value without source size."""
        job = InstallJob()
        duration = job.estimate_duration()
        assert duration == 300  # 5 minutes

    def test_estimate_duration_with_size(self) -> None:
        """estimate_duration should adjust based on source size."""
        job = InstallJob()
        job._source_size_bytes = 10 * 1024 * 1024 * 1024  # 10 GB

        duration = job.estimate_duration()
        # 10 GB / 100 MB/s = 100 seconds * 1.5 = 150 seconds
        assert duration >= 60  # At least minimum
        assert duration > 100  # Should be adjusted


class TestConstants:
    """Tests for class constants."""

    def test_exclude_dirs(self) -> None:
        """EXCLUDE_DIRS should contain expected virtual filesystems."""
        job = InstallJob()
        assert "/proc" in job.EXCLUDE_DIRS
        assert "/sys" in job.EXCLUDE_DIRS
        assert "/dev" in job.EXCLUDE_DIRS
        assert "/run" in job.EXCLUDE_DIRS
        assert "/tmp" in job.EXCLUDE_DIRS

    def test_critical_files(self) -> None:
        """CRITICAL_FILES should contain expected system files."""
        job = InstallJob()
        assert "/etc/fstab" in job.CRITICAL_FILES
        assert "/etc/passwd" in job.CRITICAL_FILES
        assert "/boot" in job.CRITICAL_FILES

    def test_min_free_space(self) -> None:
        """MIN_FREE_SPACE should be 5 GB."""
        job = InstallJob()
        expected_bytes = 5 * 1024 * 1024 * 1024
        assert expected_bytes == job.MIN_FREE_SPACE


class TestValidate:
    """Tests for the validate() method."""

    def test_validate_invalid_source_type(self) -> None:
        """validate should fail for invalid source_type."""
        job = InstallJob()
        context = JobContext(
            selections={
                "source_type": "invalid",
            }
        )

        result = job.validate(context)

        assert result.success is False
        assert result.error_code == 51
        assert "Invalid source_type" in result.message

    def test_validate_squashfs_missing_path(self) -> None:
        """validate should fail if squashfs_path not provided for squashfs type."""
        job = InstallJob()
        context = JobContext(
            selections={
                "source_type": "squashfs",
            }
        )

        result = job.validate(context)

        assert result.success is False
        assert result.error_code == 50
        assert "squashfs_path is required" in result.message

    @patch("omnis.jobs.install.Path")
    def test_validate_squashfs_not_found(self, mock_path: MagicMock) -> None:
        """validate should fail if squashfs file doesn't exist."""
        job = InstallJob()

        mock_sfs_path = MagicMock()
        mock_sfs_path.exists.return_value = False
        mock_path.return_value = mock_sfs_path

        context = JobContext(
            selections={
                "source_type": "squashfs",
                "squashfs_path": "/nonexistent.sfs",
            }
        )

        result = job.validate(context)

        assert result.success is False
        assert result.error_code == 52
        assert "Squashfs file not found" in result.message

    @patch("omnis.jobs.install.shutil.which")
    @patch("omnis.jobs.install.Path")
    def test_validate_squashfs_missing_tool(
        self, mock_path: MagicMock, mock_which: MagicMock
    ) -> None:
        """validate should fail if unsquashfs tool not available."""
        job = InstallJob()

        mock_sfs_path = MagicMock()
        mock_sfs_path.exists.return_value = True
        mock_sfs_path.is_file.return_value = True
        mock_path.return_value = mock_sfs_path

        mock_which.return_value = None  # Tool not found

        context = JobContext(
            selections={
                "source_type": "squashfs",
                "squashfs_path": "/test.sfs",
            }
        )

        result = job.validate(context)

        assert result.success is False
        assert result.error_code == 54
        assert "unsquashfs tool not found" in result.message

    @patch("omnis.jobs.install.Path")
    def test_validate_source_not_found(self, mock_path: MagicMock) -> None:
        """validate should fail if live source doesn't exist."""
        job = InstallJob()

        mock_source = MagicMock()
        mock_source.exists.return_value = False

        # Mock Path to return different objects for source and target
        def path_side_effect(p: str) -> MagicMock:
            if p == "/nonexistent":
                return mock_source
            # Return a valid target mock for other paths
            mock_target = MagicMock()
            mock_target.exists.return_value = True
            mock_target.is_dir.return_value = True
            mock_target.stat.return_value.st_mode = 0o755
            return mock_target

        mock_path.side_effect = path_side_effect

        context = JobContext(
            target_root="/mnt",
            selections={
                "source": "/nonexistent",
                "source_type": "live",
            },
        )

        result = job.validate(context)

        assert result.success is False
        assert result.error_code == 55
        assert "Source directory not found" in result.message

    @patch("omnis.jobs.install.Path")
    def test_validate_target_not_found(self, mock_path: MagicMock) -> None:
        """validate should fail if target directory doesn't exist."""
        job = InstallJob()

        mock_source = MagicMock()
        mock_source.exists.return_value = True
        mock_source.is_dir.return_value = True

        mock_target = MagicMock()
        mock_target.exists.return_value = False

        def path_side_effect(p: str) -> MagicMock:
            if p == "/":
                return mock_source
            return mock_target

        mock_path.side_effect = path_side_effect

        context = JobContext(
            target_root="/mnt",
            selections={
                "source": "/",
                "source_type": "live",
            },
        )

        result = job.validate(context)

        assert result.success is False
        assert result.error_code == 57
        assert "Target directory not found" in result.message

    @patch("omnis.jobs.install.os.access")
    @patch("omnis.jobs.install.shutil.which")
    @patch("omnis.jobs.install.Path")
    def test_validate_rsync_not_found(
        self, mock_path: MagicMock, mock_which: MagicMock, mock_access: MagicMock
    ) -> None:
        """validate should fail if rsync tool not available for live install."""
        job = InstallJob()

        # Mock valid source and target
        mock_source = MagicMock()
        mock_source.exists.return_value = True
        mock_source.is_dir.return_value = True

        mock_target = MagicMock()
        mock_target.exists.return_value = True
        mock_target.is_dir.return_value = True
        mock_target.stat.return_value.st_mode = 0o755

        def path_side_effect(p: str) -> MagicMock:
            if p == "/":
                return mock_source
            return mock_target

        mock_path.side_effect = path_side_effect
        mock_access.return_value = True

        # rsync not found, du found
        def which_side_effect(tool: str) -> str | None:
            if tool == "rsync":
                return None
            return "/usr/bin/du"

        mock_which.side_effect = which_side_effect

        context = JobContext(
            target_root="/mnt",
            selections={
                "source": "/",
                "source_type": "live",
            },
        )

        result = job.validate(context)

        assert result.success is False
        assert result.error_code == 60
        assert "rsync tool not found" in result.message

    @patch("omnis.jobs.install.os.access")
    @patch("omnis.jobs.install.shutil.disk_usage")
    @patch("omnis.jobs.install.shutil.which")
    @patch("omnis.jobs.install.Path")
    def test_validate_insufficient_space(
        self,
        mock_path: MagicMock,
        mock_which: MagicMock,
        mock_disk_usage: MagicMock,
        mock_access: MagicMock,
    ) -> None:
        """validate should fail if insufficient disk space."""
        job = InstallJob()

        # Mock valid paths
        mock_source = MagicMock()
        mock_source.exists.return_value = True
        mock_source.is_dir.return_value = True

        mock_target = MagicMock()
        mock_target.exists.return_value = True
        mock_target.is_dir.return_value = True
        mock_target.stat.return_value.st_mode = 0o755

        def path_side_effect(p: str) -> MagicMock:
            if p == "/":
                return mock_source
            return mock_target

        mock_path.side_effect = path_side_effect
        mock_access.return_value = True

        # Tools available
        mock_which.return_value = "/usr/bin/rsync"

        # Only 2 GB free (less than MIN_FREE_SPACE of 5 GB)
        mock_disk_usage.return_value = MagicMock(free=2 * 1024**3)

        context = JobContext(
            target_root="/mnt",
            selections={
                "source": "/",
                "source_type": "live",
            },
        )

        result = job.validate(context)

        assert result.success is False
        assert result.error_code == 62
        assert "Insufficient disk space" in result.message

    @patch("omnis.jobs.install.os.access")
    @patch("omnis.jobs.install.InstallJob._get_source_size")
    @patch("omnis.jobs.install.shutil.disk_usage")
    @patch("omnis.jobs.install.shutil.which")
    @patch("omnis.jobs.install.Path")
    def test_validate_success(
        self,
        mock_path: MagicMock,
        mock_which: MagicMock,
        mock_disk_usage: MagicMock,
        mock_get_source_size: MagicMock,
        mock_access: MagicMock,
    ) -> None:
        """validate should succeed with valid configuration."""
        job = InstallJob()

        # Mock valid paths
        mock_source = MagicMock()
        mock_source.exists.return_value = True
        mock_source.is_dir.return_value = True

        mock_target = MagicMock()
        mock_target.exists.return_value = True
        mock_target.is_dir.return_value = True
        mock_target.stat.return_value.st_mode = 0o755

        def path_side_effect(p: str) -> MagicMock:
            if p == "/":
                return mock_source
            return mock_target

        mock_path.side_effect = path_side_effect
        mock_access.return_value = True

        # Tools available
        mock_which.return_value = "/usr/bin/rsync"

        # 100 GB free
        mock_disk_usage.return_value = MagicMock(free=100 * 1024**3)

        # Source size 10 GB
        mock_get_source_size.return_value = 10 * 1024**3

        context = JobContext(
            target_root="/mnt",
            selections={
                "source": "/",
                "source_type": "live",
            },
        )

        result = job.validate(context)

        assert result.success is True
        assert "validated" in result.message.lower()


class TestGetSourceSize:
    """Tests for _get_source_size() method."""

    @patch("omnis.jobs.install.subprocess.run")
    def test_get_source_size_success(self, mock_subprocess: MagicMock) -> None:
        """_get_source_size should parse du output correctly."""
        job = InstallJob()

        mock_subprocess.return_value = MagicMock(
            stdout="12345678\t/source/path\n",
            returncode=0,
        )

        size = job._get_source_size("/source/path")

        assert size == 12345678
        assert job._source_size_bytes == 12345678

        # Verify du command was called with exclusions
        call_args = mock_subprocess.call_args
        assert "du" in call_args[0][0]
        assert "-sb" in call_args[0][0]
        assert "--exclude" in call_args[0][0]

    @patch("omnis.jobs.install.subprocess.run")
    def test_get_source_size_with_exclusions(self, mock_subprocess: MagicMock) -> None:
        """_get_source_size should include exclusions in du command."""
        job = InstallJob()

        mock_subprocess.return_value = MagicMock(
            stdout="10000000\t/\n",
            returncode=0,
        )

        job._get_source_size("/")

        call_args = mock_subprocess.call_args[0][0]

        # Check exclusions are present
        assert "--exclude" in call_args
        assert "/proc" in call_args or any("/proc" in str(arg) for arg in call_args)

    @patch("omnis.jobs.install.subprocess.run")
    def test_get_source_size_failure(self, mock_subprocess: MagicMock) -> None:
        """_get_source_size should raise CalledProcessError on failure."""
        job = InstallJob()

        mock_subprocess.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["du"],
        )

        with pytest.raises(subprocess.CalledProcessError):
            job._get_source_size("/source")


class TestRunRsync:
    """Tests for _run_rsync() method."""

    @patch("omnis.jobs.install.InstallJob._get_source_size")
    @patch("omnis.jobs.install.subprocess.Popen")
    def test_run_rsync_success(self, mock_popen: MagicMock, mock_get_size: MagicMock) -> None:
        """_run_rsync should execute rsync and parse progress."""
        job = InstallJob()

        mock_get_size.return_value = 10 * 1024**3  # 10 GB

        # Mock rsync progress output
        mock_process = MagicMock()
        mock_process.stdout = [
            "     1,234,567  10%   12.34MB/s    0:01:23\n",
            "     5,678,901  50%   15.67MB/s    0:00:45\n",
            "    10,000,000  100%  20.00MB/s   0:00:00\n",
        ]
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        context = JobContext(target_root="/mnt")
        result = job._run_rsync("/source/", "/mnt", context)

        assert result.success is True
        assert "copied successfully" in result.message.lower()
        assert job._bytes_copied == 10000000

        # Verify rsync command structure
        call_args = mock_popen.call_args[0][0]
        assert "rsync" in call_args
        assert "-aAXHv" in call_args
        assert "--info=progress2" in call_args

    @patch("omnis.jobs.install.InstallJob._get_source_size")
    @patch("omnis.jobs.install.subprocess.Popen")
    def test_run_rsync_with_exclusions(
        self, mock_popen: MagicMock, mock_get_size: MagicMock
    ) -> None:
        """_run_rsync should include exclusions in command."""
        job = InstallJob()

        mock_get_size.return_value = 0

        mock_process = MagicMock()
        mock_process.stdout = []
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        context = JobContext()
        job._run_rsync("/", "/mnt", context)

        call_args = mock_popen.call_args[0][0]

        # Check exclusions are present
        assert "--exclude" in call_args
        assert any("/proc" in str(arg) for arg in call_args)
        assert any("/sys" in str(arg) for arg in call_args)

    @patch("omnis.jobs.install.InstallJob._get_source_size")
    @patch("omnis.jobs.install.subprocess.Popen")
    def test_run_rsync_adds_trailing_slash(
        self, mock_popen: MagicMock, mock_get_size: MagicMock
    ) -> None:
        """_run_rsync should add trailing slash to source."""
        job = InstallJob()

        mock_get_size.return_value = 0

        mock_process = MagicMock()
        mock_process.stdout = []
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        context = JobContext()
        job._run_rsync("/source", "/mnt", context)

        call_args = mock_popen.call_args[0][0]

        # Source should have trailing slash
        assert "/source/" in call_args

    @patch("omnis.jobs.install.InstallJob._get_source_size")
    @patch("omnis.jobs.install.subprocess.Popen")
    def test_run_rsync_failure(self, mock_popen: MagicMock, mock_get_size: MagicMock) -> None:
        """_run_rsync should handle rsync failure."""
        job = InstallJob()

        mock_get_size.return_value = 0

        mock_process = MagicMock()
        mock_process.stdout = []
        mock_process.wait.return_value = 1  # Non-zero exit
        mock_popen.return_value = mock_process

        context = JobContext()
        result = job._run_rsync("/source/", "/mnt", context)

        assert result.success is False
        assert result.error_code == 64
        assert "rsync failed" in result.message

    @patch("omnis.jobs.install.InstallJob._get_source_size")
    @patch("omnis.jobs.install.subprocess.Popen")
    def test_run_rsync_progress_tracking(
        self, mock_popen: MagicMock, mock_get_size: MagicMock
    ) -> None:
        """_run_rsync should track and report progress correctly."""
        job = InstallJob()

        mock_get_size.return_value = 0

        # Mock progress updates
        mock_process = MagicMock()
        mock_process.stdout = [
            "     1,000,000  25%   10.00MB/s    0:00:30\n",
            "     2,000,000  50%   10.00MB/s    0:00:15\n",
            "     3,000,000  75%   10.00MB/s    0:00:05\n",
        ]
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        progress_calls: list[tuple[int, str]] = []

        def track_progress(percent: int, message: str) -> None:
            progress_calls.append((percent, message))

        context = JobContext(on_progress=track_progress)
        result = job._run_rsync("/source/", "/mnt", context)

        assert result.success is True

        # Should have reported progress
        assert len(progress_calls) > 0

        # Progress should be scaled to 5-90% range
        percentages = [p[0] for p in progress_calls]
        assert all(5 <= p <= 90 for p in percentages)


class TestExtractSquashfs:
    """Tests for _extract_squashfs() method."""

    @patch("omnis.jobs.install.subprocess.Popen")
    def test_extract_squashfs_success(self, mock_popen: MagicMock) -> None:
        """_extract_squashfs should execute unsquashfs successfully."""
        job = InstallJob()

        mock_process = MagicMock()
        mock_process.stdout = [
            "Parallel unsquashfs: Using 4 processors\n",
            "1234 inodes (5678 blocks) to write\n",
        ]
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        context = JobContext()
        result = job._extract_squashfs("/test.sfs", "/mnt", context)

        assert result.success is True
        assert "extracted successfully" in result.message.lower()

        # Verify command structure
        call_args = mock_popen.call_args[0][0]
        assert "unsquashfs" in call_args
        assert "-f" in call_args  # Force overwrite
        assert "-d" in call_args  # Destination
        assert "/mnt" in call_args
        assert "/test.sfs" in call_args

    @patch("omnis.jobs.install.subprocess.Popen")
    def test_extract_squashfs_failure(self, mock_popen: MagicMock) -> None:
        """_extract_squashfs should handle unsquashfs failure."""
        job = InstallJob()

        mock_process = MagicMock()
        mock_process.stdout = []
        mock_process.wait.return_value = 1  # Non-zero exit
        mock_popen.return_value = mock_process

        context = JobContext()
        result = job._extract_squashfs("/test.sfs", "/mnt", context)

        assert result.success is False
        assert result.error_code == 67
        assert "unsquashfs failed" in result.message

    @patch("omnis.jobs.install.subprocess.Popen")
    def test_extract_squashfs_tool_not_found(self, mock_popen: MagicMock) -> None:
        """_extract_squashfs should handle missing unsquashfs tool."""
        job = InstallJob()

        mock_popen.side_effect = FileNotFoundError()

        context = JobContext()
        result = job._extract_squashfs("/test.sfs", "/mnt", context)

        assert result.success is False
        assert result.error_code == 54
        assert "unsquashfs command not found" in result.message


class TestVerifyInstallation:
    """Tests for _verify_installation() method."""

    @patch("omnis.jobs.install.Path")
    def test_verify_installation_success(self, mock_path: MagicMock) -> None:
        """_verify_installation should succeed when all critical files exist."""
        job = InstallJob()

        # Mock all critical files exist
        mock_target = MagicMock()

        def mock_file_exists(_file_path: str) -> MagicMock:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            return mock_file

        mock_target.__truediv__ = lambda _self, other: mock_file_exists(other)
        mock_path.return_value = mock_target

        result = job._verify_installation("/mnt")

        assert result.success is True
        assert "verified successfully" in result.message.lower()
        assert result.data["checks_passed"] == len(job.CRITICAL_FILES)

    @patch("omnis.jobs.install.Path")
    def test_verify_installation_missing_files(self, mock_path: MagicMock) -> None:
        """_verify_installation should fail when critical files are missing."""
        job = InstallJob()

        # Mock some files missing
        mock_target = MagicMock()

        def mock_file_exists(file_path: str) -> MagicMock:
            mock_file = MagicMock()
            # Make /etc/fstab missing
            mock_file.exists.return_value = "fstab" not in str(file_path)
            return mock_file

        mock_target.__truediv__ = lambda _self, other: mock_file_exists(other)
        mock_path.return_value = mock_target

        result = job._verify_installation("/mnt")

        assert result.success is False
        assert result.error_code == 69
        assert "verification failed" in result.message.lower()
        assert "missing_files" in result.data


class TestRun:
    """Tests for the run() method integration."""

    @patch("omnis.jobs.install.InstallJob._run_rsync")
    def test_run_live_install_success(self, mock_rsync: MagicMock) -> None:
        """run should execute live install successfully."""
        job = InstallJob()

        mock_rsync.return_value = JobResult.ok("Files copied", data={"bytes_copied": 1000000})

        context = JobContext(
            target_root="/mnt",
            selections={
                "source": "/",
                "source_type": "live",
            },
        )

        result = job.run(context)

        assert result.success is True
        assert "copied successfully" in result.message.lower()
        assert result.data["source"] == "/"
        assert result.data["target"] == "/mnt"

        mock_rsync.assert_called_once()

    @patch("omnis.jobs.install.InstallJob._verify_installation")
    @patch("omnis.jobs.install.InstallJob._run_rsync")
    def test_run_with_verification(self, mock_rsync: MagicMock, mock_verify: MagicMock) -> None:
        """run should verify installation if requested."""
        job = InstallJob()

        mock_rsync.return_value = JobResult.ok("Files copied")
        mock_verify.return_value = JobResult.ok("Verified")

        context = JobContext(
            target_root="/mnt",
            selections={
                "source": "/",
                "source_type": "live",
                "verify_install": True,
            },
        )

        result = job.run(context)

        assert result.success is True
        assert result.data["verified"] is True

        mock_rsync.assert_called_once()
        mock_verify.assert_called_once_with("/mnt")

    @patch("omnis.jobs.install.InstallJob._extract_squashfs")
    def test_run_squashfs_install(self, mock_extract: MagicMock) -> None:
        """run should handle squashfs installation."""
        job = InstallJob()

        mock_extract.return_value = JobResult.ok("Extracted")

        context = JobContext(
            target_root="/mnt",
            selections={
                "source_type": "squashfs",
                "squashfs_path": "/test.sfs",
            },
        )

        result = job.run(context)

        assert result.success is True

        mock_extract.assert_called_once_with("/test.sfs", "/mnt", context)

    @patch("omnis.jobs.install.InstallJob._extract_squashfs")
    def test_run_squashfs_missing_path(self, mock_extract: MagicMock) -> None:
        """run should fail if squashfs_path not provided."""
        job = InstallJob()

        context = JobContext(
            selections={
                "source_type": "squashfs",
                # Missing squashfs_path
            }
        )

        result = job.run(context)

        assert result.success is False
        assert result.error_code == 50

        mock_extract.assert_not_called()

    @patch("omnis.jobs.install.InstallJob._run_rsync")
    def test_run_propagates_errors(self, mock_rsync: MagicMock) -> None:
        """run should propagate errors from rsync."""
        job = InstallJob()

        mock_rsync.return_value = JobResult.fail("rsync failed", error_code=64)

        context = JobContext(
            selections={
                "source": "/",
                "source_type": "live",
            }
        )

        result = job.run(context)

        assert result.success is False
        assert result.error_code == 64

    @patch("omnis.jobs.install.InstallJob._verify_installation")
    @patch("omnis.jobs.install.InstallJob._run_rsync")
    def test_run_verification_failure(self, mock_rsync: MagicMock, mock_verify: MagicMock) -> None:
        """run should fail if verification fails."""
        job = InstallJob()

        mock_rsync.return_value = JobResult.ok("Files copied")
        mock_verify.return_value = JobResult.fail("Verification failed", error_code=69)

        context = JobContext(
            selections={
                "source": "/",
                "source_type": "live",
                "verify_install": True,
            }
        )

        result = job.run(context)

        assert result.success is False
        assert result.error_code == 69


class TestCleanup:
    """Tests for cleanup() method."""

    def test_cleanup_no_action(self) -> None:
        """cleanup should complete without errors."""
        job = InstallJob()
        context = JobContext()

        # Should not raise exception
        job.cleanup(context)
