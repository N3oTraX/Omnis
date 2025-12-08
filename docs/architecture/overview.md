# Architecture Overview

> **Docs** > **Architecture** > Overview

---

## Concept Fondamental : Séparation UI / Engine

Omnis repose sur une séparation stricte entre deux processus :

| Composant | Contexte | Responsabilité |
|-----------|----------|----------------|
| **UI** | User (non-root) | Affichage, interactions utilisateur, collecte des choix |
| **Engine** | Root (privilégié) | Exécution des Jobs, opérations système |

Cette séparation garantit :
- **Sécurité** : L'UI n'a jamais accès root
- **Isolation** : Un crash UI ne corrompt pas l'installation
- **Auditabilité** : Seul l'Engine exécute des commandes privilégiées

---

## Communication IPC

```
┌──────────────┐                    ┌──────────────┐
│     UI       │◄──── Socket ──────►│    Engine    │
│  (PySide6)   │      Unix          │   (Python)   │
└──────────────┘                    └──────────────┘
       │                                   │
       ▼                                   ▼
   QML Views                          Job Runner
```

### Protocole

Messages JSON sur socket Unix :

```json
// UI → Engine : Requête
{"type": "start_job", "job": "partition", "params": {...}}

// Engine → UI : Réponse/Événement
{"type": "progress", "job": "partition", "percent": 45, "message": "..."}
```

---

## Système de Jobs

Un **Job** est une unité de travail atomique dans le processus d'installation.

### Interface BaseJob

```python
class BaseJob(ABC):
    @abstractmethod
    def run(self, context: JobContext) -> JobResult:
        """Exécute le job. Retourne succès ou erreur."""

    @abstractmethod
    def estimate_time(self) -> int:
        """Estimation en secondes pour l'UI."""

    def validate(self, context: JobContext) -> JobResult:
        """Validation avant exécution (optionnel)."""

    def cleanup(self, context: JobContext) -> None:
        """Nettoyage après exécution (optionnel)."""
```

### Cycle de Vie

```
   PENDING → RUNNING → COMPLETED
                ↓
              FAILED → (retry possible)
```

### Jobs Standards

| Job | Rôle | Status |
|-----|------|--------|
| `welcome` | Écran d'accueil, vérifications pré-installation | ✅ Implémenté |
| `requirements` | Checks système (RAM, Disk, CPU, EFI, Internet, GPU) | ✅ Implémenté |
| `locale` | Sélection langue, timezone, clavier + détection auto | ✅ Implémenté |
| `partition` | Partitionnement disque avec sécurité critique | ✅ Implémenté |
| `users` | Création utilisateurs, hostname, mot de passe | ✅ Implémenté |
| `packages` | Installation packages (pacman/apt support) | ✅ Implémenté |
| `gpu` | Détection GPU (dGPU/iGPU), drivers recommandés | ✅ Implémenté |
| `install` | Copie des fichiers système | ✅ Implémenté |
| `bootloader` | Installation GRUB/systemd-boot | ✅ Implémenté |
| `finished` | Résumé, nettoyage, reboot/shutdown | ✅ Implémenté |

---

## Configuration et Thèmes

Chaque distribution fournit son propre fichier de configuration + thème :

```
config/
├── examples/           # Configurations par distribution
│   ├── glfos.yaml      # GLF OS
│   ├── archlinux.yaml  # Arch Linux
│   └── minimal.yaml    # Template minimal
└── themes/             # Assets visuels
    └── glfos/
        ├── theme.yaml
        ├── logos/
        ├── wallpapers/
        └── boot/
```

### Structure d'une Configuration

```yaml
version: "1.0"

# Lien vers le dossier du thème (RELATIF à ce fichier config)
theme: "../themes/glfos"  # Si config dans config/examples/

branding:
  name: "GLF OS"
  version: "2025.1"

  # Couleurs de l'interface
  colors:
    primary: "#5597e6"
    background: "#1a1a1a"
    text: "#fffded"

  # Assets (chemins relatifs au dossier theme)
  assets:
    logo: "logos/logo.png"
    logo_small: "logos/logo-64.png"
    background: "wallpapers/dark.jpg"

  # Textes personnalisables
  strings:
    welcome_title: "Bienvenue sur GLF OS"
    install_button: "Installer"

jobs:
  - name: welcome
  - name: partition
    config:
      default_filesystem: ext4
  - name: bootloader
    config:
      type: grub
  - name: finished
```

### Système de Thèmes

Le système de thèmes sépare les assets visuels de la configuration :

```
omnis.yaml ──► theme: "config/themes/glfos"
                            │
                            ▼
              config/themes/glfos/
              ├── logos/logo.png    ◄── assets.logo
              └── wallpapers/dark.jpg ◄── assets.background
```

Avantages :
- Réutilisation des assets entre configurations
- Mise à jour indépendante des visuels
- Distribution de thèmes tiers

Documentation complète : [`docs/branding/theming.md`](../branding/theming.md)

### Résolution des Jobs

1. L'Engine lit `jobs` dans l'ordre
2. Chaque `name` est résolu vers `omnis.jobs.<name>.Job`
3. Le bloc `config` est injecté dans le constructeur du Job

---

## Flux d'Exécution

```
1. main.py démarre
   │
2. ├─► Fork UI (user context)
   │     └── Charge QML, affiche branding
   │
3. └─► Fork Engine (root context)
         │
4.       ├── Charge omnis.yaml
         │
5.       ├── Instancie les Jobs
         │
6.       └── Attend commandes IPC
                │
7.              ├── UI envoie "start"
                │
8.              └── Engine exécute Jobs séquentiellement
                      │
9.                    └── Chaque Job émet progress → UI
```

---

## Extensibilité

### Créer un Job Custom

```python
# omnis/jobs/my_custom_job.py
from omnis.jobs.base import BaseJob, JobContext, JobResult

class Job(BaseJob):
    name = "my_custom_job"
    description = "My custom installation step"

    def run(self, context: JobContext) -> JobResult:
        context.report_progress(50, "Working...")
        # Logique ici
        return JobResult.ok("Custom job completed")

    def estimate_duration(self) -> int:
        return 30  # secondes
```

Puis dans votre `omnis.yaml` :

```yaml
jobs:
  - name: my_custom_job
    config:
      option: value
```

---

## État d'Avancement (v0.4.2)

### Complété ✅

- [x] Socket IPC complet (protocol, transport, security, server, client)
- [x] Tous les jobs de base implémentés (10 jobs)
- [x] Tests unitaires complets (599 tests)
- [x] Système i18n avec 37 locales
- [x] Détection automatique de la locale
- [x] Live language switching
- [x] Phase 1 UI (tous les composants QML intégrés)
- [x] Network helper avec checks connectivité

### En Cours 🔄 (v0.4.2 - UsersView Integration)

- [ ] Tests unitaires validation UsersView
- [ ] Icons utilisateur (config/themes/glfos/icons/users/)
- [ ] Integration complète Engine ↔ UsersView
- [ ] Tests E2E UsersView ↔ UsersJob

### Planifié 📋

- [ ] v0.4.3: PartitionView Polish
- [ ] v0.4.4: SummaryView Polish
- [ ] v0.4.5: ProgressView Polish
- [ ] v0.4.6: FinishedView Polish
- [ ] v0.7.0: UI Complete Validation
- [ ] v1.0.0: GLFOS Installation Ready

Roadmap complet : [`docs/roadmap.md`](roadmap.md)
