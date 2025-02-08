{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  inputs.poetry2nix.url = "github:nix-community/poetry2nix";

  outputs = { self, nixpkgs, poetry2nix }:
    let
      supportedSystems =
        [ "x86_64-linux" "x86_64-darwin" "aarch64-linux" "aarch64-darwin" ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
      pkgs = forAllSystems (system: nixpkgs.legacyPackages.${system});
      override = (self: super: {
        piazza-api = super.piazza-api.overridePythonAttrs (old: {
          buildInputs = (old.buildInputs or [ ]) ++ [ super.setuptools ];
        });
      });
    in {
      packages = forAllSystems (system:
        let p2n = poetry2nix.lib.mkPoetry2Nix { pkgs = pkgs.${system}; };
        in {
          default = p2n.mkPoetryApplication {
            projectDir = self;
            overrides = p2n.defaultPoetryOverrides.extend override;
          };
        });

      devShells = forAllSystems (system:
        let p2n = poetry2nix.lib.mkPoetry2Nix { pkgs = pkgs.${system}; };
        in {
          default = pkgs.${system}.mkShellNoCC {
            packages = with pkgs.${system}; [
              (p2n.mkPoetryEnv {
                projectDir = self;
                overrides = p2n.defaultPoetryOverrides.extend override;
              })
              poetry
            ];
          };
        });
    };
}
