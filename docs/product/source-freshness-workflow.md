# Source Freshness and Remediation Workflow

## What this is

Many personal finance sources will remain manual for a long time — monthly bank exports, periodic credit card invoices, occasional credit registry snapshots. The platform should "remember" these sources operationally and tell the operator when something is overdue, missing, or broken.

This document defines the freshness model, operator workflow, and control-surface integration points. It stays focused on source freshness and remediation, while publication trust remains a reporting concern.

**Architecture reference:** `docs/architecture/finance-ingestion-model.md`

---

## Startup stories

The freshness workflow sits on top of the three blessed deployment profiles defined in `docs/runbooks/configuration.md`:

- Local demo/dev: seed the demo bundle, use disposable fixture sources, and validate the freshness UI without wiring real operational sources first.
- Single-user homelab: use the manual export and watched-folder paths, then rely on freshness badges, upload actions, and run-history remediation when a source goes stale or fails.
- Shared OIDC deployment: keep the same freshness model and operator actions, but enter the admin and upload surfaces through the shared OIDC identity path.

The model is the same in all three cases; only the startup path and operator posture change. Profile choice determines how the operator authenticates, where landing payloads live, and which bootstrap path is safest, not how freshness itself is computed.

That makes the onboarding loop demo-first: validate the disposable bundle, then move one real source at a time through the same import, freshness, and remediation flow.

The disposable bundle lives in `docs/examples/finance-source-contracts/README.md` and gives a concrete first pass for the operator before any real source is wired.

---

## The problem

Without freshness tracking, the operator must remember:
- Which sources need monthly exports
- When each export is due
- Whether last month's data was actually ingested
- Whether the parser succeeded or failed silently

This is exactly the kind of thing a platform should handle. The operator should see a dashboard that says "your OP account CSV is 12 days overdue" — not discover the gap three months later when a report looks wrong.

---

## Source freshness config

Each source asset can optionally carry a freshness configuration. This is a companion entity, not inline fields on the source asset itself — it separates the operational schedule concern from the static binding model.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `source_asset_id` | STRING | Foreign key to source asset (unique — one config per asset) |
| `acquisition_mode` | STRING | How the source is acquired |
| `expected_frequency` | STRING | How often a new export is expected |
| `coverage_kind` | STRING | What kind of time coverage each export represents |
| `due_day_of_month` | INTEGER | Day of month when the next export is expected (nullable) |
| `expected_window_days` | INTEGER | Grace period in days after the due date |
| `freshness_sla_days` | INTEGER | Maximum days since last successful ingest before "stale" |
| `sensitivity_class` | STRING | Data sensitivity classification |
| `reminder_channel` | STRING | Where reminders should surface |
| `requires_human_action` | BOOLEAN | Whether ingestion requires operator intervention |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | |

### Acquisition modes

| Mode | Description | Example |
|------|-------------|---------|
| `manual_export` | Operator downloads from provider and uploads | Bank CSV, credit registry |
| `watched_folder` | File appears in a synced/watched folder | OneDrive-synced bank exports |
| `api_pull` | Platform pulls from an API on schedule | Future: utility API |
| `manual_entry` | Operator enters data through dashboard | Loan policy facts |

### Expected frequencies

| Frequency | Description | Typical due window |
|-----------|-------------|-------------------|
| `weekly` | Expected every week | 7 days |
| `monthly` | Expected once per calendar month | due_day_of_month + window |
| `quarterly` | Expected once per quarter | ~90 days |
| `annual` | Expected once per year | ~365 days |
| `ad_hoc` | No fixed schedule — ingested when available | freshness_sla_days only |

### Coverage kinds

| Kind | Description | Example |
|------|-------------|---------|
| `rolling_period` | Each export covers a time range | Monthly bank CSV covering Jan 1–31 |
| `point_in_time` | Each export is a snapshot as of one date | Credit registry export |
| `continuous` | Source provides ongoing data without gaps | API-pulled utility data |

---

## Freshness state model

Freshness state is **computed, not stored**. It is derived from:
1. The source freshness config (expected schedule)
2. The latest ingestion run records for the asset's dataset
3. The current date

### States

| State | Meaning | Visual indicator |
|-------|---------|-----------------|
| `current` | Latest ingest covers the expected period | Green |
| `due_soon` | Within the expected window; next export is approaching | Yellow |
| `overdue` | Past the due date + window; no ingest for the expected period | Red |
| `missing_period` | A gap exists in coverage (e.g., February is missing between January and March) | Orange |
| `parse_failed` | Latest ingest attempt was rejected or failed validation | Red with error icon |
| `unconfigured` | Source asset exists but has no freshness config | Grey |

### State computation

```
if no freshness config exists:
    state = unconfigured

else if latest run status is REJECTED or FAILED:
    state = parse_failed

else if latest successful ingest covers the current expected period:
    state = current

else if today < due_day + expected_window_days:
    state = due_soon

else if today >= due_day + expected_window_days and no ingest for expected period:
    state = overdue

else if coverage gaps exist between ingested periods:
    state = missing_period
```

The `parse_failed` state takes priority over schedule-based states — a failed parse means the operator tried but the data didn't land cleanly.

---

## Operator workflow

### Setting up a recurring source

1. Create the source asset binding (source system → dataset contract → column mapping) through the admin surface for the selected deployment profile
2. Attach a freshness config specifying frequency, due date, and SLA
3. The platform begins tracking freshness from the first successful ingest
4. The freshness view should tell the operator the next action directly: upload the missing export, open the failed run, or repair the source binding before retrying

### Monthly export cycle (single-user homelab example: OP account CSV)

```
Day 1–5:   Operator exports last month's CSV from OP web banking
           Uploads to platform (file upload or watched folder drop)
           Platform parses, validates, lands
           Freshness state transitions: due_soon → current

Day 6–10:  If no upload yet: state = due_soon (within window)
           Dashboard shows yellow badge

Day 11+:   If still no upload: state = overdue
           Dashboard shows red badge
           Optional webhook fires for HA notification
```

### Handling a failed parse

```
Operator uploads file → parser rejects (bad column, encoding issue)
State = parse_failed
Operator sees error details in the ingest run history
Operator fixes the source file or reports a parser bug
Operator re-uploads → success
State transitions: parse_failed → current
```

### Coverage gap detection

```
January data ingested ✓
February data ingested ✓
March data missing ✗
April data ingested ✓

State = missing_period
Dashboard shows "February–March gap" or "March missing"
Operator can backfill by uploading the missing export
```

---

## Integration points

### Dashboard / control surface

- Source freshness summary view: list of configured sources with current state badges
- Per-source detail: last ingest date, covered period, next expected date, state
- Quick action: jump to upload for overdue sources
- Quick action: jump to run history for failed sources
- Next action column: show the operator what to do now, not just whether the source is stale

### API

- `GET /control/source-freshness` — returns freshness state for all configured sources
- Response includes: source_asset_id, name, state, last_ingest_at, next_expected_at, covered_through

### Webhook / event output

- Optional webhook fires on state transitions to `overdue` or `parse_failed`
- Payload includes source identity, state, and actionable context
- Designed for Home Assistant automation: create a persistent notification or trigger an automation when a financial source is overdue

### Home Assistant synthetic entity (future)

- One binary sensor per configured source: `binary_sensor.finance_source_{name}_fresh`
- State: `on` when current/due_soon, `off` when overdue/missing/failed
- Attributes: last_ingest_at, covered_through, next_expected_at, state detail
- Published through the existing HA synthetic entity pattern

---

## Example configurations

### Monthly bank account export

```yaml
source_asset_id: op-common-account
acquisition_mode: manual_export
expected_frequency: monthly
coverage_kind: rolling_period
due_day_of_month: 5
expected_window_days: 5
freshness_sla_days: 40
sensitivity_class: financial
reminder_channel: dashboard
requires_human_action: true
```

### Quarterly credit registry snapshot

```yaml
source_asset_id: fi-credit-registry
acquisition_mode: manual_export
expected_frequency: quarterly
coverage_kind: point_in_time
due_day_of_month: null
expected_window_days: 14
freshness_sla_days: 100
sensitivity_class: financial
reminder_channel: dashboard
requires_human_action: true
```

### Ad hoc document (credit card invoice)

```yaml
source_asset_id: op-gold-invoice
acquisition_mode: manual_export
expected_frequency: monthly
coverage_kind: rolling_period
due_day_of_month: 15
expected_window_days: 10
freshness_sla_days: 45
sensitivity_class: financial
reminder_channel: dashboard
requires_human_action: true
```

---

## What this does NOT include

- Full notification platform (email, SMS, push) — webhook is the integration point
- Calendar export (iCal feed of due dates) — designed for but not built initially
- Auto-retry of failed parses — operator intervention required
- Source acquisition automation — the platform tracks freshness, not bank login
