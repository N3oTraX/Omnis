# Suivi des retours — première ISO d'installation Omnis (v0.6.0)

Ticket : gaming-linux-fr/glf-os/glf-os#222
Testeurs : @Didic, @Pensionman, @Jeepyto, @Kuraudo
Base analysée : Omnis `develop` (v0.6.1), glf-os `feat/omnis-installer`, ISO `25.11.20260218.6d41bc2`

Légende statut : ✅ corrigé · 🔍 à confirmer avec les testeurs · 💡 évolution · ❎ non-bug

---

## 1. Synthèse

31 points remontés, regroupés en 21 causes racines distinctes. Trois d'entre elles étaient
déjà corrigées entre l'ISO testée (0.6.0) et `develop` (0.6.1). Deux causes racines
expliquent à elles seules près de la moitié des symptômes signalés.

**Cause transverse n°1 — l'entrée de boot française ne passe aucun paramètre kernel.**
Elle explique « langue FR → installeur en anglais », « le clavier ne suit pas la langue »
et, par ricochet, « la recherche ne trouve rien si on tape le nom complet ».
Le correctif est côté `glf-os`, en trois lignes.

**Cause transverse n°2 — les échecs sont détectés trop tard, après le partitionnement.**
Elle explique le blocage définitif hors live (`nixos-generate-config`), l'erreur `udevadm`,
l'absence de `mkpasswd`, et le risque de rejouer un wipe via le bouton Retry.

---

> **État au 2026-07-20 — tous les points côté Omnis sont corrigés sur `develop`.**
>
> Restent ouverts, hors dépôt Omnis ou en attente d'information :
> le correctif `kbd.*` de l'entrée de démarrage française (section 7), le choix de
> canal stable/testing (P3-1, dépend d'une option NixOS côté distribution), et les
> trois points en attente d'information des testeurs (section 8).
>
> **Validation sur la VM700** : `ruff check` et `ruff format` propres ; **mypy strict
> sans erreur sur 40 fichiers** ; **1042 tests unitaires au vert** (contre 952 avant
> ces travaux). Les 13 échecs restants sont préexistants et environnementaux —
> démontré en rejouant la suite sur la base non modifiée : 12 tests d'intégration
> QML que l'environnement de test ad-hoc ne peut pas charger faute de modules Qt, et
> un test d'écriture dans `/var/log`. Le paquet Nix build et l'interface se charge
> sans aucune erreur QML.
>
> **Reste à valider sur une ISO reconstruite** : aucun de ces correctifs n'a encore
> été éprouvé en conditions réelles de live USB.

## 2. Bloquants (P0) — ✅ corrigés

### P0-1 — Aucun contrôle préalable des outils requis : le disque est effacé avant l'échec
*Remonté par @Kuraudo (bugs 2, 5, 6)*

`runtimeTools` (`package.nix:23`) ne contient que la chaîne de partitionnement. Manquent
notamment `systemd` (`udevadm`), `whois`/`openssl` (`mkpasswd`), `nixos-install-tools`
(`nixos-generate-config`, `nixos-install`).

Aucun preflight n'existe : `SystemRequirementsChecker.check_all()`
(`src/omnis/jobs/requirements.py:125`) ne vérifie aucun binaire. La détection se fait par
`except FileNotFoundError` **au moment de l'exécution** (`partition.py:1962`,
`nixos.py:1114`). Or `wipefs -a` (`partition.py:1016`) précède le premier appel à `udevadm`
(`partition.py:1120`), et le job `nixos` s'exécute deux jobs plus tard. D'où le scénario
vécu : disque effacé, puis blocage irrécupérable.

✅ Compléter `runtimeTools` **et** ajouter un check `is_critical` « outils requis » qui
`shutil.which()` la liste complète des binaires de tous les jobs activés, avant l'écran de
résumé. Les deux volets ensemble — compléter la liste seule laisserait le piège armé pour
le prochain outil oublié.

### P0-2 — Impossible de relancer l'installeur après l'avoir fermé
*Remonté par @Didic (5), @Jeepyto (2)*

Le moteur privilégié crée `/run/omnis` en `0700 root:root` (`src/omnis/ipc/transport.py:84`).
L'UI, non privilégiée, appelle `Path.exists()` (`launcher.py:176`), qui fait un `stat()` :
`pathlib` ne rattrape que `ENOENT`/`ENOTDIR`/`EBADF`/`ELOOP`, **`EACCES` est propagé**.

Au premier lancement `/run/omnis` n'existe pas → `ENOENT` ignoré → tout va bien. Dès que le
moteur root a créé le répertoire, il survit sur le tmpfs `/run` : **toute relance échoue
jusqu'au reboot**. Le `stop()` du handler d'erreur refait le même `exists()` non protégé
(`launcher.py:206`), d'où la seconde exception qui masque le message d'origine. Lancé depuis
le `.desktop` (`Terminal=false`), stderr n'est visible nulle part → « le launcher ne lance rien ».

Reproduit sur VM700 avec le même Python 3.13.13 que le testeur :
```
drwx------ 2 root root /run/omnis
exists() RAISED PermissionError [Errno 13] Permission denied: '/run/omnis/ipc.sock'
```

✅ Blinder les deux `Path.exists()` (`try/except OSError → False`), rendre `stop()` défensif,
créer `/run/omnis` via `systemd-tmpfiles` avec un mode et un groupe exploitables.
À trancher au passage : le mode fork ne sert aujourd'hui à rien, `main.py:357-366` retombant
de toute façon sur le bridge direct. Le supprimer réglerait la classe entière de problèmes.

### P0-3 — Le bouton Retry rejoue le partitionnement destructif
*Remonté par @Kuraudo (bug 8, « boucle Finished ↔ Installing »)*

`Main.qml:695` bascule `currentStep = 6` **avant et indépendamment** du moteur, et
`onRetryClicked` (`Main.qml:533`) réenchaîne `resetInstallation()` + `startInstallation()`.
Les garde-fous Python (`bridge.py:1675`, `:1727`) retournent en silence sans émettre de
signal, donc QML n'apprend jamais que l'appel a été rejeté. Chaque cycle **relance la liste
de jobs depuis le job 0**, job `partition` inclus.

✅ `enabled:` sur le bouton Retry, bascule de vue pilotée par le signal `installationStarted`
plutôt qu'en amont, et signal de refus quand le garde-fou `isRunning()` se déclenche.

### P0-4 — Aucune barrière quand l'installeur tourne sans droits root
*Remonté par @Kuraudo (bug 1), @Jeepyto (6)*

En AppImage, `main.py:456` force `--no-fork` (moteur intégré) et se contente d'un
`logger.warning` si `geteuid() != 0`. L'utilisateur peut dérouler tout le wizard avant
d'échouer sur `Permission denied: '/mnt/target'`. `check_root_privileges()`
(`launcher.py:403`) existe mais n'est appelé nulle part.

✅ Refus bloquant en tête de `startInstallation()` (`bridge.py:1672`) + check `is_critical`
dans l'écran de prérequis.

### P0-5 — Le média live est proposé comme disque cible
*Remonté par @Jeepyto (4)*

L'exclusion du disque live repose sur une sonde unique — `findmnt SOURCE /` — qui abandonne
dès que `/` n'est pas un périphérique bloc (`src/omnis/utils/disk_detector.py:104-108`).
Sur un live ISO, `/` est un `tmpfs` : **le chemin d'exclusion est mort 100 % du temps**, ce
que confirme le log du testeur (`Live root source is not a block device: tmpfs`). Aucune
piste alternative n'existe dans le code (ni `findiso=`, ni loop backing file, ni `/run/media`).
Le garde-fou de dernier recours `holds_running_system()` ne rattrape pas non plus, le
squashfs étant monté via un loop device qui n'apparaît pas comme enfant de `sdb`.

✅ Détection multi-sources (backing file des `loop*`, `findiso=`/`root=` du cmdline,
croisement `findmnt` sur `/iso`, `/nix/.ro-store`), et à défaut de certitude, désélection
par défaut plutôt qu'exclusion silencieuse.

---

## 3. Fonctionnels majeurs (P1) — ✅ corrigés

### P1-1 — « Langue FR au boot → installeur en anglais »
*Remonté par @Didic (1), @Pensionman (3) — @Jeepyto non touché*

**Cause racine côté glf-os.** Les paramètres `kbd.layout` / `kbd.keymap` / `kbd.locale` ne
sont posés que par `mkKeyboardSpec` (`glf-os/flake.nix:244`), utilisé exclusivement par les
9 spécialisations **non françaises**. Le français est l'entrée **par défaut** — donc la
config de base, **sans aucun `kbd.*`**. Vérifié sur le `grub.cfg` de l'ISO :

```
menuentry 'GLF-OS ... Installer - AZERTY (France)'
  linux ... boot.shell_on_fail root=LABEL=... nosplit_lock_mitigate elevator=noop splash ...
                                          ^ aucun kbd.*
menuentry 'GLF-OS ... - QWERTY (English)'
  linux ... kbd.layout=us kbd.keymap=us kbd.locale=en_US.UTF-8 ...
```

Omnis lit correctement le cmdline (`locale_detector.py:358-382`) mais n'y trouve rien, puis
retombe sur le GeoIP. **Avec réseau** → `fr_FR` (cas de @Jeepyto, dont le log montre
`GeoIP detection successful`). **Sans réseau** → défaut `en_US` avec confiance 0.1, sous le
seuil de 0.8, donc rien n'est appliqué. Les deux testeurs KO ont justement dû configurer le
Wi-Fi *depuis* l'installeur.

Le comportement était donc **non déterministe et dépendant du réseau**.

✅ Côté glf-os : ajouter `boot.kernelParams = [ "kbd.layout=fr" "kbd.keymap=fr"
"kbd.locale=fr_FR.UTF-8" ]` à la config de base. Côté Omnis, en défense : replier sur
`LANG` / `localectl` de la session live avant le GeoIP.

### P1-2 — Le clavier ne suit pas la langue choisie
*Remonté par @Kuraudo (écran Choix de la langue)*

Trois couches à distinguer : le layout appliqué en live **fonctionne** ; la valeur
pré-sélectionnée dans l'UI est **fausse** — conséquence directe de P1-1, le bloc
`bridge.py:1872-1879` n'étant jamais exécuté faute de confiance suffisante, les défauts
`keymap: "us"` / `keyboardVariant: "qwerty"` (`bridge.py:1270`) subsistent.

Bug secondaire découvert : `"qwerty"` **n'est pas une variante XKB valide**, et elle est
écrite telle quelle dans la config cible (`nixos.py:567` → `services.xserver.xkb`). Par
ailleurs `_update_keyboard_variants()` n'étant appelé que dans la branche de confiance, le
combo « Variante » reste vide quand la détection échoue.

✅ Appeler `_update_keyboard_variants()` inconditionnellement et remplacer le défaut
`"qwerty"` par `""`.

### P1-3 — « Taper Europe/Paris en entier ne renvoie aucun résultat »
*Remonté par @Jeepyto (3)* — 🔍 **hypothèse à confirmer**

Le filtre a été extrait et exécuté : il est **correct**, `item.indexOf(lowerSearch)`
(`SearchableComboBox.qml:51`) matche parfaitement la chaîne complète `Region/City`.

Explication la plus probable : **décalage de disposition clavier** (P1-2). Sur un AZERTY
physique avec un layout US actif, `/` et `a` sont transposés, alors que les six lettres
d'« Europe » sont aux mêmes positions dans les deux dispositions — ce qui reproduit très
exactement le paradoxe décrit. Le log de @Jeepyto étaye : layout `us` appliqué à 17:49:10,
puis `fr` à 17:49:42.

🔍 À confirmer avec la capture d'écran du testeur (le texte réellement saisi y est visible).
Si confirmé, corriger P1-1/P1-2 fait disparaître ce point sans toucher au filtre.

### P1-4 — `GLF flake source not found: /iso/nixos`
*Remonté par @Kuraudo (bug 3)*

Chemin unique codé en dur (`nixos.py:453`), aucun repli. Vérifié : l'ISO contient bien
`iso-cfg/` et **pas** de répertoire `nixos/`. En live, le module ISO surcharge la valeur,
donc le bug ne se manifeste que hors live — mais le défaut de conception est réel.

✅ Résolution par liste de candidats (`flake_source` explicite, `/iso/nixos`, `/iso-cfg`,
`/etc/nixos`), premier contenant `flake.nix` ; échec listant les chemins essayés.

### P1-5 — Disque « busy », SSD à déverrouiller via KDE Partition Manager
*Remonté par @Pensionman (1), @Kuraudo (bug 4)*

Partiellement corrigé en 0.6.1 par `64afa24`, qui apporte un vrai mécanisme de libération
(`umount -R` non lazy, plus profond d'abord, fermeture LUKS/LVM/md, `udevadm settle`,
vérification post-libération avec liste des holders). Trois trous subsistent :

1. **Le swapfile n'est jamais désactivé** — et c'est le cas exact signalé. `release_disk()`
   ne fait `swapoff` que sur les *devices* membres du disque, or Omnis crée son swap en
   **fichier** (`partition.py:1784`, `/mnt/target/swapfile`), qui apparaît dans `/proc/swaps`
   sous ce chemin. Le swapfile actif tient `/mnt/target`, le `umount -R` échoue. De plus le
   `swapoff` est fait **après** le `umount`, alors qu'il doit venir avant.
2. **Le bouton « Apply » de l'éditeur manuel contourne toute la libération** —
   `bridge.py:294` appelle `_apply_operations()` sans passer par `PartitionJob.run()`.
3. **Journal ext4 orphelin** — provoqué par le `umount -l` de `finished.py:188`, que
   `release_disk()` ne peut plus résoudre au run suivant.

✅ Inverser l'ordre, étendre le `swapoff` aux swapfiles (`findmnt -no SOURCE -T`), brancher
la libération sur le chemin manuel, bannir `umount -l`.

### P1-6 — L'espace disque n'affiche qu'un seul disque
*Remonté par @Didic (6)*

`_check_disk_space()` (`requirements.py:259-275`) calcule un unique scalaire `max()` sur tous
les block devices. Le plus gros gagne, les autres disparaissent — le testeur avait un HDD
secondaire plus grand que son NVMe. Les NVMe sont bien énumérés, ce n'est pas un filtre
manquant. Ce check relit `/sys/block` à la main et ignore `disk_detector.list_disks()`, donc
il compte aussi la clé USB live.

✅ Consommer `disk_detector.list_disks()` et afficher une ligne par disque ; statut global
« au moins un disque ≥ minimum ».

---

## 4. UX et confort (P2) — ✅ corrigés

### P2-1 — « Votre système remplit toutes les exigences » malgré des points orange
*Remonté par @Didic (2)*

Le message n'a que **deux états**, pilotés par `canProceed`, vrai dès qu'aucun check n'est
critique — donc vrai en présence d'avertissements (`RequirementsOverlay.qml:109`).
`all_passed` existe côté Python (`requirements.py:67`) mais n'est pas exposé.

✅ Exposer `hasWarnings` et passer à un message à 3 états + pastille orange.
1 nouvelle chaîne i18n à propager dans les 37 `.ts`.

### P2-2 — Boutons radio et cases à cocher illisibles
*Remonté par @Jeepyto (5), @Kuraudo (problème 1)*

Les 5 `RadioButton` de l'écran Options (`PartitionView.qml:1057-1126`) ne définissent
**aucun `indicator:`** et retombent sur le style Fusion, dont la couleur du point coché
dérive de `palette.text` — que le projet a écrasée en gris clair (`Main.qml:44`) pour
corriger la lisibilité des champs de saisie. Contraste mesuré du point coché sur le fond de
l'indicateur : **≈ 1.68:1**, là où WCAG 2.1 exige 3:1. Même défaut sur 6 `CheckBox` (≈ 1.90:1).

Aucune clé de `theme.yaml` ne peut corriger ça en l'état, ces contrôles passant par la
palette Qt et non par le thème.

✅ Définir un `indicator: Rectangle` explicite sur le modèle de `UsersView.qml:715-749`
(déjà correct dans le projet) : anneau, bordure `primary` si coché / `text_muted` sinon,
pastille pleine. Donne ≈ 4.6:1.

### P2-3 — « Le mot de passe est trop restrictif »
*Remonté par @Didic (7), @Jeepyto* — ❎ **la contrainte n'existe pas**

La seule règle **bloquante** est la longueur ≥ 8 caractères (`UsersView.qml:75`,
`passwordValid: pwdHasMinLength`). Majuscule, minuscule, chiffre et caractère spécial ne
servent qu'à la jauge d'affichage. Côté backend, `users.py:111` ne vérifie même que le
non-vide.

Le problème est **purement visuel** : les 4 critères non bloquants s'affichent avec une
croix rouge et la jauge indique « Faible » en rouge — l'utilisateur conclut légitimement que
c'est obligatoire. Deux testeurs sur quatre s'en sont plaints : le message est à revoir, pas
la règle.

✅ Rendre les 4 critères visuellement non bloquants (icône neutre plutôt que croix rouge) —
règle sans doute l'essentiel de la plainte. Optionnellement, case « autoriser un mot de
passe faible » abaissant le minimum, avec avertissement.

### P2-4 — Le Wi-Fi apparaît dans GNOME Settings mais le clic ne fait rien
*Remonté par @Didic (3)*

Confirmé par le code. `gnome-control-center wifi` est lancé par un `Popen` **sans `env=`,
sans redescente d'UID** (`network_helper.py:179`), depuis un processus **root**. La liste
Wi-Fi vient de NetworkManager sur le bus **système** (visible en root, d'où l'affichage),
mais la connexion exige un agent secret enregistré sur le bus de **session** pour demander
la passphrase. Root n'y a pas accès → échec silencieux. Par le menu GNOME, l'outil tourne
dans la session utilisateur, avec l'agent → ça marche.

✅ Le patron correct existe déjà dans le dépôt : `keyboard_layout.py:29-71` (`_in_session()`)
résout `SUDO_UID`, reconstruit `XDG_RUNTIME_DIR` + `DBUS_SESSION_BUS_ADDRESS` et enrobe en
`runuser`. À factoriser et appliquer au lancement réseau.

### P2-5 — Les prérequis ne se rafraîchissent pas après connexion au Wi-Fi
*Remonté par @Didic (4)*

Un recheck existe mais est mal calibré : timer `repeat: false` de 5 s (`Main.qml:759`),
démarré au *lancement* de l'outil et non à sa fermeture. Choisir un SSID et saisir une
passphrase prend bien plus de 5 s → l'unique recheck tombe dans le vide. Le PID de l'outil
est jeté (`Popen` fire-and-forget), et aucun bouton « Revérifier » n'existe.

✅ Polling borné (`repeat: true`, 3 s, arrêt sur connexion ou après N essais) + bouton
« Revérifier » explicite dans l'en-tête des prérequis.

### P2-6 — L'aperçu disque ne reflète aucun choix d'options
*Remonté par @Kuraudo (problème 2)*

Découplage structurel : en mode `auto`, l'histobar est alimentée par la géométrie **actuelle**
du disque lue par lsblk (`PartitionView.qml:618`). Un vrai simulateur existe
(`bridge.simulatedSegments`) mais n'est câblé qu'à la barre du mode **manuel**
(`PartitionView.qml:1355`), et le panneau d'options n'est visible qu'en mode auto — les deux
ne coexistent jamais à l'écran. Aucun changement d'option ne déclenche de recalcul.

Cas « hibernation » : la couleur violette est bien déclarée, mappée et présente dans la
légende, mais elle ne pourra **jamais** s'afficher, la stratégie `hibernate` créant un
**fichier** de swap et non une partition. La légende promet ce que l'architecture ne produit pas.

✅ Extraire de `_partition_auto()` une fonction pure `plan_auto_layout(...)`, l'exposer sur
le bridge et y brancher l'histobar en mode auto. Émettre le swapfile comme pseudo-segment,
ou basculer `hibernate` sur une vraie partition swap (plus robuste pour le resume de toute façon).

### P2-7 — Identifier le bon disque : modèle, taille, série
*Remonté par @Kuraudo (recommandation P2)*

L'UI n'affiche que le nom kernel, un badge SSD/HDD, un badge REMOVABLE et la taille.
Or `model` est **déjà collecté et déjà exposé dans le modèle** (`disk_detector.py:271`) —
simplement jamais lu en QML. `TRAN` est demandé à lsblk mais jamais lu. `SERIAL` et `WWN`
ne sont pas collectés du tout.

Point aggravant : la sélection est stockée et re-résolue **par nom** (`bridge.py:2144`,
`:2412`). Un rafraîchissement qui permuterait `sda`/`sdb` sélectionnerait silencieusement le
mauvais disque.

✅ Ajouter `SERIAL,WWN` aux colonnes lsblk, afficher `model` + série tronquée, et indexer la
sélection sur un identifiant stable.

### P2-8 — La VF n'a pas d'accents
*Remonté par @Didic (8)*

Constat factuel : `fr_FR.conf` est le **seul** catalogue latin intégralement désaccentué
(0 ligne non-ASCII, contre 53 pour l'allemand, 70 pour l'espagnol, 90 pour le portugais).
Le pendant Qt `omnis_fr_FR.ts` est, lui, parfaitement accentué (105 lignes) — d'où des
chaînes accentuées et désaccentuées **dans le même écran**, ce qui correspond exactement au
symptôme « pas d'accents à plein d'endroits ».

Aucune justification technique ne subsiste : les polices sont bundlées (`package.nix:34-44`,
avec `FONTCONFIG_FILE` forcé), l'encodage est explicite (`configparser` en UTF-8), et
l'allemand, l'espagnol, l'italien, le portugais, le russe et le CJK passent par le **même
chemin de code** sans problème.

✅ Ré-accentuer `config/i18n/fr_FR.conf` (255 lignes, mécanique).

### P2-9 — GPU récent non reconnu
*Remonté par @Kuraudo (bug 8)* — 🔍 **partiellement à confirmer**

`AMD_DGPU_MODELS` (`gpu.py:133-172`) est une liste plate ordonnée à la main ; la série
RDNA 4 n'y contient que `RX 9070` et `RX 9070 XT`. `RX 9060 XT` est absente → index -1 → log
`Unknown model comparison`.

Nuance importante : ce chemin renvoie `True` (permissif) et classe la carte en `pass`. **Ce
log seul ne peut donc pas produire un avertissement.** Si un WARN a bien été observé, il
vient d'un autre chemin — probablement une détection en iGPU si la base `pci.ids` de l'ISO
est trop ancienne pour Navi 44.

✅ Remplacer la liste plate par un parseur structuré produisant un tuple ordonnable
(génération, tier, suffixe), auto-extensible aux séries futures ; garder une liste
d'exceptions. 🔍 Demander une sortie `lspci -v` au testeur pour trancher sur le WARN.

### P2-10 — Logs trompeurs
*Remonté par @Kuraudo (bug 4)*

`nixos.py:1219-1225` logge « Unmounted » même quand le `umount` a échoué (`check=False`,
returncode jamais consulté). Même défaut pour la fermeture LUKS (`partition.py:2075-2080`).
À l'inverse `_release_target_disk()` ne logge **rien du tout**, ni succès ni échec, sur une
étape critique.

✅ Propager les codes de retour aux logs.

---

## 5. Évolutions demandées (P3)

### P3-1 — Choisir la branche stable ou testing pendant l'installation
*Proposé par @Jeepyto*

Faisable, et le patron existe déjà : `CFG_ENVIRONMENT` (`nixos.py:70`) injecte déjà des
sélections UI dans `configuration.nix`. Ajouter un `CFG_CHANNEL` sur le même modèle est
quasi gratuit côté Omnis — **à condition que `glf-os` définisse l'option NixOS
correspondante**. Le travail réel est donc côté distribution.

À éviter en revanche : réécrire les `inputs` du flake et refaire le `flake.lock` à
l'installation. Cela imposerait un `nix flake update` sur la cible, avec réseau obligatoire
et durée imprévisible — incompatible avec le flux actuel, qui copie un lock figé et
l'exploite hors ligne.

### P3-2 — Durées d'installation
*Remonté par @Didic (9), @Pensionman (4), @Jeepyto*

Mesures rapportées : mini 8m10 (@Didic), 2m49 (mainteneur), 3m26 (@Jeepyto) ;
standard 5m39 (@Jeepyto), ~30 min (@Pensionman).

L'écart est très majoritairement imputable au réseau : `nixos-install` substitue depuis le
cache binaire, et le temps est dominé par le débit disponible, pas par le CPU. Ce n'est pas
un défaut en soi, mais l'absence d'indication rend l'attente anxiogène.

💡 Afficher le débit et le nombre de dérivations restantes pendant la phase de
substitution — la barre granulaire, déjà en place depuis 0.6.0, en expose la matière.

---

## 6. Déjà corrigé entre 0.6.0 et 0.6.1

Ces points sont réels mais ne se reproduisent plus sur `develop`. Les testeurs étaient sur
l'ISO 0.6.0.

| Point | Testeur | Correctif |
|---|---|---|
| ✅ Langues régionales en anglais (`en_GB`, `fr_BE`, `de_CH`, `fr_CA`, `pt_PT`) | logs @Jeepyto | `953e2d8` — repli par famille de langue, générique et sans liste en dur |
| ✅ Job `locale` écrit dans `/mnt/target` avant le formatage | @Kuraudo (bug 7) | `64afa24` — ordre passé à `partition` → `locale` |
| ✅ Libération du disque cible avant `wipefs` (cas automontage) | @Pensionman, @Kuraudo (bug 4) | `64afa24` — partiel, voir P1-5 pour les trous restants |

Limite connue et non corrigée : le repli i18n ne peut retomber que sur une langue présente
au catalogue, or `config/i18n/` ne contient que 10 fichiers. `be_BY`, `fil_PH`, `ka_GE`
resteront en anglais. Les `.ts` Qt couvrent ~30 langues, les `.conf` seulement 10 — cette
asymétrie mérite d'être tranchée : soit compléter les `.conf`, soit n'exposer que les
locales réellement traduisibles.

---

## 7. Correctifs hors dépôt Omnis

| Cible | Correctif | Débloque |
|---|---|---|
| `glf-os/flake.nix` | `kbd.*` sur la config de base (entrée FR par défaut) | P1-1, P1-2, P1-3 |
| `glf-os/flake.nix` | `keyboard-setup` ne fait qu'un `export LANG` sans effet — écrire `/etc/locale.conf` | P1-1 |
| `glf-os/modules/default/` | Option NixOS de canal, si P3-1 est retenu | P3-1 |

---

## 8. Points en attente d'information

- 🔍 **P1-3** — captures d'écran de @Jeepyto sur la recherche (le texte saisi y est visible).
- 🔍 **P2-9** — sortie `lspci -v` de @Kuraudo, pour confirmer l'origine du WARN GPU.
- 🔍 **@Pensionman** — le `log.txt` de l'échec d'installation n'a pas pu être récupéré.
