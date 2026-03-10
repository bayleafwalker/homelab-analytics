PYTHON := $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else command -v python; fi)
PYTEST := $(PYTHON) -m pytest
RUFF := $(PYTHON) -m ruff
MYPY := $(PYTHON) -m mypy
PIP_AUDIT := $(PYTHON) -m pip_audit

TEST ?=
DOMAIN ?=
VERIFY_CONFIG_ARGS ?=

.PHONY: lint typecheck test test-fast test-target test-integration test-e2e-local \
	test-storage-adapters verify-config verify-docs verify-agent verify-arch verify-fast \
	verify-all verify-domain helm-lint docker-build audit-deps

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
	$(PYTEST) -q tests/test_blob_store.py tests/test_run_metadata_repository.py tests/test_storage_runtime.py tests/test_postgres_run_metadata_integration.py tests/test_postgres_reporting_integration.py

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
	docker build -f infra/docker/Dockerfile -t homelab-analytics .

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
