---
specialist: test-quality
---

## Scope

Detect tests that lower confidence: behavior-pinning assertions without an independent
specification, mocks of the primary unit under test, trivially true or empty tests, and
growth in already-bloated test files without a split or justification.

Pay particular attention to growth in `tests/test_api_app.py`, `tests/test_worker_cli.py`,
`tests/test_adapter_contracts.py`, `tests/test_api_main.py`,
`tests/test_architecture_contract.py`, and `tests/control_plane_test_support.py`.

## Severity guidance

- `blocker`: an empty test or a trivially true assertion added by the diff.
- `advisory`: unmotivated growth in a calibration-anchor file or behavior-pinning
  assertions in new test code.
- `watchlist`: an unchanged bloated test file.

Return `[]` when no findings apply.