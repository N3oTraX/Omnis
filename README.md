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
│       │   └── qml/        # Fichiers QML
│       └── ipc/            # Communication UI <-> Engine
├── tests/
│   ├── unit/
│   └── integration/
├── docs/
│   ├── architecture/       # Documentation technique
│   ├── api/                # Référence API
│   └── branding/           # Guide personnalisation
├── config/
│   └── examples/           # Configurations exemples
├── omnis.yaml              # Configuration principale (exemple GLF OS)
└── pyproject.toml          # Configuration projet Python
```

---

## Installation (Développement)

### Prérequis

- Python 3.11+
- Qt6 libraries (système)
- Git

### Setup

```bash
# Cloner le repository
git clone https://github.com/glmusic/Omnis.git
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
# Lancer les tests
pytest

# Vérification des types
mypy src/

# Linting + Formatage
ruff check src/
ruff format src/
```

---

## Configuration (omnis.yaml)

Le fichier `omnis.yaml` définit le branding et le workflow d'installation :

```yaml
branding:
  name: "GLF OS"
  accent_color: "#7C3AED"

jobs:
  - welcome
  - locale
  - partition
  - install
  - bootloader
  - finished
```

Voir `config/examples/` pour des configurations complètes.

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

- [x] Structure projet
- [x] Configuration pyproject.toml
- [x] Interface Engine de base
- [x] Classe abstraite BaseJob
- [x] Template QML

### Roadmap

- [ ] v0.2.0 : IPC UI/Engine fonctionnel
- [ ] v0.3.0 : Jobs de base (welcome, locale, partition)
- [ ] v0.4.0 : Branding dynamique complet
- [ ] v1.0.0 : Release stable

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
