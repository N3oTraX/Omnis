"""
Test d'intégration E2E : chaîne complète UI -> Engine -> UsersJob.

Couvre la régression Lot 1 : les slots QML stockent fullName/isAdmin/autoLogin
en camelCase, mais UsersJob lit fullname/is_admin/auto_login en snake_case.
applySelectionsToContext() doit normaliser les clés avant de les transmettre à
l'Engine, sinon les données utilisateur sont perdues (et is_admin reste True).

Ce test ÉCHOUE sur le code AVANT le fix Lot 1 et PASSE après.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# PySide6 est requis pour EngineBridge (QObject). Skip propre si absent.
pytest.importorskip("PySide6")

from omnis.core.engine import Engine  # noqa: E402
from omnis.gui.bridge import EngineBridge  # noqa: E402
from omnis.jobs.base import JobContext, JobResult  # noqa: E402
from omnis.jobs.users import UsersJob  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MINIMAL_CONFIG = PROJECT_ROOT / "config" / "examples" / "minimal.yaml"


@pytest.fixture(scope="session")
def qapp() -> object:
    """Fournit une QApplication unique pour toute la session de test."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def bridge(qapp: object) -> EngineBridge:
    """Construit un EngineBridge réel adossé à un Engine minimal.

    `qapp` garantit l'existence d'une QApplication avant l'instanciation du
    QObject ; la valeur n'est pas utilisée directement.
    """
    assert qapp is not None
    engine = Engine.from_config_file(MINIMAL_CONFIG)
    theme_base = MINIMAL_CONFIG.parent
    return EngineBridge(engine, theme_base, debug=False, dry_run=True)


class TestUiToEngineSelectionFlow:
    """Chaîne EngineBridge.set* -> applySelectionsToContext -> Engine."""

    def test_camel_case_keys_are_normalized(self, bridge: EngineBridge) -> None:
        """
        Régression Lot 1 : après applySelectionsToContext, l'Engine doit voir
        les clés snake_case attendues par UsersJob, avec les bonnes valeurs.
        """
        bridge.setUsername("john")
        bridge.setFullName("John Doe")
        bridge.setPassword("secret123")
        bridge.setHostname("mypc")
        bridge.setIsAdmin(False)
        bridge.setAutoLogin(True)

        bridge.applySelectionsToContext()

        selections = bridge._engine._selections

        # Les clés snake_case doivent exister avec les bonnes valeurs.
        assert selections.get("fullname") == "John Doe"
        assert selections.get("is_admin") is False
        assert selections.get("auto_login") is True

        # Les clés camelCase ne doivent PAS fuiter vers l'Engine.
        assert "fullName" not in selections
        assert "isAdmin" not in selections
        assert "autoLogin" not in selections

        # Les autres champs restent inchangés.
        assert selections.get("username") == "john"
        assert selections.get("password") == "secret123"
        assert selections.get("hostname") == "mypc"

    def test_root_password_keys_are_normalized(self, bridge: EngineBridge) -> None:
        """
        Lot v0.4.2 : les clés root saisies via les slots QML
        (setRootPassword/setRootSameAsUser) doivent être normalisées en
        snake_case (root_password/root_same_as_user) avant transmission à
        l'Engine, sans fuite des clés camelCase.
        """
        bridge.setRootPassword("rootpass1")
        bridge.setRootSameAsUser(False)

        bridge.applySelectionsToContext()

        selections = bridge._engine._selections
        assert selections.get("root_password") == "rootpass1"
        assert selections.get("root_same_as_user") is False
        assert "rootPassword" not in selections
        assert "rootSameAsUser" not in selections

    def test_root_same_as_user_defaults_true(self, bridge: EngineBridge) -> None:
        """
        Par défaut, rootSameAsUser vaut True et traverse la normalisation en
        root_same_as_user=True sans intervention de l'utilisateur.
        """
        bridge.applySelectionsToContext()

        selections = bridge._engine._selections
        assert selections.get("root_same_as_user") is True
        # La valeur par défaut du mot de passe root reste vide.
        assert selections.get("root_password") == ""

    def test_selections_property_keeps_camel_case(self, bridge: EngineBridge) -> None:
        """
        La Property QML `selections` (résumé d'install) doit conserver le
        camelCase : applySelectionsToContext ne doit pas muter self._selections.
        """
        bridge.setFullName("Jane Doe")
        bridge.setIsAdmin(False)

        bridge.applySelectionsToContext()

        summary = bridge.selections
        assert summary.get("fullName") == "Jane Doe"
        assert summary.get("isAdmin") is False
        assert "fullname" not in summary
        assert "is_admin" not in summary

    def test_full_chain_to_users_job_context(self, bridge: EngineBridge) -> None:
        """
        Chaîne complète jusqu'au JobContext : un UsersJob recevant le contexte
        construit à partir des sélections normalisées valide sans erreur.
        """
        bridge.setUsername("alice")
        bridge.setFullName("Alice Liddell")
        bridge.setPassword("wonderland42")
        bridge.setHostname("rabbit-hole")
        bridge.setIsAdmin(True)

        bridge.applySelectionsToContext()

        context = JobContext(selections=bridge._engine._selections.copy())
        job = UsersJob()
        result = job.validate(context)

        assert result.success is True
        assert context.selections["fullname"] == "Alice Liddell"
        assert context.selections["is_admin"] is True


class TestUsersJobRunGecos:
    """UsersJob.run() doit transmettre le GECOS à useradd."""

    @patch("omnis.jobs.users.subprocess.run")
    @patch("omnis.jobs.users.Path")
    def test_run_passes_gecos_to_useradd(
        self, mock_path: MagicMock, mock_subprocess: MagicMock
    ) -> None:
        """run() avec subprocess mocké appelle useradd avec -c "Nom Complet"."""
        # /etc/group existe et contient wheel (chemin admin).
        mock_group_file = MagicMock()
        mock_group_file.exists.return_value = True
        mock_group_file.read_text.return_value = "wheel:x:998:\n"
        mock_path.return_value.__truediv__.return_value = mock_group_file

        mock_subprocess.return_value = MagicMock(returncode=0)

        job = UsersJob()
        context = JobContext(
            target_root="/mnt",
            selections={
                "username": "john",
                "password": "secret123",
                "fullname": "John Doe",
                "is_admin": True,
                # pas de hostname pour limiter les appels système.
            },
        )

        result = job.run(context)
        assert result.success is True

        # Retrouver l'appel useradd parmi les invocations subprocess.run.
        useradd_calls = [
            call_args
            for call_args in mock_subprocess.call_args_list
            if "useradd" in call_args[0][0]
        ]
        assert len(useradd_calls) == 1

        cmd = useradd_calls[0][0][0]
        assert "-c" in cmd
        gecos_value = cmd[cmd.index("-c") + 1]
        assert gecos_value == "John Doe"

    @patch("omnis.jobs.users.UsersJob._set_password")
    @patch("omnis.jobs.users.subprocess.run")
    @patch("omnis.jobs.users.Path")
    def test_run_reports_is_admin_false(
        self,
        mock_path: MagicMock,
        mock_subprocess: MagicMock,
        mock_set_password: MagicMock,
    ) -> None:
        """run() doit refléter is_admin=False dans les données de résultat."""
        mock_group_file = MagicMock()
        mock_group_file.exists.return_value = True
        mock_group_file.read_text.return_value = "wheel:x:998:\n"
        mock_path.return_value.__truediv__.return_value = mock_group_file
        mock_subprocess.return_value = MagicMock(returncode=0)
        mock_set_password.return_value = JobResult.ok("Password set")

        job = UsersJob()
        context = JobContext(
            target_root="/mnt",
            selections={
                "username": "bob",
                "password": "secret123",
                "is_admin": False,
            },
        )

        result = job.run(context)
        assert result.success is True
        assert result.data["is_admin"] is False
