"""Unit tests for UsersJob."""

from pathlib import Path
from unittest.mock import MagicMock, call, mock_open, patch

import pytest

try:
    from omnis.jobs.base import JobContext, JobResult, JobStatus
    from omnis.jobs.users import UsersJob

    HAS_USERS_JOB = True
except ImportError:
    HAS_USERS_JOB = False

# Skip entire module if omnis is not available
pytestmark = pytest.mark.skipif(not HAS_USERS_JOB, reason="UsersJob not available")


class TestUsersJob:
    """Tests for UsersJob implementation."""

    def test_init_defaults(self) -> None:
        """UsersJob should have correct defaults."""
        job = UsersJob()
        assert job.name == "users"
        assert job.description == "User account and hostname configuration"
        assert job.status == JobStatus.PENDING

    def test_estimate_duration(self) -> None:
        """estimate_duration should return reasonable value."""
        job = UsersJob()
        duration = job.estimate_duration()
        assert duration == 10


class TestUsernameValidation:
    """Tests for username validation logic."""

    def test_valid_usernames(self) -> None:
        """Valid usernames should pass validation."""
        job = UsersJob()

        valid_usernames = [
            "john",
            "john_doe",
            "john-doe",
            "john123",
            "_system",
            "a",
            "user_name_123",
        ]

        for username in valid_usernames:
            assert job._validate_username(username), f"'{username}' should be valid"

    def test_invalid_usernames(self) -> None:
        """Invalid usernames should fail validation."""
        job = UsersJob()

        invalid_usernames = [
            "",  # empty
            "John",  # uppercase
            "123user",  # starts with digit
            "-user",  # starts with hyphen
            "user name",  # contains space
            "user@name",  # invalid character
            "a" * 33,  # too long (>32 chars)
            "User",  # uppercase
        ]

        for username in invalid_usernames:
            assert not job._validate_username(username), f"'{username}' should be invalid"


class TestHostnameValidation:
    """Tests for hostname validation logic."""

    def test_valid_hostnames(self) -> None:
        """Valid hostnames should pass validation."""
        job = UsersJob()

        valid_hostnames = [
            "localhost",
            "my-computer",
            "server01",
            "web-server-123",
            "a",
            "srv",
        ]

        for hostname in valid_hostnames:
            assert job._validate_hostname(hostname), f"'{hostname}' should be valid"

    def test_invalid_hostnames(self) -> None:
        """Invalid hostnames should fail validation."""
        job = UsersJob()

        invalid_hostnames = [
            "",  # empty
            "-hostname",  # starts with hyphen
            "hostname-",  # ends with hyphen
            "host name",  # contains space
            "HOST",  # uppercase
            "host_name",  # underscore not allowed
            "a" * 254,  # too long (>253 chars)
            "a" * 64,  # label too long (>63 chars)
        ]

        for hostname in invalid_hostnames:
            assert not job._validate_hostname(hostname), f"'{hostname}' should be invalid"


class TestValidateMethod:
    """Tests for the validate() method."""

    def test_validate_missing_username(self) -> None:
        """validate should fail if username is missing."""
        job = UsersJob()
        context = JobContext(
            selections={
                "password": "secret123",
            }
        )

        result = job.validate(context)

        assert result.success is False
        assert result.error_code == 10
        assert "Username is required" in result.message

    def test_validate_invalid_username(self) -> None:
        """validate should fail if username is invalid."""
        job = UsersJob()
        context = JobContext(
            selections={
                "username": "InvalidUser",  # uppercase
                "password": "secret123",
            }
        )

        result = job.validate(context)

        assert result.success is False
        assert result.error_code == 11
        assert "Invalid username" in result.message

    def test_validate_missing_password(self) -> None:
        """validate should fail if password is missing."""
        job = UsersJob()
        context = JobContext(
            selections={
                "username": "john",
                "password": "",  # empty
            }
        )

        result = job.validate(context)

        assert result.success is False
        assert result.error_code == 12
        assert "Password is required" in result.message

    def test_validate_invalid_hostname(self) -> None:
        """validate should fail if hostname is invalid."""
        job = UsersJob()
        context = JobContext(
            selections={
                "username": "john",
                "password": "secret123",
                "hostname": "-invalid",  # starts with hyphen
            }
        )

        result = job.validate(context)

        assert result.success is False
        assert result.error_code == 13
        assert "Invalid hostname" in result.message

    def test_validate_success(self) -> None:
        """validate should succeed with valid configuration."""
        job = UsersJob()
        context = JobContext(
            selections={
                "username": "john",
                "password": "secret123",
                "hostname": "mypc",
            }
        )

        result = job.validate(context)

        assert result.success is True
        assert "valid" in result.message.lower()


class TestCreateUser:
    """Tests for _create_user() method."""

    @patch("omnis.jobs.users.subprocess.run")
    @patch("omnis.jobs.users.Path")
    def test_create_user_success(self, mock_path: MagicMock, mock_subprocess: MagicMock) -> None:
        """_create_user should execute useradd command correctly."""
        job = UsersJob()

        # Mock group file to check for wheel/sudo groups
        mock_group_file = MagicMock()
        mock_group_file.exists.return_value = True
        mock_group_file.read_text.return_value = "wheel:x:998:\n"
        mock_path.return_value.__truediv__.return_value = mock_group_file

        # Mock subprocess success
        mock_subprocess.return_value = MagicMock(returncode=0)

        result = job._create_user(
            target_root="/mnt",
            username="john",
            fullname="John Doe",
            shell="/bin/bash",
            is_admin=True,
        )

        assert result.success is True
        mock_subprocess.assert_called_once()

        # Verify command structure
        cmd = mock_subprocess.call_args[0][0]
        assert "arch-chroot" in cmd
        assert "/mnt" in cmd
        assert "useradd" in cmd
        assert "-m" in cmd  # create home
        assert "john" in cmd
        assert "/bin/bash" in cmd

    @patch("omnis.jobs.users.subprocess.run")
    @patch("omnis.jobs.users.Path")
    def test_create_user_with_fullname(
        self, mock_path: MagicMock, mock_subprocess: MagicMock
    ) -> None:
        """_create_user should include GECOS field if fullname provided."""
        job = UsersJob()

        mock_group_file = MagicMock()
        mock_group_file.exists.return_value = True
        mock_group_file.read_text.return_value = "wheel:x:998:\n"
        mock_path.return_value.__truediv__.return_value = mock_group_file

        mock_subprocess.return_value = MagicMock(returncode=0)

        result = job._create_user(
            target_root="/mnt",
            username="john",
            fullname="John Doe",
            shell="/bin/bash",
            is_admin=False,
        )

        assert result.success is True

        # Verify GECOS field is included
        cmd = mock_subprocess.call_args[0][0]
        assert "-c" in cmd
        assert "John Doe" in cmd

    @patch("omnis.jobs.users.subprocess.run")
    @patch("omnis.jobs.users.Path")
    def test_create_user_admin_groups(
        self, mock_path: MagicMock, mock_subprocess: MagicMock
    ) -> None:
        """_create_user should add wheel group for admin users."""
        job = UsersJob()

        mock_group_file = MagicMock()
        mock_group_file.exists.return_value = True
        mock_group_file.read_text.return_value = "wheel:x:998:\n"
        mock_path.return_value.__truediv__.return_value = mock_group_file

        mock_subprocess.return_value = MagicMock(returncode=0)

        result = job._create_user(
            target_root="/mnt",
            username="admin",
            fullname="",
            shell="/bin/bash",
            is_admin=True,
        )

        assert result.success is True

        # Verify wheel group is in groups
        cmd = mock_subprocess.call_args[0][0]
        groups_idx = cmd.index("-G") + 1
        groups = cmd[groups_idx]
        assert "wheel" in groups

    @patch("omnis.jobs.users.subprocess.run")
    @patch("omnis.jobs.users.Path")
    def test_create_user_failure(self, mock_path: MagicMock, mock_subprocess: MagicMock) -> None:
        """_create_user should handle subprocess failures."""
        import subprocess

        job = UsersJob()

        mock_group_file = MagicMock()
        mock_group_file.exists.return_value = True
        mock_group_file.read_text.return_value = "wheel:x:998:\n"
        mock_path.return_value.__truediv__.return_value = mock_group_file

        # Simulate useradd failure with CalledProcessError
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["useradd"], stderr="User already exists"
        )

        result = job._create_user(
            target_root="/mnt",
            username="john",
            fullname="",
            shell="/bin/bash",
            is_admin=False,
        )

        assert result.success is False


class TestSetPassword:
    """Tests for _set_password() method."""

    @patch("omnis.jobs.users.subprocess.run")
    def test_set_password_success(self, mock_subprocess: MagicMock) -> None:
        """_set_password should use chpasswd with stdin."""
        job = UsersJob()

        mock_subprocess.return_value = MagicMock(returncode=0)

        result = job._set_password(
            target_root="/mnt",
            username="john",
            password="secret123",
        )

        assert result.success is True
        mock_subprocess.assert_called_once()

        # Verify chpasswd is called
        cmd = mock_subprocess.call_args[0][0]
        assert "arch-chroot" in cmd
        assert "/mnt" in cmd
        assert "chpasswd" in cmd

        # Verify password is passed via stdin (not command line)
        kwargs = mock_subprocess.call_args[1]
        assert kwargs.get("input") == "john:secret123"
        assert kwargs.get("text") is True

    @patch("omnis.jobs.users.subprocess.run")
    def test_set_password_never_logged(
        self, mock_subprocess: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """SECURITY: _set_password should never log the password."""
        job = UsersJob()

        mock_subprocess.return_value = MagicMock(returncode=0)

        # Set a distinctive password
        test_password = "SuperSecretPassword123!"

        result = job._set_password(
            target_root="/mnt",
            username="john",
            password=test_password,
        )

        assert result.success is True

        # CRITICAL: Verify password is NOT in any log messages
        for record in caplog.records:
            assert test_password not in record.message, "Password found in log!"
            assert test_password not in str(record.args), "Password found in log args!"

    @patch("omnis.jobs.users.subprocess.run")
    def test_set_password_failure_no_leak(
        self, mock_subprocess: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """SECURITY: _set_password should not leak password on error."""
        job = UsersJob()

        test_password = "SuperSecretPassword123!"

        # Simulate chpasswd failure
        import subprocess

        mock_subprocess.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["chpasswd"], stderr="chpasswd failed"
        )

        result = job._set_password(
            target_root="/mnt",
            username="john",
            password=test_password,
        )

        assert result.success is False

        # CRITICAL: Verify password is NOT in error messages or logs
        assert test_password not in result.message
        for record in caplog.records:
            assert test_password not in record.message
            assert test_password not in str(record.args)


class TestSetHostname:
    """Tests for _set_hostname() method."""

    def test_set_hostname_success(self) -> None:
        """_set_hostname should write /etc/hostname and /etc/hosts."""
        import tempfile

        job = UsersJob()

        # Use a temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create /etc directory
            etc_dir = Path(tmpdir) / "etc"
            etc_dir.mkdir()

            result = job._set_hostname(tmpdir, "mypc")

            assert result.success is True

            # Verify /etc/hostname was written
            hostname_file = etc_dir / "hostname"
            assert hostname_file.exists()
            hostname_content = hostname_file.read_text()
            assert "mypc" in hostname_content

            # Verify /etc/hosts was written
            hosts_file = etc_dir / "hosts"
            assert hosts_file.exists()
            hosts_content = hosts_file.read_text()
            assert "mypc" in hosts_content
            assert "127.0.1.1" in hosts_content

    @patch("omnis.jobs.users.Path")
    def test_set_hostname_failure(self, mock_path_class: MagicMock) -> None:
        """_set_hostname should handle file write errors."""
        job = UsersJob()

        # Create a mock for the hostname file that raises OSError on write_text
        mock_hostname_file = MagicMock()
        mock_hostname_file.write_text.side_effect = OSError("Permission denied")

        # Mock the Path chain: Path(target_root) / "etc" / "hostname"
        mock_root = MagicMock()
        mock_etc = MagicMock()
        mock_etc.__truediv__.return_value = mock_hostname_file
        mock_root.__truediv__.return_value = mock_etc
        mock_path_class.return_value = mock_root

        result = job._set_hostname("/mnt", "mypc")

        assert result.success is False
        assert result.error_code == 24


class TestRunMethod:
    """Tests for the run() method."""

    @patch("omnis.jobs.users.UsersJob._set_hostname")
    @patch("omnis.jobs.users.UsersJob._set_password")
    @patch("omnis.jobs.users.UsersJob._create_user")
    def test_run_success_full_workflow(
        self,
        mock_create: MagicMock,
        mock_password: MagicMock,
        mock_hostname: MagicMock,
    ) -> None:
        """run should execute full workflow successfully."""
        job = UsersJob()

        # Mock all operations as successful
        mock_create.return_value = JobResult.ok("User created")
        mock_password.return_value = JobResult.ok("Password set")
        mock_hostname.return_value = JobResult.ok("Hostname set")

        context = JobContext(
            target_root="/mnt",
            selections={
                "username": "john",
                "password": "secret123",
                "fullname": "John Doe",
                "is_admin": True,
                "hostname": "mypc",
                "shell": "/bin/bash",
            },
        )
        context.on_progress = MagicMock()

        result = job.run(context)

        assert result.success is True
        assert "john" in result.message

        # Verify all steps were called
        mock_create.assert_called_once()
        mock_password.assert_called_once()
        mock_hostname.assert_called_once()

        # Verify progress was reported
        assert context.on_progress.call_count >= 4

    @patch("omnis.jobs.users.UsersJob._create_user")
    def test_run_create_user_failure(self, mock_create: MagicMock) -> None:
        """run should stop if user creation fails."""
        job = UsersJob()

        # Simulate user creation failure
        mock_create.return_value = JobResult.fail("User creation failed", error_code=22)

        context = JobContext(
            selections={
                "username": "john",
                "password": "secret123",
            }
        )

        result = job.run(context)

        assert result.success is False
        assert result.error_code == 22

    @patch("omnis.jobs.users.UsersJob._set_password")
    @patch("omnis.jobs.users.UsersJob._create_user")
    def test_run_password_failure(self, mock_create: MagicMock, mock_password: MagicMock) -> None:
        """run should stop if password setting fails."""
        job = UsersJob()

        mock_create.return_value = JobResult.ok("User created")
        mock_password.return_value = JobResult.fail("Password failed", error_code=23)

        context = JobContext(
            selections={
                "username": "john",
                "password": "secret123",
            }
        )

        result = job.run(context)

        assert result.success is False
        assert result.error_code == 23

    @patch("omnis.jobs.users.UsersJob._set_password")
    @patch("omnis.jobs.users.UsersJob._create_user")
    def test_run_without_hostname(self, mock_create: MagicMock, mock_password: MagicMock) -> None:
        """run should skip hostname if not provided."""
        job = UsersJob()

        mock_create.return_value = JobResult.ok("User created")
        mock_password.return_value = JobResult.ok("Password set")

        context = JobContext(
            selections={
                "username": "john",
                "password": "secret123",
                # No hostname provided
            }
        )

        result = job.run(context)

        assert result.success is True
        assert result.data["hostname"] == "not_set"

    def test_run_validation_failure(self) -> None:
        """run should fail if validation fails."""
        job = UsersJob()

        context = JobContext(
            selections={
                "username": "InvalidUser",  # uppercase - invalid
                "password": "secret123",
            }
        )

        result = job.run(context)

        assert result.success is False
        assert result.error_code == 11  # validation error code
