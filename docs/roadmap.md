# Omnis Installer - Roadmap de Versioning

**Document cree**: 2025-12-08
**Derniere mise a jour**: 2025-12-08
**Objectif v1.0.0**: Installation GLFOS fonctionnelle
**Objectif v2.0.0**: Installeur universel multi-distribution (comme Calamares)

---

## Etat Actuel (v0.4.1 → v0.4.2)

### Vues QML Integrees dans Main.qml

| Step | Vue | Etat | Validation |
|------|-----|------|------------|
| 0 | WelcomeView | Complete | Requirements, i18n |
| 1 | LocaleView | Complete | i18n, keyboard variants |
| 2 | UsersView | En cours | Validation + icons en cours |
| 3 | PartitionView | Basique | Necessite polish |
| 4 | SummaryView | Basique | Necessite polish |
| 5 | ProgressView | Basique | Necessite polish |
| 6 | FinishedView | Basique | Necessite polish |

### Jobs Implementes (10 jobs)

welcome, requirements, locale, partition, users, packages, gpu, install, bootloader, finished

---

## Phase 1: Polish des Vues (v0.4.x)

### v0.4.2 - UsersView Integration

**Focus**: Configuration compte utilisateur

- [x] Validation username (regex: `^[a-z][a-z0-9_-]*$`)
- [x] Validation hostname (regex: `^[a-z][a-z0-9-]*$`)
- [x] Password strength indicator (NIST SP 800-63B)
- [x] Password criteria checklist
- [ ] Tests unitaires validation (test_users_validation.py)
- [ ] Icons utilisateur (icons/users/)
- [ ] Integration engine.setUsername/setPassword/etc.
- [ ] Tests E2E UsersView <-> UsersJob

### v0.4.3 - PartitionView Polish

**Focus**: Selection disque securisee

- [ ] Visualisation graphique des partitions
- [ ] Warning modal pour operations destructives
- [ ] Support mode automatique/manuel
- [ ] Tests E2E PartitionView <-> PartitionJob
- [ ] Dry-run mode pour tests sans risque

### v0.4.4 - SummaryView Polish

**Focus**: Recapitulatif avant installation

- [ ] Affichage complet des selections
- [ ] Edition rapide (liens vers autres vues)
- [ ] Estimation duree installation
- [ ] Confirmation finale avant install
- [ ] Tests E2E validation selections

### v0.4.5 - ProgressView Polish

**Focus**: Progression installation

- [ ] Barre de progression dual (global + job)
- [ ] Logs detailles expandable
- [ ] Gestion erreurs avec recovery options
- [ ] Cancel operation avec cleanup
- [ ] Tests E2E progression jobs

### v0.4.6 - FinishedView Polish

**Focus**: Ecran de fin

- [ ] Success/Failure etats distincts
- [ ] Summary installation realisee
- [ ] Actions: Reboot/Shutdown/Continue
- [ ] Cleanup automatique
- [ ] Tests E2E finished flow

---

## Phase 2: Integration Testing (v0.5.x)

### v0.5.0 - E2E Integration Tests & Security

**Focus**: Tests end-to-end complets + Correctifs securite

**Tests E2E:**

- [ ] Test wizard flow complet (Welcome -> Finished)
- [ ] Test mode dry-run integral
- [ ] Test IPC UI <-> Engine
- [ ] Test i18n switching dans workflow
- [ ] Couverture tests >= 80%

**Securite (CVE Patches):**

- [ ] Fix CVE-2025-32463: Remplacer arch-chroot par systemd-nspawn/chroot
- [ ] Fix CVE-2024-12084: Version check rsync >= 3.4.0
- [ ] Audit securite des jobs (commandes privilegiees)
- [ ] Tests unitaires securite (injection, permissions)

### v0.5.1 - Accessibility & Polish

- [ ] WCAG 2.1 AA compliance
- [ ] Keyboard navigation complete
- [ ] Screen reader support
- [ ] High contrast mode
- [ ] RTL language support (ar, he)

---

## Phase 3: IPC Production (v0.6.x)

### v0.6.0 - IPC Validation Production

**Focus**: Separation UI/Engine en production

- [ ] Tests pkexec elevation
- [ ] Tests socket permissions (0600/0700)
- [ ] Tests multi-client concurrent
- [ ] Security audit IPC
- [ ] Performance benchmarks

### v0.6.1 - Error Handling & Recovery

- [ ] Graceful degradation
- [ ] Rollback mechanisms
- [ ] Error reporting system
- [ ] Crash recovery
- [ ] Logs structured

---

## Phase 4: UI Complete (v0.7.0)

### v0.7.0 - Complete UI Validation

**Milestone**: Interface utilisateur completement validee

- [ ] Tous les tests UI green
- [ ] Tous les tests E2E green
- [ ] Audit UX complet
- [ ] Performance UI optimisee (< 100ms transitions)
- [ ] Documentation utilisateur complete
- [ ] Screenshots pour documentation

**Criteres d'acceptation**:

- 100% couverture tests vues
- 0 bugs critiques UI
- Temps demarrage < 3s
- Smooth 60fps animations

---

## Phase 5: GLFOS Integration (v0.8.x - v0.9.x)

### v0.8.0 - GLFOS Module Base

**Focus**: Premier module d'installation

- [ ] Module GLFOS packages list
- [ ] Post-install scripts GLFOS
- [ ] Configuration GRUB GLFOS
- [ ] Theme GLFOS complet valide
- [ ] Tests installation GLFOS (VM)

### v0.8.1 - GLFOS Customization

- [ ] Selection packages optionnels
- [ ] Configuration desktop environment
- [ ] Network configuration post-install
- [ ] User customization options

### v0.9.0 - Production Hardening

- [ ] Security audit complet
- [ ] Performance optimization
- [ ] Memory leak detection
- [ ] Stress testing (100+ installations)
- [ ] Documentation deploiement

### v0.9.1 - Release Candidate

- [ ] Beta testing externe
- [ ] Bug fixes from feedback
- [ ] Final polish
- [ ] Release notes
- [ ] Migration guide

---

## Release (v1.0.0)

### v1.0.0 - First Stable Release

**Objectif**: Installation GLFOS fonctionnelle

- [ ] Installation complete GLFOS validee
- [ ] Documentation complete (user + dev)
- [ ] Packaging (.deb, .rpm, AUR)
- [ ] CI/CD release pipeline
- [ ] Website/landing page

**Criteres d'acceptation**:

- Installation GLFOS de A a Z fonctionnelle
- 0 bugs bloquants
- Documentation a jour
- Tests coverage >= 85%
- Performance validee sur hardware reel

---

## Phase 6: Multi-Distribution Foundation (v1.1.x)

### v1.1.0 - Abstractions Distro-Agnostic

**Focus**: Architecture extensible pour multi-distribution

**Interfaces Abstraites:**

- [ ] Interface `PackageManager` (apt, pacman, dnf, nix)
- [ ] Interface `BootloaderManager` (grub, systemd-boot, refind)
- [ ] Interface `LocaleManager` (systemd-localed, locale-gen)
- [ ] Interface `UserManager` (useradd, passwd, chage)
- [ ] Factory pattern pour instanciation selon distro

**Detection Distribution:**

- [ ] `DistributionDetector` via /etc/os-release
- [ ] Auto-selection des implementations selon distro
- [ ] Configuration YAML adaptive (source, packages, scripts)

**Refactoring Jobs:**

- [ ] Extraire logique NixOS-specific de chaque job
- [ ] Implementer Strategy pattern dans les jobs
- [ ] Tests unitaires pour chaque interface

### v1.1.1 - Support Arch Linux

**Focus**: Premiere distribution additionnelle

- [ ] Implementation `PacmanPackageManager`
- [ ] Implementation `ArchBootloaderManager`
- [ ] Configuration YAML exemple Arch Linux
- [ ] Tests Docker Arch Linux
- [ ] Documentation: "Ajouter une distribution"

### v1.1.2 - Support Debian/Ubuntu

**Focus**: Famille Debian

- [ ] Implementation `AptPackageManager`
- [ ] Implementation `DebianBootloaderManager`
- [ ] Support detection Debian vs Ubuntu vs derivees
- [ ] Configuration YAML exemple Debian
- [ ] Tests Docker Debian + Ubuntu

---

## Phase 7: Multi-Distribution Expansion (v1.2.x)

### v1.2.0 - Support Fedora/RHEL

**Focus**: Famille Red Hat

- [ ] Implementation `DnfPackageManager`
- [ ] Implementation `FedoraBootloaderManager`
- [ ] Support SELinux configuration
- [ ] Configuration YAML exemple Fedora
- [ ] Tests Docker Fedora

### v1.2.1 - Support NixOS Declaratif

**Focus**: Mode declaratif NixOS (configuration.nix)

- [ ] Generation `configuration.nix` depuis selections
- [ ] Support `nixos-install` natif
- [ ] Gestion flakes optionnelle
- [ ] Migration GLFOS vers mode declaratif
- [ ] Tests NixOS VM

### v1.2.2 - CI/CD Multi-Distribution

**Focus**: Validation automatisee

- [ ] GitHub Actions matrix (Arch, Debian, Fedora, NixOS)
- [ ] Tests integration Docker par distro
- [ ] Tests E2E installation complete (VM)
- [ ] Rapport couverture multi-distro
- [ ] Badge compatibilite README

---

## Phase 8: Plugin System (v1.3.x)

### v1.3.0 - Architecture Plugin

**Focus**: Systeme de plugins comme Calamares

**Plugin Infrastructure:**

- [ ] Interface `OmnisPlugin` (module.yaml + main.py)
- [ ] Loader dynamique de plugins
- [ ] Configuration plugins dans settings.yaml
- [ ] Hooks pre/post installation

**Plugin Types:**

- [ ] ViewPlugin (pages QML additionnelles)
- [ ] JobPlugin (jobs custom)
- [ ] ThemePlugin (themes complets)

### v1.3.1 - Plugins Communautaires

- [ ] Template plugin (cookiecutter/copier)
- [ ] Documentation plugin developer guide
- [ ] Repository plugins officiels
- [ ] Validation/signature plugins

---

## Phase 9: Parite Calamares (v1.4.x - v2.0.0)

### v1.4.0 - Modules Additionnels

**Focus**: Modules manquants vs Calamares

- [ ] Module `netinstall` (installation reseau)
- [ ] Module `packagechooser` (selection packages)
- [ ] Module `services` (systemd/openrc)
- [ ] Module `displaymanager` (SDDM, GDM, LightDM)
- [ ] Module `shellprocess` (scripts custom)

### v1.4.1 - Distributions Additionnelles

- [ ] Support openSUSE (zypper)
- [ ] Support Void Linux (xbps)
- [ ] Support Alpine Linux (apk)
- [ ] Support Gentoo (portage) - optionnel

### v2.0.0 - Installeur Universel

**Milestone**: Parite fonctionnelle avec Calamares core

**Criteres d'acceptation**:

- Support 10+ distributions Linux
- 25+ modules/jobs disponibles
- Plugin system fonctionnel
- Documentation complete (user + dev + plugin)
- Performance validee multi-hardware
- Communaute active (contributions externes)

**Metriques cibles v2.0.0**:

| Metrique | v1.0.0 | v2.0.0 |
|----------|--------|--------|
| Distributions | 1 | 10+ |
| Jobs/Modules | 12 | 25+ |
| Plugins | 0 | 10+ |
| Tests coverage | 85% | 90%+ |
| Contributors | 1-2 | 5+ |

---

## Metriques Actuelles

| Metrique | v0.4.1 | v0.7.0 | v1.0.0 | v2.0.0 |
|----------|--------|--------|--------|--------|
| Tests unitaires | 599 | 800+ | 1000+ | 1500+ |
| Couverture | ~70% | 80%+ | 85%+ | 90%+ |
| Locales | 37 | 37 | 40+ | 50+ |
| Jobs/Modules | 10 | 10 | 12+ | 25+ |
| Vues QML | 7 | 7 | 7 | 10+ |
| Distributions | 1 | 1 | 1 | 10+ |
| Plugins | 0 | 0 | 0 | 10+ |

---

## Conventions de Versioning

### v0.x.x - Development (GLFOS Focus)

- **v0.4.x**: Une vue par version mineure (polish + tests)
- **v0.5.x**: Integration testing + Security patches
- **v0.6.x**: IPC production ready
- **v0.7.0**: UI milestone (tout valide)
- **v0.8.x**: GLFOS integration
- **v0.9.x**: Production hardening
- **v1.0.0**: First stable release (GLFOS)

### v1.x.x - Multi-Distribution

- **v1.1.x**: Abstractions + Arch + Debian
- **v1.2.x**: Fedora + NixOS declaratif + CI multi-distro
- **v1.3.x**: Plugin system
- **v1.4.x**: Modules additionnels + distros supplementaires
- **v2.0.0**: Installeur universel (parite Calamares)

**Semantic Versioning**:

- MAJOR (1.x.x): Breaking changes, major features
- MINOR (x.4.x): New features, views, backward compatible
- PATCH (x.x.2): Bug fixes, polish, no new features

---

## Resume Visuel

```
┌─────────────────────────────────────────────────────────────────┐
│                    GLFOS FOCUS (v0.x - v1.0)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  v0.4.2  UsersView      ─┐                                      │
│  v0.4.3  PartitionView   │ Phase 1: Polish Vues                 │
│  v0.4.4  SummaryView     │                                      │
│  v0.4.5  ProgressView    │                                      │
│  v0.4.6  FinishedView   ─┘                                      │
│                                                                 │
│  v0.5.0  E2E + Security ─┐ Phase 2: Integration + CVE Patches   │
│  v0.5.1  Accessibility  ─┘                                      │
│                                                                 │
│  v0.6.0  IPC Prod       ─┐ Phase 3: IPC                         │
│  v0.6.1  Error Handling ─┘                                      │
│                                                                 │
│  v0.7.0  UI Complete    ─── Milestone: UI Validee               │
│                                                                 │
│  v0.8.0  GLFOS Base     ─┐                                      │
│  v0.8.1  GLFOS Custom    │ Phase 5: GLFOS                       │
│  v0.9.0  Hardening       │                                      │
│  v0.9.1  RC             ─┘                                      │
│                                                                 │
│  v1.0.0  RELEASE        ─── 🎯 First Stable (GLFOS Only)        │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                 MULTI-DISTRIBUTION (v1.1 - v2.0)                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  v1.1.0  Abstractions   ─┐                                      │
│  v1.1.1  Arch Linux      │ Phase 6: Foundation Multi-Distro     │
│  v1.1.2  Debian/Ubuntu  ─┘                                      │
│                                                                 │
│  v1.2.0  Fedora/RHEL    ─┐                                      │
│  v1.2.1  NixOS Declaratif│ Phase 7: Expansion                   │
│  v1.2.2  CI Multi-Distro─┘                                      │
│                                                                 │
│  v1.3.0  Plugin System  ─┐ Phase 8: Plugins                     │
│  v1.3.1  Plugins Comm.  ─┘                                      │
│                                                                 │
│  v1.4.0  Modules Add.   ─┐                                      │
│  v1.4.1  Distros Add.    │ Phase 9: Parite Calamares            │
│  v2.0.0  UNIVERSAL      ─┘ 🎯 Installeur Universel              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Notes

Ce roadmap est maintenu dans `docs/roadmap.md` et versionne avec Git.

### Historique des mises a jour

- **2025-12-08**: Creation initiale (v0.4.x → v1.0.0 GLFOS)
- **2025-12-08**: Ajout phases multi-distribution (v1.1.x → v2.0.0)
  - Integration audit multi-distro (score actuel: 33/100)
  - Ajout correctifs securite CVE dans v0.5.0
  - Comparaison Calamares et gap analysis
  - Voir: `claudedocs/audit-multi-distro-red-team.md`

### References

- [Calamares Installer](https://calamares.io/) - Reference architecture
- [Calamares Modules](https://github.com/calamares/calamares/tree/calamares/src/modules) - 62 modules
