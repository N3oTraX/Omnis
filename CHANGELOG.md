# Changelog

Toutes les modifications notables du projet Omnis sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/lang/fr/).

## [Non publié]

Traitement complet des retours de la première ISO d'installation utilisant Omnis
(ticket glf-os#222, testeurs @Didic, @Pensionman, @Jeepyto, @Kuraudo). 31 points
remontés, ramenés à 21 causes racines. Analyse détaillée et suivi point par point :
`docs/suivi-tests-iso-0.6.0.md`.

### Fixed — bloquants

- **Impossible de relancer l'installeur après l'avoir fermé** : le moteur privilégié créait `/run/omnis` en `0700 root`, et l'interface non privilégiée levait une `PermissionError` en sondant le socket au lieu de le considérer comme absent. Le premier lancement passait, tous les suivants échouaient **jusqu'au redémarrage** (`/run` est un tmpfs), sans le moindre message quand l'installeur était lancé depuis le menu d'applications. Le sondage ne lève plus, et le moteur cède désormais la propriété du socket à l'utilisateur qui l'a lancé.
- **Outils manquants détectés après l'effacement du disque** : `udevadm`, `mkpasswd`/`openssl`, `nixos-generate-config` et `nixos-install` n'étaient réclamés qu'à l'exécution, soit **après** le `wipefs` du disque cible — un testeur s'est retrouvé avec un disque effacé et une installation irrécupérable. Tous les outils requis par les jobs configurés sont désormais vérifiés **avant le démarrage du premier job**, et `udevadm`, `mkpasswd` et `openssl` sont maintenant embarqués dans le paquet.
- **Le bouton « Réessayer » pouvait rejouer le partitionnement** : l'interface basculait sur l'écran d'installation sans attendre le moteur, et les refus côté moteur étaient silencieux. La bascule suit désormais le signal `installationStarted`, le bouton est inerte pendant une installation, et tout refus est remonté à l'utilisateur.
- **Aucune barrière sans droits root** : l'AppImage laissait dérouler tout l'assistant avant d'échouer sur `Permission denied: '/mnt/target'`. L'installation est maintenant refusée d'emblée, avec un message expliquant qu'il faut relancer avec les droits administrateur.
- **Le média d'installation était proposé comme disque cible** : l'exclusion reposait sur une sonde unique (`findmnt /`) inopérante sur un live ISO, où la racine est un tmpfs — la clé USB portant l'installeur apparaissait donc dans la liste. La détection croise désormais plusieurs sources : fichiers de backing des périphériques loop, points de montage du live et racines de montage amovible.

### Fixed — langue et clavier

- **Installeur en anglais malgré un démarrage en français** : sans paramètre `kbd.*` sur la ligne de commande du noyau, la détection retombait sur le GeoIP ; sans réseau au démarrage, le résultat par défaut arrivait avec une confiance trop basse pour être appliqué et l'interface restait en anglais. Une source de détection intermédiaire lit désormais la locale réellement active dans la session live (`LANG`/`LC_ALL`/`LC_CTYPE`, puis `/etc/locale.conf`, puis `localectl`), tentée avant le GeoIP et avec une confiance suffisante pour être retenue. *La cause première reste côté distribution : l'entrée de démarrage française de l'ISO ne passe aucun paramètre `kbd.*`, contrairement aux neuf autres.*
- **Disposition clavier bloquée en QWERTY US** : le modèle des variantes n'était alimenté que lorsque la détection de locale aboutissait. Quand elle échouait, la liste des variantes restait vide et la sélection conservait sa valeur par défaut `"qwerty"` — qui **n'est pas une variante XKB valide** et partait telle quelle dans le `services.xserver.xkb.variant` du système installé. Le modèle est désormais alimenté systématiquement et la variante par défaut est la variante vide.
- **La recherche ne renvoyait rien sur une saisie complète** : le filtre était correct, mais un espace parasite en début ou fin de saisie vidait la liste. La saisie est maintenant nettoyée avant filtrage.
- **Interface française sans accents** : `config/i18n/fr_FR.conf` était le seul catalogue latin intégralement désaccentué, alors que le catalogue Qt correspondant est accentué — les deux se mélangeaient dans le même écran. Les 255 lignes ont été ré-accentuées (clés, sections et paramètres de format inchangés).

### Fixed — disque et partitionnement

- **Disque cible jamais libéré quand un fichier d'échange était actif** : la libération désactivait l'échange uniquement sur les *partitions* du disque, alors qu'Omnis crée son échange sous forme de **fichier** (`/mnt/target/swapfile`) — jamais reconnu comme membre du disque. Le fichier restait actif, tenait le point de montage, le démontage échouait et le disque n'était jamais libéré. C'est le cas qui obligeait un testeur à passer par KDE Partition Manager pour « déverrouiller » son SSD. La désactivation de l'échange précède désormais les démontages et couvre les fichiers d'échange ; ils apparaissent aussi dans la liste des détenteurs en cas d'échec.
- **Démontage paresseux proscrit** : `umount -l` laissait survivre le fil de journal ext4, qui tenait ensuite le périphérique et faisait échouer le `wipefs` du run suivant sans que rien ne puisse plus le libérer. Remplacé par des tentatives temporisées et un échec explicite.
- **Le bouton « Appliquer » de l'éditeur manuel contournait la libération du disque** : il appelait directement l'application des opérations sans passer par le job de partitionnement, et pouvait donc attaquer un disque encore monté.
- **Chemin du flake GLF codé en dur** : `/iso/nixos` était le seul chemin testé, alors que l'ISO livrée porte son flake dans `iso-cfg`. La résolution parcourt désormais plusieurs candidats et retient le premier contenant réellement un `flake.nix` ; en cas d'échec, le message liste tous les chemins essayés.
- **Journaux mensongers** : plusieurs opérations journalisaient un succès sans consulter le code de retour (« Unmounted » après un démontage échoué, fermeture LUKS, désactivation de l'échange). La libération du disque, jusqu'ici totalement silencieuse, rend maintenant compte de ce qu'elle a libéré ou pas.

### Fixed — interface

- **« Votre système remplit toutes les exigences » affiché malgré des indicateurs orange** : le message n'avait que deux états, pilotés par un booléen déjà vrai en présence d'avertissements. Un troisième état distingue désormais « configuration minimale atteinte, mais certaines recommandations ne le sont pas », avec un indicateur orange.
- **Boutons radio et cases à cocher illisibles** : faute d'indicateur explicite, ces contrôles retombaient sur le style Fusion, dont la pastille dérive d'une couleur de palette que le projet éclaircit pour la lisibilité des champs de saisie. Le contraste entre coché et non coché tombait à 1,68:1 là où les règles d'accessibilité en exigent 3:1 — deux testeurs ont signalé ne pas distinguer leur choix. Indicateurs explicites, contraste porté à environ 4,6:1.
- **Politique de mot de passe perçue comme trop stricte** : la seule règle bloquante a toujours été la longueur minimale de 8 caractères, mais les quatre critères purement indicatifs s'affichaient avec une croix rouge et la jauge annonçait « Faible » en rouge. Les recommandations sont désormais visuellement neutres, séparées des exigences, et le rouge est réservé au seul blocage réel. **La règle n'a pas changé.**
- **Le clic sur un réseau Wi-Fi restait sans effet** : l'outil de configuration réseau était lancé en root, sans redescente vers la session utilisateur. La liste des réseaux s'affichait (bus système) mais la connexion échouait faute d'agent de secrets sur le bus de session. L'outil est maintenant lancé dans la session de l'utilisateur.
- **Les prérequis ne se rafraîchissaient pas après connexion** : un unique contrôle programmé 5 secondes après l'*ouverture* de l'outil réseau tombait systématiquement dans le vide. Remplacé par un sondage borné, arrêté dès la connexion établie, et complété par un bouton « Revérifier » explicite.
- **L'aperçu du disque ignorait toutes les options** : en mode automatique il affichait la géométrie *actuelle* du disque, si bien que changer de système de fichiers, de stratégie d'échange ou activer le chiffrement ne produisait aucun changement visible. Il projette désormais la disposition planifiée ; le fichier d'échange, qui ne crée aucune partition, apparaît comme une bande dédiée à l'intérieur de la racine.
- **Espace disque : un seul disque visible** : la vérification ne retenait que le plus gros périphérique, faisant disparaître le NVMe d'un testeur au profit d'un disque secondaire plus grand. Chaque disque est désormais évalué et listé individuellement.
- **Identification du disque cible** : la carte n'affichait que le nom noyau, qui peut permuter d'un démarrage à l'autre. Modèle, bus et numéro de série sont maintenant affichés.
- **Cartes graphiques récentes non reconnues** : la comparaison reposait sur une liste ordonnée à la main, où toute carte absente devenait non classable (cas d'une RX 9060 XT), et où la recherche par sous-chaîne classait « RX 9070 XT » sous « RX 9070 ». Un analyseur structuré (génération, palier, suffixe) rend le classement auto-extensible aux séries futures ; les listes ne servent plus que de table d'exceptions.

### Added

- Module `omnis.utils.session` : résolution de la session de bureau (identifiant utilisateur, bus de session, variables d'affichage) et enrobage d'une commande pour l'exécuter dans cette session. Factorisé depuis la gestion du clavier, désormais partagé avec le lancement de l'outil réseau.
- Vérification préalable de l'outillage (`preflight`) sur les jobs, exécutée par le moteur avant le premier job. Un job déclare ses binaires requis ; les alternatives sont exprimables (`mkpasswd` **ou** `openssl`).
- Planificateur de disposition automatique (`plan_auto_layout`), fonction pure partagée entre le job de partitionnement et l'aperçu de l'interface.

### Changed

- `udevadm` (via systemd), `mkpasswd` (via whois) et `openssl` ajoutés aux outils embarqués dans le paquet Nix. `nixos-generate-config` et `nixos-install` restent volontairement non embarqués — ils n'ont de sens que depuis le live ISO — mais leur absence est désormais détectée avant tout partitionnement.
- La résolution de la session utilisateur ne se rabat plus sur un identifiant codé en dur et respecte un bus de session déjà présent dans l'environnement.

## [0.6.1] - 2026-07-12

Correctifs remontés par les premiers testeurs : partitionnement bloqué après un formatage externe, et installeur en anglais pour les locales régionales.

### Fixed

- **Partitionnement bloqué après GParted** : un disque fraîchement formaté restait monté par le bureau (auto-montage udisks), et `wipefs` échouait en `EBUSY` (« Périphérique ou ressource occupé »). Omnis ne libérait que son propre point de montage. Le disque cible est désormais réellement libéré avant toute écriture : démontage de tous les points de montage qui s'y adossent, `swapoff`, fermeture des mappers LUKS/LVM/md.
- **Refus explicite du disque système** : Omnis refuse désormais de toucher au disque qui porte le système en cours d'exécution — aussi bien depuis l'ISO live (`/iso`, `/nix/.ro-store`) que depuis l'AppImage sur un système installé (`/`, `/usr`), où la racine est un vrai périphérique bloc. En cas de disque occupé, l'erreur nomme le détenteur au lieu d'afficher un `EBUSY` brut.
- **Installeur en anglais pour les variantes régionales** : choisir « AZERTY - (Belge) » au démarrage de l'ISO donnait une interface en **anglais**. La locale (`fr_BE`) était bien propagée, mais aucune traduction `fr_BE` n'existe et l'installeur retombait directement sur l'anglais. Un repli par famille de langue résout la locale d'affichage (`fr_BE` → `fr_FR`, `de_CH` → `de_DE`, `fr_CA` → `fr_FR`, `pt_PT` → `pt_BR`), sans modifier la locale système écrite sur la cible. 5 des 9 entrées clavier du menu de démarrage étaient concernées.
- **Job `locale` exécuté avant `partition`** : il écrivait dans la cible avant son montage, les fichiers atterrissaient sur le tmpfs live puis étaient masqués. Il s'exécute désormais après le partitionnement.
- **Bouton « Install » non traduit** : `Automatic`, `Manual` et `Install` étaient traduits mais marqués `unfinished`, donc exclus des catalogues `.qm` — ils restaient en anglais dans les 8 langues.
- Les journaux de nettoyage n'affichent plus « Unmounted » lorsque le démontage a échoué (logs trompeurs).

### Changed

- **8 langues complétées** : `de_DE`, `es_ES`, `it_IT`, `ja_JP`, `ko_KR`, `pt_BR`, `ru_RU` et `zh_CN` étaient proposées avec seulement 110/229 chaînes traduites (la moitié de l'interface en anglais) ; elles passent à 229/229. Ces traductions sont générées et **non relues par un locuteur natif** : voir `docs/i18n/RELECTURE.md`.

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
