# Dev shells for STUPA Events: backend (python 3.13, uv) and frontend (node 24).
# Copied from STUPA-Workflow@93c33d6 flake.nix (adapted). Project dependencies come from uv and npm, not Nix.
{
  description = "STUPA Events: event pipeline with dossiers, roles and PWA";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";

  outputs =
    { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};

      # greenlet needs libstdc++, python-magic needs libmagic; a plain `uv sync` cannot supply them.
      nativeLibs = [
        pkgs.stdenv.cc.cc.lib
        pkgs.file
      ];
      libPath = pkgs.lib.makeLibraryPath nativeLibs;

      backendTools = [
        pkgs.python313
        pkgs.uv
        pkgs.ruff
        pkgs.basedpyright
        pkgs.postgresql
        pkgs.age
        pkgs.jq
      ] ++ nativeLibs;

      backendHook = ''
        export LD_LIBRARY_PATH="${libPath}''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        echo "STUPA Events backend: python ${pkgs.python313.version}, uv. Setup: cd backend && uv sync"
      '';

      frontendHook = ''
        echo "STUPA Events frontend: node $(node --version). Setup: git submodule update --init && cd frontend && npm ci"
      '';
    in
    {
      devShells.${system} = {
        default = pkgs.mkShell {
          packages = backendTools ++ [ pkgs.nodejs_24 ];
          shellHook = backendHook + frontendHook;
        };
        backend = pkgs.mkShell {
          packages = backendTools;
          shellHook = backendHook;
        };
        frontend = pkgs.mkShell {
          packages = [ pkgs.nodejs_24 ];
          shellHook = frontendHook;
        };
      };
    };
}
