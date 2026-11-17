#!/usr/bin/env bash

dev_run_local_test_runtime_probe() {
  local python="$1" probe="$2" duration="${3:-10}"
  if ! timeout --kill-after=1s "${duration}s" "$python" "$probe"; then
    printf 'local FastAPI/TestClient runtime probe failed or timed out within %ss\n' "$duration" >&2
    return 1
  fi
}
