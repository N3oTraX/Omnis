"""Unit tests for Omnis Engine."""

from pathlib import Path

import pytest

try:
    from omnis.core.engine import ConfigurationError, Engine, OmnisConfig

    HAS_OMNIS = True
except ImportError:
    HAS_OMNIS = False

# Skip entire module if omnis is not available
pytestmark = pytest.mark.skipif(not HAS_OMNIS, reason="omnis package not available")


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


class TestThemeOverlay:
    """Tests for the <theme_dir>/theme.yaml overlay onto inline branding."""

    @staticmethod
    def _write_theme(tmp_path: Path, theme_yaml: str) -> None:
        theme_dir = tmp_path / "themes" / "glfos"
        theme_dir.mkdir(parents=True)
        (theme_dir / "theme.yaml").write_text(theme_yaml)

    def test_theme_colors_override_inline_branding(self, tmp_path: Path) -> None:
        self._write_theme(
            tmp_path,
            """
colors:
  primary: "#222222"
  secondary: "#333333"
""",
        )
        config_file = tmp_path / "omnis.yaml"
        config_file.write_text("""
version: "1.0"
theme: "themes/glfos"
branding:
  name: "Inline OS"
  colors:
    primary: "#111111"
    text: "#ABCDEF"
jobs: []
""")
        branding = Engine.from_config_file(config_file).get_branding()
        assert branding.colors.primary == "#222222"  # theme wins
        assert branding.colors.secondary == "#333333"  # theme provides
        assert branding.colors.text == "#ABCDEF"  # inline kept (theme silent)
        assert branding.name == "Inline OS"  # no theme metadata

    def test_theme_metadata_maps_to_identity(self, tmp_path: Path) -> None:
        self._write_theme(
            tmp_path,
            """
metadata:
  name: "Theme OS"
  version: "2025.1"
  codename: "Omnislash"
colors:
  primary: "#222222"
""",
        )
        config_file = tmp_path / "omnis.yaml"
        config_file.write_text("""
version: "1.0"
theme: "themes/glfos"
branding:
  name: "Inline OS"
jobs: []
""")
        branding = Engine.from_config_file(config_file).get_branding()
        assert branding.name == "Theme OS"
        assert branding.version == "2025.1"
        assert branding.edition == "Omnislash"

    def test_theme_extra_color_keys_are_ignored(self, tmp_path: Path) -> None:
        self._write_theme(
            tmp_path,
            """
colors:
  primary: "#222222"
  success: "#010203"
""",
        )
        config_file = tmp_path / "omnis.yaml"
        config_file.write_text("""
version: "1.0"
theme: "themes/glfos"
branding:
  name: "Inline OS"
jobs: []
""")
        # Must not raise despite `success` not being a BrandingColors field.
        branding = Engine.from_config_file(config_file).get_branding()
        assert branding.colors.primary == "#222222"

    def test_missing_theme_yaml_uses_inline_branding(self, tmp_path: Path) -> None:
        config_file = tmp_path / "omnis.yaml"
        config_file.write_text("""
version: "1.0"
theme: "themes/absent"
branding:
  name: "Inline OS"
  colors:
    primary: "#111111"
jobs: []
""")
        branding = Engine.from_config_file(config_file).get_branding()
        assert branding.colors.primary == "#111111"
        assert branding.name == "Inline OS"
