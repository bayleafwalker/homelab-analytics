"""Decision ledger worker commands: evidence-correction trace and outcome export.

``trace-decision-evidence`` compares every recorded decision's pinned
evidence fingerprint with the current reporting row and marks corrected
evidence as superseded (HLA-K02). ``export-outcome-references`` writes the
portable outcome-reference feed (HLA-K04) as JSON to stdout or a file; it
makes no outbound network call — delivery to any consumer is a separate,
operator-controlled step.
"""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from typing import Any

from apps.worker.runtime import WorkerRuntime
from apps.worker.serialization import _write_json
from packages.application.use_cases.decision_evidence_trace import (
    trace_evidence_corrections,
)
from packages.application.use_cases.decision_outcome_reference import (
    outcome_reference_feed,
)
from packages.pipelines.household_decisions import (
    get_decision_definition,
    read_decision_subject,
    snapshot_evidence_components,
)
from packages.pipelines.reporting_service import ReportingService
from packages.storage.decision_ledger import DecisionLedgerStore


def trace_decision_evidence(
    ledger: object,
    reporting_service: ReportingService,
    *,
    decision_key: str | None = None,
) -> dict[str, Any] | None:
    """Run the trace when the control plane holds a decision ledger."""
    if not isinstance(ledger, DecisionLedgerStore):
        return None
    report = trace_evidence_corrections(
        ledger,
        definition_lookup=get_decision_definition,
        subject_reader=lambda key, period: read_decision_subject(
            key, reporting_service, period
        ),
        snapshot_components=snapshot_evidence_components,
        decision_key=decision_key,
    )
    return report.as_dict()


def handle_trace_decision_evidence(args: Namespace, runtime: WorkerRuntime) -> int:
    from apps.worker.command_handlers.ingest_commands import _build_reporting_runtime

    _, reporting_service = _build_reporting_runtime(runtime)
    trace = trace_decision_evidence(
        runtime.config_repository,
        reporting_service,
        decision_key=getattr(args, "decision_key", None) or None,
    )
    if trace is None:
        _write_json(runtime.output, {"error": "The control plane has no decision ledger."})
        return 1
    _write_json(runtime.output, {"trace": trace})
    return 0


def handle_export_outcome_references(args: Namespace, runtime: WorkerRuntime) -> int:
    ledger = runtime.config_repository
    if not isinstance(ledger, DecisionLedgerStore):
        _write_json(runtime.output, {"error": "The control plane has no decision ledger."})
        return 1
    feed = outcome_reference_feed(
        ledger,
        decision_key=getattr(args, "decision_key", None) or None,
        include_history=not getattr(args, "latest_only", False),
    )
    output_file = getattr(args, "output_file", None)
    if output_file:
        path = Path(output_file)
        path.write_text(json.dumps(feed, indent=2, sort_keys=True) + "\n")
        _write_json(runtime.output, {"written": str(path), "event_count": len(feed["events"])})
        return 0
    _write_json(runtime.output, feed)
    return 0
