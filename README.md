# Omnis Installer

**Installeur Linux universel, modulaire et moderne** - Alternative à Calamares.

| Métrique | Valeur |
|----------|--------|
| Version | `0.1.0` (Squelette) |
| Python | `>=3.11` |
| GUI | PySide6 (Qt6) + QML |
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

# Lancer les tests (34 tests)
pytest

# Démarrer l'installeur GLF OS (mode debug)
python -m omnis.main --debug
```

Output attendu :
```
Using config: config/examples/glfos.yaml
Theme base: /path/to/Omnis/config/themes/glfos
[Branding] Loaded: GLF OS
[Branding] Resolved: logos/logo.png -> file:///path/to/logos/logo.png
```

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
# Lancer tous les tests (34 tests)
pytest -v

# Vérification des types
mypy src/

# Linting + Formatage
ruff check src/
ruff format src/

# Démarrer avec une config spécifique
python -m omnis.main --config config/examples/glfos.yaml --debug
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

### v0.1.0 - Squelette (Actuel)

**Core**
- [x] Structure projet complète
- [x] Configuration pyproject.toml avec dépendances
- [x] Modèles Pydantic pour validation YAML
- [x] Interface Engine avec chargement config
- [x] Classe abstraite BaseJob

**GUI**
- [x] Interface QML avec branding dynamique
- [x] Bridge Python ↔ QML (BrandingProxy, EngineBridge)
- [x] Résolution des assets en URLs `file://`
- [x] Fallback UI si assets manquants

**Thèmes**
- [x] Système de thèmes modulaire
- [x] Thème GLF OS complet (10 logos, 5 wallpapers, 2 boot assets)
- [x] Documentation theming complète (400+ lignes)

**Tests**
- [x] 34 tests unitaires (pytest)
- [x] Tests de cohérence config/thème
- [x] Validation structure thème

### Roadmap

| Version | Objectif | Status |
|---------|----------|--------|
| v0.1.0 | Squelette + Thèmes | ✅ Actuel |
| v0.2.0 | IPC UI/Engine | 🔲 À faire |
| v0.3.0 | Jobs de base | 🔲 À faire |
| v1.0.0 | Release stable | 🔲 À faire |

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
