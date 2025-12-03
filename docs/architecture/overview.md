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
```

### Cycle de Vie

```
   PENDING → RUNNING → COMPLETED
                ↓
              FAILED → (retry possible)
```

### Jobs Standards

| Job | Rôle |
|-----|------|
| `welcome` | Écran d'accueil, vérifications pré-installation |
| `locale` | Sélection langue, timezone, clavier |
| `partition` | Partitionnement disque (manuel/auto) |
| `install` | Copie des fichiers système |
| `bootloader` | Installation GRUB/systemd-boot |
| `users` | Création utilisateurs |
| `finished` | Résumé, redémarrage |

---

## Configuration YAML

Chaque distribution fournit son propre fichier `omnis.yaml` :

```
config/examples/
├── glfos.yaml       # GLF OS
├── archlinux.yaml   # Arch Linux
└── minimal.yaml     # Template minimal
```

Structure d'une configuration :

```yaml
branding:
  name: "Distribution Name"
  colors:
    primary: "#7C3AED"
    background: "#1F2937"
  assets:
    logo: "assets/logo.svg"
  strings:
    welcome_title: "Bienvenue"

jobs:
  - name: welcome
  - name: partition
    config:
      default_filesystem: ext4
      allow_manual_partitioning: true
  - name: bootloader
    config:
      type: grub
  - name: finished
```

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

## Prochaines Étapes

- [ ] Implémentation socket IPC
- [ ] Jobs de base fonctionnels
- [ ] Tests d'intégration UI/Engine
