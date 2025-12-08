# Omnis Installer

[![CI](https://github.com/N3oTraX/Omnis/actions/workflows/ci.yml/badge.svg)](https://github.com/N3oTraX/Omnis/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-green.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Qt6](https://img.shields.io/badge/Qt-6-41CD52.svg)](https://www.qt.io/)

**Installeur Linux universel, modulaire et moderne** - Alternative à Calamares.

| Métrique | Valeur |
|----------|--------|
| Version | `0.4.2` (en cours) |
| Python | `>=3.11` |
| GUI | PySide6 (Qt6) + QML |
| IPC | Unix Socket + JSON |
| Tests | 599 tests unitaires |
| i18n | 37 locales supportées |
| Licence | GPL-3.0-or-later |

---

## Qu'est-ce qu'Omnis ?

Omnis est un installeur graphique pour distributions Linux conçu pour être :

- **Modulaire** : Architecture basée sur des Jobs indépendants et configurables
- **Sécurisé** : Séparation stricte UI (utilisateur) / Engine (root) via IPC
- **Personnalisable** : Branding dynamique via YAML (couleurs, logos, textes)
- **Multi-distro** : Support NixOS, Arch, Debian, et autres via modules adaptés

---

## Structure du Projet

```
Omnis/
├── src/
│   └── omnis/
│       ├── core/           # Moteur d'exécution (Engine)
│       │   └── engine.py   # Chargement config + orchestration Jobs
│       ├── jobs/           # Modules d'installation
│       │   └── base.py     # Interface abstraite BaseJob
│       ├── gui/            # Interface utilisateur
│       │   ├── bridge.py   # Pont Python ↔ QML
│       │   └── qml/        # Fichiers QML
│       └── ipc/            # Communication UI <-> Engine
├── tests/
│   ├── unit/
│   └── integration/
├── docs/
│   ├── architecture/       # Documentation technique
│   └── branding/           # Guide personnalisation
├── config/
│   ├── examples/           # Configurations par distribution
│   │   ├── glfos.yaml      # GLF OS
│   │   ├── archlinux.yaml  # Arch Linux
│   │   └── minimal.yaml    # Template minimal
│   └── themes/             # Thèmes (assets visuels)
│       └── glfos/          # Thème GLF OS complet
├── omnis.yaml.example      # Template de configuration
└── pyproject.toml          # Configuration projet Python
```

---

## Système de Thèmes

Omnis utilise un système de thèmes modulaire permettant de personnaliser entièrement l'apparence de l'installeur pour chaque distribution.

### Structure d'un Thème

```
config/themes/<nom-theme>/
├── theme.yaml              # Définition complète du thème
├── logos/
│   ├── logo.png            # Logo principal (fond sombre)
│   ├── logo_light.png      # Logo (fond clair)
│   ├── logo-128.png        # Tailles multiples
│   └── ...
├── wallpapers/
│   ├── dark.jpg            # Fond d'écran par défaut
│   └── ...
└── boot/
    ├── bootloader.png      # Splash bootloader
    └── efi-icon.png        # Icône EFI
```

### Lier un Thème à une Configuration

Dans votre fichier `omnis.yaml` :

```yaml
# Chemin relatif vers le dossier du thème (relatif à ce fichier config)
theme: "../themes/glfos"  # Si config dans config/examples/

branding:
  name: "GLF OS"
  version: "2025.1"

  # Référence aux assets du thème (chemins relatifs au dossier theme)
  assets:
    logo: "logos/logo.png"
    logo_small: "logos/logo-64.png"
    background: "wallpapers/dark.jpg"

  colors:
    primary: "#5597e6"
    background: "#1a1a1a"
    text: "#fffded"
```

### Créer un Thème pour votre Distribution

1. Créer le dossier : `config/themes/<votre-distro>/`
2. Ajouter vos assets (logos, wallpapers, boot)
3. Créer `theme.yaml` avec les métadonnées
4. Référencer le thème dans votre config

Documentation complète : [`docs/branding/theming.md`](docs/branding/theming.md)

---

## Quick Start

```bash
# Cloner et installer
git clone https://github.com/N3oTraX/Omnis.git
cd Omnis
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Lancer les tests (599 tests)
pytest

# Démarrer l'installeur GLF OS (mode développement)
python -m omnis.main --debug --no-fork
```

Output attendu :
```
Using config: config/examples/glfos.yaml
Theme base: /path/to/Omnis/config/themes/glfos
```

---

## Modes d'Exécution

Omnis utilise une architecture **UI/Engine séparée** pour la sécurité :

```
┌─────────────────────────────────────────────────────────────┐
│                     Mode Production                          │
├─────────────────────────────────────────────────────────────┤
│   UI Process (user)          Engine Process (root)          │
│   ┌──────────────┐           ┌──────────────┐               │
│   │  QML/Qt GUI  │◄─────────►│  Jobs/Disk   │               │
│   │  (ton user)  │   IPC     │  (pkexec)    │               │
│   └──────────────┘  Socket   └──────────────┘               │
│                   /run/omnis/ipc.sock                       │
└─────────────────────────────────────────────────────────────┘
```

### Commandes Disponibles

| Mode | Commande | Description |
|------|----------|-------------|
| **Développement** | `python -m omnis.main --debug --no-fork` | Processus unique, pas de root |
| **Production** | `python -m omnis.main` | Fork engine avec pkexec |
| **Engine seul** | `python -m omnis.main --engine --socket /tmp/test.sock` | Serveur IPC isolé |

### Pourquoi `--no-fork` ?

En mode normal, Omnis lance automatiquement un processus Engine avec privilèges root via `pkexec`. Cela pose des problèmes en développement :

| Problème | Cause |
|----------|-------|
| Popup d'authentification | pkexec demande le mot de passe |
| Répertoire `/run/omnis/` | Nécessite root pour création |
| Debugging complexe | Deux processus à suivre |

Le flag `--no-fork` résout ces problèmes en exécutant tout dans un seul processus utilisateur :

```bash
# Développement UI/UX (recommandé)
python -m omnis.main --debug --no-fork

# Test avec config spécifique
python -m omnis.main --config config/examples/archlinux.yaml --debug --no-fork
```

### Configuration Production (Polkit)

En mode production, `pkexec` nécessite une policy polkit pour autoriser l'élévation de privilèges.

Documentation complète : [`docs/deployment/polkit.md`](docs/deployment/polkit.md)

---

## Installation (Développement)

### Prérequis

- Python 3.11+
- Qt6 libraries (système)
- Git

### Setup Complet

```bash
# Cloner le repository
git clone https://github.com/N3oTraX/Omnis.git
cd Omnis

# Créer l'environnement virtuel
python3 -m venv .venv
source .venv/bin/activate

# Installer les dépendances (mode développement)
pip install -e ".[dev]"

# Vérifier l'installation
python -c "from omnis.core.engine import Engine; print('OK')"
```

### Commandes Développement

```bash
# Lancer tous les tests (599 tests)
pytest -v

# Tests IPC uniquement
pytest tests/unit/test_ipc.py -v

# Vérification des types
mypy src/

# Linting + Formatage
ruff check src/
ruff format src/

# Démarrer en mode développement (recommandé)
python -m omnis.main --config config/examples/glfos.yaml --debug --no-fork

# Démarrer le serveur engine isolé (pour tests IPC)
python -m omnis.main --engine --socket /tmp/omnis_test.sock --debug
```

---

## Configuration

Chaque distribution fournit son propre fichier `omnis.yaml`. Copiez le template et personnalisez :

```bash
cp omnis.yaml.example omnis.yaml
# ou utilisez une config existante
cp config/examples/archlinux.yaml omnis.yaml
```

Structure d'une configuration :

```yaml
branding:
  name: "Ma Distribution"
  colors:
    primary: "#3B82F6"
  strings:
    welcome_title: "Bienvenue"

jobs:
  - name: welcome
  - name: locale
    config:
      default_language: "fr_FR"
  - name: partition
  - name: install
  - name: finished
```

Configurations disponibles dans `config/examples/` :
- `glfos.yaml` - GLF OS (complet)
- `archlinux.yaml` - Arch Linux
- `minimal.yaml` - Template minimal

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    UI Process (User)                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                   QML Interface                      │    │
│  │         (Main.qml + Composants dynamiques)           │    │
│  └─────────────────────────────────────────────────────┘    │
│                            │                                 │
│                       IPC (Socket)                           │
│                            │                                 │
└────────────────────────────┼────────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────────┐
│                    Engine (Root)                             │
│                            ▼                                 │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                 Job Orchestrator                     │    │
│  │    ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐     │    │
│  │    │ Job1 │→│ Job2 │→│ Job3 │→│ Job4 │→│ Job5 │     │    │
│  │    └──────┘ └──────┘ └──────┘ └──────┘ └──────┘     │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

Documentation complète : [`docs/architecture/overview.md`](docs/architecture/overview.md)

---

## État du Projet

### v0.4.2 - Stabilisation (En cours)

- [ ] Polish UI et animations
- [ ] Tests d'intégration end-to-end
- [ ] Documentation utilisateur

### v0.4.1 - i18n & Locale Detection ✅

Internationalisation complète :

- [x] Détection automatique locale avec cascade fallback (système → DE → défaut)
- [x] Live language switching dans l'UI (changement sans redémarrage)
- [x] 37 locales supportées (fr, de, es, it, pt, ru, zh, ja, ko, ar, etc.)
- [x] Scripts de gestion traductions (`fix_translation_encoding.py`, `compile_translations.sh`)
- [x] Documentation i18n complète (`docs/translations.md`)

Network & Connectivity :

- [x] NetworkHelper : Vérification connectivité internet
- [x] Détection environnement desktop (KDE, GNOME, etc.)
- [x] Support proxy système

Améliorations UI :

- [x] Keyboard variants auto-update lors de la sélection locale
- [x] Fix layout LocaleView et boutons dupliqués
- [x] GPU check amélioré dans requirements

### v0.4.0 - Jobs de Base + Phase 1 UI ✅

Jobs d'installation :

- [x] LocaleJob : Configuration langue, timezone, clavier
- [x] UsersJob : Création utilisateur, mot de passe, options admin
- [x] PartitionJob : Partitionnement automatique avec sécurité critique
- [x] PackagesJob : Installation packages (pacman/apt)
- [x] InstallJob : Copie système vers cible
- [x] BootloaderJob : Installation GRUB/systemd-boot
- [x] FinishedJob : Résumé et nettoyage

Interface utilisateur (Phase 1) :

- [x] LocaleView : Sélection locale/timezone/keymap
- [x] UsersView : Formulaire utilisateur complet
- [x] PartitionView : Sélection disque et mode
- [x] SummaryView : Récapitulatif avant installation
- [x] ProgressView : Barre de progression jobs
- [x] FinishedView : Écran de fin (reboot/shutdown)
- [x] Navigation wizard multi-étapes

### v0.3.0 - WelcomeJob ✅

Welcome Screen (Écran d'accueil complet) :

- [x] Requirements panel avec checks système configurables
- [x] Checks disponibles : RAM, Disk, CPU, EFI, Secure Boot, Internet, Power, GPU
- [x] GPU : Détection dGPU/iGPU, noms courts marketing, tri par type
- [x] Power : Détection laptop-only (filtre batteries wireless)
- [x] Tooltips informatifs sur hover (warn/fail)
- [x] Panel masqué automatiquement si tous checks désactivés
- [x] Lien website cliquable dans footer (configurable)
- [x] BrandingLinks model (website, git, documentation, support)

### v0.2.0 - IPC ✅

IPC (Inter-Process Communication) :

- [x] Protocole JSON avec framing length-prefix (4 bytes big-endian)
- [x] Transport Unix Socket sécurisé (permissions 0600/0700)
- [x] Server multi-client avec threads
- [x] Client avec commandes synchrones/asynchrones
- [x] Système d'événements (broadcast)
- [x] Validation de sécurité (whitelist, path traversal, injection)
- [x] Dispatcher avec handlers enregistrables

Launcher (Séparation UI/Engine) :

- [x] EngineProcess avec élévation de privilèges (pkexec/sudo)
- [x] Mode `--no-fork` pour développement
- [x] Mode `--engine` pour serveur IPC isolé
- [x] Handlers pour toutes les commandes (PING, GET_STATUS, GET_BRANDING, etc.)

### v0.1.0 - Squelette ✅

Core :

- [x] Structure projet complète
- [x] Configuration pyproject.toml avec dépendances
- [x] Modèles Pydantic pour validation YAML
- [x] Interface Engine avec chargement config
- [x] Classe abstraite BaseJob

GUI :

- [x] Interface QML avec branding dynamique
- [x] Bridge Python ↔ QML (BrandingProxy, EngineBridge)
- [x] Résolution des assets en URLs `file://`
- [x] Fallback UI si assets manquants

Thèmes :

- [x] Système de thèmes modulaire
- [x] Thème GLF OS complet (10 logos, 5 wallpapers, 2 boot assets)
- [x] Documentation theming complète

### Roadmap

| Version | Objectif | Status |
|---------|----------|--------|
| v0.1.0 | Squelette + Thèmes | ✅ Terminé |
| v0.2.0 | IPC UI/Engine | ✅ Terminé |
| v0.3.0 | WelcomeJob + Requirements | ✅ Terminé |
| v0.4.0 | Jobs de base + Phase 1 UI | ✅ Terminé |
| v0.4.1 | i18n + Locale Detection | ✅ Terminé |
| v0.4.2 | UsersView Integration | 🔄 En cours |
| v0.4.3 | PartitionView Polish | 🔲 À faire |
| v0.4.4 | SummaryView Polish | 🔲 À faire |
| v0.4.5 | ProgressView Polish | 🔲 À faire |
| v0.4.6 | FinishedView Polish | 🔲 À faire |
| v0.5.0 | E2E Integration Tests | 🔲 À faire |
| v0.6.0 | IPC Production Ready | 🔲 À faire |
| v0.7.0 | UI Complete Validation | 🔲 Milestone |
| v0.8.0 | GLFOS Module Integration | 🔲 À faire |
| v0.9.0 | Production Hardening | 🔲 À faire |
| v1.0.0 | First Stable Release | 🔲 Release |

Roadmap détaillé : [`docs/roadmap.md`](docs/roadmap.md)

---

## Contribuer

1. Fork le projet
2. Créer une branche (`git checkout -b feature/ma-feature`)
3. Commit (`git commit -m 'Add: ma feature'`)
4. Push (`git push origin feature/ma-feature`)
5. Ouvrir une Pull Request

**Standards** : Code typé, testé, conforme à ruff.

---

## Licence

GPL-3.0-or-later - Voir [LICENSE](LICENSE)
