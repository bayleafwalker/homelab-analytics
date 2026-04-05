# Sprint forge-amber-lens — Sprint Packet

**Sprint:** #31  
**Dates:** 2026-04-06 to 2026-04-17  
**Goal:** Complete Stage 9 confidence surface — wire the confidence model into the dashboard, scenario annotation, and policy metadata so every operator-facing output carries visible freshness and trust signals.

---

## Foundation (delivered by proof-grain-veil #30)

Everything needed for this sprint is already in `main`:

| What | Where |
|---|---|
| `PublicationConfidenceSnapshot` model + verdict logic | `packages/platform/publication_confidence.py` |
| Confidence snapshots recorded on every mart refresh | `packages/pipelines/transformation_service.py` (hook in `refresh_publications`) |
| `get_latest_publication_confidence()` retrieval helper | `packages/pipelines/publication_confidence_service.py` |
| Storage read/write (Postgres + SQLite) | `packages/storage/control_plane.py` — `list_publication_confidence_snapshots()` |
| Confidence fields on `PublicationContract` | `packages/platform/publication_contracts.py` |
| `publication-contracts.json` enriched at export | `apps/api/export_contracts.py` |
| Non-finance freshness configs bootstrapped at startup | `packages/pipelines/source_freshness_bootstrap.py` |
| 27 unit tests passing | `tests/test_publication_confidence.py` |

---

## Scope

### #259 — Confidence dashboard (track: dashboard)

**Deliverable:** New page at `/control/confidence` showing confidence state for all tracked publications.

**Backend:**
- New route in `apps/api/routes/control_routes.py`: `GET /control/confidence`
- Returns list of latest snapshots per publication via `control_plane.list_publication_confidence_snapshots()`
- Response shape: `{ publications: [{ publication_key, freshness_state, completeness_pct, confidence_verdict, assessed_at }] }`
- Group by domain for summary cards

**Frontend:**
- New route: `apps/web/frontend/app/control/confidence/page.js`
- Domain summary cards: aggregate verdict per domain (worst-case roll-up)
- Per-publication rows: key, verdict badge (TRUSTWORTHY/DEGRADED/UNRELIABLE/UNAVAILABLE), freshness state, completeness %, last assessed
- Stale filter: toggle to show only DEGRADED/UNRELIABLE/UNAVAILABLE

**Acceptance:**
- Page renders with live data from a mart-refreshed state
- Domain cards show correct worst-case verdicts
- Stale filter hides TRUSTWORTHY rows
- Verdict badges use consistent colour coding (reuse from publication-contracts badge system if available)

---

### #260 — Scenario assumptions_summary (track: tracing)

**Deliverable:** Each scenario result includes `assumptions_summary` listing source freshness per contributing source.

**Backend:**
- `packages/pipelines/scenario_service.py`: after scenario execution, query `get_latest_publication_confidence()` for each publication contributing to the scenario; attach to result
- Response model update in `apps/api/response_models.py`: add `assumptions_summary: list[SourceFreshnessSummary] | None`
- `SourceFreshnessSummary`: `{ source_asset_id, freshness_state, last_ingest_at, covered_through }`

**Frontend:**
- `apps/web/frontend/app/scenarios/[scenarioId]/page.js`: add assumptions panel below scenario result
- Show each source with freshness badge; call out STALE/UNAVAILABLE sources prominently

**Acceptance:**
- Scenario detail page shows assumptions_summary when confidence data exists
- Gracefully omits panel when no confidence data is available (no error state)
- STALE sources visually distinguished

---

### #261 — Policy input_freshness (track: tracing)

**Deliverable:** Policy evaluation responses include `input_freshness` capturing source freshness at decision time.

**Backend:**
- `packages/pipelines/ha_policy.py`: at evaluation time, snapshot freshness for publications feeding the policy; attach to verdict object
- Response model: add `input_freshness: ConfidenceSummary | None` to policy verdict API response
- `ConfidenceSummary`: `{ verdict, freshness_state, completeness_pct, assessed_at }`

**Acceptance:**
- Policy API response includes `input_freshness` when confidence data exists
- Null-safe: policies evaluated before confidence wiring don't break
- Freshness captured at evaluation time (point-in-time, not current)

---

### #262 — Bidirectional lineage (track: lineage)

**Deliverable:** Given a source asset ID, retrieve all downstream publications that depend on it.

**Backend:**
- `packages/storage/control_plane.py`: extend `list_source_lineage()` with `source_asset_id` filter param (reverse lookup direction)
- Both `packages/storage/postgres_provenance_control_plane.py` and `packages/storage/sqlite_provenance_control_plane.py` updated
- New API route: `GET /control/lineage/downstream?source_asset_id=<id>` in `control_routes.py`

**Acceptance:**
- Given a source ID, returns all publication keys in the lineage table that list it as a contributing source
- Works on both Postgres and SQLite backends
- Returns empty list (not error) when no downstream publications exist

---

### #263 — Fix pre-existing test failures (track: test-debt)

**Three failing tests** in `packages/pipelines/transformation_service.py` tests:
- `test_refresh_recent_large_transactions`
- `test_recent_large_transactions_is_idempotent`
- `test_refresh_publications_includes_new_marts`

Root cause: large transaction threshold logic. Not confidence-related. Fix before sprint closes so `make verify-fast` is fully green.

**Acceptance:** All three tests pass; no regressions introduced.

---

## Out of scope

Carry to the sprint after this one:
- `#206` Semantic closure — shared-dimension normalization
- `#207/#208` Runtime parity — pack registration and capability metadata
- `#211/#212` Auditable outputs — recommendation object model + assistant hooks

---

## Dependencies

| Dependency | Status |
|---|---|
| `PublicationConfidenceSnapshot` model | ✓ In main (3d25fa7) |
| `list_publication_confidence_snapshots()` | ✓ In main (3d25fa7) |
| `get_latest_publication_confidence()` | ✓ In main (3d3ebdf) |
| Confidence snapshots recorded on refresh | ✓ In main (796f48a) |
| Non-finance freshness configs | ✓ In main (3868620) |
| No pending migrations | ✓ 0008/0009 already applied |

---

## Verification path

```bash
source .envrc

# 1. Run full test suite (expect 1442 passing, 3 pre-existing fail — target 0 by end of sprint)
make test

# 2. Confirm confidence snapshots are being recorded
# (run a mart refresh and query the table)

# 3. After #259: GET /control/confidence returns structured response
# 4. After #260: GET /scenarios/<id> response includes assumptions_summary
# 5. After #261: policy verdict response includes input_freshness
# 6. After #262: GET /control/lineage/downstream?source_asset_id=<id> returns publication list
# 7. make verify-fast passes clean
```

---

## Item order recommendation

1. **#263** (test-debt) — clears noise, establishes clean baseline
2. **#262** (lineage) — pure backend, no frontend, clean scope
3. **#260** (scenario tracing) — backend + frontend, builds on lineage
4. **#261** (policy tracing) — backend-only, parallel with #260
5. **#259** (dashboard) — depends on lineage (#262) for full data richness; do last
