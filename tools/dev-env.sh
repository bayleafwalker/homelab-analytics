#!/usr/bin/env bash
# Shared runtime checks for HLA-owned development entrypoints.

HLA_NODE_ARCHIVE="node-v20.20.1-linux-x64.tar.gz"
HLA_NODE_ARCHIVE_SHA256="6362e50804cdcc110592201f67beda93bcd702fdcbe1c42840a50d590e3af0ce"
HLA_NODE_PROVENANCE="archive=$HLA_NODE_ARCHIVE sha256=$HLA_NODE_ARCHIVE_SHA256"

dev_fail() {
  printf 'dev environment error: %s\n' "$*" >&2
  exit 1
}

dev_prepare_env() {
  local root="$1"
  local node_home="$root/.tooling/node-v20.20.1-linux-x64"
  local expected_home
  local node_dir="$node_home/bin"
  local node="$node_dir/node"
  local npm="$node_dir/npm"
  local version gcc_lib provenance resolved

  [[ -d "$node_home" && ! -L "$node_home" ]] \
    || dev_fail "owned pinned Node runtime directory is missing or symlinked at $node_home; run 'make dev-setup'"
  expected_home="$(cd "$root" && pwd -P)/.tooling/node-v20.20.1-linux-x64"
  command -v realpath >/dev/null 2>&1 || dev_fail "realpath is required to verify the owned Node runtime path"
  [[ "$(realpath -e "$node_home" 2>/dev/null)" == "$expected_home" ]] \
    || dev_fail "pinned Node runtime resolves outside this checkout at $node_home"
  [[ -f "$node_home/.hla-node-provenance" && ! -L "$node_home/.hla-node-provenance" ]] \
    || dev_fail "pinned Node runtime has no checksum-verified install provenance; remove $node_home and run 'make dev-setup'"
  provenance="$(<"$node_home/.hla-node-provenance")"
  [[ "$provenance" == "$HLA_NODE_PROVENANCE" ]] \
    || dev_fail "pinned Node runtime provenance does not match the repository checksum; remove $node_home and run 'make dev-setup'"
  for resolved in "$node" "$npm"; do
    resolved="$(realpath -e "$resolved" 2>/dev/null)" \
      || dev_fail "pinned Node or npm is unusable inside $node_home"
    [[ "$resolved" == "$expected_home"/* ]] \
      || dev_fail "pinned Node or npm resolves outside this checkout's verified runtime"
  done
  [[ -x "$node" ]] || dev_fail "pinned Node.js 20.20.1 is missing at $node; run 'make dev-setup'"
  [[ -f "$npm" ]] || dev_fail "pinned npm launcher is missing at $npm; run 'make dev-setup'"
  version="$("$node" --version 2>/dev/null)" || dev_fail "pinned Node.js at $node cannot run; run 'make dev-setup'"
  [[ "$version" == v20.20.1 ]] || dev_fail "expected pinned Node.js v20.20.1 at $node, found ${version:-unusable}; run 'make dev-setup' after removing the invalid runtime"
  PATH="$node_dir:$PATH"
  export PATH
  "$node" "$npm" --version >/dev/null 2>&1 || dev_fail "pinned npm cannot run with $node; run 'make dev-setup'"

  # DuckDB needs libstdc++ on some Nix-built Python installations. Only add a
  # loader directory after measuring that it contains the required library.
  for gcc_lib in /nix/store/*-gcc-*-lib/lib; do
    if [[ -f "$gcc_lib/libstdc++.so.6" ]]; then
      case ":${LD_LIBRARY_PATH:-}:" in
        *":$gcc_lib:"*) ;;
        *) export LD_LIBRARY_PATH="$gcc_lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" ;;
      esac
      break
    fi
  done
}

dev_require_python_env() {
  local root="$1"
  [[ -x "$root/.venv/bin/python" ]] || dev_fail "project Python environment is missing; run 'make dev-setup'"
  "$root/.venv/bin/python" -c 'import sys; assert sys.version_info >= (3, 11)' 2>/dev/null \
    || dev_fail "project Python must be 3.11 or newer; run 'make dev-setup' with a supported Python"
  "$root/.venv/bin/python" -c 'import duckdb' >/dev/null 2>&1 \
    || dev_fail "project Python cannot load the locked DuckDB runtime; install libstdc++ or repair LD_LIBRARY_PATH before running HLA checks"
}
