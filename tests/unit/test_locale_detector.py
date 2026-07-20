"""Unit tests for LocaleDetector."""

import json
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

try:
    from omnis.utils.locale_detector import (
        COUNTRY_TO_TIMEZONE,
        EFI_LANG_TO_LOCALE,
        TIMEZONE_TO_LOCALE,
        LocaleDetectionResult,
        LocaleDetector,
        LocaleDetectorConfig,
    )

    HAS_LOCALE_DETECTOR = True
except ImportError:
    HAS_LOCALE_DETECTOR = False

# Skip entire module if omnis locale detector is not available
pytestmark = pytest.mark.skipif(not HAS_LOCALE_DETECTOR, reason="LocaleDetector not available")


@pytest.fixture(autouse=True)
def neutral_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the developer's own session locale out of every detection result."""
    for var in ("LANG", "LC_ALL", "LC_CTYPE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(LocaleDetector, "LOCALE_CONF_PATH", Path("/nonexistent/locale.conf"))
    monkeypatch.setattr(shutil, "which", lambda _cmd: None)


# =============================================================================
# LocaleDetectionResult Tests
# =============================================================================


class TestLocaleDetectionResult:
    """Tests for LocaleDetectionResult dataclass."""

    def test_result_creation(self) -> None:
        """LocaleDetectionResult should be created with all fields."""
        result = LocaleDetectionResult(
            language="fr_FR.UTF-8",
            timezone="Europe/Paris",
            keymap="fr",
            source="geoip",
            confidence=0.9,
        )
        assert result.language == "fr_FR.UTF-8"
        assert result.timezone == "Europe/Paris"
        assert result.keymap == "fr"
        assert result.source == "geoip"
        assert result.confidence == 0.9

    def test_result_is_frozen(self) -> None:
        """LocaleDetectionResult should be immutable."""
        result = LocaleDetectionResult(
            language="en_US.UTF-8",
            timezone="UTC",
            keymap="us",
            source="default",
            confidence=0.1,
        )
        with pytest.raises(AttributeError):
            result.language = "fr_FR.UTF-8"  # type: ignore[misc]

    def test_to_dict(self) -> None:
        """LocaleDetectionResult.to_dict should return correct dictionary."""
        result = LocaleDetectionResult(
            language="de_DE.UTF-8",
            timezone="Europe/Berlin",
            keymap="de",
            source="cmdline",
            confidence=0.7,
        )
        d = result.to_dict()
        assert d == {
            "language": "de_DE.UTF-8",
            "timezone": "Europe/Berlin",
            "keymap": "de",
            "source": "cmdline",
            "confidence": 0.7,
        }


# =============================================================================
# LocaleDetectorConfig Tests
# =============================================================================


class TestLocaleDetectorConfig:
    """Tests for LocaleDetectorConfig dataclass."""

    def test_config_defaults(self) -> None:
        """LocaleDetectorConfig should have correct defaults."""
        config = LocaleDetectorConfig()
        assert config.enabled is True
        assert config.geoip_enabled is True
        assert config.geoip_timeout == 2.0
        assert config.cmdline_enabled is True
        assert config.session_enabled is True
        assert config.efi_enabled is True
        assert config.override_mode == "auto"
        assert config.confidence_threshold == 0.8

    def test_config_custom_values(self) -> None:
        """LocaleDetectorConfig should accept custom values."""
        config = LocaleDetectorConfig(
            enabled=False,
            geoip_enabled=False,
            geoip_timeout=5.0,
            cmdline_enabled=False,
            session_enabled=False,
            efi_enabled=False,
            override_mode="prefer_geoip",
            confidence_threshold=0.5,
        )
        assert config.enabled is False
        assert config.geoip_enabled is False
        assert config.geoip_timeout == 5.0
        assert config.cmdline_enabled is False
        assert config.session_enabled is False
        assert config.efi_enabled is False
        assert config.override_mode == "prefer_geoip"
        assert config.confidence_threshold == 0.5


# =============================================================================
# LocaleDetector Initialization Tests
# =============================================================================


class TestLocaleDetectorInit:
    """Tests for LocaleDetector initialization."""

    def test_init_defaults(self) -> None:
        """LocaleDetector should initialize with default config."""
        detector = LocaleDetector()
        assert detector.config is not None
        assert detector.config.enabled is True

    def test_init_with_config(self) -> None:
        """LocaleDetector should accept configuration."""
        config = LocaleDetectorConfig(geoip_timeout=5.0)
        detector = LocaleDetector(config)
        assert detector.config.geoip_timeout == 5.0

    def test_from_config_empty(self) -> None:
        """LocaleDetector.from_config should handle empty config."""
        detector = LocaleDetector.from_config({})
        assert detector.config.enabled is True
        assert detector.config.geoip_enabled is True

    def test_from_config_full(self) -> None:
        """LocaleDetector.from_config should parse full config."""
        config_dict = {
            "enabled": True,
            "methods": {
                "geoip": {"enabled": True, "timeout": 3.0},
                "cmdline": {"enabled": False},
                "session": {"enabled": False},
                "efi": {"enabled": True},
            },
            "override_mode": "prefer_local",
            "confidence_threshold": 0.6,
        }
        detector = LocaleDetector.from_config(config_dict)
        assert detector.config.enabled is True
        assert detector.config.geoip_enabled is True
        assert detector.config.geoip_timeout == 3.0
        assert detector.config.cmdline_enabled is False
        assert detector.config.efi_enabled is True
        assert detector.config.override_mode == "prefer_local"
        assert detector.config.confidence_threshold == 0.6


# =============================================================================
# GeoIP Detection Tests
# =============================================================================


class TestGeoIPDetection:
    """Tests for GeoIP-based locale detection."""

    def test_geoip_detection_success(self) -> None:
        """GeoIP detection should work with valid response."""
        mock_response = json.dumps(
            {"status": "success", "countryCode": "FR", "timezone": "Europe/Paris"}
        ).encode()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = mock_response
            detector = LocaleDetector()
            result = detector._detect_geoip()

        assert result is not None
        assert result.language == "fr_FR.UTF-8"
        assert result.timezone == "Europe/Paris"
        assert result.keymap == "fr"
        assert result.source == "geoip"
        assert result.confidence == 0.9

    def test_geoip_detection_germany(self) -> None:
        """GeoIP detection should work for Germany."""
        mock_response = json.dumps(
            {"status": "success", "countryCode": "DE", "timezone": "Europe/Berlin"}
        ).encode()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = mock_response
            detector = LocaleDetector()
            result = detector._detect_geoip()

        assert result is not None
        assert result.language == "de_DE.UTF-8"
        assert result.timezone == "Europe/Berlin"
        assert result.keymap == "de"

    def test_geoip_timeout_fallback(self) -> None:
        """GeoIP should return None on timeout."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = TimeoutError("Request timed out")
            detector = LocaleDetector()
            result = detector._detect_geoip()

        assert result is None

    def test_geoip_network_error(self) -> None:
        """GeoIP should return None on network error."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = OSError("Network unreachable")
            detector = LocaleDetector()
            result = detector._detect_geoip()

        assert result is None

    def test_geoip_error_status(self) -> None:
        """GeoIP should return None on error status."""
        mock_response = json.dumps({"status": "fail", "message": "private range"}).encode()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = mock_response
            detector = LocaleDetector()
            result = detector._detect_geoip()

        assert result is None

    def test_geoip_fallback_to_country(self) -> None:
        """GeoIP should fall back to country code when timezone is missing."""
        mock_response = json.dumps(
            {"status": "success", "countryCode": "JP", "timezone": ""}
        ).encode()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = mock_response
            detector = LocaleDetector()
            result = detector._detect_geoip()

        assert result is not None
        assert result.timezone == "Asia/Tokyo"
        assert result.language == "ja_JP.UTF-8"


# =============================================================================
# Cmdline Detection Tests
# =============================================================================


class TestCmdlineDetection:
    """Tests for kernel cmdline locale detection."""

    def test_cmdline_detection_full(self) -> None:
        """Cmdline detection should parse all parameters."""
        cmdline = (
            "BOOT_IMAGE=/boot/vmlinuz root=/dev/sda1 "
            "lang=fr_FR.UTF-8 timezone=Europe/Paris keymap=fr"
        )

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=cmdline),
        ):
            detector = LocaleDetector()
            result = detector._detect_cmdline()

        assert result is not None
        assert result.language == "fr_FR.UTF-8"
        assert result.timezone == "Europe/Paris"
        assert result.keymap == "fr"
        assert result.source == "cmdline"
        assert result.confidence == 0.9

    def test_cmdline_glf_iso_kbd_params(self) -> None:
        """GLF ISO GRUB params: kbd.locale + kbd.layout drive the selection;
        kbd.keymap (a console keymap like de-latin1) must be ignored."""
        cmdline = (
            "BOOT_IMAGE=/boot/vmlinuz kbd.layout=de kbd.keymap=de-latin1 kbd.locale=de_DE.UTF-8"
        )

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=cmdline),
        ):
            detector = LocaleDetector()
            result = detector._detect_cmdline()

        assert result is not None
        assert result.language == "de_DE.UTF-8"
        assert result.keymap == "de"  # kbd.layout, NOT "de-latin1"
        assert result.confidence == 0.9

    def test_prefer_local_cmdline_wins_over_geoip(self) -> None:
        """override_mode=prefer_local: the GRUB cmdline choice wins over GeoIP,
        which must not even be queried."""
        cmdline = "BOOT_IMAGE=/boot/vmlinuz kbd.layout=fr kbd.locale=fr_FR.UTF-8"
        config = LocaleDetectorConfig(override_mode="prefer_local")

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=cmdline),
            patch("urllib.request.urlopen") as mock_urlopen,
        ):
            detector = LocaleDetector(config)
            result = detector.detect()

        mock_urlopen.assert_not_called()
        assert result.source == "cmdline"
        assert result.keymap == "fr"
        assert result.language == "fr_FR.UTF-8"

    def test_cmdline_detection_partial(self) -> None:
        """Cmdline detection should work with partial parameters."""
        cmdline = "BOOT_IMAGE=/boot/vmlinuz root=/dev/sda1 timezone=Europe/Berlin"

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=cmdline),
        ):
            detector = LocaleDetector()
            result = detector._detect_cmdline()

        assert result is not None
        assert result.timezone == "Europe/Berlin"
        # Should derive locale and keymap from timezone
        assert result.language == "de_DE.UTF-8"
        assert result.keymap == "de"

    def test_cmdline_detection_locale_only(self) -> None:
        """Cmdline detection should work with locale parameter only."""
        cmdline = "BOOT_IMAGE=/boot/vmlinuz locale=es_ES.UTF-8"

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=cmdline),
        ):
            detector = LocaleDetector()
            result = detector._detect_cmdline()

        assert result is not None
        assert result.language == "es_ES.UTF-8"
        # Defaults for missing values
        assert result.timezone == "UTC"
        assert result.keymap == "us"

    def test_cmdline_english_ignored(self) -> None:
        """Cmdline should ignore English default locales."""
        cmdline = "BOOT_IMAGE=/boot/vmlinuz lang=en_US.UTF-8"

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=cmdline),
        ):
            detector = LocaleDetector()
            result = detector._detect_cmdline()

        # Should return None because en_US is default and should be skipped
        assert result is None

    def test_cmdline_normalize_locale(self) -> None:
        """Cmdline should normalize locale format."""
        cmdline = "BOOT_IMAGE=/boot/vmlinuz lang=pt_BR"  # Missing .UTF-8

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=cmdline),
        ):
            detector = LocaleDetector()
            result = detector._detect_cmdline()

        assert result is not None
        assert result.language == "pt_BR.UTF-8"

    def test_cmdline_not_available(self) -> None:
        """Cmdline detection should return None when file doesn't exist."""
        with patch.object(Path, "exists", return_value=False):
            detector = LocaleDetector()
            result = detector._detect_cmdline()

        assert result is None

    def test_cmdline_empty(self) -> None:
        """Cmdline detection should return None for empty cmdline."""
        cmdline = "BOOT_IMAGE=/boot/vmlinuz root=/dev/sda1 quiet"

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=cmdline),
        ):
            detector = LocaleDetector()
            result = detector._detect_cmdline()

        assert result is None


# =============================================================================
# Session Detection Tests
# =============================================================================


LOCALECTL_STATUS = """   System Locale: LANG=fr_FR.UTF-8
       VC Keymap: fr-latin9
      X11 Layout: fr
     X11 Variant: oss
"""

LOCALECTL_STATUS_NO_X11 = """   System Locale: LANG=de_DE.UTF-8
       VC Keymap: de
      X11 Layout: n/a
"""


class TestSessionDetection:
    """Tests for live-session locale detection.

    The GLF ISO French boot entry passes no kbd.* kernel parameter, so an
    offline live boot used to fall through to the en_US default. The session
    locale is the remaining reliable local signal.
    """

    def test_session_from_lang(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LANG should drive the detection."""
        monkeypatch.setenv("LANG", "fr_FR.UTF-8")
        result = LocaleDetector()._detect_session()

        assert result is not None
        assert result.language == "fr_FR.UTF-8"
        assert result.timezone == "Europe/Paris"
        assert result.keymap == "fr"
        assert result.source == "session"

    def test_session_confidence_clears_threshold(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Session confidence must be above the default 0.8 threshold."""
        monkeypatch.setenv("LANG", "fr_FR.UTF-8")
        result = LocaleDetector()._detect_session()

        assert result is not None
        assert result.confidence >= 0.85
        assert result.confidence > LocaleDetectorConfig().confidence_threshold

    def test_session_env_priority(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LANG should win over LC_ALL and LC_CTYPE."""
        monkeypatch.setenv("LANG", "de_DE.UTF-8")
        monkeypatch.setenv("LC_ALL", "es_ES.UTF-8")
        monkeypatch.setenv("LC_CTYPE", "it_IT.UTF-8")
        result = LocaleDetector()._detect_session()

        assert result is not None
        assert result.language == "de_DE.UTF-8"

    def test_session_falls_through_to_lc_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A C fallback in LANG should not shadow a real LC_ALL."""
        monkeypatch.setenv("LANG", "C.UTF-8")
        monkeypatch.setenv("LC_ALL", "pt_PT.UTF-8")
        result = LocaleDetector()._detect_session()

        assert result is not None
        assert result.language == "pt_PT.UTF-8"

    @pytest.mark.parametrize("value", ["C", "C.UTF-8", "POSIX", "en_US.UTF-8", "en_US", ""])
    def test_session_ignores_fallback_locales(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        """C/POSIX/en_US must not be reported as a detected session locale."""
        monkeypatch.setenv("LANG", value)
        assert LocaleDetector()._detect_session() is None

    def test_session_normalizes_missing_encoding(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A locale without an encoding suffix should get .UTF-8."""
        monkeypatch.setenv("LANG", "fr_FR")
        result = LocaleDetector()._detect_session()

        assert result is not None
        assert result.language == "fr_FR.UTF-8"

    def test_session_from_locale_conf(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """/etc/locale.conf should be read when the environment is unset."""
        locale_conf = tmp_path / "locale.conf"
        locale_conf.write_text('LANG="it_IT.UTF-8"\nLC_TIME=it_IT.UTF-8\n', encoding="utf-8")
        monkeypatch.setattr(LocaleDetector, "LOCALE_CONF_PATH", locale_conf)
        result = LocaleDetector()._detect_session()

        assert result is not None
        assert result.language == "it_IT.UTF-8"
        assert result.timezone == "Europe/Rome"
        assert result.keymap == "it"

    def test_session_env_wins_over_locale_conf(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The environment takes precedence over /etc/locale.conf."""
        locale_conf = tmp_path / "locale.conf"
        locale_conf.write_text("LANG=it_IT.UTF-8\n", encoding="utf-8")
        monkeypatch.setattr(LocaleDetector, "LOCALE_CONF_PATH", locale_conf)
        monkeypatch.setenv("LANG", "fr_FR.UTF-8")
        result = LocaleDetector()._detect_session()

        assert result is not None
        assert result.language == "fr_FR.UTF-8"

    def test_session_missing_locale_conf(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A missing /etc/locale.conf should not raise."""
        monkeypatch.setattr(LocaleDetector, "LOCALE_CONF_PATH", Path("/nonexistent/locale.conf"))
        assert LocaleDetector()._detect_session() is None

    def test_session_from_localectl(self) -> None:
        """localectl should provide both the locale and the X11 layout."""
        with (
            patch("shutil.which", return_value="/usr/bin/localectl"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = Mock(returncode=0, stdout=LOCALECTL_STATUS)
            result = LocaleDetector()._detect_session()

        assert result is not None
        assert result.language == "fr_FR.UTF-8"
        assert result.keymap == "fr"  # X11 Layout, not the VC "fr-latin9"
        assert result.source == "session"

    def test_session_localectl_vc_keymap_fallback(self) -> None:
        """VC Keymap is used when no X11 layout is configured."""
        with (
            patch("shutil.which", return_value="/usr/bin/localectl"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = Mock(returncode=0, stdout=LOCALECTL_STATUS_NO_X11)
            result = LocaleDetector()._detect_session()

        assert result is not None
        assert result.keymap == "de"

    def test_session_localectl_absent(self) -> None:
        """No localectl binary means no session result."""
        with (
            patch("shutil.which", return_value=None),
            patch("subprocess.run") as mock_run,
        ):
            assert LocaleDetector()._detect_session() is None
            mock_run.assert_not_called()


class TestSessionCascade:
    """Tests for the position of the session source in the detection cascade."""

    def test_session_wins_over_geoip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The session locale is tried before the network lookup."""
        monkeypatch.setenv("LANG", "fr_FR.UTF-8")

        with patch("urllib.request.urlopen") as mock_urlopen:
            result = LocaleDetector().detect()

        mock_urlopen.assert_not_called()
        assert result.source == "session"
        assert result.language == "fr_FR.UTF-8"

    def test_cmdline_wins_over_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """override_mode=prefer_local: the GRUB choice still wins."""
        monkeypatch.setenv("LANG", "fr_FR.UTF-8")
        cmdline = "BOOT_IMAGE=/boot/vmlinuz kbd.layout=de kbd.locale=de_DE.UTF-8"

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=cmdline),
        ):
            result = LocaleDetector(LocaleDetectorConfig(override_mode="prefer_local")).detect()

        assert result.source == "cmdline"
        assert result.language == "de_DE.UTF-8"

    def test_session_offline_avoids_english_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Offline live boot without kbd.* params must not fall back to en_US."""
        monkeypatch.setenv("LANG", "fr_FR.UTF-8")
        cmdline = "BOOT_IMAGE=/boot/vmlinuz root=/dev/sda1 quiet"

        with (
            patch("urllib.request.urlopen", side_effect=OSError("Network unreachable")),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=cmdline),
        ):
            result = LocaleDetector(LocaleDetectorConfig(override_mode="prefer_local")).detect()

        assert result.source == "session"
        assert result.language == "fr_FR.UTF-8"
        assert result.keymap == "fr"

    def test_prefer_geoip_keeps_session_as_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """override_mode=prefer_geoip: GeoIP first, session when it fails."""
        monkeypatch.setenv("LANG", "fr_FR.UTF-8")
        config = LocaleDetectorConfig(override_mode="prefer_geoip")
        mock_response = json.dumps(
            {"status": "success", "countryCode": "DE", "timezone": "Europe/Berlin"}
        ).encode()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = mock_response
            result = LocaleDetector(config).detect()
        assert result.source == "geoip"

        with patch("urllib.request.urlopen", side_effect=OSError("Network unreachable")):
            fallback = LocaleDetector(config).detect()
        assert fallback.source == "session"
        assert fallback.language == "fr_FR.UTF-8"

    def test_session_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Session detection should be skippable."""
        monkeypatch.setenv("LANG", "fr_FR.UTF-8")
        config = LocaleDetectorConfig(
            geoip_enabled=False,
            cmdline_enabled=False,
            session_enabled=False,
            efi_enabled=False,
        )
        result = LocaleDetector(config).detect()

        assert result.source == "default"


# =============================================================================
# EFI Detection Tests
# =============================================================================


class TestEFIDetection:
    """Tests for EFI PlatformLang detection."""

    def test_efi_detection_success(self) -> None:
        """EFI detection should work with valid efivar output."""
        efivar_output = "PlatformLang: fr-FR"

        with (
            patch.object(Path, "exists", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = Mock(returncode=0, stdout=efivar_output)
            detector = LocaleDetector()
            result = detector._detect_efi()

        assert result is not None
        assert result.language == "fr_FR.UTF-8"
        assert result.source == "efi"
        assert result.confidence == 0.5

    def test_efi_detection_german(self) -> None:
        """EFI detection should work for German."""
        efivar_output = "Some output with de-DE language"

        with (
            patch.object(Path, "exists", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = Mock(returncode=0, stdout=efivar_output)
            detector = LocaleDetector()
            result = detector._detect_efi()

        assert result is not None
        assert result.language == "de_DE.UTF-8"

    def test_efi_not_available(self) -> None:
        """EFI detection should return None on non-UEFI system."""
        with patch.object(Path, "exists", return_value=False):
            detector = LocaleDetector()
            result = detector._detect_efi()

        assert result is None

    def test_efi_command_not_found(self) -> None:
        """EFI detection should return None when efivar not installed."""
        with (
            patch.object(Path, "exists", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.side_effect = FileNotFoundError("efivar not found")
            detector = LocaleDetector()
            result = detector._detect_efi()

        assert result is None

    def test_efi_command_failed(self) -> None:
        """EFI detection should return None when efivar fails."""
        with (
            patch.object(Path, "exists", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="Variable not found")
            detector = LocaleDetector()
            result = detector._detect_efi()

        assert result is None

    def test_efi_english_ignored(self) -> None:
        """EFI detection should ignore English defaults."""
        efivar_output = "PlatformLang: en-US"

        with (
            patch.object(Path, "exists", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = Mock(returncode=0, stdout=efivar_output)
            detector = LocaleDetector()
            result = detector._detect_efi()

        assert result is None


# =============================================================================
# Cascade Fallback Tests
# =============================================================================


class TestCascadeFallback:
    """Tests for detection cascade and fallback behavior."""

    def test_cascade_geoip_first(self) -> None:
        """Detection should use GeoIP result when available."""
        mock_response = json.dumps(
            {"status": "success", "countryCode": "FR", "timezone": "Europe/Paris"}
        ).encode()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = mock_response
            detector = LocaleDetector()
            result = detector.detect()

        assert result.source == "geoip"
        assert result.language == "fr_FR.UTF-8"

    def test_cascade_fallback_to_cmdline(self) -> None:
        """Detection should fall back to cmdline when GeoIP fails."""
        cmdline = "BOOT_IMAGE=/boot/vmlinuz timezone=Europe/Rome"

        with (
            patch("urllib.request.urlopen") as mock_urlopen,
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=cmdline),
        ):
            mock_urlopen.side_effect = TimeoutError()
            detector = LocaleDetector()
            result = detector.detect()

        assert result.source == "cmdline"
        assert result.timezone == "Europe/Rome"

    def test_cascade_fallback_to_default(self) -> None:
        """Detection should fall back to default when all methods fail."""
        # Disable all detection methods except default
        config = LocaleDetectorConfig(
            geoip_enabled=False,
            cmdline_enabled=False,
            session_enabled=False,
            efi_enabled=False,
        )
        detector = LocaleDetector(config)
        result = detector.detect()

        assert result.source == "default"
        assert result.language == "en_US.UTF-8"
        assert result.timezone == "UTC"
        assert result.keymap == "us"
        assert result.confidence == 0.1

    def test_detection_disabled(self) -> None:
        """Detection should return default when disabled."""
        config = LocaleDetectorConfig(enabled=False)
        detector = LocaleDetector(config)
        result = detector.detect()

        assert result.source == "default"


# =============================================================================
# Disabled Methods Tests
# =============================================================================


class TestDisabledMethods:
    """Tests for disabled detection methods."""

    def test_geoip_disabled(self) -> None:
        """GeoIP should be skipped when disabled."""
        config = LocaleDetectorConfig(geoip_enabled=False)
        detector = LocaleDetector(config)

        with patch("urllib.request.urlopen") as mock_urlopen:
            # Should not be called
            detector.detect()
            mock_urlopen.assert_not_called()

    def test_cmdline_disabled(self) -> None:
        """Cmdline should be skipped when disabled."""
        config = LocaleDetectorConfig(
            geoip_enabled=False,
            cmdline_enabled=False,
            session_enabled=False,
            efi_enabled=False,
        )
        detector = LocaleDetector(config)

        with patch.object(Path, "read_text") as mock_read:
            detector.detect()
            mock_read.assert_not_called()

    def test_efi_disabled(self) -> None:
        """EFI should be skipped when disabled."""
        config = LocaleDetectorConfig(
            geoip_enabled=False,
            cmdline_enabled=False,
            session_enabled=False,
            efi_enabled=False,
        )
        detector = LocaleDetector(config)

        with patch("subprocess.run") as mock_run:
            detector.detect()
            mock_run.assert_not_called()


# =============================================================================
# Mapping Tests
# =============================================================================


class TestMappings:
    """Tests for timezone/country/locale mappings."""

    def test_timezone_to_locale_mapping(self) -> None:
        """TIMEZONE_TO_LOCALE should contain common timezones."""
        assert "Europe/Paris" in TIMEZONE_TO_LOCALE
        assert "Europe/Berlin" in TIMEZONE_TO_LOCALE
        assert "America/New_York" in TIMEZONE_TO_LOCALE
        assert "Asia/Tokyo" in TIMEZONE_TO_LOCALE

    def test_timezone_to_locale_values(self) -> None:
        """TIMEZONE_TO_LOCALE values should be (locale, keymap) tuples."""
        for _tz, (locale, keymap) in TIMEZONE_TO_LOCALE.items():
            assert isinstance(locale, str)
            assert isinstance(keymap, str)
            assert ".UTF-8" in locale or "UTF8" in locale

    def test_country_to_timezone_mapping(self) -> None:
        """COUNTRY_TO_TIMEZONE should contain common countries."""
        assert "FR" in COUNTRY_TO_TIMEZONE
        assert "DE" in COUNTRY_TO_TIMEZONE
        assert "US" in COUNTRY_TO_TIMEZONE
        assert "JP" in COUNTRY_TO_TIMEZONE

    def test_efi_lang_mapping(self) -> None:
        """EFI_LANG_TO_LOCALE should contain common EFI languages."""
        assert "fr-FR" in EFI_LANG_TO_LOCALE
        assert "de-DE" in EFI_LANG_TO_LOCALE
        assert "en-US" in EFI_LANG_TO_LOCALE
        assert "ja-JP" in EFI_LANG_TO_LOCALE
