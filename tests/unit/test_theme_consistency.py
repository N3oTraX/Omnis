"""
Tests for theme and configuration consistency.

Validates that module configurations correctly reference theme assets
and that all required assets exist.
"""

from pathlib import Path

import pytest

try:
    import yaml

    HAS_YAML = True
except ImportError:
    yaml = None  # type: ignore[assignment]
    HAS_YAML = False

try:
    from omnis.core.engine import Engine, OmnisConfig

    HAS_OMNIS = True
except ImportError:
    Engine = None  # type: ignore[assignment, misc]
    OmnisConfig = None  # type: ignore[assignment, misc]
    HAS_OMNIS = False

# Skip entire module if dependencies are missing
pytestmark = pytest.mark.skipif(
    not (HAS_YAML and HAS_OMNIS),
    reason="Required dependencies (yaml, omnis) not available",
)

# Path to config examples directory
EXAMPLES_DIR = Path(__file__).parent.parent.parent / "config" / "examples"
THEMES_DIR = Path(__file__).parent.parent.parent / "config" / "themes"


class TestThemeConsistency:
    """Tests for theme asset consistency."""

    @pytest.fixture
    def glfos_config_path(self) -> Path:
        """Path to GLF OS configuration."""
        return EXAMPLES_DIR / "glfos.yaml"

    @pytest.fixture
    def glfos_config(self, glfos_config_path: Path) -> OmnisConfig:
        """Load GLF OS configuration."""
        with glfos_config_path.open("r") as f:
            raw = yaml.safe_load(f)
        return OmnisConfig.model_validate(raw)

    @pytest.fixture
    def glfos_theme_base(self, glfos_config_path: Path, glfos_config: OmnisConfig) -> Path:
        """Resolve GLF OS theme base directory."""
        theme_path = glfos_config.theme
        if theme_path:
            return (glfos_config_path.parent / theme_path).resolve()
        return glfos_config_path.parent

    def test_glfos_config_exists(self, glfos_config_path: Path) -> None:
        """GLF OS config file should exist."""
        assert glfos_config_path.exists(), f"Config not found: {glfos_config_path}"

    def test_glfos_theme_directory_exists(self, glfos_theme_base: Path) -> None:
        """GLF OS theme directory should exist."""
        assert glfos_theme_base.exists(), f"Theme directory not found: {glfos_theme_base}"
        assert glfos_theme_base.is_dir(), f"Theme path is not a directory: {glfos_theme_base}"

    def test_glfos_theme_yaml_exists(self, glfos_theme_base: Path) -> None:
        """Theme should have a theme.yaml file."""
        theme_yaml = glfos_theme_base / "theme.yaml"
        assert theme_yaml.exists(), f"theme.yaml not found in {glfos_theme_base}"

    def test_glfos_logo_asset_exists(
        self, glfos_config: OmnisConfig, glfos_theme_base: Path
    ) -> None:
        """Logo asset referenced in config should exist."""
        logo_path = glfos_config.branding.assets.logo
        if logo_path:
            full_path = glfos_theme_base / logo_path
            assert full_path.exists(), f"Logo not found: {full_path}"

    def test_glfos_logo_small_asset_exists(
        self, glfos_config: OmnisConfig, glfos_theme_base: Path
    ) -> None:
        """Small logo asset referenced in config should exist."""
        logo_path = glfos_config.branding.assets.logo_small
        if logo_path:
            full_path = glfos_theme_base / logo_path
            assert full_path.exists(), f"Small logo not found: {full_path}"

    def test_glfos_background_asset_exists(
        self, glfos_config: OmnisConfig, glfos_theme_base: Path
    ) -> None:
        """Background asset referenced in config should exist."""
        bg_path = glfos_config.branding.assets.background
        if bg_path:
            full_path = glfos_theme_base / bg_path
            assert full_path.exists(), f"Background not found: {full_path}"

    def test_glfos_all_configured_assets_exist(
        self, glfos_config: OmnisConfig, glfos_theme_base: Path
    ) -> None:
        """All assets referenced in config should exist in theme directory."""
        assets = glfos_config.branding.assets
        asset_fields = [
            ("logo", assets.logo),
            ("logo_light", assets.logo_light),
            ("logo_small", assets.logo_small),
            ("logo_256", assets.logo_256),
            ("background", assets.background),
            ("background_alt", assets.background_alt),
            ("icon", assets.icon),
            ("bootloader", assets.bootloader),
            ("efi_icon", assets.efi_icon),
        ]

        missing = []
        for name, path in asset_fields:
            if path:  # Only check non-empty paths
                full_path = glfos_theme_base / path
                if not full_path.exists():
                    missing.append(f"{name}: {full_path}")

        assert not missing, "Missing assets:\n" + "\n".join(missing)


class TestConfigThemeIntegration:
    """Integration tests for config and theme loading."""

    def test_engine_loads_glfos_config(self) -> None:
        """Engine should load GLF OS config without errors."""
        config_path = EXAMPLES_DIR / "glfos.yaml"
        engine = Engine.from_config_file(config_path)
        assert engine.config.branding.name == "GLF OS"

    def test_engine_resolves_theme_path(self) -> None:
        """Engine should provide theme path from config."""
        config_path = EXAMPLES_DIR / "glfos.yaml"
        engine = Engine.from_config_file(config_path)
        theme_path = engine.get_theme_path()
        assert theme_path, "Theme path should not be empty"

    def test_resolved_theme_directory_exists(self) -> None:
        """Resolved theme directory should exist."""
        config_path = EXAMPLES_DIR / "glfos.yaml"
        engine = Engine.from_config_file(config_path)
        theme_path = engine.get_theme_path()

        # Resolve relative to config file
        theme_base = (config_path.parent / theme_path).resolve()
        assert theme_base.exists(), f"Theme directory not found: {theme_base}"


class TestThemeStructure:
    """Tests for theme directory structure."""

    @pytest.fixture
    def glfos_theme_dir(self) -> Path:
        """GLF OS theme directory."""
        return THEMES_DIR / "glfos"

    def test_theme_has_logos_directory(self, glfos_theme_dir: Path) -> None:
        """Theme should have a logos directory."""
        logos_dir = glfos_theme_dir / "logos"
        assert logos_dir.exists(), "logos/ directory missing"
        assert logos_dir.is_dir()

    def test_theme_has_wallpapers_directory(self, glfos_theme_dir: Path) -> None:
        """Theme should have a wallpapers directory."""
        wallpapers_dir = glfos_theme_dir / "wallpapers"
        assert wallpapers_dir.exists(), "wallpapers/ directory missing"
        assert wallpapers_dir.is_dir()

    def test_theme_has_main_logo(self, glfos_theme_dir: Path) -> None:
        """Theme should have a main logo file."""
        logo = glfos_theme_dir / "logos" / "logo.png"
        assert logo.exists(), "Main logo (logos/logo.png) missing"

    def test_theme_has_default_wallpaper(self, glfos_theme_dir: Path) -> None:
        """Theme should have a default wallpaper."""
        # Check for common wallpaper names
        wallpapers_dir = glfos_theme_dir / "wallpapers"
        wallpapers = list(wallpapers_dir.glob("*"))
        assert len(wallpapers) > 0, "No wallpapers found in wallpapers/"

    def test_theme_yaml_valid(self, glfos_theme_dir: Path) -> None:
        """theme.yaml should be valid YAML."""
        theme_yaml = glfos_theme_dir / "theme.yaml"
        assert theme_yaml.exists()

        with theme_yaml.open("r") as f:
            data = yaml.safe_load(f)

        assert data is not None, "theme.yaml is empty"
        assert "metadata" in data or "colors" in data, "theme.yaml missing expected keys"


class TestMultipleConfigs:
    """Tests for multiple configuration files."""

    @pytest.mark.parametrize("config_name", ["glfos.yaml", "archlinux.yaml", "minimal.yaml"])
    def test_example_config_is_valid(self, config_name: str) -> None:
        """All example configs should be valid."""
        config_path = EXAMPLES_DIR / config_name
        if not config_path.exists():
            pytest.skip(f"Config {config_name} not found")

        with config_path.open("r") as f:
            raw = yaml.safe_load(f)

        # Should not raise validation error
        config = OmnisConfig.model_validate(raw)
        assert config.branding.name, f"{config_name} missing branding name"

    def test_glfos_config_references_existing_theme(self) -> None:
        """GLF OS config theme reference should resolve to existing directory."""
        config_path = EXAMPLES_DIR / "glfos.yaml"
        with config_path.open("r") as f:
            raw = yaml.safe_load(f)
        config = OmnisConfig.model_validate(raw)

        if config.theme:
            theme_base = (config_path.parent / config.theme).resolve()
            assert theme_base.exists(), (
                f"Theme '{config.theme}' resolves to non-existent path: {theme_base}"
            )
