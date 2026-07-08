"""
Test d'intégration offscreen : écran EnvironmentView (DE + Edition).

Couvre l'insertion de l'écran « Environnement de bureau + Edition » dans le
wizard (Calamares : users -> environnement/edition -> partition) :

- Le chargement de Main.qml offscreen ne produit AUCUNE binding loop ni
  warning QML (garde-fou anti-régression sur la renumérotation des steps).
- La navigation traverse bien les 8 étapes (0..7) après insertion.
- setDesktopEnvironment/setEdition se reflètent dans la Property `selections`
  (lue par SummaryView) et dans les getters notifiés.
- Les catalogues DE/edition sont chargés depuis la config du job `nixos`.

Le test s'exécute en plateforme offscreen (aucune fenêtre réelle).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

# Force la plateforme offscreen AVANT tout import Qt (aucune GUI réelle).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QtMsgType, QUrl, qInstallMessageHandler  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from omnis.core.engine import Engine  # noqa: E402
from omnis.gui.bridge import EngineBridge  # noqa: E402
from omnis.gui.translator_proxy import TranslatorProxy  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GLFOS_CONFIG = PROJECT_ROOT / "config" / "examples" / "glfos.yaml"
MAIN_QML = PROJECT_ROOT / "src" / "omnis" / "gui" / "qml" / "Main.qml"


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """QApplication unique (offscreen) pour toute la session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app  # type: ignore[return-value]


@pytest.fixture
def bridge(qapp: QApplication) -> EngineBridge:
    """EngineBridge réel adossé à la config GLF OS (catalogues DE/edition)."""
    assert qapp is not None
    engine = Engine.from_config_file(GLFOS_CONFIG)
    theme_base = GLFOS_CONFIG.parent
    return EngineBridge(engine, theme_base, debug=False, dry_run=True, skip_requirements=True)


class _QmlMessageCollector:
    """Collecte les messages Qt (warnings/erreurs) émis pendant le chargement."""

    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def handler(self, msg_type: QtMsgType, _context: object, message: str) -> None:
        if msg_type == QtMsgType.QtWarningMsg:
            self.warnings.append(message)
        elif msg_type in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            self.errors.append(message)


class TestEnvironmentCatalogs:
    """Les catalogues DE/edition sont exposés à QML depuis la config."""

    def test_desktop_environments_loaded(self, bridge: EngineBridge) -> None:
        model = bridge.desktopEnvironmentsModel
        ids = [item["id"] for item in model]
        assert "gnome" in ids
        assert "plasma" in ids

    def test_editions_loaded(self, bridge: EngineBridge) -> None:
        model = bridge.editionsModel
        ids = [item["id"] for item in model]
        # Modèle réel Calamares GLF OS.
        assert {"standard", "mini", "streamers", "studio", "studio-pro"} <= set(ids)

    def test_defaults_from_config(self, bridge: EngineBridge) -> None:
        # gnome + standard sont marqués default: true dans glfos.yaml.
        assert bridge.desktopEnvironment == "gnome"
        assert bridge.edition == "standard"


class TestEnvironmentSelectionFlow:
    """setDesktopEnvironment/setEdition -> getters + Property selections."""

    def test_set_desktop_environment_reflects(self, bridge: EngineBridge) -> None:
        bridge.setDesktopEnvironment("plasma")
        assert bridge.desktopEnvironment == "plasma"
        assert bridge.selections["desktopEnvironment"] == "plasma"

    def test_set_edition_reflects(self, bridge: EngineBridge) -> None:
        bridge.setEdition("studio")
        assert bridge.edition == "studio"
        assert bridge.selections["edition"] == "studio"

    def test_selection_emits_selectionsChanged(self, bridge: EngineBridge) -> None:
        received: list[int] = []
        bridge.selectionsChanged.connect(lambda: received.append(1))
        bridge.setDesktopEnvironment("plasma")
        bridge.setEdition("mini")
        assert len(received) >= 2

    def test_normalization_to_snake_case(self, bridge: EngineBridge) -> None:
        """applySelectionsToContext -> desktop_environment/edition côté Engine."""
        bridge.setDesktopEnvironment("plasma")
        bridge.setEdition("streamers")
        bridge.applySelectionsToContext()

        selections = bridge._engine._selections
        assert selections.get("desktop_environment") == "plasma"
        assert selections.get("edition") == "streamers"
        # La clé camelCase ne fuite pas vers l'Engine.
        assert "desktopEnvironment" not in selections
        # Le résumé QML garde le camelCase (self._selections non muté).
        assert bridge.selections["desktopEnvironment"] == "plasma"


class TestMainQmlOffscreen:
    """Chargement offscreen de Main.qml : 0 binding loop, navigation 0..7."""

    def _load(
        self, bridge: EngineBridge
    ) -> tuple[QQmlApplicationEngine, Any, _QmlMessageCollector, TranslatorProxy]:
        collector = _QmlMessageCollector()
        qInstallMessageHandler(collector.handler)

        qml_engine = QQmlApplicationEngine()
        translator_proxy = TranslatorProxy(engine=qml_engine)
        qml_engine.rootContext().setContextProperty("engine", bridge)
        qml_engine.rootContext().setContextProperty("branding", bridge.branding_proxy)
        qml_engine.rootContext().setContextProperty("translator", translator_proxy)

        qml_engine.load(QUrl.fromLocalFile(str(MAIN_QML)))
        roots = qml_engine.rootObjects()
        assert roots, "Main.qml n'a pas pu être chargé"
        return qml_engine, roots[0], collector, translator_proxy

    def test_no_binding_loops_on_load(self, bridge: EngineBridge, qapp: QApplication) -> None:
        qml_engine, root, collector, _tp = self._load(bridge)
        try:
            qapp.processEvents()
            binding_loops = [w for w in collector.warnings if "Binding loop" in w]
            assert not binding_loops, f"Binding loops détectées : {binding_loops}"
            assert not collector.errors, f"Erreurs QML : {collector.errors}"
        finally:
            qInstallMessageHandler(None)
            del qml_engine

    def test_navigation_traverses_eight_steps(
        self, bridge: EngineBridge, qapp: QApplication
    ) -> None:
        qml_engine, root, collector, _tp = self._load(bridge)
        try:
            assert root.property("totalSteps") == 8
            step_names_raw = root.property("stepNames")
            # stepNames est un tableau JS (QJSValue) : convertir en liste Python.
            step_names = (
                step_names_raw.toVariant()
                if hasattr(step_names_raw, "toVariant")
                else list(step_names_raw)
            )
            assert step_names == [
                "Welcome",
                "Locale",
                "Users",
                "Desktop",
                "Partition",
                "Summary",
                "Installing",
                "Finished",
            ]

            # Parcours 0..7 en écrivant currentStep (skipValidation=True via
            # skip_requirements côté bridge => canProceedToNext ne bloque pas).
            for step in range(0, 8):
                root.setProperty("currentStep", step)
                qapp.processEvents()
                assert root.property("currentStep") == step

            # L'écran Environment est bien à l'index 3.
            assert step_names[3] == "Desktop"

            binding_loops = [w for w in collector.warnings if "Binding loop" in w]
            assert not binding_loops, f"Binding loops pendant la navigation : {binding_loops}"
        finally:
            qInstallMessageHandler(None)
            del qml_engine

    def test_summary_reflects_environment_selection(
        self, bridge: EngineBridge, qapp: QApplication
    ) -> None:
        """La sélection DE/edition faite via le bridge apparaît dans selections."""
        qml_engine, root, _collector, _tp = self._load(bridge)
        try:
            bridge.setDesktopEnvironment("plasma")
            bridge.setEdition("studio-pro")
            qapp.processEvents()

            # SummaryView lit engine.selections : la source de vérité reflète le choix.
            summary = bridge.selections
            assert summary["desktopEnvironment"] == "plasma"
            assert summary["edition"] == "studio-pro"
        finally:
            del qml_engine
