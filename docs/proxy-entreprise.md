<!--
  BROUILLON - NE PAS PUBLIER.
  A publier dans la documentation officielle GLF-OS seulement une fois qu'une
  installation complete (ISO -> systeme installe) a ete validee de bout en bout.
-->

# Installer GLF-OS derriere un proxy d'entreprise

GLF-OS installe le systeme avec `nixos-install`, qui telecharge les paquets
depuis le cache Nix. Derriere un proxy d'entreprise, il faut declarer le proxy
**à deux moments** : pendant l'installation (ISO live), puis sur le systeme
installe pour le persister.

> GLF-OS boote en **systemd-boot (UEFI)** et installe via l'installeur **Omnis**.

---

## 1. Pendant l'installation (ISO live)

L'installeur herite des variables d'environnement de la session live. Il suffit
donc de declarer le proxy **avant de lancer l'installation**, dans un terminal
de l'ISO :

```bash
export http_proxy="http://utilisateur:motdepasse@proxy.entreprise:3128"
export https_proxy="$http_proxy"
export HTTP_PROXY="$http_proxy"
export HTTPS_PROXY="$http_proxy"
# Optionnel : hotes a ne PAS passer par le proxy
export no_proxy="127.0.0.1,localhost,.entreprise.local"
export NO_PROXY="$no_proxy"
```

Puis lancer/relancer l'installateur **depuis ce meme terminal** pour qu'il herite
du proxy :

```bash
sudo -E omnis   # -E preserve les variables http(s)_proxy
```

- Le `-E` de `sudo` est important : sans lui, les variables de proxy sont
  effacees et les telechargements Nix echouent.
- Ces reglages sont **volatils** (perdus au reboot) : ils ne servent qu'a
  l'installation. Voir la section 2 pour les persister.

### Proxy avec authentification

Si le mot de passe contient des caracteres speciaux (`@`, `:`, `/`...),
il faut les encoder en pourcent (`@` -> `%40`, `:` -> `%3A`, etc.).

---

## 2. Persister le proxy sur le systeme installe (post 1er boot)

Apres le premier demarrage, declarer le proxy de maniere **declarative** dans
NixOS. Editer `/etc/nixos/configuration.nix` (ou un fichier importe par
`customConfig`) et ajouter :

```nix
{
  # Proxy global (variables d'environnement systeme + session).
  networking.proxy.default = "http://utilisateur:motdepasse@proxy.entreprise:3128";
  networking.proxy.noProxy = "127.0.0.1,localhost,.entreprise.local";
}
```

Le daemon Nix (`nix-daemon`), qui telecharge les paquets lors des
`nixos-rebuild`, doit aussi connaitre le proxy. `networking.proxy.default`
l'expose deja globalement ; si besoin on peut le forcer explicitement :

```nix
{
  systemd.services.nix-daemon.environment = {
    http_proxy = "http://utilisateur:motdepasse@proxy.entreprise:3128";
    https_proxy = "http://utilisateur:motdepasse@proxy.entreprise:3128";
    no_proxy = "127.0.0.1,localhost,.entreprise.local";
  };
}
```

Appliquer la configuration :

```bash
sudo nixos-rebuild switch
```

### Verification

```bash
# Les variables sont bien exportees ?
env | grep -i proxy
# Nix telecharge-t-il a travers le proxy ?
nix store ping --store https://cache.nixos.org
```

---

## Notes

- **Secrets** : un mot de passe de proxy en clair dans `configuration.nix` est
  lisible par la racine du systeme. Pour un environnement sensible, utiliser un
  gestionnaire de secrets (agenix / sops-nix) plutot qu'un mot de passe en dur.
- **WiFi/filaire** : les connexions NetworkManager de la session live sont
  recopiees automatiquement par l'installeur ; pas besoin de resaisir le mot de
  passe WiFi apres le reboot.
