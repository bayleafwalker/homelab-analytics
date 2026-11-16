#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=tools/dev-env.sh
source "$ROOT/tools/dev-env.sh"

fail() { printf 'dev setup error: %s\n' "$*" >&2; exit 1; }

command -v uv >/dev/null 2>&1 || fail "uv is required to prepare the locked Python environment"
[[ -f "$ROOT/uv.lock" ]] || fail "uv.lock is missing; this checkout cannot install a locked Python environment"
[[ -f "$ROOT/apps/web/frontend/package.json" ]] || fail "frontend package.json is missing"
[[ -f "$ROOT/apps/web/frontend/package-lock.json" ]] || fail "frontend package-lock.json is missing; commit a lockfile before setup"
dev_require_owned_path "$ROOT" ".tooling" "tooling directory"
dev_require_owned_path "$ROOT" ".venv" "Python environment"
dev_require_owned_path "$ROOT" "apps/web/frontend" "frontend checkout"
dev_require_owned_path "$ROOT" "apps/web/frontend/node_modules" "frontend dependencies"
dev_require_owned_path "$ROOT" "apps/web/frontend/.next" "Next.js build output"
[[ -z "${UV_PROJECT_ENVIRONMENT:-}" ]] \
  || fail "UV_PROJECT_ENVIRONMENT redirects the Python environment; unset it to keep setup inside this checkout"
for npm_target_setting in npm_config_prefix NPM_CONFIG_PREFIX npm_config_global NPM_CONFIG_GLOBAL; do
  [[ -z "${!npm_target_setting:-}" ]] \
    || fail "$npm_target_setting redirects npm installation; unset it to keep dependencies inside this checkout"
done

NODE_DIR="$ROOT/.tooling/node-v20.20.1-linux-x64/bin"
if [[ ! -x "$NODE_DIR/node" || ! -f "$NODE_DIR/npm" ]]; then
  [[ ! -e "$ROOT/.tooling/node-v20.20.1-linux-x64" ]] \
    || fail "incomplete pinned Node runtime at $ROOT/.tooling/node-v20.20.1-linux-x64; remove that owned runtime directory and retry"
  [[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] \
    || fail "automatic Node bootstrap supports Linux x86_64; install the repository-pinned Node.js 20.20.1 runtime for this platform"
  command -v curl >/dev/null 2>&1 || fail "curl is required to bootstrap the pinned Node.js runtime"
  command -v sha256sum >/dev/null 2>&1 || fail "sha256sum is required to verify the pinned Node.js runtime"
  command -v tar >/dev/null 2>&1 || fail "tar is required to unpack the pinned Node.js runtime"

  archive_name="$HLA_NODE_ARCHIVE"
  archive_sha256="$HLA_NODE_ARCHIVE_SHA256"
  archive_url="https://nodejs.org/dist/v20.20.1/$archive_name"
  mkdir -p "$ROOT/.tooling"
  install_tmp="$(mktemp -d "$ROOT/.tooling/.node-install.XXXXXX")"
  trap 'rm -rf "$install_tmp"' EXIT
  printf 'Downloading pinned Node.js 20.20.1 from nodejs.org...\n'
  if ! curl --fail --location --retry 2 --output "$install_tmp/$archive_name" "$archive_url"; then
    fail "could not download $archive_url; check network access and retry make dev-setup"
  fi
  printf '%s  %s\n' "$archive_sha256" "$install_tmp/$archive_name" | sha256sum --check --status \
    || fail "Node.js archive SHA-256 did not match the published Node.js 20.20.1 checksum"
  mkdir "$install_tmp/runtime"
  tar -xzf "$install_tmp/$archive_name" -C "$install_tmp/runtime" --strip-components=1 \
    || fail "could not unpack the verified Node.js archive"
  [[ "$($install_tmp/runtime/bin/node --version)" == v20.20.1 ]] \
    || fail "verified Node.js archive did not contain runtime v20.20.1"
  "$install_tmp/runtime/bin/node" "$install_tmp/runtime/bin/npm" --version >/dev/null \
    || fail "verified Node.js archive contains an unusable npm runtime"
  printf '%s\n' "$HLA_NODE_PROVENANCE" > "$install_tmp/runtime/.hla-node-provenance"
  mv "$install_tmp/runtime" "$ROOT/.tooling/node-v20.20.1-linux-x64"
  rm -f "$install_tmp/$archive_name"
  rmdir "$install_tmp"
  trap - EXIT
fi

dev_prepare_env "$ROOT"
mkdir -p "$ROOT/.tooling"
# Keep package-manager write caches inside the checkout, so warm setup does not
# depend on mutating a user-wide cache or reuse another checkout's cache.
export UV_PROJECT_ENVIRONMENT="$ROOT/.venv"
export UV_CACHE_DIR="$ROOT/.tooling/uv-cache"
printf 'Preparing locked Python dependencies...\n'
(cd "$ROOT" && uv sync --locked --extra dev) \
  || fail "uv could not prepare dependencies from uv.lock; check the Python lock and package availability"
dev_require_python_env "$ROOT"

printf 'Installing locked frontend dependencies with npm ci...\n'
if ! npm --cache "$ROOT/.tooling/npm-cache" --prefix "$ROOT/apps/web/frontend" ci; then
  fail "npm ci failed; check package-lock.json compatibility, registry access, and native build prerequisites (including esbuild)"
fi
ESBUILD="$ROOT/apps/web/frontend/node_modules/@esbuild/linux-x64/bin/esbuild"
if [[ ! -x "$ESBUILD" ]] || ! "$ESBUILD" --version >/dev/null 2>&1; then
  fail "frontend dependencies were installed but the esbuild native executable is unusable; retry npm ci after checking platform support and package availability"
fi
printf 'HLA development dependencies are ready.\n'
