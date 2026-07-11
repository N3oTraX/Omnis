# Polices du thème

Déposez ici les fichiers de police (`.ttf`, `.otf`, `.ttc`) que le thème doit
embarquer. Ils sont chargés automatiquement au démarrage d'Omnis
(`QFontDatabase.addApplicationFont`), puis sélectionnables dans `theme.yaml` par
leur **nom de famille** :

```yaml
fonts:
  primary: "Poppins"
  display: "Lemon Milk"     # -> déposer fonts/LEMONMILK-Regular.otf
  monospace: "Roboto Mono"
```

Le nom de famille (ce qu'on met dans `theme.yaml`) est celui embarqué dans le
fichier de police, pas le nom du fichier.

Les polices déjà fournies par le système (ou bundlées via le paquet Nix :
Poppins, Roboto Mono, Noto Sans, Noto emoji monochrome) n'ont pas besoin d'être
déposées ici — c'est surtout utile pour les polices absentes des dépôts
(ex. « Lemon Milk »).
