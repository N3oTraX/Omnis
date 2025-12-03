# Guide de Personnalisation des Thèmes

> **Docs** > **Branding** > Theming

---

## Concept

Le système de thèmes Omnis sépare la **configuration** (workflow, jobs) des **assets visuels** (logos, wallpapers). Cette séparation permet :

- Réutiliser un même thème avec différentes configurations
- Mettre à jour les assets sans modifier la config
- Distribuer des thèmes indépendamment

---

## Architecture du Système

```
omnis.yaml                    config/themes/glfos/
    │                              │
    ├── theme: "config/..."  ────► │
    │                              ├── theme.yaml
    └── branding:                  ├── logos/
        └── assets:                │   ├── logo.png
            └── logo: "logos/..." ─┤   └── ...
                                   ├── wallpapers/
                                   └── boot/
```

### Flux de Résolution

1. `main.py` lit le chemin `theme` depuis la config
2. Le chemin est résolu relativement au fichier de config
3. `BrandingProxy` convertit les chemins d'assets en URLs `file://`
4. QML charge les images via ces URLs

---

## Structure d'un Thème

```
config/themes/<nom>/
├── theme.yaml              # Métadonnées et définitions
├── logos/
│   ├── logo.png            # Logo principal (≥256px, fond sombre)
│   ├── logo_light.png      # Logo pour fond clair
│   ├── logo-256.png        # Tailles spécifiques
│   ├── logo-128.png
│   ├── logo-64.png
│   └── logo-32.png
├── wallpapers/
│   ├── dark.jpg            # Fond d'écran par défaut
│   ├── light.jpg           # Variante claire (optionnel)
│   └── ...
└── boot/
    ├── bootloader.png      # Splash GRUB/systemd-boot
    └── efi-icon.png        # Icône UEFI
```

### Fichier theme.yaml

Définition complète d'un thème avec métadonnées :

```yaml
metadata:
  name: "GLF OS"
  codename: "Omnislash"
  version: "2025.1"
  author: "Gaming Linux FR"
  website: "https://www.gaminglinux.fr"
  license: "MIT"

colors:
  primary: "#5597e6"
  secondary: "#4a8bd4"
  accent: "#5597e6"
  background: "#1a1a1a"
  surface: "#32373c"
  text: "#fffded"
  text_muted: "#9CA3AF"

fonts:
  primary: "Poppins"
  display: "Lemon Milk"
  monospace: "Roboto Mono"

logos:
  main: "logos/logo.png"
  main_256: "logos/logo-256.png"
  light: "logos/logo_light.png"

wallpapers:
  default: "wallpapers/dark.jpg"
  alternatives:
    - "wallpapers/frost-dark.png"
    - "wallpapers/dalle-dark.png"

boot:
  bootloader: "boot/glf-bootloader.png"
  efi_icon: "boot/glf-efi.png"

strings:
  welcome_title: "Bienvenue sur GLF OS"
  welcome_subtitle: "Linux Gaming made easy!"
  install_button: "Installer GLF OS"
  finished_title: "Installation terminée !"
  finished_message: "Redémarrez pour découvrir le gaming sur Linux."
```

---

## Lier un Thème à une Configuration

### Configuration Minimale

```yaml
# config/examples/glfos.yaml
version: "1.0"

# Chemin vers le dossier du thème (RELATIF à ce fichier config)
theme: "../themes/glfos"  # Résout vers config/themes/glfos

branding:
  name: "GLF OS"
  version: "2025.1"

  # Assets (chemins relatifs au dossier theme)
  assets:
    logo: "logos/logo.png"
    logo_small: "logos/logo-64.png"
    background: "wallpapers/dark.jpg"

  colors:
    primary: "#5597e6"
    background: "#1a1a1a"
    text: "#fffded"

jobs:
  - welcome
  - partition
  - install
  - finished
```

### Configuration Complète

```yaml
version: "1.0"
theme: "../themes/glfos"  # Relatif au fichier config

branding:
  name: "GLF OS"
  version: "2025.1"
  edition: "Omnislash"

  colors:
    primary: "#5597e6"
    secondary: "#4a8bd4"
    accent: "#5597e6"
    background: "#1a1a1a"
    surface: "#32373c"
    text: "#fffded"
    text_muted: "#9CA3AF"

  assets:
    logo: "logos/logo.png"
    logo_light: "logos/logo_light.png"
    logo_small: "logos/logo-64.png"
    logo_256: "logos/logo-256.png"
    background: "wallpapers/dark.jpg"
    background_alt: "wallpapers/frost-2-dark.png"
    icon: "logos/logo-32.png"
    bootloader: "boot/glf-bootloader.png"
    efi_icon: "boot/glf-efi.png"

  strings:
    welcome_title: "Bienvenue sur GLF OS"
    welcome_subtitle: "Linux Gaming made easy!"
    install_button: "Installer GLF OS"
    finished_title: "Installation terminée !"
    finished_message: "Redémarrez pour découvrir le gaming sur Linux."

  fonts:
    primary: "Poppins"
    display: "Lemon Milk"
    monospace: "Roboto Mono"
```

---

## Créer un Nouveau Thème

### Étape 1 : Créer la Structure

```bash
mkdir -p config/themes/ma-distro/{logos,wallpapers,boot}
```

### Étape 2 : Préparer les Assets

| Asset | Format | Dimensions | Notes |
|-------|--------|------------|-------|
| `logo.png` | PNG (transparent) | ≥256×256 | Logo principal |
| `logo_light.png` | PNG (transparent) | ≥256×256 | Pour fonds clairs |
| `logo-*.png` | PNG | 32/64/128/256 | Tailles spécifiques |
| `wallpapers/*.jpg` | JPG/PNG | 1920×1080+ | Fond d'écran |
| `boot/*.png` | PNG | Variable | Bootloader splash |

### Étape 3 : Créer theme.yaml

```yaml
metadata:
  name: "Ma Distribution"
  version: "1.0"
  author: "Mon Équipe"

colors:
  primary: "#3B82F6"
  background: "#0F172A"
  text: "#F8FAFC"

logos:
  main: "logos/logo.png"

wallpapers:
  default: "wallpapers/default.jpg"

strings:
  welcome_title: "Bienvenue"
  install_button: "Installer"
```

### Étape 4 : Créer la Configuration

```yaml
# config/examples/ma-distro.yaml
version: "1.0"
theme: "config/themes/ma-distro"

branding:
  name: "Ma Distribution"
  assets:
    logo: "logos/logo.png"
    background: "wallpapers/default.jpg"
  colors:
    primary: "#3B82F6"
    background: "#0F172A"

jobs:
  - welcome
  - partition
  - install
  - finished
```

### Étape 5 : Tester

```bash
python -m omnis.main --config config/examples/ma-distro.yaml --debug
```

---

## Propriétés Exposées au QML

Le `BrandingProxy` expose les propriétés suivantes au QML :

### Textes

| Propriété QML | Source YAML |
|---------------|-------------|
| `branding.name` | `branding.name` |
| `branding.version` | `branding.version` |
| `branding.edition` | `branding.edition` |
| `branding.welcomeTitle` | `branding.strings.welcome_title` |
| `branding.welcomeSubtitle` | `branding.strings.welcome_subtitle` |
| `branding.installButton` | `branding.strings.install_button` |

### Couleurs

| Propriété QML | Source YAML |
|---------------|-------------|
| `branding.primaryColor` | `branding.colors.primary` |
| `branding.secondaryColor` | `branding.colors.secondary` |
| `branding.accentColor` | `branding.colors.accent` |
| `branding.backgroundColor` | `branding.colors.background` |
| `branding.surfaceColor` | `branding.colors.surface` |
| `branding.textColor` | `branding.colors.text` |
| `branding.textMutedColor` | `branding.colors.text_muted` |

### URLs d'Assets

| Propriété QML | Source YAML | Format |
|---------------|-------------|--------|
| `branding.logoUrl` | `branding.assets.logo` | `file:///...` |
| `branding.logoSmallUrl` | `branding.assets.logo_small` | `file:///...` |
| `branding.logoLightUrl` | `branding.assets.logo_light` | `file:///...` |
| `branding.backgroundUrl` | `branding.assets.background` | `file:///...` |
| `branding.iconUrl` | `branding.assets.icon` | `file:///...` |

---

## Utilisation dans QML

### Afficher le Logo

```qml
Image {
    source: branding.logoUrl
    fillMode: Image.PreserveAspectFit
    visible: status === Image.Ready
}

// Fallback si logo non disponible
Rectangle {
    visible: logoImage.status !== Image.Ready
    color: branding.primaryColor
    Text {
        text: branding.name.charAt(0)
        color: branding.textColor
    }
}
```

### Fond d'Écran

```qml
Image {
    anchors.fill: parent
    source: branding.backgroundUrl
    fillMode: Image.PreserveAspectCrop
    visible: status === Image.Ready
}

// Gradient fallback
Rectangle {
    anchors.fill: parent
    visible: backgroundImage.status !== Image.Ready
    gradient: Gradient {
        GradientStop { position: 0.0; color: branding.backgroundColor }
        GradientStop { position: 1.0; color: Qt.darker(branding.backgroundColor, 1.3) }
    }
}
```

---

## Thème GLF OS de Référence

Le thème GLF OS (`config/themes/glfos/`) sert de référence :

```
config/themes/glfos/
├── theme.yaml              # Définition complète
├── logos/
│   ├── logo.png            # 400×400 PNG
│   ├── logo_light.png      # Variante claire
│   ├── logo-256.png
│   ├── logo-128.png
│   ├── logo-64.png
│   ├── logo-32.png
│   ├── mango.svg           # Logo Mango (MangoHUD)
│   └── selector.svg        # Sélecteur GRUB
├── wallpapers/
│   ├── dark.jpg            # Fond par défaut
│   ├── frost-2-dark.png    # Variante Frost
│   ├── frost-2.png
│   ├── dalle-dark-glf.png  # Variante DALL-E
│   └── dalle-glf.png
└── boot/
    ├── glf-bootloader.png  # Splash GRUB
    └── glf-efi.png         # Icône EFI
```

Source des assets : [Gaming-Linux-FR/GLF-OS](https://github.com/Gaming-Linux-FR/GLF-OS)

---

## Dépannage

### Les images ne s'affichent pas

1. Vérifier que le chemin `theme` est correct
2. Vérifier que les fichiers existent dans le dossier du thème
3. Lancer avec `--debug` pour voir le chemin résolu :
   ```
   Theme base: /chemin/absolu/config/themes/glfos
   ```

### Fallback au lieu du logo

Le fallback (cercle avec initiale) s'affiche si :
- Le fichier n'existe pas
- Le chemin d'asset est vide dans la config
- Le format d'image n'est pas supporté

### Couleurs non appliquées

Vérifier le format hexadécimal : `#RRGGBB` (avec le `#`)
