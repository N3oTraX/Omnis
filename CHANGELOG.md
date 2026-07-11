# Changelog

Toutes les modifications notables du projet Omnis sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/lang/fr/).

## [0.6.0] - 2026-07-11

Jalon : première installation GLF OS de bout en bout qui aboutit, avec barre de progression granulaire honnête.

### Added

- Barre de progression **granulaire** pendant `nixos-install` : le dénominateur exact provient des totaux annoncés par nix (« these N derivations will be built » / « these M paths will be fetched »), le compteur suit les builds et les substitutions (copies depuis le cache), et l'affichage bascule dynamiquement d'un mode indéterminé (pulse) à déterminé dès que le total est connu.
- Changement de **langue** appliqué dynamiquement à toutes les vues et propagé à la configuration d'installation.
- Changement de **clavier** appliqué en live à la session utilisateur (Wayland via `gsettings`/`input-sources`, X11 via `setxkbmap`), exécuté dans la session de l'utilisateur via `runuser` — Omnis tournant en root, l'uid est résolu depuis `SUDO_UID` pour rester portable (AppImage / multi-DE) — puis écrit dans la config d'installation.
- 36 fichiers de traduction régénérés (fr_FR et en_US complètes).

### Changed

- Installation NixOS via `nixos-install --flake` seul : abandon de l'offload `nix build`, qui déclenchait une assertion interne de libnixstore (nix 2.34.7) à la réalisation.
- Throttle CPU/IO pendant l'installation (`nice`/`ionice`, `--cores` et `--max-jobs` à ~80 % des cœurs, `--option max-substitution-jobs`) pour garder le bureau live réactif.
- Pile nix passée en illimitée pour éviter un `SIGSEGV` au prébuild.

### Fixed

- Montage root/EFI avec type de système de fichiers explicite (`-t <fs>`) au lieu de l'auto-détection blkid périmée, qui tentait FAT sur de l'ext4 (« superbloc erroné »).
- Démontage récursif de `/mnt/target` avant partitionnement (retry d'installation sûr).
- Chemin d'écriture des journaux corrigé (`/var/log/omnis-install.log`) : l'anomalie « Failed to save logs: /tmp/omnis.log » est résolue.

## [0.5.5] - 2026-07-10

### Fixed

- Progression fluide pendant la copie du système vers le disque.

## [0.5.4] - 2026-07-09

### Added

- Icônes de catégorie colorées pour les prérequis, pilotées par `theme.yaml`.

### Fixed

- Usernames réservés désormais rejetés ; correction de la progression réelle.
- Plugin `qsvg` ajouté à `QT_PLUGIN_PATH` (rendu SVG dans l'AppImage).
- Renommage du résolveur d'icône pour lever la collision avec `iconUrl`.

## [0.5.3] - 2026-07-08

### Added

- Polices embarquées via `<theme>/fonts` avec sélection dans `theme.yaml`.

### Changed

- `theme.yaml` documenté comme référence de branding.

### Fixed

- Polices et `fontconfig` embarqués dans l'AppImage.

## [0.5.2] - 2026-07-08

### Changed

- Smoke test exécuté hors de l'arbre source.

### Fixed

- Backend Qt Quick logiciel par défaut (rendu sans GPU).
- Moteur d'installation intégré dans l'AppImage (le fork `pkexec` étant impossible depuis le bundle).

## [0.5.1] - 2026-07-08

### Fixed

- Résolution de la configuration embarquée hors du répertoire courant : Omnis localise `share/omnis/config` au lieu de quitter sur « No configuration file found ». Premier AppImage réellement lançable.

## [0.5.0] - 2026-07-08

Installation NixOS de bout en bout, éditeur de partition manuel et livrable AppImage standalone.

### Added

- Job d'installation NixOS : `configuration.nix`, `nixos-generate-config`, `nixos-install`, systemd-boot, LUKS chiffré/non-chiffré, injection de la config GPU multi-vendor, durcissement des répertoires de build nix.
- Éditeur de partition manuel type GParted : create/delete/format/resize/flags, chemins `/dev` et numéros réels via `parted`, étiquette GPT auto sur disque vierge, blocage `bios_grub`, barre disque segmentée avec espace libre.
- Écran de choix de l'environnement de bureau (DE + saveurs GLF OS).
- Livrable AppImage standalone (Nix bundle), `package.nix` pour l'intégration ISO GLF et CI de release.
- Capture, affichage et upload des journaux d'installation ; icône d'application Omnis.
- Barre de progression live pendant `nixos-install`.

### Changed

- Pipeline NixOS pur (retrait des jobs packages/users) ; GPU non bloquant.
- Réception des paramètres GRUB `kbd.*` de l'ISO (langue/clavier).
- Bump de version 0.1.0 → 0.4.2 → 0.5.0.

### Fixed

- Passphrase LUKS jamais transmise (émission conditionnée à un binding périmé).
- Cible d'installation gardée montée pour le job nixos (cause d'échec d'installation).
- Résolution de `config/i18n` dans les layouts packagés ; lancement du moteur via l'entrypoint wrappé (pkexec/Nix).
- Nombreux correctifs de l'éditeur de partition (taille, synchro slider/champ, application de la file d'opérations en JSON, rafraîchissement après Apply).

## [0.4.x] - 2026-07-01

Jobs d'installation de base et Phase 1 de l'interface (entrée synthétique regroupant la ligne 0.4.x).

### Added

- Jobs : `LocaleJob`, `UsersJob`, `PartitionJob` (avec garde-fous de sécurité), `PackagesJob` (pacman/apt), `InstallJob`, `BootloaderJob`, `FinishedJob`, et chargeur de jobs dynamique.
- Vues QML Phase 1 : Locale, Users, Partition, Summary, Progress, Finished, avec navigation wizard multi-étapes.
- Internationalisation : détection automatique de la locale avec cascade de fallback, changement de langue en live, refonte de l'écran de création de compte traduit en 9 langues.
- Réseau : vérification de la connectivité internet, détection de l'environnement de bureau, support proxy système.

### Fixed

- Boucles de binding QML sur plusieurs vues ; layout LocaleView et boutons dupliqués ; logique de check GPU.

## [0.3.0] - 2025-12-04

### Added

#### Welcome Screen (WelcomeJob)
- Panel requirements avec checks système configurables (`jobs/requirements.py`)
  - RAM : Vérification mémoire disponible vs minimum requis
  - Disk : Espace disque disponible vs minimum requis
  - CPU : Nombre de cœurs vs minimum requis
  - EFI : Détection mode boot UEFI
  - Secure Boot : Détection état Secure Boot
  - Internet : Test connectivité réseau
  - Power : Détection alimentation secteur (laptop-only)
  - GPU : Détection cartes graphiques
- GPU Detector avancé (`jobs/gpu.py`)
  - Parsing lspci pour détection vendor/model
  - Extraction noms marketing courts (`_get_short_gpu_name()`)
  - Différenciation dGPU/iGPU avec tri automatique
  - Support AMD, NVIDIA, Intel
- Interface QML Requirements (`gui/qml/components/`)
  - `RequirementsOverlay.qml` : Panel overlay avec animation
  - `RequirementItem.qml` : Item individuel avec icône status
  - Tooltips informatifs sur hover (warn/fail)
  - Panel masqué si tous checks désactivés

#### Branding Links
- Modèle `BrandingLinks` dans `BrandingConfig` (`core/engine.py`)
  - website : URL site web distribution
  - website_label : Label optionnel pour le lien
  - git : URL repository Git
  - documentation : URL documentation
  - support : URL support/forum
- Lien website cliquable dans footer (`gui/qml/Main.qml`)
  - Visible uniquement sur écran Welcome
  - Full URL affichée avec hover effect
  - Aligné à droite (symétrique à "Powered by Omnis")

#### Configuration
- Section `links:` dans config YAML (`config/examples/glfos.yaml`)
- Section `requirements:` avec paramètres par check
  - `enabled` : Activer/désactiver le check
  - `type` : "error" ou "warning"
  - `minimum` : Valeur seuil pour checks quantitatifs

### Changed
- Footer QML restructuré pour affichage conditionnel du lien website
- `WelcomeView.qml` simplifié (lien déplacé vers `Main.qml`)

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
