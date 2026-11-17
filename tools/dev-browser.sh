#!/usr/bin/env bash
# Locked Playwright browser installation and its pinned Linux runtime closure.

dev_browser_root() {
  printf '%s/.tooling/playwright-browsers' "$1"
}

dev_browser_runtime_path() {
  local runtime_root="$1" directory result=""
  for directory in "$runtime_root"/lib/*; do
    [[ -d "$directory" ]] || continue
    result="${result:+$result:}$directory"
  done
  printf '%s' "$result"
}

dev_browser_runtime_fingerprint() {
  cat "$1/tools/dev-browser-runtime/flake.nix" "$1/tools/dev-browser-runtime/flake.lock" \
    "$1/tools/dev-browser-assets.json" "$1/tools/dev-browser-assets.py" \
    | sha256sum | awk '{print $1}'
}

dev_browser_python() {
  local root="$1"
  if [[ -x "$root/.venv/bin/python" ]]; then
    printf '%s' "$root/.venv/bin/python"
  else
    command -v python3 || command -v python
  fi
}

dev_browser_system_assets_match() {
  "$(dev_browser_python "$1")" "$1/tools/dev-browser-assets.py" system-matches
}

dev_materialize_browser_assets() {
  local root="$1" runtime_path="${2:-system}"
  dev_require_owned_path "$root" ".tooling/playwright-fonts" "Playwright font bundle"
  dev_require_owned_path "$root" ".tooling/playwright-fontconfig" "Playwright Fontconfig bundle"
  dev_require_owned_path "$root" ".tooling/fontconfig-cache" "Fontconfig cache"
  if [[ "$runtime_path" == system ]]; then
    "$(dev_browser_python "$root")" "$root/tools/dev-browser-assets.py" materialize-system
  else
    "$(dev_browser_python "$root")" "$root/tools/dev-browser-assets.py" materialize \
      "$runtime_path/assets"
  fi
}

dev_browser_executable() {
  local root="$1" frontend="$1/apps/web/frontend"
  "$root/.tooling/node-v20.20.1-linux-x64/bin/node" \
    "$root/tools/dev-playwright-executable.cjs" \
    "$frontend/node_modules/playwright-core/lib/server/registry/index.js"
}

dev_browser_missing_libraries() {
  local browser="$1" loader_path="$2"
  if [[ -n "$loader_path" ]]; then
    LD_LIBRARY_PATH="$loader_path" ldd "$browser" 2>&1
  else
    env -u LD_LIBRARY_PATH ldd "$browser" 2>&1
  fi | sed -n 's/^[[:space:]]*\([^[:space:]]*\)[[:space:]]*=>[[:space:]]*not found.*/\1/p'
}

dev_materialize_browser_runtime() {
  local root="$1" runtime_link provenance_file runtime_path build_log expected_runtime missing browser assets_match
  runtime_link="$root/.tooling/playwright-runtime"
  provenance_file="$root/.tooling/playwright-runtime.provenance"
  [[ "$(uname -s)" == Linux ]] || return 0
  [[ ! -L "$provenance_file" ]] \
    || dev_fail "Chromium runtime provenance is symlinked outside this checkout: $provenance_file"
  command -v ldd >/dev/null 2>&1 || dev_fail "ldd is required to check Playwright's Linux browser runtime"
  browser="$(dev_browser_executable "$root")"
  [[ -n "$browser" && -x "$browser" ]] \
    || dev_fail "locked Playwright Chromium headless shell was not installed; run 'make dev-setup'"
  missing="$(dev_browser_missing_libraries "$browser" "")"
  assets_match=0
  if dev_browser_system_assets_match "$root"; then assets_match=1; fi
  if [[ -z "$missing" && "$assets_match" == 1 ]]; then
    dev_materialize_browser_assets "$root" system
    return 0
  fi
  expected_runtime="source-sha256=$(dev_browser_runtime_fingerprint "$root")"
  if [[ -L "$runtime_link" ]]; then
    runtime_path="$(realpath -e "$runtime_link" 2>/dev/null)" \
      || dev_fail "the pinned Chromium runtime link is dangling; rerun 'make dev-setup'"
    [[ "$runtime_path" == /nix/store/*-hla-playwright-runtime ]] \
      || dev_fail "the Chromium runtime link does not point to its Nix store closure"
    if [[ -f "$provenance_file" && ! -L "$provenance_file" ]] \
      && [[ "$(<"$provenance_file")" == "$expected_runtime store-path=$runtime_path" ]]; then
      missing="$(dev_browser_missing_libraries "$browser" "$(dev_browser_runtime_path "$runtime_link")")"
      if [[ -z "$missing" ]]; then
        if [[ "$assets_match" == 1 ]]; then
          dev_materialize_browser_assets "$root" system
        else
          dev_materialize_browser_assets "$root" "$runtime_path"
        fi
        return 0
      fi
    fi
    rm "$runtime_link"
  elif [[ -e "$runtime_link" ]]; then
    dev_fail "the Chromium runtime path is not the verified pinned Nix closure: $runtime_link"
  fi

  [[ -f "$root/tools/dev-browser-runtime/flake.lock" ]] \
    || dev_fail "the pinned Chromium runtime lock is missing; native libraries ($missing), font payloads, and Fontconfig rules cannot be verified"
  if ! command -v nix >/dev/null 2>&1; then
    if [[ -n "$missing" ]]; then
      dev_fail "Chromium is missing native libraries ($missing); install Playwright's Linux dependencies or Nix, then rerun 'make dev-setup'"
    fi
    dev_fail "host font payloads or Fontconfig rules differ from the visual baseline; install Nix to materialize the pinned bundle, then rerun 'make dev-setup'"
  fi
  mkdir -p "$root/.tooling"
  build_log="$root/.tooling/playwright-runtime-build.log"
  printf 'Building the pinned Playwright native runtime for Chromium...\n'
  if ! XDG_CACHE_HOME="$root/.tooling/nix-cache" \
    XDG_STATE_HOME="$root/.tooling/nix-state" \
    nix --extra-experimental-features 'nix-command flakes' build \
      "$root/tools/dev-browser-runtime#default" --out-link "$runtime_link" 2>"$build_log"; then
    cat "$build_log" >&2
    dev_fail "could not build the pinned Chromium runtime; repair Nix cache/network access and rerun 'make dev-setup'"
  fi
  runtime_path="$(realpath -e "$runtime_link" 2>/dev/null)" \
    || dev_fail "Nix did not create the pinned Chromium runtime link"
  [[ "$runtime_path" == /nix/store/*-hla-playwright-runtime && -d "$runtime_path/lib" ]] \
    || dev_fail "pinned Chromium runtime has an unexpected store path: $runtime_path"
  printf '%s store-path=%s\n' "$expected_runtime" "$runtime_path" > "$provenance_file"
  missing="$(dev_browser_missing_libraries "$browser" "$(dev_browser_runtime_path "$runtime_link")")"
  [[ -z "$missing" ]] \
    || dev_fail "pinned Chromium runtime still lacks native libraries ($missing); report this platform mismatch"
  if [[ "$assets_match" == 1 ]]; then
    dev_materialize_browser_assets "$root" system
  else
    dev_materialize_browser_assets "$root" "$runtime_path"
  fi
}

dev_browser_provenance() {
  local root="$1" frontend="$1/apps/web/frontend" version lock_hash browser
  lock_hash="$(sha256sum "$frontend/package-lock.json" | awk '{print $1}')" \
    || dev_fail "sha256sum is required to fingerprint the locked frontend browser"
  version="$(node -e 'process.stdout.write(require(process.argv[1]).version)' "$frontend/node_modules/playwright/package.json" 2>/dev/null)" \
    || dev_fail "locked Playwright package is missing; run 'make dev-setup'"
  browser="$(dev_browser_executable "$root")"
  printf 'package-lock-sha256=%s playwright-version=%s browser-path=%s\n' \
    "$lock_hash" "$version" "$browser"
}

dev_install_browser() {
  local root="$1" browser_root provenance
  browser_root="$(dev_browser_root "$root")"
  dev_require_owned_path "$root" ".tooling/playwright-browsers" "Playwright browser install"
  dev_require_owned_path "$root" "apps/web/frontend/node_modules" "frontend dependencies"
  [[ ! -L "$browser_root/.hla-playwright-provenance" ]] \
    || dev_fail "Playwright browser provenance is a symlink; remove it and rerun 'make dev-setup'"
  command -v sha256sum >/dev/null 2>&1 \
    || dev_fail "sha256sum is required to verify the locked Playwright browser install"
  export PLAYWRIGHT_BROWSERS_PATH="$browser_root"
  printf 'Installing the Chromium revision selected by package-lock.json...\n'
  npm --prefix "$root/apps/web/frontend" exec -- playwright install chromium \
    || dev_fail "Playwright could not install its locked Chromium revision; check network access and retry 'make dev-setup'"
  provenance="$(dev_browser_provenance "$root")"
  printf '%s\n' "$provenance" > "$browser_root/.hla-playwright-provenance"
  dev_materialize_browser_runtime "$root"
}

dev_prepare_browser_env() {
  local root="$1" browser_root runtime_link provenance_file provenance browser missing runtime_path
  browser_root="$(dev_browser_root "$root")"
  runtime_link="$root/.tooling/playwright-runtime"
  provenance_file="$root/.tooling/playwright-runtime.provenance"
  [[ ! -L "$provenance_file" ]] \
    || dev_fail "Chromium runtime provenance is symlinked outside this checkout: $provenance_file"
  dev_require_owned_path "$root" ".tooling/playwright-browsers" "Playwright browser install"
  [[ -d "$browser_root" ]] || dev_fail "Playwright Chromium is missing; run 'make dev-setup'"
  [[ -f "$browser_root/.hla-playwright-provenance" && ! -L "$browser_root/.hla-playwright-provenance" ]] \
    || dev_fail "Playwright Chromium has no checkout-owned install provenance; run 'make dev-setup'"
  export PLAYWRIGHT_BROWSERS_PATH="$browser_root"
  provenance="$(dev_browser_provenance "$root")"
  [[ "$(<"$browser_root/.hla-playwright-provenance")" == "$provenance" ]] \
    || dev_fail "Playwright Chromium does not match the current package lock; run 'make dev-setup'"
  browser="$(dev_browser_executable "$root")"
  [[ -n "$browser" && -x "$browser" ]] || dev_fail "locked Playwright Chromium is unusable; run 'make dev-setup'"
  [[ "$browser" == "$browser_root"/* ]] \
    || dev_fail "Playwright's selected Chromium resolves outside this checkout's owned browser install"
  if [[ -f "$provenance_file" ]]; then
    local expected_runtime
    expected_runtime="source-sha256=$(dev_browser_runtime_fingerprint "$root")"
    [[ -L "$runtime_link" ]] \
      || dev_fail "pinned Chromium runtime closure is missing; run 'make dev-setup'"
    runtime_path="$(realpath -e "$runtime_link" 2>/dev/null)" \
      || dev_fail "pinned Chromium runtime closure is dangling; run 'make dev-setup'"
    [[ "$runtime_path" == /nix/store/*-hla-playwright-runtime ]] \
      || dev_fail "Chromium runtime does not resolve to the pinned Nix closure"
    provenance="$expected_runtime store-path=$runtime_path"
    [[ "$(<"$provenance_file")" == "$provenance" ]] \
      || dev_fail "pinned Chromium runtime provenance is stale; run 'make dev-setup'"
    export LD_LIBRARY_PATH="$(dev_browser_runtime_path "$runtime_link")"
  else
    unset LD_LIBRARY_PATH
  fi
  missing="$(dev_browser_missing_libraries "$browser" "${LD_LIBRARY_PATH:-}")"
  [[ -z "$missing" ]] \
    || dev_fail "Chromium cannot load native libraries ($missing); install Playwright's Linux dependencies and rerun 'make dev-setup'"
  if ! "$(dev_browser_python "$root")" "$root/tools/dev-browser-assets.py" materialized-matches; then
    if dev_browser_system_assets_match "$root"; then
      dev_materialize_browser_assets "$root" system
    else
      dev_fail "Playwright font and Fontconfig bundle is missing or changed; run 'make dev-setup'"
    fi
  fi
  export FONTCONFIG_FILE="$root/.tooling/playwright-fontconfig/fonts.conf"
  export FONTCONFIG_PATH="$root/.tooling/playwright-fontconfig"
  export XDG_CACHE_HOME="$root/.tooling/fontconfig-cache"
  export XDG_CONFIG_HOME="$root/.tooling/playwright-xdg-config"
  export HOME="$root/.tooling/playwright-home"
  unset FONTCONFIG_SYSROOT
}
