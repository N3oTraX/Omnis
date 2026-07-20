# Omnis Installer

[![CI](https://github.com/N3oTraX/Omnis/actions/workflows/ci.yml/badge.svg)](https://github.com/N3oTraX/Omnis/actions/workflows/ci.yml)
[![Release AppImage](https://github.com/N3oTraX/Omnis/actions/workflows/release.yml/badge.svg)](https://github.com/N3oTraX/Omnis/actions/workflows/release.yml)
[![Release](https://img.shields.io/github/v/release/N3oTraX/Omnis?sort=semver)](https://github.com/N3oTraX/Omnis/releases)
[![Downloads](https://img.shields.io/github/downloads/N3oTraX/Omnis/total.svg)](https://github.com/N3oTraX/Omnis/releases)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-green.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Qt6](https://img.shields.io/badge/Qt-6-41CD52.svg)](https://www.qt.io/)

**Installeur Linux universel, modulaire et moderne** - Alternative à Calamares.

| Métrique | Valeur |
|----------|--------|
| Version | `0.6.1` |
| Python | `>=3.11` |
| GUI | PySide6 (Qt6) + QML |
| Livrable | AppImage standalone (Nix bundle, CI sur tag) |
| Tests | 963 tests unitaires |
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

# Lancer les tests (963 tests)
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

## Livrable standalone (AppImage)

Omnis se distribue aussi en **exécutable unique** (AppImage), généré par la CI sur chaque tag `v*` et reproductible (Nix bundle épinglé au tag). L'UI et le partitionnement sont portables ; l'installation réelle de GLF-OS reste liée à l'environnement live NixOS (`nixos-install`).

```bash
# Construire l'AppImage localement (nécessite Nix)
nix bundle .#omnis                      # -> ./omnis (AppImage unique)

# Ou récupérer la dernière release publiée
# https://github.com/N3oTraX/Omnis/releases
./omnis-<version>-x86_64.AppImage
```

Étude complète : [`docs/etude-packaging-standalone.md`](docs/etude-packaging-standalone.md).

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
# Lancer tous les tests (963 tests)
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

### v0.6.1 - Retours des premiers testeurs ✅

Correctifs remontés par les premiers tests sur ISO :

- [x] **Partitionnement bloqué après un formatage externe** : un disque fraîchement formaté restait monté par le bureau (auto-montage udisks) et `wipefs` échouait en `EBUSY`. Le disque cible est désormais réellement libéré avant toute écriture (démontage de tous les points de montage qui s'y adossent, `swapoff`, fermeture des mappers LUKS/LVM/md)
- [x] **Refus explicite du disque système** : Omnis refuse de toucher au disque portant le système en cours — depuis l'ISO live (`/iso`, `/nix/.ro-store`) comme depuis l'AppImage sur un système installé (`/`, `/usr`) ; en cas de disque occupé, l'erreur nomme le détenteur au lieu d'un `EBUSY` brut
- [x] **Installeur en anglais pour les variantes régionales** : repli par famille de langue (`fr_BE` → `fr_FR`, `de_CH` → `de_DE`, `fr_CA` → `fr_FR`, `pt_PT` → `pt_BR`) pour la langue d'affichage, sans modifier la locale système écrite sur la cible (5 des 9 entrées clavier du menu de démarrage étaient concernées)
- [x] **8 langues complétées** (`de`, `es`, `it`, `ja`, `ko`, `pt`, `ru`, `zh`) : de 110/229 à 229/229 chaînes — traductions générées, **non relues par des locuteurs natifs** (voir [`docs/i18n/RELECTURE.md`](docs/i18n/RELECTURE.md))
- [x] Job `locale` exécuté après `partition` (il écrivait dans la cible avant son montage), bouton « Install » traduit, journaux de nettoyage non trompeurs

### v0.6.0 - Installation GLF OS de bout en bout + barre granulaire ✅

Première installation GLF OS complète qui aboutit, avec progression honnête et session live réactive :

- [x] Installation NixOS de bout en bout menée à terme via `nixos-install --flake` (abandon de l'offload `nix build`, qui déclenchait une assertion interne de libnixstore avec nix 2.34.7)
- [x] Barre de progression **granulaire** : le dénominateur exact provient des totaux annoncés par `nixos-install` (dérivations à construire + chemins à récupérer), le compteur suit builds et substitutions, et l'affichage bascule dynamiquement d'indéterminé (pulse) à déterminé dès que le total est connu
- [x] Montage root/EFI avec type de système de fichiers explicite (`-t <fs>`) au lieu de l'auto-détection blkid périmée (qui tentait FAT sur de l'ext4 → « superbloc erroné ») ; démontage récursif de `/mnt/target` avant partitionnement (retry sûr)
- [x] Changement de **langue** appliqué dynamiquement à toutes les vues et à la config d'installation ; changement de **clavier** appliqué en live à la session utilisateur (via `runuser`, car Omnis tourne en root) et écrit dans la config d'installation ; 36 fichiers de traduction régénérés (fr_FR / en_US complètes)
- [x] Bureau live réactif pendant l'install : throttle CPU/IO (`nice`/`ionice`, `--cores`/`--max-jobs` à ~80 % des cœurs, `--option max-substitution-jobs`) et pile nix illimitée (évite un `SIGSEGV` au prébuild)
- [x] Chemin de log corrigé (`/var/log/omnis-install.log`) — l'anomalie « Failed to save logs: /tmp/omnis.log » est résolue

### v0.5.1 - AppImage lançable ✅

- [x] Correction de la résolution de configuration hors du répertoire courant : lancé depuis n'importe quel dossier (AppImage, install Nix), Omnis localise la config embarquée (`share/omnis/config`) au lieu de quitter sur `No configuration file found`
- [x] Premier AppImage réellement lançable en dehors de l'arbre source (thème + i18n + QML résolus depuis le bundle)

### v0.5.0 - Install NixOS, éditeur de partition, packaging ✅

- [x] Job d'installation NixOS complet : `configuration.nix`, `nixos-generate-config`, `nixos-install`, LUKS chiffré/non-chiffré, GPU multi-vendor, systemd-boot
- [x] Éditeur de partition manuel type GParted (create/delete/format/resize/flags, Apply live, table GPT auto)
- [x] Barre de progression réelle pendant `nixos-install` (parse nix internal-json)
- [x] Copie NetworkManager (wifi + filaire), i18n auto (boot GRUB + GeoIP, override manuel), durcissement permissions nix
- [x] Livrable **AppImage standalone** + CI de release (Nix bundle)
- [x] Validation installation de bout en bout (ISO GLF-OS) — livrée en v0.6.0

### v0.4.2 - Stabilisation ✅

- [x] Polish UI et animations
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
| v0.4.2 | Stabilisation UI | ✅ Terminé |
| v0.5.0 | Install NixOS + éditeur partition + packaging AppImage | ✅ Terminé |
| v0.5.1 | AppImage lançable (fix résolution config) | ✅ Terminé |
| v0.6.0 | Installation GLF OS E2E + barre granulaire + langue/clavier live | ✅ Terminé |
| v0.6.1 | Libération du disque cible + i18n des variantes régionales | ✅ Actuel |
| v0.7.0 | Slimming AppImage + intégration module GLF-OS | 🔲 À faire |
| v0.8.0 | Durcissement production (Polkit, IPC) | 🔲 À faire |
| v1.0.0 | Première release stable | 🔲 Release |

Roadmap détaillé : [`docs/roadmap.md`](docs/roadmap.md)

---

## Contribuer

Le projet suit un **flux GitOps** classique à deux branches longues :

- **`develop`** : branche d'intégration — tout le développement s'y fait (features, fixes).
- **`main`** : branche stable — reçoit `develop` par Pull Request ; les releases y sont taguées (`v*`).

```
feature/*  ──PR──►  develop  ──PR──►  main  ──tag vX.Y.Z──►  CI release (AppImage + changelog)
```

1. Partir de `develop` (`git switch develop`)
2. Créer une branche `feature/ma-feature` (ou committer sur `develop`)
3. Commits **Conventional Commits** (`feat:`, `fix:`, `docs:`…) — ils alimentent le changelog auto
4. Ouvrir une **PR vers `develop`**
5. Une PR **`develop` → `main`** puis un **tag `vX.Y.Z`** déclenchent la publication de la release

**Standards** : code typé (mypy strict), testé (pytest), conforme à ruff, commentaires minimaux.

---

## Licence

GPL-3.0-or-later - Voir [LICENSE](LICENSE)
