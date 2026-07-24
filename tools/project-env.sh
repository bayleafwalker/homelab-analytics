# Shared project environment for homelab-analytics.
#
# Single source of truth for the project-scoped sprintctl/kctl/auditctl vars and
# the duckdb libstdc++ loader path. Sourced by:
#   - .envrc (direnv / interactive shells)
#   - agents and CLIs that need the env without direnv (Claude, Codex, etc.)
#
# MUST stay safe to source from any shell and any cwd: no `set -e`, no `:?`
# assertions, no hard exits. It is idempotent — re-sourcing does not duplicate
# path entries. The one fail-fast assertion (SPRINTCTL_URL) lives in .envrc.

# Resolve repo root from this file's own location, so values are correct
# regardless of the caller's working directory.
if [ -n "${BASH_SOURCE[0]:-}" ]; then
  _pe_self="${BASH_SOURCE[0]}"
else
  _pe_self="$0"
fi
_pe_repo_root="$(cd "$(dirname "${_pe_self}")/.." && pwd)"

# duckdb needs libstdc++, which is not on the default loader path when the venv
# is built against the workstation Python rather than the devbox image Python.
# The gcc store hash rotates on each nix update, so glob for a current one rather
# than pinning a hash that will silently go stale.
for _pe_gcc_lib in /nix/store/*-gcc-*-lib/lib; do
  if [ -f "${_pe_gcc_lib}/libstdc++.so.6" ]; then
    case ":${LD_LIBRARY_PATH:-}:" in
      *":${_pe_gcc_lib}:"*) ;;  # already present — keep idempotent
      *) export LD_LIBRARY_PATH="${_pe_gcc_lib}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}" ;;
    esac
    break
  fi
done
unset _pe_gcc_lib

export SPRINTCTL_DB="${_pe_repo_root}/.sprintctl/sprintctl.db"
# sprintctl runs in served mode against the Vuoro work adapter (backfilled
# into vuoro-shared 2026-07-24 -- see sprintctl
# docs/plans/1164-gate-evidence-ledger.md). Direct PostgreSQL credentials
# are no longer the default path; set SPRINTCTL_BACKEND=remote in
# .env.sprintctl.local (still sourced below) to roll back.
export SPRINTCTL_BACKEND=served
export SPRINTCTL_VUORO_PROFILE=/projects/dev/agentops/templates/dispatch/environment-record/profiles/workstation-vuoro-shared.json
if [ -d "/home/dev/.local/bin" ]; then
  case ":${PATH}:" in
    *":/home/dev/.local/bin:"*) ;;
    *) export PATH="/home/dev/.local/bin:${PATH}" ;;
  esac
fi
if [ -f "${_pe_repo_root}/.env.sprintctl.local" ]; then
  # shellcheck disable=SC1091
  . "${_pe_repo_root}/.env.sprintctl.local"
fi
export KCTL_DB="${_pe_repo_root}/.kctl/kctl.db"
export AUDITCTL_DB="${_pe_repo_root}/.auditctl/auditctl.db"
export AUDITCTL_ARTIFACTS_ROOT="/projects/dev"

unset _pe_self _pe_repo_root
