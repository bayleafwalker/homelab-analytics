SHELL := /usr/bin/bash

PYTHON := $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else command -v python; fi)
PYTEST := $(PYTHON) -m pytest
RUFF := $(PYTHON) -m ruff
MYPY := $(PYTHON) -m mypy
PIP_AUDIT := $(PYTHON) -m pip_audit
WEB_DIR := apps/web/frontend
WEB_NODE_BIN_DIR := $(abspath .tooling/node-v20.20.1-linux-x64/bin)
COMPOSE_FILE := infra/examples/compose.yaml
APP_IMAGE := homelab-analytics:latest
WEB_IMAGE := homelab-analytics-web:latest

TEST ?=
DOMAIN ?=
VERIFY_CONFIG_ARGS ?=
CONTRACT_BASE_REF ?=
CONTRACT_RELEASE_DIR ?= dist/contracts

.PHONY: lint typecheck test test-fast test-target test-integration test-e2e-local \
	test-storage-adapters test-sqlite-adapters test-coverage verify-config verify-docs \
	verify-agent verify-arch verify-fast verify-all verify-domain helm-lint \
	docker-build compose-smoke audit-deps db-migrate-sqlite db-migrate-postgres \
	db-migrate-postgres-control-plane db-migrate-postgres-run-metadata \
	web-codegen web-codegen-check web-token-check web-typecheck web-build demo-generate demo-seed \
	web-ui-test \
	contract-export-check contract-compat-report contract-release-artifacts

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

test-sqlite-adapters:
	$(PYTEST) -q tests/test_blob_store.py tests/test_run_metadata_repository.py tests/test_storage_runtime.py tests/test_sqlite_control_plane_smoke.py tests/test_sqlite_auth_store_contract.py tests/test_migration_runner.py

db-migrate-sqlite:
	@if [ -z "$(DB_PATH)" ]; then echo "DB_PATH is required, e.g. make db-migrate-sqlite DB_PATH=data/config.db"; exit 1; fi
	$(PYTHON) -c "import sqlite3; from pathlib import Path; from packages.storage.migration_runner import apply_pending_sqlite_migrations; conn = sqlite3.connect('$(DB_PATH)'); applied = apply_pending_sqlite_migrations(conn, Path('migrations/sqlite')); conn.close(); print('Applied:', applied or 'none (already up to date)')"

db-migrate-postgres:
	@if [ -z "$(POSTGRES_DSN)" ]; then echo "POSTGRES_DSN is required, e.g. make db-migrate-postgres POSTGRES_DSN=postgresql://..."; exit 1; fi
	$(MAKE) db-migrate-postgres-control-plane POSTGRES_DSN="$(POSTGRES_DSN)"
	$(MAKE) db-migrate-postgres-run-metadata POSTGRES_DSN="$(POSTGRES_DSN)"

db-migrate-postgres-control-plane:
	@if [ -z "$(POSTGRES_DSN)" ]; then echo "POSTGRES_DSN is required, e.g. make db-migrate-postgres-control-plane POSTGRES_DSN=postgresql://..."; exit 1; fi
	$(PYTHON) -c "import psycopg; from pathlib import Path; from packages.storage.migration_runner import apply_pending_postgres_migrations; conn = psycopg.connect('$(POSTGRES_DSN)'); applied = apply_pending_postgres_migrations(conn, Path('migrations/postgres')); conn.close(); print('Applied control-plane:', applied or 'none (already up to date)')"

db-migrate-postgres-run-metadata:
	@if [ -z "$(POSTGRES_DSN)" ]; then echo "POSTGRES_DSN is required, e.g. make db-migrate-postgres-run-metadata POSTGRES_DSN=postgresql://..."; exit 1; fi
	$(PYTHON) -c "import psycopg; from pathlib import Path; from packages.storage.migration_runner import apply_pending_postgres_migrations; conn = psycopg.connect('$(POSTGRES_DSN)'); applied = apply_pending_postgres_migrations(conn, Path('migrations/postgres_run_metadata')); conn.close(); print('Applied run-metadata:', applied or 'none (already up to date)')"

test-storage-adapters:
	$(PYTEST) -q --override-ini addopts=-ra tests/test_blob_store.py tests/test_run_metadata_repository.py tests/test_storage_runtime.py tests/test_sqlite_control_plane_smoke.py tests/test_sqlite_auth_store_contract.py tests/test_control_plane_store_contract.py tests/test_postgres_run_metadata_integration.py tests/test_postgres_ingestion_config_integration.py tests/test_postgres_auth_store_integration.py tests/test_postgres_reporting_integration.py tests/test_s3_postgres_control_plane_integration.py

test-coverage:
	$(PYTEST) -q --cov=apps --cov=packages --cov-report=term-missing

verify-config:
	$(PYTHON) -m apps.worker.main verify-config $(VERIFY_CONFIG_ARGS)

verify-docs:
	$(PYTEST) -q tests/test_requirements_contract.py tests/test_repository_contract.py

verify-agent:
	$(PYTEST) -q tests/test_agent_guidance.py

verify-arch:
	$(PYTEST) -q tests/test_architecture_contract.py

contract-export-check:
	$(PYTHON) -m apps.api.contract_artifacts export-check

contract-compat-report:
	$(PYTHON) -m apps.api.contract_artifacts report \
		$(if $(CONTRACT_BASE_REF),--base-ref $(CONTRACT_BASE_REF),) \
		--output-dir $(CONTRACT_RELEASE_DIR)

contract-release-artifacts:
	$(PYTHON) -m apps.api.contract_artifacts bundle \
		$(if $(CONTRACT_BASE_REF),--base-ref $(CONTRACT_BASE_REF),) \
		--output-dir $(CONTRACT_RELEASE_DIR)

web-codegen:
	PATH=$(WEB_NODE_BIN_DIR):$$PATH npm --prefix $(WEB_DIR) run codegen

web-codegen-check:
	PATH=$(WEB_NODE_BIN_DIR):$$PATH npm --prefix $(WEB_DIR) run codegen:check

web-token-check:
	PATH=$(WEB_NODE_BIN_DIR):$$PATH npm --prefix $(WEB_DIR) run tokens:check

web-typecheck:
	PATH=$(WEB_NODE_BIN_DIR):$$PATH npm --prefix $(WEB_DIR) run typecheck

web-build:
	PATH=$(WEB_NODE_BIN_DIR):$$PATH npm --prefix $(WEB_DIR) run build

web-ui-test:
	PATH=$(WEB_NODE_BIN_DIR):$$PATH npm --prefix $(WEB_DIR) run ui:test

demo-generate:
	$(PYTHON) -m apps.worker.main generate-demo-data --output-dir infra/examples/demo-data

demo-seed:
	$(PYTHON) -m apps.worker.main seed-demo-data --input-dir infra/examples/demo-data

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

verify-fast: lint typecheck test-fast test-sqlite-adapters verify-docs verify-agent verify-arch contract-export-check web-codegen-check web-token-check web-build web-typecheck web-ui-test helm-lint

verify-all: verify-fast test-integration test-e2e-local docker-build

verify-domain:
	@if [ -z "$(DOMAIN)" ]; then \
		echo "DOMAIN is required, for example: make verify-domain DOMAIN=utility"; \
		exit 1; \
	fi
	$(PYTEST) -q tests/test_local_domain_harness.py -k "$(DOMAIN)"
