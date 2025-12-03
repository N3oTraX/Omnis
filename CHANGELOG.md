# Changelog

Toutes les modifications notables du projet Omnis sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/lang/fr/).

## [0.2.0] - 2025-12-03

### Added

#### IPC (Inter-Process Communication)
- Protocole de messages JSON avec versioning (`protocol.py`)
- Transport Unix Socket avec framing length-prefix 4 bytes (`transport.py`)
- Validation de sécurité multi-couches (`security.py`)
  - Whitelist de commandes autorisées
  - Protection path traversal
  - Détection patterns d'injection shell
  - Limites de taille et profondeur
- Dispatcher de commandes avec handlers enregistrables (`dispatcher.py`)
- Serveur IPC multi-client avec threads (`server.py`)
  - Support connexions concurrentes
  - Broadcast d'événements
  - Graceful shutdown
- Client IPC pour processus UI (`client.py`)
  - Commandes synchrones et asynchrones
  - Subscription aux événements
  - Gestion reconnection

#### Launcher (Séparation UI/Engine)
- `EngineProcess` pour gestion du processus Engine (`launcher.py`)
- Élévation de privilèges via pkexec/sudo
- `create_engine_dispatcher()` avec handlers pour toutes les commandes
- `run_engine_server()` pour mode serveur isolé

#### CLI
- Flag `--engine` : Lancer en mode serveur IPC uniquement
- Flag `--socket PATH` : Spécifier chemin socket personnalisé
- Flag `--no-fork` : Mode développement sans fork Engine

#### Tests
- 72 nouveaux tests IPC (`test_ipc.py`)
  - Tests protocol (messages, serialization)
  - Tests transport (socket, framing)
  - Tests security (validation, sanitization)
  - Tests dispatcher (routing, handlers)
  - Tests server (multi-client, events)
  - Tests client (sync, async, events)
  - Tests intégration (workflows complets)
  - Tests launcher (process, handlers)

#### Documentation
- `docs/architecture/ipc.md` : Documentation technique IPC
- Mise à jour README avec modes d'exécution
- Documentation `--no-fork` pour développement

### Fixed
- Socket directory permissions : Ne plus chmod les répertoires système (`/tmp`)
- Race condition création répertoire socket avec `exist_ok=True`

### Changed
- Nombre total de tests : 34 → 122

## [0.1.0] - 2025-01-15

### Added

#### Core
- Structure projet initiale
- Configuration `pyproject.toml` avec dépendances
- Modèles Pydantic pour validation YAML (`engine.py`)
- Interface `Engine` avec chargement configuration
- Classe abstraite `BaseJob` (`jobs/base.py`)

#### GUI
- Interface QML avec branding dynamique (`gui/qml/Main.qml`)
- Bridge Python ↔ QML (`bridge.py`)
  - `BrandingProxy` pour exposition branding
  - `EngineBridge` pour orchestration
- Résolution assets en URLs `file://`
- Fallback UI si assets manquants

#### Thèmes
- Système de thèmes modulaire (`config/themes/`)
- Thème GLF OS complet
  - 10 logos (différentes tailles)
  - 5 wallpapers
  - 2 boot assets
- Documentation theming (`docs/branding/theming.md`)

#### Tests
- 34 tests unitaires initiaux
- Tests de cohérence config/thème
- Validation structure thème

#### CI/CD
- Pipeline GitHub Actions
- Tests lint, format, typecheck
- Tests unitaires automatisés

### Documentation
- README complet avec Quick Start
- Architecture overview
- Guide personnalisation thèmes
