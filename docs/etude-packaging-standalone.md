<!-- BROUILLON D'ETUDE - ne pas publier. -->

# Étude : Omnis en livrable exécutable unique, standalone et versionné

## 1. Objectif et périmètre honnête

Objectif : produire **un seul fichier exécutable** d'Omnis, lançable sur « n'importe quel » Linux, généré par CI/CD à partir d'**une version taguée** du projet.

**Ce qui est réellement empaquetable dans un exécutable unique :**
- L'application Python + **PySide6/Qt6 + QML** (assistant, éditeur de partition, logique, dry-run).
- Ses assets (QML 436 Ko, icônes, config par défaut).

**La limite dure (à assumer, ce n'est pas un défaut de packaging) :** Omnis est un **installeur système**. Son moteur d'installation appelle **`nixos-install` / `nixos-generate-config` / `nixos-version`** et lit le flake GLF de l'ISO. Ces commandes ne s'empaquettent pas (c'est toute la machinerie Nix + store) et n'ont de sens que sur **l'environnement live NixOS**. Calamares a exactement la même propriété : l'UI est portable, le *backend d'install* dépend des outils de la cible.

> **Conclusion de périmètre** : un exécutable unique standalone est réaliste et utile pour l'**UI + le partitionnement + le dry-run** (démo, dev, distribution découplée). L'**installation réelle de GLF-OS** reste liée à l'ISO NixOS. C'est la bonne granularité — le même binaire tourne partout ; l'action « installer » n'aboutit que là où `nixos-install` existe.

## 2. Inventaire technique (état réel du code)

| Élément | Détail |
|---|---|
| Python | `>=3.11` |
| Deps Python | PySide6 `>=6.6`, pydantic `>=2.5`, PyYAML `>=6` |
| Qt6 runtime | qtbase, **qtdeclarative** (QtQuick/Controls), qtsvg, **qtwayland** |
| Entrypoint | `omnis.main:main` |
| Résolution assets | `Path(__file__).parent / gui/qml` → **relative au package** (bon signe pour le freeze) |
| Config | `config/` = **28 Mo** (wallpapers) → à fournir hors-bundle ou bundler un thème minimal |
| Packaging Nix | **`package.nix` existe** (buildPythonApplication + wrap Qt + `QML2_IMPORT_PATH`) |
| CI existante | `.github/workflows/ci.yml` : lint/mypy/pytest/security — **aucun job de build/release** |

**Outils système externes invoqués (23)** — non empaquetés, supposés dans le PATH :
`parted, sgdisk, wipefs, partprobe, udevadm, lsblk, blkid, lspci, mkfs.{ext4,btrfs,fat}, mkswap, cryptsetup, resize2fs, btrfs, dd, mount, umount` (partitionnement, **bundlables** en statique) — et `nixos-install, nixos-generate-config, nixos-version` (**non bundlables**, NixOS-only). Plus `pkexec` (élévation).

## 3. Points de blocage (par gravité)

| # | Blocage | Gravité | Traitement |
|---|---|---|---|
| B1 | Couplage `nixos-install` (backend NixOS-only) | 🔴 structurel | Assumé : install réelle = ISO. UI/partition = partout |
| B2 | Privilèges root (pkexec/sudo) | 🟠 | Le binaire doit se ré-exécuter en root ; gérer `sys.executable`=bundle |
| B3 | Outils partition absents hors ISO | 🟠 | Les **bundler statiques** (gptfdisk, parted, e2fsprogs, dosfstools, util-linux, cryptsetup ≈ +20–40 Mo) ou supposer présents |
| B4 | Plugins Qt (wayland **vs** xcb) + software GL | 🟠 | Bundler qtwayland+xcb ; **détecter le socket** au lancement (cf. bug wayland-0/1 vécu) |
| B5 | Compat glibc (voie PyInstaller/Nuitka) | 🟡 | Builder sur vieux glibc (manylinux/ubuntu-20.04). La voie Nix contourne (glibc du closure) |
| B6 | Assets QML/config en frozen | 🟡 | PyInstaller n'auto-collecte pas les `.qml` → `--collect-data omnis` + vérifier `find_qml_file` |
| B7 | Taille (~300–500 Mo, Qt lourd) | 🟡 | Acceptable pour un composant d'ISO ; AppImage extract-and-run |

## 4. Options de packaging

| Option | Qt/QML | Reproductible/versionné | Agnostique | Effort | Risque |
|---|---|---|---|---|---|
| **Nix → AppImage** (`nix bundle`) | ✅ closure Nix (fiable) | ✅✅ (flake + tag) | ✅ (AppImage extract-and-run) | **Faible** (package.nix existe) | Faible |
| PyInstaller `--onefile` | ⚠️ collecte manuelle plugins/QML | ⚠️ (lock deps requis) | ✅ si build vieux glibc | Moyen-élevé | Moyen |
| Nuitka `--onefile --enable-plugin=pyside6` | ✅ plugin pyside6 correct | ⚠️ | ✅ | Moyen | Moyen |

## 5. Recommandation

**Voie Nix → AppImage**, parce que : `package.nix` est **déjà écrit et éprouvé** (il sert l'ISO), l'écosystème GLF est Nix-natif, et surtout elle satisfait nativement « **se baser systématiquement sur une version** » (le flake épingle la source par tag → build **reproductible bit-à-bit**). On garde `package.nix` pour l'ISO (inchangé) et on **ajoute** un `flake.nix` + un bundler AppImage pour le livrable standalone.

Voie de repli (si on veut zéro dépendance à Nix pour builder) : **Nuitka + plugin pyside6** (meilleure gestion Qt/QML que PyInstaller brut), buildé sur ubuntu-20.04, wrappé en AppImage via linuxdeploy.

## 6. Versioning + CI/CD

**Source unique de version** : `pyproject.toml:version` (garder `package.nix` en phase, idéalement dérivé d'un `VERSION`/du tag). Release = tag `vX.Y.Z`.

**Workflow `release.yml` (déclenché sur `push: tags: v*`) :**
1. **Gates qualité** (réutiliser lint/mypy/pytest offscreen de `ci.yml`).
2. **Build** (voie Nix) : `install-nix-action` → `nix build .#omnis` → `nix bundle --bundler github:ralismark/nix-appimage .#omnis`.
3. **Nommage** : `omnis-${version}-x86_64.AppImage` + `.sha256`.
4. **Release GitHub** : créer la release du tag, y attacher l'AppImage + checksum.

Propriétés obtenues : build **épinglé au tag** (source = version), **reproductible** (Nix), livrable **unique** et **auto-porté**. L'ISO peut continuer à consommer le package via le flake (reproductible) **ou** télécharger l'AppImage publiée (découplé).

## 7. Étapes concrètes (voie recommandée)

1. **`flake.nix`** à la racine Omnis exposant `packages.default = callPackage ./package.nix {}` + `apps.default`.
2. Vérifier la résolution QML/config depuis le **chemin bundle** (déjà relative au package ; valider en AppImage).
3. **Launcher interne** au bundle : détection socket Wayland / repli xcb, env software GL (`LIBGL_ALWAYS_SOFTWARE`, `QT_QUICK_BACKEND=software`), ré-exécution root via pkexec.
4. (Option B3) **Bundler l'outillage partition** (gptfdisk/parted/e2fsprogs/dosfstools/util-linux/cryptsetup) dans le closure pour un partitionnement hors-ISO.
5. **`release.yml`** : tag → nix build + bundle + checksum + Release.
6. **Sync de version** pyproject ↔ package.nix (un seul `VERSION`).
7. Doc d'usage (`./omnis-x.y.z.AppImage`, run root, `--config`).

## 8. Effort / risque

| Voie | Effort | Risque | Note |
|---|---|---|---|
| **Nix → AppImage** | ~1 j | Faible | `package.nix` prouvé ; reste flake + workflow + vérifs |
| Nuitka/PyInstaller + AppImage | 2–4 j | Moyen | Pièges plugins Qt/QML, glibc, tests multi-distros |

**Verdict** : faisable, **effort faible** par la voie Nix, avec un **périmètre clair** (UI/partition portables ; install réelle = ISO NixOS). Les seuls vrais choix produit : (a) bundler ou non l'outillage partition (B3), (b) accepter la dépendance Nix au *build* (pas au *run*).
