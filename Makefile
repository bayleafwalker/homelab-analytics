SHELL := /usr/bin/bash

PYTHON := $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else command -v python; fi)
PYTEST := $(PYTHON) -m pytest
RUFF := $(PYTHON) -m ruff
MYPY := $(PYTHON) -m mypy
PIP_AUDIT := $(PYTHON) -m pip_audit
COMPOSE_FILE := infra/examples/compose.yaml
APP_IMAGE := homelab-analytics:latest
WEB_IMAGE := homelab-analytics-web:latest

TEST ?=
DOMAIN ?=
VERIFY_CONFIG_ARGS ?=

.PHONY: lint typecheck test test-fast test-target test-integration test-e2e-local \
	test-storage-adapters verify-config verify-docs verify-agent verify-arch verify-fast \
	verify-all verify-domain helm-lint docker-build compose-smoke audit-deps

lint:
	$(RUFF) check .

typecheck:
	$(MYPY) apps packages

test:
	$(PYTEST) -q

test-fast:
	$(PYTEST) -q -m "not slow"

test-target:
	$(PYTEST) -q $(TEST)

test-integration:
	$(PYTEST) -q -m integration

test-e2e-local:
	$(PYTEST) -q -m e2e

test-storage-adapters:
	$(PYTEST) -q tests/test_blob_store.py tests/test_run_metadata_repository.py tests/test_storage_runtime.py tests/test_sqlite_control_plane_contract.py tests/test_sqlite_auth_store_contract.py tests/test_postgres_run_metadata_integration.py tests/test_postgres_ingestion_config_integration.py tests/test_postgres_auth_store_integration.py tests/test_postgres_reporting_integration.py tests/test_s3_postgres_control_plane_integration.py

verify-config:
	$(PYTHON) -m apps.worker.main verify-config $(VERIFY_CONFIG_ARGS)

verify-docs:
	$(PYTEST) -q tests/test_requirements_contract.py tests/test_repository_contract.py

verify-agent:
	$(PYTEST) -q tests/test_agent_guidance.py

verify-arch:
	$(PYTEST) -q tests/test_architecture_contract.py

helm-lint:
	helm lint charts/homelab-analytics

docker-build:
	docker build -f infra/docker/Dockerfile -t $(APP_IMAGE) .
	docker build -f infra/docker/web.Dockerfile -t $(WEB_IMAGE) .

compose-smoke:
	@set -euo pipefail; \
	trap 'docker compose -f $(COMPOSE_FILE) down -v --remove-orphans' EXIT; \
	if ! docker image inspect $(APP_IMAGE) >/dev/null 2>&1 || ! docker image inspect $(WEB_IMAGE) >/dev/null 2>&1; then \
		$(MAKE) docker-build; \
	fi; \
	docker compose -f $(COMPOSE_FILE) up -d api web; \
	for attempt in $$(seq 1 30); do \
		if curl -fsS http://127.0.0.1:8080/health >/dev/null; then \
			break; \
		fi; \
		if [ "$$attempt" -eq 30 ]; then \
			echo "API health check did not become ready"; \
			exit 1; \
		fi; \
		sleep 2; \
	done; \
	for attempt in $$(seq 1 30); do \
		if curl -fsS http://127.0.0.1:8081/health >/dev/null; then \
			break; \
		fi; \
		if [ "$$attempt" -eq 30 ]; then \
			echo "Web health check did not become ready"; \
			exit 1; \
		fi; \
		sleep 2; \
	done; \
	docker compose -f $(COMPOSE_FILE) --profile worker run --rm worker list-runs >/dev/null

audit-deps:
	-$(PIP_AUDIT)

verify-fast: lint typecheck test-fast verify-docs verify-agent verify-arch helm-lint

verify-all: verify-fast test-integration test-e2e-local docker-build

verify-domain:
	@if [ -z "$(DOMAIN)" ]; then \
		echo "DOMAIN is required, for example: make verify-domain DOMAIN=utility"; \
		exit 1; \
	fi
	$(PYTEST) -q tests/test_local_domain_harness.py -k "$(DOMAIN)"
