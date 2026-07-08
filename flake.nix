{
  description = "Omnis - modular GLF-OS installer (standalone AppImage)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    nix-appimage = {
      url = "github:ralismark/nix-appimage";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      nix-appimage,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
    in
    {
      packages = forAll (
        system:
        let
          omnis = nixpkgs.legacyPackages.${system}.callPackage ./package.nix { };
        in
        {
          default = omnis;
          omnis = omnis;
        }
      );

      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/omnis";
        };
      });

      # `nix bundle .#omnis` -> single-file AppImage (bundles Qt/QML + the
      # partition toolchain via package.nix's wrapper).
      bundlers = forAll (system: {
        default = nix-appimage.bundlers.${system}.default;
        appimage = nix-appimage.bundlers.${system}.default;
      });

      devShells = forAll (system: {
        default = nixpkgs.legacyPackages.${system}.mkShell {
          inputsFrom = [ self.packages.${system}.default ];
        };
      });
    };
}
