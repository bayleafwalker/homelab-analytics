#!/usr/bin/env bash
# lanectl dev train deploy for homelab-analytics: build images from this checkout, start the
# example stack as Compose project $LANE_NAMESPACE, check health, or tear it down.
#   scripts/lane-dev-deploy.sh up | health | down
# lanectl passes LANE_NAMESPACE, LANE_TRAIN_ID and LANE_TTL_S and strips the rest of the
# environment except governance's env_allow (lanectl governance/repos.toml).
set -euo pipefail
: "${LANE_NAMESPACE:?set by lanectl deploy}"
cd "$(dirname "$0")/.."
files=(--project-name "$LANE_NAMESPACE" -f infra/examples/compose.yaml
       -f infra/examples/compose-smoke.override.yaml -f infra/examples/compose-lane-dev.override.yaml)
app="homelab-analytics:$LANE_NAMESPACE"
web="homelab-analytics-web:$LANE_NAMESPACE"

health_of() {   # service container_port
  local addr
  addr=$(docker compose "${files[@]}" port "$1" "$2")
  for _ in $(seq 1 60); do
    if curl -fsS "http://$addr/health" >/dev/null 2>&1; then echo "$1 healthy at $addr"; return 0; fi
    sleep 2
  done
  echo "$1 not healthy at $addr after 120s" >&2
  docker compose "${files[@]}" logs --tail 40 "$1" >&2 || true
  return 1
}

case "${1:-}" in
  up)
    docker build -q -f infra/docker/Dockerfile -t "$app" \
      --label "lanectl.namespace=$LANE_NAMESPACE" .
    docker build -q -f infra/docker/web.Dockerfile -t "$web" \
      --label "lanectl.namespace=$LANE_NAMESPACE" .
    docker compose "${files[@]}" up -d --no-build api web
    ;;
  health)
    health_of api 8080
    health_of web 8081
    ;;
  down)
    docker compose "${files[@]}" down -v --remove-orphans
    docker image rm -f "$app" "$web" >/dev/null 2>&1 || true
    ;;
  *)
    echo "usage: $0 up|health|down" >&2
    exit 2
    ;;
esac
