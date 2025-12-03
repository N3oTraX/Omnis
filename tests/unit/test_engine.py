"""Unit tests for Omnis Engine."""

from pathlib import Path

import pytest

from omnis.core.engine import Engine, OmnisConfig, ConfigurationError


class TestOmnisConfig:
    """Tests for configuration loading."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = OmnisConfig()
        assert config.version == "1.0"
        assert config.branding.name == "Linux"
        assert config.jobs == []

    def test_normalize_jobs_strings(self) -> None:
        """Test job normalization from strings."""
        config = OmnisConfig(jobs=["welcome", "locale", "install"])
        normalized = config.normalize_jobs()

        assert len(normalized) == 3
        assert normalized[0].name == "welcome"
        assert normalized[1].name == "locale"
        assert normalized[2].name == "install"


class TestEngine:
    """Tests for Engine class."""

    def test_config_file_not_found(self) -> None:
        """Test error when config file doesn't exist."""
        with pytest.raises(ConfigurationError, match="not found"):
            Engine.from_config_file("/nonexistent/path.yaml")

    def test_get_job_names(self, tmp_path: Path) -> None:
        """Test retrieving job names."""
        config_file = tmp_path / "test.yaml"
        config_file.write_text("""
version: "1.0"
branding:
  name: "Test OS"
jobs:
  - welcome
  - install
""")

        engine = Engine.from_config_file(config_file)
        names = engine.get_job_names()

        assert names == ["welcome", "install"]

    def test_branding_loaded(self, tmp_path: Path) -> None:
        """Test branding configuration loading."""
        config_file = tmp_path / "test.yaml"
        config_file.write_text("""
version: "1.0"
branding:
  name: "Custom OS"
  version: "1.0.0"
  colors:
    primary: "#FF0000"
jobs: []
""")

        engine = Engine.from_config_file(config_file)
        branding = engine.get_branding()

        assert branding.name == "Custom OS"
        assert branding.version == "1.0.0"
        assert branding.colors.primary == "#FF0000"
