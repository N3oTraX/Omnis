"""
Bridge between QML UI and Python Engine.

Exposes engine functionality to QML via Qt properties and signals.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Property, QObject, QThread, QUrl, Signal, Slot

from omnis.i18n.translator import get_translator
from omnis.jobs.locale import LocaleJob
from omnis.jobs.requirements import SystemRequirementsChecker
from omnis.utils.locale_detector import LocaleDetectionResult, LocaleDetector
from omnis.utils.network_helper import NetworkHelper

if TYPE_CHECKING:
    from omnis.core.engine import Engine

# Native names for locales (displayed in UI with proper Unicode characters)
# Each language is shown in its native script/form
LOCALE_NATIVE_NAMES: dict[str, str] = {
    # English variants
    "en_US.UTF-8": "English (United States)",
    "en_GB.UTF-8": "English (United Kingdom)",
    "en_CA.UTF-8": "English (Canada)",
    "en_AU.UTF-8": "English (Australia)",
    "en_NZ.UTF-8": "English (New Zealand)",
    "en_IE.UTF-8": "English (Ireland)",
    "en_ZA.UTF-8": "English (South Africa)",
    "en_IN.UTF-8": "English (India)",
    # French variants
    "fr_FR.UTF-8": "Français (France)",
    "fr_CA.UTF-8": "Français (Canada)",
    "fr_BE.UTF-8": "Français (Belgique)",
    "fr_CH.UTF-8": "Français (Suisse)",
    "fr_LU.UTF-8": "Français (Luxembourg)",
    # German variants
    "de_DE.UTF-8": "Deutsch (Deutschland)",
    "de_AT.UTF-8": "Deutsch (Österreich)",
    "de_CH.UTF-8": "Deutsch (Schweiz)",
    "de_LU.UTF-8": "Deutsch (Luxemburg)",
    "de_LI.UTF-8": "Deutsch (Liechtenstein)",
    # Spanish variants
    "es_ES.UTF-8": "Español (España)",
    "es_MX.UTF-8": "Español (México)",
    "es_AR.UTF-8": "Español (Argentina)",
    "es_CO.UTF-8": "Español (Colombia)",
    "es_CL.UTF-8": "Español (Chile)",
    "es_PE.UTF-8": "Español (Perú)",
    "es_VE.UTF-8": "Español (Venezuela)",
    # Italian
    "it_IT.UTF-8": "Italiano (Italia)",
    "it_CH.UTF-8": "Italiano (Svizzera)",
    # Portuguese variants
    "pt_BR.UTF-8": "Português (Brasil)",
    "pt_PT.UTF-8": "Português (Portugal)",
    # Russian and Cyrillic languages
    "ru_RU.UTF-8": "Русский (Россия)",
    "uk_UA.UTF-8": "Українська (Україна)",
    "be_BY.UTF-8": "Беларуская (Беларусь)",
    "bg_BG.UTF-8": "Български (България)",
    "sr_RS.UTF-8": "Српски (Србија)",
    "mk_MK.UTF-8": "Македонски (Македонија)",
    # Chinese variants
    "zh_CN.UTF-8": "简体中文 (中国)",
    "zh_TW.UTF-8": "繁體中文 (台灣)",
    "zh_HK.UTF-8": "繁體中文 (香港)",
    "zh_SG.UTF-8": "简体中文 (新加坡)",
    # Japanese
    "ja_JP.UTF-8": "日本語 (日本)",
    # Korean
    "ko_KR.UTF-8": "한국어 (대한민국)",
    # Arabic variants
    "ar_SA.UTF-8": "العربية (السعودية)",
    "ar_EG.UTF-8": "العربية (مصر)",
    "ar_MA.UTF-8": "العربية (المغرب)",
    "ar_DZ.UTF-8": "العربية (الجزائر)",
    "ar_TN.UTF-8": "العربية (تونس)",
    "ar_AE.UTF-8": "العربية (الإمارات)",
    # Hebrew
    "he_IL.UTF-8": "עברית (ישראל)",
    # Persian
    "fa_IR.UTF-8": "فارسی (ایران)",
    # Hindi and Indian languages
    "hi_IN.UTF-8": "हिन्दी (भारत)",
    "bn_IN.UTF-8": "বাংলা (ভারত)",
    "bn_BD.UTF-8": "বাংলা (বাংলাদেশ)",
    "ta_IN.UTF-8": "தமிழ் (இந்தியா)",
    "te_IN.UTF-8": "తెలుగు (భారతదేశం)",
    "mr_IN.UTF-8": "मराठी (भारत)",
    "gu_IN.UTF-8": "ગુજરાતી (ભારત)",
    "kn_IN.UTF-8": "ಕನ್ನಡ (ಭಾರತ)",
    "ml_IN.UTF-8": "മലയാളം (ഇന്ത്യ)",
    "pa_IN.UTF-8": "ਪੰਜਾਬੀ (ਭਾਰਤ)",
    # Thai
    "th_TH.UTF-8": "ไทย (ประเทศไทย)",
    # Vietnamese
    "vi_VN.UTF-8": "Tiếng Việt (Việt Nam)",
    # Indonesian and Malay
    "id_ID.UTF-8": "Bahasa Indonesia (Indonesia)",
    "ms_MY.UTF-8": "Bahasa Melayu (Malaysia)",
    # Turkish
    "tr_TR.UTF-8": "Türkçe (Türkiye)",
    # Greek
    "el_GR.UTF-8": "Ελληνικά (Ελλάδα)",
    "el_CY.UTF-8": "Ελληνικά (Κύπρος)",
    # Polish
    "pl_PL.UTF-8": "Polski (Polska)",
    # Dutch
    "nl_NL.UTF-8": "Nederlands (Nederland)",
    "nl_BE.UTF-8": "Nederlands (België)",
    # Nordic languages
    "sv_SE.UTF-8": "Svenska (Sverige)",
    "sv_FI.UTF-8": "Svenska (Finland)",
    "da_DK.UTF-8": "Dansk (Danmark)",
    "nb_NO.UTF-8": "Norsk Bokmål (Norge)",
    "nn_NO.UTF-8": "Norsk Nynorsk (Norge)",
    "fi_FI.UTF-8": "Suomi (Suomi)",
    "is_IS.UTF-8": "Íslenska (Ísland)",
    # Czech and Slovak
    "cs_CZ.UTF-8": "Čeština (Česko)",
    "sk_SK.UTF-8": "Slovenčina (Slovensko)",
    # Hungarian
    "hu_HU.UTF-8": "Magyar (Magyarország)",
    # Romanian
    "ro_RO.UTF-8": "Română (România)",
    "ro_MD.UTF-8": "Română (Moldova)",
    # Baltic languages
    "lt_LT.UTF-8": "Lietuvių (Lietuva)",
    "lv_LV.UTF-8": "Latviešu (Latvija)",
    "et_EE.UTF-8": "Eesti (Eesti)",
    # Slavic languages
    "sl_SI.UTF-8": "Slovenščina (Slovenija)",
    "hr_HR.UTF-8": "Hrvatski (Hrvatska)",
    "bs_BA.UTF-8": "Bosanski (Bosna i Hercegovina)",
    # Catalan
    "ca_ES.UTF-8": "Català (Espanya)",
    # Basque
    "eu_ES.UTF-8": "Euskara (Espainia)",
    # Galician
    "gl_ES.UTF-8": "Galego (España)",
    # Welsh
    "cy_GB.UTF-8": "Cymraeg (Y Deyrnas Unedig)",
    # Irish
    "ga_IE.UTF-8": "Gaeilge (Éire)",
    # Albanian
    "sq_AL.UTF-8": "Shqip (Shqipëri)",
    # Georgian
    "ka_GE.UTF-8": "ქართული (საქართველო)",
    # Armenian
    "hy_AM.UTF-8": "Հայերեն (Հայաստան)",
    # Kazakh
    "kk_KZ.UTF-8": "Қазақша (Қазақстан)",
    # Uzbek
    "uz_UZ.UTF-8": "O'zbek (O'zbekiston)",
    # Afrikaans
    "af_ZA.UTF-8": "Afrikaans (Suid-Afrika)",
    # Swahili
    "sw_KE.UTF-8": "Kiswahili (Kenya)",
    # Filipino
    "fil_PH.UTF-8": "Filipino (Pilipinas)",
    # Esperanto
    "eo.UTF-8": "Esperanto",
}


class InstallationWorker(QObject):
    """Worker that runs installation in a separate thread."""

    finished = Signal(bool)  # success: bool
    error = Signal(str)  # error_message

    def __init__(self, engine: Engine, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._engine = engine

    def run(self) -> None:
        """Execute the installation process."""
        try:
            success = self._engine.run_all()
            self.finished.emit(success)
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False)


class BrandingProxy(QObject):
    """Exposes branding configuration to QML."""

    # Signal emitted when translatable text properties change
    brandingChanged = Signal()

    def __init__(
        self, engine: Engine, theme_base: Path, parent: QObject | None = None, debug: bool = False
    ) -> None:
        super().__init__(parent)
        self._branding = engine.get_branding()
        self._theme_base = theme_base
        self._debug = debug

        if self._debug:
            print(f"[Branding] Loaded: {self._branding.name}")
            print(f"[Branding] Theme base: {self._theme_base}")
            print(
                f"[Branding] Colors - primary: {self._branding.colors.primary}, "
                f"bg: {self._branding.colors.background}, text: {self._branding.colors.text}"
            )

    def _resolve_asset(self, relative_path: str) -> str:
        """Resolve asset path to absolute file:// URL."""
        if not relative_path:
            if self._debug:
                print("[Branding] Asset path is empty")
            return ""
        full_path = self._theme_base / relative_path
        if full_path.exists():
            url = QUrl.fromLocalFile(str(full_path.resolve())).toString()
            if self._debug:
                print(f"[Branding] Resolved: {relative_path} -> {url}")
            return url
        if self._debug:
            print(f"[Branding] Asset not found: {full_path}")
        return ""

    @Property(str, constant=True)
    def name(self) -> str:
        """Distribution name."""
        return self._branding.name

    @Property(str, constant=True)
    def version(self) -> str:
        """Distribution version."""
        return self._branding.version

    @Property(str, constant=True)
    def edition(self) -> str:
        """Distribution edition."""
        return self._branding.edition

    @Property(str, constant=True)
    def primaryColor(self) -> str:
        """Primary brand color."""
        return self._branding.colors.primary

    @Property(str, constant=True)
    def secondaryColor(self) -> str:
        """Secondary brand color."""
        return self._branding.colors.secondary

    @Property(str, constant=True)
    def accentColor(self) -> str:
        """Accent color."""
        return self._branding.colors.accent

    @Property(str, constant=True)
    def backgroundColor(self) -> str:
        """Background color."""
        return self._branding.colors.background

    @Property(str, constant=True)
    def surfaceColor(self) -> str:
        """Surface color."""
        return self._branding.colors.surface

    @Property(str, constant=True)
    def textColor(self) -> str:
        """Primary text color."""
        return self._branding.colors.text

    @Property(str, constant=True)
    def textMutedColor(self) -> str:
        """Muted text color."""
        return self._branding.colors.text_muted

    @Property(str, notify=brandingChanged)
    def welcomeTitle(self) -> str:
        """Welcome screen title with i18n interpolation."""
        translator = get_translator()
        return translator.get(
            "title",
            "welcome",
            default=self._branding.strings.welcome_title,
            distro_name=self._branding.name,
        )

    @Property(str, notify=brandingChanged)
    def welcomeSubtitle(self) -> str:
        """Welcome screen subtitle with i18n interpolation."""
        translator = get_translator()
        # Get tagline from branding config
        tagline = getattr(self._branding, "tagline", "")
        return translator.get(
            "subtitle",
            "welcome",
            default=self._branding.strings.welcome_subtitle,
            distro_tagline=tagline,
        )

    @Property(str, notify=brandingChanged)
    def installButton(self) -> str:
        """Install button text with i18n interpolation."""
        translator = get_translator()
        return translator.get(
            "install_button",
            "welcome",
            default=self._branding.strings.install_button,
            distro_name=self._branding.name,
        )

    @Property(str, constant=True)
    def logoPath(self) -> str:
        """Path to logo asset."""
        return self._branding.assets.logo

    # Asset URLs (resolved to absolute file:// URLs)
    @Property(str, constant=True)
    def logoUrl(self) -> str:
        """URL to main logo."""
        return self._resolve_asset(self._branding.assets.logo)

    @Property(str, constant=True)
    def logoLightUrl(self) -> str:
        """URL to light variant logo."""
        return self._resolve_asset(self._branding.assets.logo_light)

    @Property(str, constant=True)
    def logoSmallUrl(self) -> str:
        """URL to small logo (64px)."""
        return self._resolve_asset(self._branding.assets.logo_small)

    @Property(str, constant=True)
    def backgroundUrl(self) -> str:
        """URL to background wallpaper."""
        return self._resolve_asset(self._branding.assets.background)

    @Property(str, constant=True)
    def iconUrl(self) -> str:
        """URL to icon."""
        return self._resolve_asset(self._branding.assets.icon)

    # Links
    @Property(str, constant=True)
    def websiteUrl(self) -> str:
        """Main website URL."""
        return self._branding.links.website

    @Property(str, constant=True)
    def websiteLabel(self) -> str:
        """Display label for website link (falls back to full URL if empty)."""
        label = self._branding.links.website_label
        if not label and self._branding.links.website:
            # Use full URL as fallback, only remove trailing slash
            label = self._branding.links.website.rstrip("/")
        return label

    @Property(str, constant=True)
    def gitUrl(self) -> str:
        """Git repository URL."""
        return self._branding.links.git

    @Property(str, constant=True)
    def documentationUrl(self) -> str:
        """Documentation URL."""
        return self._branding.links.documentation

    @Property(str, constant=True)
    def supportUrl(self) -> str:
        """Support/forum URL."""
        return self._branding.links.support

    @Slot()
    def retranslate(self) -> None:
        """
        Force re-evaluation of all translatable text properties.

        Call this when the application language changes to update
        all QML bindings that use branding text properties.
        """
        if self._debug:
            print("[Branding] Retranslating branding strings...")
        self.brandingChanged.emit()


class EngineBridge(QObject):
    """
    Main bridge between QML and installation engine.

    Exposes:
    - Installation control (start, pause, cancel)
    - Progress reporting
    - Job navigation
    - Branding configuration
    """

    # Signals for QML
    installationStarted = Signal()
    installationFinished = Signal(bool)  # success: bool
    jobStarted = Signal(str)  # job_name
    jobProgress = Signal(str, int, str)  # job_name, percent, message
    jobCompleted = Signal(str, bool)  # job_name, success
    errorOccurred = Signal(str, str)  # job_name, error_message
    requirementsChanged = Signal()  # emitted when requirements check completes

    # Network settings signals
    networkSettingsLaunched = Signal(str)  # command that was launched
    networkSettingsError = Signal(str)  # error message
    internetStatusChanged = Signal(bool)  # connected: bool

    # Signals for user selections
    selectionsChanged = Signal()  # emitted when any selection changes
    localeDataChanged = Signal()  # emitted when locale data is loaded
    keyboardVariantsChanged = Signal()  # emitted when keyboard variants change
    disksChanged = Signal()  # emitted when disks are scanned
    progressChanged = Signal()  # emitted when progress updates
    systemFontChanged = Signal()  # emitted when system font family changes

    # Locale prefixes that require non-Latin font (CJK, Arabic, Hebrew, etc.)
    # These scripts need fonts with broader Unicode coverage like Noto Sans
    NON_LATIN_LOCALE_PREFIXES = (
        # CJK (Chinese, Japanese, Korean)
        "zh_",
        "ja_",
        "ko_",
        # Arabic script
        "ar_",
        "fa_",
        "ur_",
        # Hebrew script
        "he_",
        "yi_",
        # Indic scripts (Devanagari, Bengali, Tamil, etc.)
        "hi_",
        "bn_",
        "ta_",
        "te_",
        "mr_",
        "gu_",
        "kn_",
        "ml_",
        "pa_",
        "ne_",
        "si_",
        # Thai script
        "th_",
        # Georgian script
        "ka_",
        # Armenian script
        "hy_",
        # Greek script (while Latin-based in some ways, benefits from Noto)
        "el_",
        # Cyrillic script (Russian, Ukrainian, etc.)
        "ru_",
        "uk_",
        "be_",
        "bg_",
        "sr_",
        "mk_",
        "kk_",
        "ky_",
        "mn_",
        "tg_",
        # Other scripts
        "am_",  # Amharic (Ethiopic)
        "my_",  # Burmese
        "km_",  # Khmer
        "lo_",  # Lao
    )

    # Font family for non-Latin scripts (Noto Sans has excellent Unicode coverage)
    UNICODE_FONT_FAMILY = "Noto Sans"

    # Default Latin font family (empty string = system default)
    LATIN_FONT_FAMILY = ""

    def __init__(
        self,
        engine: Engine,
        theme_base: Path,
        debug: bool = False,
        dry_run: bool = False,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._debug = debug
        self._dry_run = dry_run
        self._branding_proxy = BrandingProxy(engine, theme_base, self, debug=debug)
        self._theme_base = theme_base

        # Thread management
        self._worker: InstallationWorker | None = None
        self._thread: QThread | None = None

        # Requirements state
        self._requirements_checker: SystemRequirementsChecker | None = None
        self._requirements_model: list[dict[str, Any]] = []
        self._can_proceed: bool = True
        self._is_checking_requirements: bool = False
        self._show_requirements: bool = True

        # Locale data
        self._locales_model: list[str] = []
        self._locales_model_native: list[dict[str, str]] = []
        self._timezones_model: list[str] = []
        self._keymaps_model: list[str] = []
        self._keyboard_variants_model: list[str] = []
        self._locale_detection_result: LocaleDetectionResult | None = None
        self._locale_auto_detection_config: dict[str, Any] = {}

        # Keyboard variants by layout (XKB-compatible)
        # Each layout has a list of available variants
        # Empty string "" means default/basic variant
        self._keyboard_variants: dict[str, list[str]] = {
            # US layouts
            "us": [
                "",
                "alt-intl",
                "altgr-intl",
                "chr",
                "colemak",
                "colemak_dh",
                "colemak_dh_iso",
                "dvorak",
                "dvorak-alt-intl",
                "dvorak-classic",
                "dvorak-intl",
                "dvorak-l",
                "dvorak-r",
                "dvp",
                "euro",
                "hbs",
                "intl",
                "mac",
                "norman",
                "olpc2",
                "rus",
                "workman",
                "workman-intl",
            ],
            # French layouts
            "fr": [
                "",
                "azerty",
                "bepo",
                "bepo_afnor",
                "bepo_latin9",
                "bre",
                "dvorak",
                "geo",
                "latin9",
                "mac",
                "nodeadkeys",
                "oci",
                "oss",
                "oss_latin9",
                "oss_nodeadkeys",
                "sun_type6",
                "us",
            ],
            # German layouts
            "de": [
                "",
                "T3",
                "adnw",
                "bone",
                "deadacute",
                "deadgraveacute",
                "deadtilde",
                "dsb",
                "dsb_qwertz",
                "dvorak",
                "e1",
                "e2",
                "koy",
                "legacy",
                "mac",
                "mac_nodeadkeys",
                "neo",
                "nodeadkeys",
                "qwerty",
                "ro",
                "ro_nodeadkeys",
                "ru",
                "sun_type6",
                "tr",
            ],
            # UK layouts
            "gb": [
                "",
                "colemak",
                "colemak_dh",
                "dvorak",
                "dvorakukp",
                "extd",
                "intl",
                "mac",
                "mac_intl",
                "sun_type6",
            ],
            # Spanish layouts
            "es": [
                "",
                "ast",
                "cat",
                "deadtilde",
                "dvorak",
                "mac",
                "nodeadkeys",
                "sun_type6",
                "winkeys",
            ],
            # Italian layouts
            "it": [
                "",
                "fur",
                "geo",
                "ibm",
                "intl",
                "lld",
                "mac",
                "nodeadkeys",
                "sun_type6",
                "us",
                "winkeys",
            ],
            # Portuguese layouts
            "pt": [
                "",
                "mac",
                "mac_nodeadkeys",
                "mac_sundeadkeys",
                "nativo",
                "nativo-epo",
                "nativo-us",
                "nodeadkeys",
                "sun_type6",
                "sundeadkeys",
            ],
            # Brazilian Portuguese
            "br": [
                "",
                "dvorak",
                "nativo",
                "nativo-epo",
                "nativo-us",
                "nodeadkeys",
                "sun_type6",
                "thinkpad",
            ],
            # Russian layouts
            "ru": [
                "",
                "bak",
                "chm",
                "chu",
                "cv",
                "cv_latin",
                "dos",
                "komi",
                "legacy",
                "mac",
                "os_legacy",
                "os_winkeys",
                "phonetic",
                "phonetic_azerty",
                "phonetic_dvorak",
                "phonetic_fr",
                "phonetic_winkeys",
                "rulemak",
                "sah",
                "srp",
                "sun_type6",
                "tt",
                "typewriter",
                "typewriter-legacy",
                "udm",
                "xal",
            ],
            # Japanese layouts
            "jp": [
                "",
                "OADG109A",
                "dvorak",
                "kana",
                "kana86",
                "mac",
                "sun_type6",
                "sun_type7",
                "sun_type7_suncompat",
            ],
            # Chinese layouts
            "cn": ["", "altgr-pinyin", "tib", "tib_asciinum", "ug"],
            # Korean layouts
            "kr": ["", "kr104", "sun_type6"],
            # Arabic layouts
            "ara": [
                "",
                "azerty",
                "azerty_digits",
                "basic",
                "buckwalter",
                "digits",
                "mac",
                "olpc",
                "qwerty",
                "qwerty_digits",
                "sun_type6",
            ],
            # Hebrew layouts
            "il": ["", "biblical", "lyx", "phonetic", "sun_type6"],
            # Greek layouts
            "gr": [
                "",
                "extended",
                "nodeadkeys",
                "polytonic",
                "simple",
                "sun_type6",
            ],
            # Turkish layouts
            "tr": [
                "",
                "alt",
                "crh",
                "crh_alt",
                "crh_f",
                "f",
                "intl",
                "ku",
                "ku_alt",
                "ku_f",
                "sun_type6",
            ],
            # Polish layouts
            "pl": [
                "",
                "csb",
                "dvorak",
                "dvorak_altquotes",
                "dvorak_quotes",
                "dvp",
                "legacy",
                "qwertz",
                "ru_phonetic_dvorak",
                "sun_type6",
                "szl",
            ],
            # Dutch layouts
            "nl": ["", "mac", "std", "sun_type6", "sundeadkeys"],
            # Swedish layouts
            "se": [
                "",
                "dvorak",
                "dvorak_a5",
                "mac",
                "nodeadkeys",
                "rus",
                "rus_nodeadkeys",
                "smi",
                "sun_type6",
                "svdvorak",
                "swl",
                "us",
                "us_dvorak",
            ],
            # Norwegian layouts
            "no": [
                "",
                "colemak",
                "dvorak",
                "mac",
                "mac_nodeadkeys",
                "nodeadkeys",
                "smi",
                "smi_nodeadkeys",
                "sun_type6",
                "winkeys",
            ],
            # Danish layouts
            "dk": [
                "",
                "dvorak",
                "mac",
                "mac_nodeadkeys",
                "nodeadkeys",
                "sun_type6",
                "winkeys",
            ],
            # Finnish layouts
            "fi": [
                "",
                "classic",
                "das",
                "dvorak",
                "mac",
                "nodeadkeys",
                "smi",
                "sun_type6",
                "winkeys",
            ],
            # Czech layouts
            "cz": [
                "",
                "bksl",
                "dvorak-ucw",
                "qwerty",
                "qwerty_bksl",
                "sun_type6",
                "ucw",
            ],
            # Slovak layouts
            "sk": ["", "bksl", "qwerty", "qwerty_bksl", "sun_type6"],
            # Hungarian layouts
            "hu": [
                "",
                "101_qwerty_comma_dead",
                "101_qwerty_comma_nodead",
                "101_qwerty_dot_dead",
                "101_qwerty_dot_nodead",
                "101_qwertz_comma_dead",
                "101_qwertz_comma_nodead",
                "101_qwertz_dot_dead",
                "101_qwertz_dot_nodead",
                "102_qwerty_comma_dead",
                "102_qwerty_comma_nodead",
                "102_qwerty_dot_dead",
                "102_qwerty_dot_nodead",
                "102_qwertz_comma_dead",
                "102_qwertz_comma_nodead",
                "102_qwertz_dot_dead",
                "102_qwertz_dot_nodead",
                "nodeadkeys",
                "qwerty",
                "standard",
                "sun_type6",
            ],
            # Romanian layouts
            "ro": [
                "",
                "cedilla",
                "crh_dobruja",
                "std",
                "std_cedilla",
                "sun_type6",
                "winkeys",
            ],
            # Ukrainian layouts
            "ua": [
                "",
                "crh",
                "crh_alt",
                "crh_f",
                "homophonic",
                "legacy",
                "macOS",
                "phonetic",
                "rstu",
                "rstu_ru",
                "sun_type6",
                "typewriter",
                "winkeys",
            ],
            # Bulgarian layouts
            "bg": [
                "",
                "bas_phonetic",
                "bekl",
                "phonetic",
                "sun_type6",
            ],
            # Serbian layouts
            "rs": [
                "",
                "alterstrstrings",
                "combstrstrings",
                "latin",
                "latinyz",
                "latinunicodeyz",
                "latinunicode",
                "rue",
                "sun_type6",
            ],
            # Croatian layouts
            "hr": [
                "",
                "alterstrstrings",
                "combstrstrings",
                "sun_type6",
                "unicode",
                "unicodeus",
                "us",
            ],
            # Slovenian layouts
            "si": ["", "alterstrstrings", "sun_type6", "us"],
            # Lithuanian layouts
            "lt": [
                "",
                "ibm",
                "lekp",
                "lekpa",
                "ratise",
                "sgs",
                "std",
                "sun_type6",
                "us",
                "us_dvorak",
            ],
            # Latvian layouts
            "lv": [
                "",
                "adapted",
                "apostrophe",
                "ergonomic",
                "fkey",
                "modern",
                "sun_type6",
                "tilde",
            ],
            # Estonian layouts
            "ee": ["", "dvorak", "nodeadkeys", "sun_type6", "us"],
            # Swiss layouts (multilingual)
            "ch": [
                "",
                "de_mac",
                "de_nodeadkeys",
                "de_sundeadkeys",
                "fr",
                "fr_mac",
                "fr_nodeadkeys",
                "fr_sundeadkeys",
                "legacy",
                "sun_type6",
            ],
            # Belgian layouts
            "be": [
                "",
                "iso-alternate",
                "nodeadkeys",
                "oss",
                "oss_latin9",
                "oss_sundeadkeys",
                "sun_type6",
                "sundeadkeys",
                "wang",
            ],
            # Canadian layouts
            "ca": [
                "",
                "eng",
                "fr-dvorak",
                "fr-legacy",
                "ike",
                "kut",
                "multi",
                "multi-2gr",
                "multix",
                "shs",
                "sun_type6",
            ],
            # Indian layouts
            "in": [
                "",
                "ben",
                "ben_baishakhi",
                "ben_bornona",
                "ben_gitanjali",
                "ben_inscript",
                "ben_probhat",
                "bolnagri",
                "deva",
                "eng",
                "guj",
                "guru",
                "hin-kagapa",
                "hin-wx",
                "jhelum",
                "kan",
                "kan-kagapa",
                "mal",
                "mal_enhanced",
                "mal_lalitha",
                "mar-kagapa",
                "ori",
                "san-kagapa",
                "tam",
                "tam_TAB",
                "tam_TSCII",
                "tam_keyboard_with_numerals",
                "tam_unicode",
                "tel",
                "tel-kagapa",
                "urd-phonetic",
                "urd-phonetic3",
                "urd-winkeys",
            ],
            # Thai layouts
            "th": ["", "pat", "sun_type6", "tis"],
            # Vietnamese layouts
            "vn": ["", "fr", "us"],
            # Indonesian layouts
            "id": ["", "phoneticx"],
            # Catalan layouts
            "ad": [""],  # Andorra/Catalan
            # Irish layouts
            "ie": ["", "CloGaelach", "UnicodeExpert", "ogam", "ogam_is434"],
            # Default fallback
            "latam": [
                "",
                "colemak",
                "deadtilde",
                "dvorak",
                "nodeadkeys",
                "sun_type6",
            ],
        }

        # User selections
        self._selections: dict[str, Any] = {
            "locale": "en_US.UTF-8",
            "timezone": "UTC",
            "keymap": "us",
            "keyboardVariant": "qwerty",
            "username": "",
            "fullName": "",
            "hostname": "",
            "password": "",
            "autoLogin": False,
            "isAdmin": True,
            "disk": "",
            "partitionMode": "auto",
        }

        # Disk data
        self._disks_model: list[dict[str, Any]] = []

        # Progress tracking
        self._overall_progress: int = 0
        self._current_job_progress: int = 0
        self._current_job_name: str = ""
        self._current_job_message: str = ""
        self._jobs_list: list[dict[str, Any]] = []
        self._installation_status: str = "idle"  # idle, running, success, failed
        self._error_message: str = ""

        # Connect engine callbacks
        self._engine.on_job_start = self._on_job_start
        self._engine.on_job_progress = self._on_job_progress
        self._engine.on_job_complete = self._on_job_complete
        self._engine.on_error = self._on_error

        # Initialize requirements checker with config
        self._init_requirements_checker()

    @property
    def branding_proxy(self) -> BrandingProxy:
        """Get branding proxy for QML context."""
        return self._branding_proxy

    def _init_requirements_checker(self) -> None:
        """Initialize the requirements checker with config from engine."""
        # Get requirements config from welcome job config if available
        welcome_config = {}
        for job_def in self._engine.config.normalize_jobs():
            if job_def.name == "welcome":
                welcome_config = job_def.config.get("requirements", {})
                break

        self._requirements_checker = SystemRequirementsChecker(welcome_config)

        if self._debug:
            print(f"[Engine] Requirements checker initialized with config: {welcome_config}")

    def _on_job_start(self, job_name: str) -> None:
        """Handle job start event."""
        self._current_job_name = job_name
        self._current_job_progress = 0
        self._current_job_message = f"Starting {job_name}..."
        self._update_jobs_list()
        self.progressChanged.emit()
        self.jobStarted.emit(job_name)

    def _on_job_progress(self, job_name: str, percent: int, message: str) -> None:
        """Handle job progress event."""
        self._current_job_name = job_name
        self._current_job_progress = percent
        self._current_job_message = message

        # Calculate overall progress
        total_jobs = len(self._engine.jobs)
        current_idx = self.getCurrentJobIndex()
        if total_jobs > 0 and current_idx >= 0:
            base_progress = (current_idx * 100) // total_jobs
            job_contribution = percent // total_jobs
            self._overall_progress = base_progress + job_contribution

        self.progressChanged.emit()
        self.jobProgress.emit(job_name, percent, message)

    def _on_job_complete(self, job_name: str, result: Any) -> None:
        """Handle job completion event."""
        self._update_jobs_list()
        self.progressChanged.emit()
        self.jobCompleted.emit(job_name, result.success)

    def _on_error(self, job_name: str, error: str) -> None:
        """Handle error event."""
        self._error_message = error
        self._installation_status = "failed"
        self.progressChanged.emit()
        self.errorOccurred.emit(job_name, error)

    @Property(bool, constant=True)
    def debugMode(self) -> bool:
        """Check if debug mode is enabled."""
        return self._debug

    @Property(bool, constant=True)
    def dryRun(self) -> bool:
        """Check if dry-run mode is enabled."""
        return self._dry_run

    # =========================================================================
    # Font Properties for Non-Latin Languages
    # =========================================================================

    def _needs_unicode_font(self, locale: str) -> bool:
        """
        Check if the given locale needs a Unicode-complete font.

        Args:
            locale: Locale string (e.g., "zh_CN.UTF-8", "ja_JP.UTF-8")

        Returns:
            True if locale requires non-Latin font (CJK, Arabic, etc.)
        """
        # Check if locale starts with any non-Latin prefix
        return any(locale.startswith(prefix) for prefix in self.NON_LATIN_LOCALE_PREFIXES)

    @Property(str, notify=systemFontChanged)
    def systemFontFamily(self) -> str:
        """
        Get the recommended font family for the current locale.

        Returns:
            Font family name (e.g., "Noto Sans") or empty string for system default
        """
        current_locale = self._selections.get("locale", "en_US.UTF-8")
        if self._needs_unicode_font(current_locale):
            return self.UNICODE_FONT_FAMILY
        return self.LATIN_FONT_FAMILY

    @Property(bool, notify=systemFontChanged)
    def needsUnicodeFont(self) -> bool:
        """
        Check if current locale needs Unicode-complete font.

        Returns:
            True if current locale is non-Latin (CJK, Arabic, Hebrew, etc.)
        """
        current_locale = self._selections.get("locale", "en_US.UTF-8")
        return self._needs_unicode_font(current_locale)

    # Requirements properties
    @Property(bool, notify=requirementsChanged)
    def showRequirements(self) -> bool:
        """Whether to show requirements panel."""
        return self._show_requirements

    @Property(list, notify=requirementsChanged)
    def requirementsModel(self) -> list[dict[str, Any]]:
        """Get requirements list for QML ListView."""
        return self._requirements_model

    @Property(bool, notify=requirementsChanged)
    def canProceed(self) -> bool:
        """Whether installation can proceed based on requirements."""
        return self._can_proceed

    @Property(bool, notify=requirementsChanged)
    def isCheckingRequirements(self) -> bool:
        """Whether requirements are currently being checked."""
        return self._is_checking_requirements

    @Slot()
    def checkRequirements(self) -> None:
        """Perform requirements check and update model."""
        if self._requirements_checker is None:
            self._init_requirements_checker()

        # Safety check for mypy (should never be None after init)
        if self._requirements_checker is None:
            return

        self._is_checking_requirements = True
        self.requirementsChanged.emit()

        if self._debug:
            print("[Engine] Starting requirements check...")

        # Perform the check
        result = self._requirements_checker.check_all()

        # Convert to QML-compatible list
        self._requirements_model = []
        for check in result.checks:
            self._requirements_model.append(
                {
                    "name": check.name,
                    "description": check.description,
                    "status": check.status.name.lower(),
                    "currentValue": check.current_value,
                    "requiredValue": check.required_value,
                    "recommendedValue": check.recommended_value,
                    "details": check.details,
                }
            )

        # Update state
        self._can_proceed = result.can_continue
        self._is_checking_requirements = False

        # Hide panel if no checks are configured/enabled
        self._show_requirements = len(result.checks) > 0

        if self._debug:
            print(f"[Engine] Requirements check complete: {len(result.checks)} checks")
            print(f"[Engine] Can proceed: {self._can_proceed}")
            print(f"[Engine] Show requirements panel: {self._show_requirements}")
            for item in self._requirements_model:
                print(f"[Engine]   - {item['name']}: {item['status']}")

        self.requirementsChanged.emit()

    @Property(list, constant=True)
    def jobNames(self) -> list[str]:
        """Get list of job names in order."""
        return self._engine.get_job_names()

    @Property(int, constant=True)
    def totalJobs(self) -> int:
        """Get total number of jobs."""
        return len(self._engine.jobs)

    @Slot()
    def startInstallation(self) -> None:
        """Start the installation process in a separate thread."""
        # Prevent multiple concurrent installations
        if self._thread is not None and self._thread.isRunning():
            if self._debug:
                print("[Engine] Installation already in progress")
            return

        self.installationStarted.emit()

        # Create worker and thread
        self._thread = QThread(self)
        self._worker = InstallationWorker(self._engine)
        self._worker.moveToThread(self._thread)

        # Connect signals
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_installation_finished)
        self._worker.error.connect(self._on_installation_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._cleanup_thread)

        # Start installation
        if self._debug:
            print("[Engine] Starting installation in background thread")
        self._thread.start()

    def _on_installation_finished(self, success: bool) -> None:
        """Handle installation completion."""
        if self._debug:
            print(f"[Engine] Installation finished: {'success' if success else 'failed'}")
        self.installationFinished.emit(success)

    def _on_installation_error(self, error_message: str) -> None:
        """Handle installation error."""
        if self._debug:
            print(f"[Engine] Installation error: {error_message}")
        self.errorOccurred.emit("installation", error_message)

    def _cleanup_thread(self) -> None:
        """Clean up thread references after completion."""
        self._thread = None
        self._worker = None

    @Slot(result=int)
    def getCurrentJobIndex(self) -> int:
        """Get current job index (0-based)."""
        current, _ = self._engine.get_progress()
        return current - 1

    @Slot(result=str)
    def getCurrentJobName(self) -> str:
        """Get current job name."""
        idx = self.getCurrentJobIndex()
        if 0 <= idx < len(self._engine.jobs):
            return self._engine.jobs[idx].name
        return ""

    @Slot(result=bool)
    def isRunning(self) -> bool:
        """Check if installation is running."""
        return self._engine.state.is_running

    @Slot(result=bool)
    def isFinished(self) -> bool:
        """Check if installation is finished."""
        return self._engine.state.is_finished

    @Slot(result=str)
    def getLastError(self) -> str:
        """Get last error message."""
        return self._engine.state.last_error or ""

    # =========================================================================
    # Locale Data Properties
    # =========================================================================

    @Property(list, notify=localeDataChanged)
    def localesModel(self) -> list[str]:
        """Get available locales for QML."""
        return self._locales_model

    @Property(list, notify=localeDataChanged)
    def localesModelNative(self) -> list[dict[str, str]]:
        """Get available locales with native names for QML."""
        return self._locales_model_native

    @Property(list, notify=localeDataChanged)
    def timezonesModel(self) -> list[str]:
        """Get available timezones for QML."""
        return self._timezones_model

    @Property(list, notify=localeDataChanged)
    def keymapsModel(self) -> list[str]:
        """Get available keyboard layouts for QML."""
        return self._keymaps_model

    @Property(list, notify=keyboardVariantsChanged)
    def keyboardVariantsModel(self) -> list[str]:
        """Get available keyboard variants for selected layout."""
        return self._keyboard_variants_model

    @Property(str, notify=localeDataChanged)
    def detectedLocale(self) -> str:
        """Get auto-detected locale."""
        if self._locale_detection_result:
            return self._locale_detection_result.language
        return ""

    @Property(str, notify=localeDataChanged)
    def detectedTimezone(self) -> str:
        """Get auto-detected timezone."""
        if self._locale_detection_result:
            return self._locale_detection_result.timezone
        return ""

    @Property(str, notify=localeDataChanged)
    def detectedKeymap(self) -> str:
        """Get auto-detected keymap."""
        if self._locale_detection_result:
            return self._locale_detection_result.keymap
        return ""

    @Property(str, notify=localeDataChanged)
    def detectionSource(self) -> str:
        """Get detection source (geoip, cmdline, efi, default)."""
        if self._locale_detection_result:
            return self._locale_detection_result.source
        return ""

    @Property(float, notify=localeDataChanged)
    def detectionConfidence(self) -> float:
        """Get detection confidence (0.0-1.0)."""
        if self._locale_detection_result:
            return self._locale_detection_result.confidence
        return 0.0

    def _load_locale_auto_detection_config(self) -> None:
        """Load auto-detection configuration from locale job config."""
        for job_def in self._engine.config.normalize_jobs():
            if job_def.name == "locale":
                self._locale_auto_detection_config = job_def.config.get("auto_detection", {})
                break
        if self._debug:
            print(f"[Engine] Locale auto-detection config: {self._locale_auto_detection_config}")

    def _run_locale_detection(self) -> None:
        """Run locale auto-detection if enabled."""
        if not self._locale_auto_detection_config.get("enabled", False):
            if self._debug:
                print("[Engine] Locale auto-detection disabled")
            return

        detector = LocaleDetector.from_config(self._locale_auto_detection_config)
        self._locale_detection_result = detector.detect()

        if self._debug:
            result = self._locale_detection_result
            print(
                f"[Engine] Auto-detected locale: {result.language} "
                f"(source: {result.source}, confidence: {result.confidence})"
            )
            print(f"[Engine] Auto-detected timezone: {result.timezone}")
            print(f"[Engine] Auto-detected keymap: {result.keymap}")

        # Apply detected values if confidence is high enough
        threshold = self._locale_auto_detection_config.get("confidence_threshold", 0.8)
        if self._locale_detection_result.confidence >= threshold:
            self._selections["locale"] = self._locale_detection_result.language
            self._selections["timezone"] = self._locale_detection_result.timezone
            self._selections["keymap"] = self._locale_detection_result.keymap
            if self._debug:
                print("[Engine] Applied auto-detected locale settings")
            # Emit signal to update QML UI with detected values
            self._update_keyboard_variants(self._selections["keymap"])
            self.selectionsChanged.emit()

    @Slot()
    def loadLocaleData(self) -> None:
        """Load locale, timezone, and keymap data."""
        if self._debug:
            print("[Engine] Loading locale data...")

        # Load auto-detection config and run detection
        self._load_locale_auto_detection_config()
        self._run_locale_detection()

        # Load locales from LocaleJob
        self._locales_model = list(LocaleJob.COMMON_LOCALES)

        # Build native names model
        self._locales_model_native = []
        for locale_code in self._locales_model:
            native_name = LOCALE_NATIVE_NAMES.get(locale_code, locale_code)
            self._locales_model_native.append({"code": locale_code, "name": native_name})

        # Load timezones from system
        locale_job = LocaleJob()
        self._timezones_model = locale_job._get_available_timezones()

        # Load keymaps from LocaleJob
        self._keymaps_model = list(LocaleJob.COMMON_KEYMAPS)

        if self._debug:
            print(f"[Engine] Loaded {len(self._locales_model)} locales")
            print(f"[Engine] Loaded {len(self._timezones_model)} timezones")
            print(f"[Engine] Loaded {len(self._keymaps_model)} keymaps")

        self.localeDataChanged.emit()

    # =========================================================================
    # User Selections Properties
    # =========================================================================

    @Property(str, notify=selectionsChanged)
    def selectedLocale(self) -> str:
        """Get selected locale."""
        return str(self._selections.get("locale", "en_US.UTF-8"))

    @Slot(str)
    def setSelectedLocale(self, locale: str) -> None:
        """Set selected locale and update font/keymap if needed."""
        if self._selections.get("locale") != locale:
            old_locale = self._selections.get("locale", "en_US.UTF-8")
            self._selections["locale"] = locale

            if self._debug:
                print(f"[Engine] Locale set to: {locale}")

            # Auto-derive keymap from locale
            derived_keymap = self._derive_keymap_from_locale(locale)
            if self._selections.get("keymap") != derived_keymap:
                self._selections["keymap"] = derived_keymap
                self._update_keyboard_variants(derived_keymap)
                if self._debug:
                    print(f"[Engine] Keymap auto-derived to: {derived_keymap}")

            # Check if font needs to change (Latin <-> non-Latin transition)
            old_needs_unicode = self._needs_unicode_font(old_locale)
            new_needs_unicode = self._needs_unicode_font(locale)
            if old_needs_unicode != new_needs_unicode:
                if self._debug:
                    font = self.UNICODE_FONT_FAMILY if new_needs_unicode else "system default"
                    print(f"[Engine] Font changed to: {font}")
                self.systemFontChanged.emit()

            self.selectionsChanged.emit()

    @Property(str, notify=selectionsChanged)
    def selectedTimezone(self) -> str:
        """Get selected timezone."""
        return str(self._selections.get("timezone", "UTC"))

    @Slot(str)
    def setSelectedTimezone(self, timezone: str) -> None:
        """Set selected timezone."""
        if self._selections.get("timezone") != timezone:
            self._selections["timezone"] = timezone
            if self._debug:
                print(f"[Engine] Timezone set to: {timezone}")
            self.selectionsChanged.emit()

    @Property(str, notify=selectionsChanged)
    def selectedKeymap(self) -> str:
        """Get selected keyboard layout."""
        return str(self._selections.get("keymap", "us"))

    @Slot(str)
    def setSelectedKeymap(self, keymap: str) -> None:
        """Set selected keyboard layout and update available variants."""
        if self._selections.get("keymap") != keymap:
            self._selections["keymap"] = keymap

            # Update keyboard variants for new layout
            self._update_keyboard_variants(keymap)

            if self._debug:
                print(f"[Engine] Keymap set to: {keymap}")
                print(f"[Engine] Available variants: {self._keyboard_variants_model}")
            self.selectionsChanged.emit()

    @Property(str, notify=selectionsChanged)
    def selectedKeyboardVariant(self) -> str:
        """Get selected keyboard variant."""
        return str(self._selections.get("keyboardVariant", "qwerty"))

    @Slot(str)
    def setSelectedKeyboardVariant(self, variant: str) -> None:
        """Set selected keyboard variant."""
        if self._selections.get("keyboardVariant") != variant:
            self._selections["keyboardVariant"] = variant
            if self._debug:
                print(f"[Engine] Keyboard variant set to: {variant}")
            self.selectionsChanged.emit()

    def _update_keyboard_variants(self, keymap: str) -> None:
        """Update keyboard variants model based on selected keymap."""
        # Extract base layout code (e.g., "us" from "us" or "fr_CA" from "fr")
        base_layout = keymap.split("_")[0] if "_" in keymap else keymap

        # Get variants for this layout (default to qwerty if unknown)
        self._keyboard_variants_model = self._keyboard_variants.get(base_layout, ["qwerty"])

        # Auto-select first variant if current one is not available
        current_variant = self._selections.get("keyboardVariant", "")
        if current_variant not in self._keyboard_variants_model:
            self._selections["keyboardVariant"] = self._keyboard_variants_model[0]

        self.keyboardVariantsChanged.emit()

    @Property(str, notify=selectionsChanged)
    def username(self) -> str:
        """Get username."""
        return str(self._selections.get("username", ""))

    @Slot(str)
    def setUsername(self, username: str) -> None:
        """Set username."""
        if self._selections.get("username") != username:
            self._selections["username"] = username
            self.selectionsChanged.emit()

    @Property(str, notify=selectionsChanged)
    def fullName(self) -> str:
        """Get full name."""
        return str(self._selections.get("fullName", ""))

    @Slot(str)
    def setFullName(self, fullName: str) -> None:
        """Set full name."""
        if self._selections.get("fullName") != fullName:
            self._selections["fullName"] = fullName
            self.selectionsChanged.emit()

    @Property(str, notify=selectionsChanged)
    def hostname(self) -> str:
        """Get hostname."""
        return str(self._selections.get("hostname", ""))

    @Slot(str)
    def setHostname(self, hostname: str) -> None:
        """Set hostname."""
        if self._selections.get("hostname") != hostname:
            self._selections["hostname"] = hostname
            self.selectionsChanged.emit()

    @Property(str, notify=selectionsChanged)
    def password(self) -> str:
        """Get password (for internal use, not displayed)."""
        return str(self._selections.get("password", ""))

    @Slot(str)
    def setPassword(self, password: str) -> None:
        """Set password."""
        if self._selections.get("password") != password:
            self._selections["password"] = password
            self.selectionsChanged.emit()

    @Property(bool, notify=selectionsChanged)
    def autoLogin(self) -> bool:
        """Get auto-login setting."""
        return bool(self._selections.get("autoLogin", False))

    @Slot(bool)
    def setAutoLogin(self, autoLogin: bool) -> None:
        """Set auto-login setting."""
        if self._selections.get("autoLogin") != autoLogin:
            self._selections["autoLogin"] = autoLogin
            self.selectionsChanged.emit()

    @Property(bool, notify=selectionsChanged)
    def isAdmin(self) -> bool:
        """Get admin privileges setting."""
        return bool(self._selections.get("isAdmin", True))

    @Slot(bool)
    def setIsAdmin(self, isAdmin: bool) -> None:
        """Set admin privileges setting."""
        if self._selections.get("isAdmin") != isAdmin:
            self._selections["isAdmin"] = isAdmin
            self.selectionsChanged.emit()

    # =========================================================================
    # Disk/Partition Properties
    # =========================================================================

    @Property(list, notify=disksChanged)
    def disksModel(self) -> list[dict[str, Any]]:
        """Get available disks for QML."""
        return self._disks_model

    @Property(str, notify=selectionsChanged)
    def selectedDisk(self) -> str:
        """Get selected disk."""
        return str(self._selections.get("disk", ""))

    @Slot(str)
    def setSelectedDisk(self, disk: str) -> None:
        """Set selected disk."""
        if self._selections.get("disk") != disk:
            self._selections["disk"] = disk
            if self._debug:
                print(f"[Engine] Disk set to: {disk}")
            self.selectionsChanged.emit()

    @Property(str, notify=selectionsChanged)
    def partitionMode(self) -> str:
        """Get partition mode (auto/manual)."""
        return str(self._selections.get("partitionMode", "auto"))

    @Slot(str)
    def setPartitionMode(self, mode: str) -> None:
        """Set partition mode."""
        if self._selections.get("partitionMode") != mode:
            self._selections["partitionMode"] = mode
            if self._debug:
                print(f"[Engine] Partition mode set to: {mode}")
            self.selectionsChanged.emit()

    @Slot()
    def refreshDisks(self) -> None:
        """Scan and refresh available disks."""
        if self._debug:
            print("[Engine] Scanning disks...")

        self._disks_model = []

        try:
            # Use lsblk to get disk information
            result = subprocess.run(
                [
                    "lsblk",
                    "-J",
                    "-o",
                    "NAME,SIZE,TYPE,MOUNTPOINT,MODEL,HOTPLUG,TRAN,ROTA",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                import json

                data = json.loads(result.stdout)

                for device in data.get("blockdevices", []):
                    if device.get("type") == "disk":
                        # Skip mounted system disks
                        has_mounted_partition = False
                        partitions = []

                        for child in device.get("children", []):
                            if child.get("mountpoint"):
                                has_mounted_partition = True
                            partitions.append(
                                {
                                    "name": child.get("name", ""),
                                    "size": child.get("size", ""),
                                    "fstype": child.get("fstype", ""),
                                    "mountpoint": child.get("mountpoint", ""),
                                }
                            )

                        # Determine disk type
                        is_removable = device.get("hotplug") == "1" or device.get("hotplug")
                        is_ssd = not device.get("rota", True)

                        if is_removable:
                            disk_type = "removable"
                        elif is_ssd:
                            disk_type = "ssd"
                        else:
                            disk_type = "hdd"

                        disk_info = {
                            "name": device.get("name", ""),
                            "size": device.get("size", ""),
                            "model": device.get("model", "").strip() if device.get("model") else "",
                            "type": disk_type,
                            "removable": is_removable,
                            "partitions": partitions,
                            "hasMounted": has_mounted_partition,
                        }
                        self._disks_model.append(disk_info)

        except subprocess.TimeoutExpired:
            if self._debug:
                print("[Engine] Disk scan timeout")
        except FileNotFoundError:
            if self._debug:
                print("[Engine] lsblk not found, using mock data")
            # Mock data for testing
            self._disks_model = [
                {
                    "name": "sda",
                    "size": "500G",
                    "model": "Samsung SSD 860",
                    "type": "ssd",
                    "removable": False,
                    "partitions": [
                        {"name": "sda1", "size": "512M", "fstype": "vfat", "mountpoint": ""},
                        {"name": "sda2", "size": "499.5G", "fstype": "ext4", "mountpoint": ""},
                    ],
                    "hasMounted": False,
                },
                {
                    "name": "nvme0n1",
                    "size": "1T",
                    "model": "WD Black SN850",
                    "type": "ssd",
                    "removable": False,
                    "partitions": [],
                    "hasMounted": False,
                },
            ]
        except Exception as e:
            if self._debug:
                print(f"[Engine] Disk scan error: {e}")

        if self._debug:
            print(f"[Engine] Found {len(self._disks_model)} disks")

        self.disksChanged.emit()

    # =========================================================================
    # Progress Properties
    # =========================================================================

    @Property(int, notify=progressChanged)
    def overallProgress(self) -> int:
        """Get overall installation progress (0-100)."""
        return self._overall_progress

    @Property(int, notify=progressChanged)
    def currentJobProgress(self) -> int:
        """Get current job progress (0-100)."""
        return self._current_job_progress

    @Property(str, notify=progressChanged)
    def currentJobName(self) -> str:
        """Get current job name."""
        return self._current_job_name

    @Property(str, notify=progressChanged)
    def currentJobMessage(self) -> str:
        """Get current job status message."""
        return self._current_job_message

    @Property(list, notify=progressChanged)
    def jobsList(self) -> list[dict[str, Any]]:
        """Get jobs list with status for progress view."""
        return self._jobs_list

    @Property(str, notify=progressChanged)
    def installationStatus(self) -> str:
        """Get installation status: idle, running, success, failed."""
        return self._installation_status

    @Property(str, notify=progressChanged)
    def errorMessage(self) -> str:
        """Get error message if installation failed."""
        return self._error_message

    def _update_jobs_list(self) -> None:
        """Update jobs list with current status."""
        self._jobs_list = []
        job_names = self._engine.get_job_names()
        current_idx = self.getCurrentJobIndex()

        for i, name in enumerate(job_names):
            if i < current_idx:
                status = "completed"
            elif i == current_idx:
                status = "running"
            else:
                status = "pending"

            self._jobs_list.append({"name": name, "status": status})

    # =========================================================================
    # Summary Properties
    # =========================================================================

    @Property(object, notify=selectionsChanged)  # type: ignore[arg-type]
    def selections(self) -> dict[str, Any]:
        """Get all selections for summary view."""
        return self._selections.copy()

    @Property(object, notify=progressChanged)  # type: ignore[arg-type]
    def installationSummary(self) -> dict[str, Any]:
        """Get installation summary for finished view."""
        branding = self._engine.get_branding()
        return {
            "distroName": branding.name,
            "distroVersion": branding.version,
            "targetDisk": self._selections.get("disk", ""),
            "diskSize": self._get_disk_size(self._selections.get("disk", "")),
            "installationTime": "N/A",  # Could track actual time
            "installedPackages": 0,  # Could track from packages job
        }

    def _get_disk_size(self, disk_name: str) -> str:
        """Get disk size by name."""
        for disk in self._disks_model:
            if disk.get("name") == disk_name:
                return str(disk.get("size", ""))
        return ""

    # =========================================================================
    # Actions
    # =========================================================================

    @Slot(str)
    def executeFinishAction(self, action: str) -> None:
        """Execute finish action: reboot, shutdown, or continue."""
        if self._debug:
            print(f"[Engine] Executing finish action: {action}")

        if self._dry_run:
            print(f"[Engine] Dry run: would execute {action}")
            return

        try:
            if action == "reboot":
                subprocess.run(["systemctl", "reboot"], check=False)
            elif action == "shutdown":
                subprocess.run(["systemctl", "poweroff"], check=False)
            # "continue" does nothing - user can manually close
        except Exception as e:
            if self._debug:
                print(f"[Engine] Action failed: {e}")

    @Slot()
    def applySelectionsToContext(self) -> None:
        """Apply user selections to the engine context before installation."""
        if self._debug:
            print("[Engine] Applying selections to context...")
            for key, value in self._selections.items():
                if key != "password":  # Don't log password
                    print(f"[Engine]   {key}: {value}")

        # The engine context will receive these during job execution
        # Jobs read from context.selections which we'll populate
        self._engine.set_selections(self._selections)

    # =========================================================================
    # Network Settings
    # =========================================================================

    @Slot()
    def launchNetworkSettings(self) -> None:
        """Launch the native network configuration tool."""
        if self._debug:
            print("[Engine] Launching network settings...")

        success, message = NetworkHelper.launch_network_settings()

        if success:
            if self._debug:
                print(f"[Engine] Network settings launched: {message}")
            self.networkSettingsLaunched.emit(message)
        else:
            if self._debug:
                print(f"[Engine] Network settings error: {message}")
            self.networkSettingsError.emit(message)

    @Slot(result=bool)
    def checkInternetConnectivity(self) -> bool:
        """Check if internet connectivity is available."""
        connected = NetworkHelper.check_internet_connectivity()
        if self._debug:
            print(f"[Engine] Internet connectivity: {connected}")
        self.internetStatusChanged.emit(connected)
        return connected

    @Slot()
    def recheckInternetStatus(self) -> None:
        """Re-check internet status and update requirements if changed."""
        if self._debug:
            print("[Engine] Re-checking internet status...")

        # Check connectivity (this emits internetStatusChanged signal)
        self.checkInternetConnectivity()

        # Re-run requirements check to update the internet requirement status
        if self._requirements_checker is not None:
            self.checkRequirements()

    # =========================================================================
    # Locale to Keymap Derivation
    # =========================================================================

    # Mapping from locale prefix to keyboard layout
    LOCALE_TO_KEYMAP: dict[str, str] = {
        # English variants
        "en_US": "us",
        "en_GB": "gb",
        "en_CA": "ca",
        "en_AU": "us",  # Australia uses US layout
        "en_NZ": "us",  # New Zealand uses US layout
        "en_IE": "ie",
        "en_ZA": "us",
        "en_IN": "in",
        # French variants
        "fr_FR": "fr",
        "fr_CA": "ca",
        "fr_BE": "be",
        "fr_CH": "ch",
        "fr_LU": "fr",
        # German variants
        "de_DE": "de",
        "de_AT": "de",
        "de_CH": "ch",
        "de_LU": "de",
        "de_LI": "ch",
        # Spanish variants
        "es_ES": "es",
        "es_MX": "latam",
        "es_AR": "latam",
        "es_CO": "latam",
        "es_CL": "latam",
        "es_PE": "latam",
        "es_VE": "latam",
        # Italian
        "it_IT": "it",
        "it_CH": "ch",
        # Portuguese variants
        "pt_BR": "br",
        "pt_PT": "pt",
        # Russian and Cyrillic
        "ru_RU": "ru",
        "uk_UA": "ua",
        "be_BY": "by",
        "bg_BG": "bg",
        "sr_RS": "rs",
        "mk_MK": "mk",
        # Chinese
        "zh_CN": "cn",
        "zh_TW": "tw",
        "zh_HK": "cn",
        "zh_SG": "cn",
        # Japanese
        "ja_JP": "jp",
        # Korean
        "ko_KR": "kr",
        # Arabic
        "ar_SA": "ara",
        "ar_EG": "ara",
        "ar_MA": "ara",
        "ar_DZ": "ara",
        "ar_TN": "ara",
        "ar_AE": "ara",
        # Hebrew
        "he_IL": "il",
        # Persian
        "fa_IR": "ir",
        # Hindi and Indian
        "hi_IN": "in",
        "bn_IN": "in",
        "bn_BD": "bd",
        "ta_IN": "in",
        "te_IN": "in",
        # Thai
        "th_TH": "th",
        # Vietnamese
        "vi_VN": "vn",
        # Indonesian and Malay
        "id_ID": "id",
        "ms_MY": "my",
        # Turkish
        "tr_TR": "tr",
        # Greek
        "el_GR": "gr",
        "el_CY": "gr",
        # Polish
        "pl_PL": "pl",
        # Dutch
        "nl_NL": "nl",
        "nl_BE": "be",
        # Nordic languages
        "sv_SE": "se",
        "sv_FI": "fi",
        "da_DK": "dk",
        "nb_NO": "no",
        "nn_NO": "no",
        "fi_FI": "fi",
        "is_IS": "is",
        # Czech and Slovak
        "cs_CZ": "cz",
        "sk_SK": "sk",
        # Hungarian
        "hu_HU": "hu",
        # Romanian
        "ro_RO": "ro",
        "ro_MD": "ro",
        # Baltic
        "lt_LT": "lt",
        "lv_LV": "lv",
        "et_EE": "ee",
        # Slavic
        "sl_SI": "si",
        "hr_HR": "hr",
        "bs_BA": "ba",
        # Catalan, Basque, Galician
        "ca_ES": "es",
        "eu_ES": "es",
        "gl_ES": "es",
        # Welsh, Irish
        "cy_GB": "gb",
        "ga_IE": "ie",
        # Albanian
        "sq_AL": "al",
        # Georgian
        "ka_GE": "ge",
        # Armenian
        "hy_AM": "am",
        # Kazakh
        "kk_KZ": "kz",
        # Uzbek
        "uz_UZ": "uz",
        # Afrikaans
        "af_ZA": "za",
    }

    def _derive_keymap_from_locale(self, locale: str) -> str:
        """
        Derive keyboard layout from locale.

        Args:
            locale: Locale string (e.g., "fr_FR.UTF-8", "de_DE.UTF-8")

        Returns:
            Keyboard layout code (e.g., "fr", "de", "us")
        """
        # Remove .UTF-8 suffix if present
        locale_base = locale.replace(".UTF-8", "").replace(".utf8", "")

        # Try exact match first
        if locale_base in self.LOCALE_TO_KEYMAP:
            return self.LOCALE_TO_KEYMAP[locale_base]

        # Try matching just the language part (e.g., "fr" from "fr_FR")
        lang_code = locale_base.split("_")[0]
        for locale_prefix, keymap in self.LOCALE_TO_KEYMAP.items():
            if locale_prefix.startswith(lang_code + "_"):
                return keymap

        # Default to US layout if no match
        return "us"

    @Slot(str, result=str)
    def deriveKeymapFromLocale(self, locale: str) -> str:
        """QML-accessible slot to derive keymap from locale."""
        return self._derive_keymap_from_locale(locale)
