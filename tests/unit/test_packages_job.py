"""Unit tests for PackagesJob."""

import tempfile
from unittest.mock import MagicMock, Mock, patch

import pytest

try:
    from omnis.jobs.base import JobContext, JobResult, JobStatus
    from omnis.jobs.packages import PackagesJob

    HAS_PACKAGES_JOB = True
except ImportError:
    HAS_PACKAGES_JOB = False

# Skip entire module if omnis packages job is not available
pytestmark = pytest.mark.skipif(not HAS_PACKAGES_JOB, reason="PackagesJob not available")


# =============================================================================
# PackagesJob Initialization Tests
# =============================================================================


class TestPackagesJobInit:
    """Tests for PackagesJob initialization."""

    def test_init_defaults(self) -> None:
        """PackagesJob should have correct defaults."""
        job = PackagesJob()
        assert job.name == "packages"
        assert job.description == "System package installation"
        assert job.status == JobStatus.PENDING
        assert job._packages_installed == []
        assert job._packages_failed == []

    def test_init_with_config(self) -> None:
        """PackagesJob should accept configuration."""
        config = {"mode": "desktop"}
        job = PackagesJob(config)
        assert job._config == config

    def test_constants_defined(self) -> None:
        """PackagesJob should define necessary constants."""
        assert PackagesJob.MODE_ESSENTIAL == "essential"
        assert PackagesJob.MODE_DESKTOP == "desktop"
        assert PackagesJob.MODE_CUSTOM == "custom"
        assert len(PackagesJob.ESSENTIAL_PACKAGES) > 0
        assert len(PackagesJob.DESKTOP_PACKAGES) > 0
        assert "pacman" in PackagesJob.SUPPORTED_PACKAGE_MANAGERS


# =============================================================================
# Package List Building Tests
# =============================================================================


class TestGetPackageList:
    """Tests for package list building."""

    def test_get_package_list_essential(self) -> None:
        """Should return essential packages for essential mode."""
        job = PackagesJob()
        context = JobContext(selections={"mode": "essential"})

        packages = job._get_package_list(context)

        assert packages == PackagesJob.ESSENTIAL_PACKAGES
        assert "base" in packages
        assert "linux" in packages

    def test_get_package_list_desktop(self) -> None:
        """Should return combined packages for desktop mode."""
        job = PackagesJob()
        context = JobContext(selections={"mode": "desktop"})

        packages = job._get_package_list(context)

        # Should contain both essential and desktop packages
        assert all(pkg in packages for pkg in PackagesJob.ESSENTIAL_PACKAGES)
        assert all(pkg in packages for pkg in PackagesJob.DESKTOP_PACKAGES)
        assert len(packages) > len(PackagesJob.ESSENTIAL_PACKAGES)

    def test_get_package_list_custom(self) -> None:
        """Should return custom packages for custom mode."""
        job = PackagesJob()
        custom_pkgs = ["vim", "git", "htop"]
        context = JobContext(
            selections={
                "mode": "custom",
                "packages": custom_pkgs,
            }
        )

        packages = job._get_package_list(context)

        assert packages == custom_pkgs

    def test_get_package_list_custom_empty(self) -> None:
        """Should fallback to essential if custom mode has no packages."""
        job = PackagesJob()
        context = JobContext(
            selections={
                "mode": "custom",
                "packages": [],
            }
        )

        packages = job._get_package_list(context)

        assert packages == PackagesJob.ESSENTIAL_PACKAGES

    def test_get_package_list_default(self) -> None:
        """Should default to essential mode if not specified."""
        job = PackagesJob()
        context = JobContext()

        packages = job._get_package_list(context)

        assert packages == PackagesJob.ESSENTIAL_PACKAGES


# =============================================================================
# Package Name Validation Tests
# =============================================================================


class TestValidatePackageNames:
    """Tests for package name validation."""

    def test_validate_valid_packages(self) -> None:
        """Valid package names should pass validation."""
        job = PackagesJob()

        result = job._validate_package_names(["vim", "git", "htop"])
        assert result.success is True

        result = job._validate_package_names(["python-pip", "gcc-libs"])
        assert result.success is True

        result = job._validate_package_names(["lib32-gcc-libs"])
        assert result.success is True

    def test_validate_empty_list(self) -> None:
        """Empty package list should fail validation."""
        job = PackagesJob()

        result = job._validate_package_names([])

        assert result.success is False
        assert result.error_code == 30

    def test_validate_invalid_characters(self) -> None:
        """Package names with invalid characters should fail."""
        job = PackagesJob()

        result = job._validate_package_names(["vim!", "git@", "htop#"])

        assert result.success is False
        assert result.error_code == 31
        assert "invalid_packages" in result.data

    def test_validate_empty_package_name(self) -> None:
        """Empty package names should fail validation."""
        job = PackagesJob()

        result = job._validate_package_names(["vim", "", "git"])

        assert result.success is False
        assert result.error_code == 31


# =============================================================================
# Repository Update Tests
# =============================================================================


class TestUpdateRepositories:
    """Tests for repository update operations."""

    @patch("subprocess.run")
    def test_update_repositories_pacman_success(self, mock_run: Mock) -> None:
        """Should successfully update pacman repositories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_run.return_value = Mock(stdout="", stderr="")

            job = PackagesJob()
            context = JobContext(
                target_root=tmpdir,
                selections={"package_manager": "pacman"},
            )

            result = job._update_repositories(context)

            assert result.success is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "pacman" in call_args
            assert "-Syy" in call_args

    @patch("subprocess.run")
    def test_update_repositories_apt_success(self, mock_run: Mock) -> None:
        """Should successfully update apt repositories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_run.return_value = Mock(stdout="", stderr="")

            job = PackagesJob()
            context = JobContext(
                target_root=tmpdir,
                selections={"package_manager": "apt"},
            )

            result = job._update_repositories(context)

            assert result.success is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "apt-get" in call_args
            assert "update" in call_args

    @patch("subprocess.run")
    def test_update_repositories_failure(self, mock_run: Mock) -> None:
        """Should handle repository update failures."""
        import subprocess

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "pacman", stderr="Repository error"
            )

            job = PackagesJob()
            context = JobContext(target_root=tmpdir)

            result = job._update_repositories(context)

            assert result.success is False
            assert result.error_code == 33

    @patch("subprocess.run")
    def test_update_repositories_timeout(self, mock_run: Mock) -> None:
        """Should handle repository update timeout."""
        import subprocess

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_run.side_effect = subprocess.TimeoutExpired("pacman", 300)

            job = PackagesJob()
            context = JobContext(target_root=tmpdir)

            result = job._update_repositories(context)

            assert result.success is False
            assert result.error_code == 34

    def test_update_repositories_unsupported_manager(self) -> None:
        """Should fail with unsupported package manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job = PackagesJob()
            context = JobContext(
                target_root=tmpdir,
                selections={"package_manager": "yum"},
            )

            result = job._update_repositories(context)

            assert result.success is False
            assert result.error_code == 32


# =============================================================================
# Package Installation Tests
# =============================================================================


class TestInstallPackages:
    """Tests for package installation operations."""

    @patch("subprocess.Popen")
    def test_install_packages_pacman_success(self, mock_popen: Mock) -> None:
        """Should successfully install packages with pacman."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock process output
            mock_process = Mock()
            mock_process.stdout = iter(
                [
                    "installing base-1.0\n",
                    "installing linux-6.0\n",
                    "installing vim-9.0\n",
                ]
            )
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            job = PackagesJob()
            packages = ["base", "linux", "vim"]
            context = JobContext(target_root=tmpdir)
            context.on_progress = MagicMock()

            result = job._install_packages_pacman(packages, tmpdir, context)

            assert result.success is True
            assert job._packages_installed == packages
            mock_popen.assert_called_once()

    @patch("subprocess.Popen")
    def test_install_packages_pacman_failure(self, mock_popen: Mock) -> None:
        """Should handle pacman installation failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_process = Mock()
            mock_process.stdout = iter(["error: failed to install\n"])
            mock_process.wait.return_value = 1
            mock_popen.return_value = mock_process

            job = PackagesJob()
            packages = ["nonexistent"]
            context = JobContext(target_root=tmpdir)

            result = job._install_packages_pacman(packages, tmpdir, context)

            assert result.success is False
            assert result.error_code == 36

    @patch("subprocess.Popen")
    def test_install_packages_apt_success(self, mock_popen: Mock) -> None:
        """Should successfully install packages with apt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_process = Mock()
            mock_process.stdout = iter(
                [
                    "Setting up vim (1.0)\n",
                    "Setting up git (2.0)\n",
                ]
            )
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            job = PackagesJob()
            packages = ["vim", "git"]
            context = JobContext(target_root=tmpdir)
            context.on_progress = MagicMock()

            result = job._install_packages_apt(packages, tmpdir, context)

            assert result.success is True
            assert job._packages_installed == packages


# =============================================================================
# Retry Logic Tests
# =============================================================================


class TestInstallWithRetry:
    """Tests for installation retry logic."""

    @patch.object(PackagesJob, "_install_packages_pacman")
    def test_install_retry_success_first_attempt(self, mock_install: Mock) -> None:
        """Should succeed on first attempt without retry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_install.return_value = JobResult.ok("Installed")

            job = PackagesJob()
            context = JobContext(target_root=tmpdir)
            packages = ["vim", "git"]

            result = job._install_packages_with_retry(packages, context)

            assert result.success is True
            assert mock_install.call_count == 1

    @patch.object(PackagesJob, "_install_packages_pacman")
    @patch("time.sleep")
    def test_install_retry_success_after_retry(self, mock_sleep: Mock, mock_install: Mock) -> None:
        """Should succeed after retry on network failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # First attempt fails, second succeeds
            mock_install.side_effect = [
                JobResult.fail("Network error", error_code=33),
                JobResult.ok("Installed"),
            ]

            job = PackagesJob()
            context = JobContext(target_root=tmpdir)
            context.on_progress = MagicMock()
            packages = ["vim"]

            result = job._install_packages_with_retry(packages, context)

            assert result.success is True
            assert mock_install.call_count == 2
            mock_sleep.assert_called_once_with(PackagesJob.RETRY_DELAY)

    @patch.object(PackagesJob, "_install_packages_pacman")
    @patch("time.sleep")
    def test_install_retry_max_attempts(self, _mock_sleep: Mock, mock_install: Mock) -> None:
        """Should fail after max retries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_install.return_value = JobResult.fail("Network error", error_code=33)

            job = PackagesJob()
            context = JobContext(target_root=tmpdir)
            context.on_progress = MagicMock()
            packages = ["vim"]

            result = job._install_packages_with_retry(packages, context)

            assert result.success is False
            assert result.error_code == 39
            assert mock_install.call_count == PackagesJob.MAX_RETRIES

    @patch.object(PackagesJob, "_install_packages_pacman")
    def test_install_retry_non_network_error(self, mock_install: Mock) -> None:
        """Should not retry for non-network errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_install.return_value = JobResult.fail("Invalid package", error_code=31)

            job = PackagesJob()
            context = JobContext(target_root=tmpdir)
            packages = ["invalid!"]

            result = job._install_packages_with_retry(packages, context)

            assert result.success is False
            assert result.error_code == 31
            assert mock_install.call_count == 1  # No retry


# =============================================================================
# Validation Tests
# =============================================================================


class TestPackagesJobValidate:
    """Tests for JobContext validation."""

    def test_validate_all_valid(self) -> None:
        """Validate should pass with all valid selections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job = PackagesJob()
            context = JobContext(
                target_root=tmpdir,
                selections={
                    "package_manager": "pacman",
                    "mode": "essential",
                },
            )

            result = job.validate(context)

            assert result.success is True

    def test_validate_unsupported_package_manager(self) -> None:
        """Should fail with unsupported package manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job = PackagesJob()
            context = JobContext(
                target_root=tmpdir,
                selections={"package_manager": "yum"},
            )

            result = job.validate(context)

            assert result.success is False
            assert result.error_code == 40
            assert "package manager" in result.message.lower()

    def test_validate_invalid_mode(self) -> None:
        """Should fail with invalid installation mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job = PackagesJob()
            context = JobContext(
                target_root=tmpdir,
                selections={"mode": "invalid"},
            )

            result = job.validate(context)

            assert result.success is False
            assert "mode" in result.message.lower()

    def test_validate_custom_mode_no_packages(self) -> None:
        """Should fail if custom mode has no packages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job = PackagesJob()
            context = JobContext(
                target_root=tmpdir,
                selections={"mode": "custom"},
            )

            result = job.validate(context)

            assert result.success is False
            assert "packages" in result.message.lower()

    def test_validate_custom_mode_invalid_packages(self) -> None:
        """Should fail if custom packages are invalid."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job = PackagesJob()
            context = JobContext(
                target_root=tmpdir,
                selections={
                    "mode": "custom",
                    "packages": ["vim!", "git@"],
                },
            )

            result = job.validate(context)

            assert result.success is False

    def test_validate_target_not_exists(self) -> None:
        """Should fail if target directory does not exist."""
        job = PackagesJob()
        context = JobContext(target_root="/nonexistent/path")

        result = job.validate(context)

        assert result.success is False
        assert "target directory not found" in result.message.lower()

    def test_validate_multiple_errors(self) -> None:
        """Should report all validation errors."""
        job = PackagesJob()
        context = JobContext(
            target_root="/nonexistent",
            selections={
                "package_manager": "yum",
                "mode": "invalid",
            },
        )

        result = job.validate(context)

        assert result.success is False
        assert "errors" in result.data
        assert len(result.data["errors"]) >= 2


# =============================================================================
# Full Job Execution Tests
# =============================================================================


class TestPackagesJobRun:
    """Tests for full PackagesJob execution."""

    @patch.object(PackagesJob, "_install_packages_with_retry")
    @patch.object(PackagesJob, "_update_repositories")
    def test_run_essential_mode(self, mock_update: Mock, mock_install: Mock) -> None:
        """Should run successfully in essential mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_update.return_value = JobResult.ok("Updated")
            mock_install.return_value = JobResult.ok("Installed")

            job = PackagesJob()
            context = JobContext(
                target_root=tmpdir,
                selections={"mode": "essential"},
            )
            context.on_progress = MagicMock()

            result = job.run(context)

            assert result.success is True
            assert result.data["mode"] == "essential"
            assert "packages_installed" in result.data
            mock_update.assert_called_once()
            mock_install.assert_called_once()

    @patch.object(PackagesJob, "_install_packages_with_retry")
    @patch.object(PackagesJob, "_update_repositories")
    def test_run_desktop_mode(self, mock_update: Mock, mock_install: Mock) -> None:
        """Should run successfully in desktop mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_update.return_value = JobResult.ok("Updated")
            mock_install.return_value = JobResult.ok("Installed")

            job = PackagesJob()
            context = JobContext(
                target_root=tmpdir,
                selections={"mode": "desktop"},
            )
            context.on_progress = MagicMock()

            result = job.run(context)

            assert result.success is True
            assert result.data["mode"] == "desktop"

    @patch.object(PackagesJob, "_install_packages_with_retry")
    @patch.object(PackagesJob, "_update_repositories")
    def test_run_custom_mode(self, mock_update: Mock, mock_install: Mock) -> None:
        """Should run successfully in custom mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_update.return_value = JobResult.ok("Updated")
            mock_install.return_value = JobResult.ok("Installed")

            job = PackagesJob()
            custom_pkgs = ["vim", "git", "htop"]
            context = JobContext(
                target_root=tmpdir,
                selections={
                    "mode": "custom",
                    "packages": custom_pkgs,
                },
            )
            context.on_progress = MagicMock()

            result = job.run(context)

            assert result.success is True
            assert result.data["mode"] == "custom"

    @patch.object(PackagesJob, "_install_packages_with_retry")
    @patch.object(PackagesJob, "_update_repositories")
    def test_run_update_failure_continues(self, mock_update: Mock, mock_install: Mock) -> None:
        """Should continue installation if update fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_update.return_value = JobResult.fail("Update failed", error_code=33)
            mock_install.return_value = JobResult.ok("Installed")

            job = PackagesJob()
            context = JobContext(target_root=tmpdir)
            context.on_progress = MagicMock()

            result = job.run(context)

            # Should succeed despite update failure
            assert result.success is True
            mock_install.assert_called_once()

    @patch.object(PackagesJob, "_install_packages_with_retry")
    @patch.object(PackagesJob, "_update_repositories")
    def test_run_validation_fails(self, mock_update: Mock, mock_install: Mock) -> None:
        """Should fail if validation fails."""
        job = PackagesJob()
        context = JobContext(
            target_root="/nonexistent",
            selections={"mode": "essential"},
        )

        result = job.run(context)

        assert result.success is False
        mock_update.assert_not_called()
        mock_install.assert_not_called()

    @patch.object(PackagesJob, "_install_packages_with_retry")
    @patch.object(PackagesJob, "_update_repositories")
    def test_run_installation_fails(self, mock_update: Mock, mock_install: Mock) -> None:
        """Should fail if installation fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_update.return_value = JobResult.ok("Updated")
            mock_install.return_value = JobResult.fail("Installation failed", error_code=36)

            job = PackagesJob()
            context = JobContext(target_root=tmpdir)

            result = job.run(context)

            assert result.success is False
            assert result.error_code == 36

    def test_estimate_duration_essential(self) -> None:
        """Should return reasonable duration estimate for essential mode."""
        job = PackagesJob({"mode": "essential"})
        duration = job.estimate_duration()
        assert duration == 300

    def test_estimate_duration_desktop(self) -> None:
        """Should return longer duration for desktop mode."""
        job = PackagesJob({"mode": "desktop"})
        duration = job.estimate_duration()
        assert duration == 900

    def test_estimate_duration_custom(self) -> None:
        """Should estimate based on package count for custom mode."""
        job = PackagesJob({"mode": "custom", "packages": ["vim", "git", "htop"]})
        duration = job.estimate_duration()
        # Should be at least base estimate
        assert duration >= 300


# =============================================================================
# Integration Tests
# =============================================================================


class TestPackagesJobIntegration:
    """Integration tests for complete PackagesJob workflow."""

    @patch.object(PackagesJob, "_install_packages_with_retry")
    @patch.object(PackagesJob, "_update_repositories")
    def test_full_workflow_essential(self, mock_update: Mock, mock_install: Mock) -> None:
        """Test complete package installation workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_update.return_value = JobResult.ok("Updated")
            mock_install.return_value = JobResult.ok("Installed")

            # Create job
            job = PackagesJob({"mode": "essential"})

            # Prepare context
            context = JobContext(
                target_root=tmpdir,
                selections={
                    "package_manager": "pacman",
                    "mode": "essential",
                },
            )
            context.on_progress = MagicMock()

            # Validate first
            validation = job.validate(context)
            assert validation.success is True

            # Run the job
            result = job.run(context)
            assert result.success is True

            # Verify results
            assert result.data["mode"] == "essential"
            assert "packages_installed" in result.data
            assert context.on_progress.called

    def test_cleanup(self) -> None:
        """Test cleanup operation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job = PackagesJob()
            context = JobContext(target_root=tmpdir)

            # Should not raise any exceptions
            job.cleanup(context)
