---
specialist: test-quality
model: haiku
---

## Scope

Detect tests that reduce confidence rather than increase it, and additions that worsen
already-bloated test files. Check for:

1. **Behavior pinning** — assertions of the form `assert result == current_output` without
   an independent specification of what the correct output should be. These lock in
   current behavior including bugs.
2. **Mock circularity** — tests that mock the primary thing under test (e.g., mocking
   `TransactionService` in `test_transaction_service.py`) so the test can only verify
   the mock, not the implementation.
3. **Green-build padding** — new test functions added to make a failing build pass without
   covering new logic (empty tests, trivially true assertions, `assert True`).
4. **God-class test growth** — new content added to already-bloated test files without
   a split or a comment explaining why this file is the right location.

## Reference docs

- `docs/runbooks/project-working-practices.md` — working practices, change-class done
  criteria, test expectations for behavior changes

## Calibration anchors — flag any addition to these files

Additions to the files below should come with a justification or a note in the review.
They are already large; growing them further makes review harder:

`tests/test_api_app.py` 2,758 LOC |
`tests/test_worker_cli.py` 1,703 LOC |
`tests/test_adapter_contracts.py` 1,502 LOC |
`tests/test_api_main.py` 1,280 LOC |
`tests/test_architecture_contract.py` 1,276 LOC |
`tests/control_plane_test_support.py` 1,260 LOC

## Does NOT duplicate

No existing test audits test quality. The contract test suite enforces structural
completeness, not whether individual tests provide meaningful coverage or are correctly
structured. This specialist is entirely uncovered by the test suite.

## Severity guidance

- **blocker**: Empty test function or trivially true assertion added in this scope.
- **advisory**: New content added to a calibration-anchor file without split or
  justification; behavior-pinning assertion detected in new test code.
- **watchlist**: Pre-existing bloated file that was not changed in this scope.

## Output schema

Return a JSON array. `line` is the line number of the problematic assertion or test
function. Use null for file-level findings.

```json
[
  {
    "specialist": "test-quality",
    "severity": "blocker | advisory | watchlist",
    "file": "tests/test_api_app.py",
    "line": null,
    "finding": "New test function added to 2,758 LOC file without split or justification",
    "evidence": "def test_new_endpoint_behavior — file grew from 2758 to 2789 lines",
    "recommendation": "Extract new endpoint tests to tests/test_new_endpoint.py",
    "blocker": false
  }
]
```

Return `[]` if no findings.
