# Testing And Verification

**Classification:** CROSS-CUTTING

This runbook is the operator-facing reference for local verification.

Use it when you need to decide which verification path to run, how broad the run should be, and how to capture logs for later handoff or agent review.

## Choose The Smallest Useful Run

### 1. Changed-surface check

Use this during normal implementation when you changed a small number of files and want fast signal.

- Lint changed Python files: `./.venv/bin/python -m ruff check <files>`
- Typecheck changed Python files: `./.venv/bin/python -m mypy <files-or-packages>`
- Run targeted tests: `./.venv/bin/python -m pytest <changed-tests> -x --tb=short`
- Check backend contract exports when route or publication contracts changed: `./.venv/bin/python -m apps.api.contract_artifacts export-check`

Recommended pattern:

```bash
cd /projects/dev/homelab-analytics

./.venv/bin/python -m ruff check apps/api/routes/adapter_routes.py tests/test_adapter_contracts.py
./.venv/bin/python -m mypy apps/api/routes/adapter_routes.py packages/adapters/compatibility.py
./.venv/bin/python -m pytest -q tests/test_adapter_contracts.py tests/test_assistant_confidence.py -x --tb=short
./.venv/bin/python -m apps.api.contract_artifacts export-check
```

### 2. Pre-push fast gate

Use this before opening a PR or pushing a branch that will trigger CI.

- Run: `make verify-fast`
- Scope: lint, typecheck, Python fast-path tests, contract export sync, frontend checks, and Helm lint
- Expected use: blocking local gate before push

```bash
cd /projects/dev/homelab-analytics
make verify-fast
```

### 3. Full suite

Use this when you want the slowest, broadest local signal or when an agent/reviewer specifically needs the full test output.

- Run: `make test`
- Scope: full Python test suite
- Expected use: operator-initiated deep validation, not the default inner-loop gate

```bash
cd /projects/dev/homelab-analytics
make test
```

## Best Logging Options

### 1. Plain log files with `tee`

Use this when you want simple log files for later reading.

```bash
cd /projects/dev/homelab-analytics

LOG_DIR="/projects/dev/homelab-analytics/.artifacts/test-logs/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR"

make verify-fast 2>&1 | tee "$LOG_DIR/verify-fast.log"
make test 2>&1 | tee "$LOG_DIR/full-test.log"

printf '%s\n' "$LOG_DIR" | tee "$LOG_DIR/_log_dir.txt"
```

Use this when:

- you want readable text logs
- you do not need exact terminal control sequences preserved
- you plan to hand the directory path to another agent later

### 2. Slow or buffered commands with `stdbuf`

Use this when a long-running `make` target buffers too much output before writing it.

```bash
cd /projects/dev/homelab-analytics

LOG_DIR="/projects/dev/homelab-analytics/.artifacts/test-logs/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR"

stdbuf -oL -eL make verify-fast 2>&1 | tee "$LOG_DIR/verify-fast.log"
stdbuf -oL -eL make test 2>&1 | tee "$LOG_DIR/full-test.log"

printf '%s\n' "$LOG_DIR" | tee "$LOG_DIR/_log_dir.txt"
```

Use this when:

- you want line-buffered output
- `tee` alone does not flush often enough
- you still want plain-text logs rather than a terminal transcript

### 3. Exact terminal transcript with `script`

Use this when you want the closest match to what was shown live in the terminal.

On this host, the output file must be the final positional argument.

```bash
cd /projects/dev/homelab-analytics

LOG_DIR="/projects/dev/homelab-analytics/.artifacts/test-logs/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR"

script -q -f -c "make verify-fast" "$LOG_DIR/verify-fast.typescript"
script -q -f -c "make test" "$LOG_DIR/full-test.typescript"

printf '%s\n' "$LOG_DIR" | tee "$LOG_DIR/_log_dir.txt"
```

Use this when:

- you need continuous flush behavior
- you want a full terminal transcript rather than just stdout and stderr
- you expect another operator or agent to inspect exactly what you saw

Do not use this host-specific invalid form:

```bash
script -q -f "$LOG_DIR/verify-fast.typescript" -c "make verify-fast"
```

That ordering fails here with `script: unexpected number of arguments`.

## Recommended Defaults

For everyday development:

1. run changed-surface checks first
2. run `make verify-fast` before push or PR
3. run `make test` only when you want full slow validation or need a full-suite log artifact

For logging:

1. use `tee` by default
2. switch to `stdbuf ... | tee` if output buffering is annoying
3. use `script -q -f -c ... <file>` when you need a terminal transcript for handoff

## Handoff Path Convention

When you want to hand logs to another agent or save a reusable reference, give the directory path rather than an individual file path.

Example:

```text
/projects/dev/homelab-analytics/.artifacts/test-logs/20260407-215907
```

That directory should contain:

- `_log_dir.txt`
- one or more verification log files such as `verify-fast.log`, `full-test.log`, or `*.typescript`

## Related References

- `docs/runbooks/project-working-practices.md`
- `docs/runbooks/release-governance.md`
- `docs/architecture/contract-governance.md`
- `.agents/skills/code-change-verification/SKILL.md`