# Omnis Installer - Roadmap de Versioning

**Document cree**: 2025-12-08
**Objectif final**: v1.0.0 capable d'installer GLFOS

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

### v0.5.0 - E2E Integration Tests

**Focus**: Tests end-to-end complets

- [ ] Test wizard flow complet (Welcome -> Finished)
- [ ] Test mode dry-run integral
- [ ] Test IPC UI <-> Engine
- [ ] Test i18n switching dans workflow
- [ ] Couverture tests >= 80%

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

## Metriques Actuelles

| Metrique | v0.4.1 | Target v0.7.0 | Target v1.0.0 |
|----------|--------|---------------|---------------|
| Tests unitaires | 599 | 800+ | 1000+ |
| Couverture | ~70% | 80%+ | 85%+ |
| Locales | 37 | 37 | 40+ |
| Jobs | 10 | 10 | 12+ |
| Vues QML | 7 | 7 | 7 |

---

## Conventions de Versioning

- **v0.4.x**: Une vue par version mineure (polish + tests)
- **v0.5.x**: Integration testing
- **v0.6.x**: IPC production ready
- **v0.7.0**: UI milestone (tout valide)
- **v0.8.x**: GLFOS integration
- **v0.9.x**: Production hardening
- **v1.0.0**: First stable release

**Semantic Versioning**:

- MAJOR (1.x.x): Breaking changes, major features
- MINOR (x.4.x): New features, views, backward compatible
- PATCH (x.x.2): Bug fixes, polish, no new features

---

## Resume Visuel

```
v0.4.2  UsersView      ─┐
v0.4.3  PartitionView   │ Phase 1: Polish Vues
v0.4.4  SummaryView     │
v0.4.5  ProgressView    │
v0.4.6  FinishedView   ─┘

v0.5.0  E2E Tests      ─┐ Phase 2: Integration
v0.5.1  Accessibility  ─┘

v0.6.0  IPC Prod       ─┐ Phase 3: IPC
v0.6.1  Error Handling ─┘

v0.7.0  UI Complete    ─── Milestone: UI Validee

v0.8.0  GLFOS Base     ─┐
v0.8.1  GLFOS Custom    │ Phase 5: GLFOS
v0.9.0  Hardening       │
v0.9.1  RC             ─┘

v1.0.0  RELEASE        ─── First Stable
```

---

## Notes

Ce roadmap est maintenu dans `docs/roadmap.md` et versionne avec Git.

Derniere mise a jour: 2025-12-08
