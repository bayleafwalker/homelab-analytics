from __future__ import annotations

import shlex
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.config_preflight import run_config_preflight
from packages.pipelines.promotion_registry import PromotionHandlerRegistry
from packages.shared.extensions import ExtensionRegistry
from packages.shared.function_registry import FunctionRegistry
from packages.storage.control_plane import ControlPlaneStore


@dataclass(frozen=True)
class TerminalCommandSpec:
    name: str
    usage: str
    description: str
    mutating: bool = False


@dataclass(frozen=True)
class TerminalExecution:
    command_name: str
    normalized_command: str
    status: str
    mutating: bool
    exit_code: int
    stdout_lines: tuple[str, ...]
    stderr_lines: tuple[str, ...]
    result: dict[str, Any]


@dataclass(frozen=True)
class TerminalExecutionContext:
    service: AccountTransactionService
    config_repository: ControlPlaneStore
    extension_registry: ExtensionRegistry
    function_registry: FunctionRegistry
    promotion_handler_registry: PromotionHandlerRegistry
    build_operational_summary: Callable[[], dict[str, Any]]
    to_jsonable: Callable[[Any], Any]


class TerminalCommandRejected(ValueError):
    def __init__(self, message: str, *, normalized_command: str = "") -> None:
        super().__init__(message)
        self.normalized_command = normalized_command.strip()


_COMMAND_SPECS: tuple[TerminalCommandSpec, ...] = (
    TerminalCommandSpec(
        name="help",
        usage="help",
        description="Show the allowlisted terminal commands.",
    ),
    TerminalCommandSpec(
        name="status",
        usage="status",
        description="Summarize queue, worker, run, and auth state from the control plane.",
    ),
    TerminalCommandSpec(
        name="runs",
        usage="runs [limit]",
        description="List recent ingestion runs. Default limit is 10, max 50.",
    ),
    TerminalCommandSpec(
        name="dispatches",
        usage="dispatches [status]",
        description="List schedule dispatches, optionally filtered by status.",
    ),
    TerminalCommandSpec(
        name="heartbeats",
        usage="heartbeats",
        description="List current worker heartbeats.",
    ),
    TerminalCommandSpec(
        name="freshness",
        usage="freshness",
        description="Show latest dataset freshness snapshots.",
    ),
    TerminalCommandSpec(
        name="schedules",
        usage="schedules [limit]",
        description="List execution schedules. Default limit is 10, max 50.",
    ),
    TerminalCommandSpec(
        name="tokens",
        usage="tokens [limit]",
        description="List service tokens, including revoked tokens. Default limit is 10, max 50.",
    ),
    TerminalCommandSpec(
        name="audit",
        usage="audit [limit]",
        description="List recent auth/control audit events. Default limit is 10, max 50.",
    ),
    TerminalCommandSpec(
        name="publication-audit",
        usage="publication-audit [limit]",
        description="List recent publication audit records. Default limit is 10, max 50.",
    ),
    TerminalCommandSpec(
        name="users",
        usage="users [limit]",
        description="List local users. Default limit is 10, max 50.",
    ),
    TerminalCommandSpec(
        name="source-systems",
        usage="source-systems [limit]",
        description="List configured source systems. Default limit is 10, max 50.",
    ),
    TerminalCommandSpec(
        name="source-assets",
        usage="source-assets [limit]",
        description="List source assets, including archived assets. Default limit is 10, max 50.",
    ),
    TerminalCommandSpec(
        name="ingestion-definitions",
        usage="ingestion-definitions [limit]",
        description="List ingestion definitions, including archived definitions. Default limit is 10, max 50.",
    ),
    TerminalCommandSpec(
        name="publication-definitions",
        usage="publication-definitions [limit]",
        description="List publication definitions, including archived definitions. Default limit is 10, max 50.",
    ),
    TerminalCommandSpec(
        name="lineage",
        usage="lineage [limit]",
        description="List recent source-lineage records. Default limit is 10, max 50.",
    ),
    TerminalCommandSpec(
        name="verify-config",
        usage="verify-config",
        description="Run config preflight validation against the current control-plane state.",
    ),
    TerminalCommandSpec(
        name="enqueue-due",
        usage="enqueue-due [limit]",
        description="Enqueue due execution schedules using the control-plane queue.",
        mutating=True,
    ),
)
_COMMANDS_BY_NAME = {command.name: command for command in _COMMAND_SPECS}
_VALID_DISPATCH_STATUSES = {"enqueued", "running", "completed", "failed"}


def terminal_command_specs() -> tuple[TerminalCommandSpec, ...]:
    return _COMMAND_SPECS


def execute_terminal_command(
    command_line: str,
    context: TerminalExecutionContext,
) -> TerminalExecution:
    stripped = command_line.strip()
    if not stripped:
        raise TerminalCommandRejected("Enter a command.")

    try:
        tokens = shlex.split(stripped)
    except ValueError as exc:
        raise TerminalCommandRejected(
            f"Could not parse command line: {exc}",
            normalized_command=stripped,
        ) from exc

    command_name = tokens[0].lower()
    command = _COMMANDS_BY_NAME.get(command_name)
    normalized_command = " ".join(tokens)
    if command is None:
        raise TerminalCommandRejected(
            f"Unsupported command: {command_name}",
            normalized_command=normalized_command,
        )

    args = tokens[1:]
    if command_name == "help":
        return _execute_help(command, normalized_command)
    if command_name == "status":
        _require_argument_count(args, expected=0, normalized_command=normalized_command)
        return _execute_status(command, normalized_command, context)
    if command_name == "runs":
        return _execute_runs(command, normalized_command, context, args)
    if command_name == "dispatches":
        return _execute_dispatches(command, normalized_command, context, args)
    if command_name == "heartbeats":
        _require_argument_count(args, expected=0, normalized_command=normalized_command)
        return _execute_heartbeats(command, normalized_command, context)
    if command_name == "freshness":
        _require_argument_count(args, expected=0, normalized_command=normalized_command)
        return _execute_freshness(command, normalized_command, context)
    if command_name == "schedules":
        return _execute_schedules(command, normalized_command, context, args)
    if command_name == "tokens":
        return _execute_tokens(command, normalized_command, context, args)
    if command_name == "audit":
        return _execute_audit(command, normalized_command, context, args)
    if command_name == "publication-audit":
        return _execute_publication_audit(command, normalized_command, context, args)
    if command_name == "users":
        return _execute_users(command, normalized_command, context, args)
    if command_name == "source-systems":
        return _execute_source_systems(command, normalized_command, context, args)
    if command_name == "source-assets":
        return _execute_source_assets(command, normalized_command, context, args)
    if command_name == "ingestion-definitions":
        return _execute_ingestion_definitions(command, normalized_command, context, args)
    if command_name == "publication-definitions":
        return _execute_publication_definitions(command, normalized_command, context, args)
    if command_name == "lineage":
        return _execute_lineage(command, normalized_command, context, args)
    if command_name == "verify-config":
        _require_argument_count(args, expected=0, normalized_command=normalized_command)
        return _execute_verify_config(command, normalized_command, context)
    if command_name == "enqueue-due":
        return _execute_enqueue_due(command, normalized_command, context, args)

    raise TerminalCommandRejected(
        f"Unsupported command: {command_name}",
        normalized_command=normalized_command,
    )


def rejected_terminal_execution(
    command_line: str,
    message: str,
) -> TerminalExecution:
    normalized_command = " ".join(command_line.strip().split())
    return TerminalExecution(
        command_name="rejected",
        normalized_command=normalized_command,
        status="rejected",
        mutating=False,
        exit_code=2,
        stdout_lines=(),
        stderr_lines=(message,),
        result={"message": message},
    )


def failed_terminal_execution(
    command_line: str,
    message: str,
) -> TerminalExecution:
    normalized_command = " ".join(command_line.strip().split())
    return TerminalExecution(
        command_name="internal-error",
        normalized_command=normalized_command,
        status="failed",
        mutating=False,
        exit_code=70,
        stdout_lines=(),
        stderr_lines=(message,),
        result={"message": message},
    )


def _require_argument_count(
    args: list[str],
    *,
    expected: int,
    normalized_command: str,
) -> None:
    if len(args) != expected:
        raise TerminalCommandRejected(
            f"Unexpected arguments for '{normalized_command or 'command'}'.",
            normalized_command=normalized_command,
        )


def _parse_limit(
    args: list[str],
    *,
    default: int,
    maximum: int,
    normalized_command: str,
) -> int:
    if not args:
        return default
    if len(args) != 1:
        raise TerminalCommandRejected(
            f"Expected at most one numeric limit for '{normalized_command}'.",
            normalized_command=normalized_command,
        )
    try:
        limit = int(args[0])
    except ValueError as exc:
        raise TerminalCommandRejected(
            f"Limit must be an integer for '{normalized_command}'.",
            normalized_command=normalized_command,
        ) from exc
    if limit < 1 or limit > maximum:
        raise TerminalCommandRejected(
            f"Limit must be between 1 and {maximum} for '{normalized_command}'.",
            normalized_command=normalized_command,
        )
    return limit


def _execute_help(
    command: TerminalCommandSpec,
    normalized_command: str,
) -> TerminalExecution:
    lines = tuple(
        f"{entry.usage:<20} {'mutates' if entry.mutating else 'read-only'} :: {entry.description}"
        for entry in _COMMAND_SPECS
    )
    return TerminalExecution(
        command_name=command.name,
        normalized_command=normalized_command,
        status="succeeded",
        mutating=command.mutating,
        exit_code=0,
        stdout_lines=lines,
        stderr_lines=(),
        result={
            "commands": [
                {
                    "name": entry.name,
                    "usage": entry.usage,
                    "description": entry.description,
                    "mutating": entry.mutating,
                }
                for entry in _COMMAND_SPECS
            ]
        },
    )


def _execute_status(
    command: TerminalCommandSpec,
    normalized_command: str,
    context: TerminalExecutionContext,
) -> TerminalExecution:
    summary = context.build_operational_summary()
    queue = summary.get("queue", {})
    auth = summary.get("auth", {}).get("service_tokens", {})
    stdout_lines = (
        (
            "queue "
            f"enqueued={queue.get('enqueued_dispatches', 0)} "
            f"running={queue.get('running_dispatches', 0)} "
            f"stale={queue.get('stale_running_dispatches', 0)} "
            f"workers={queue.get('active_workers', 0)}"
        ),
        (
            "auth "
            f"active_tokens={auth.get('active', 0)} "
            f"used_24h={auth.get('used_within_24h', 0)} "
            f"expiring_7d={auth.get('expiring_within_7d', 0)}"
        ),
        (
            "failures "
            f"runs={len(summary.get('recent_failed_runs', []))} "
            f"dispatches={len(summary.get('recent_failed_dispatches', []))}"
        ),
    )
    return TerminalExecution(
        command_name=command.name,
        normalized_command=normalized_command,
        status="succeeded",
        mutating=command.mutating,
        exit_code=0,
        stdout_lines=stdout_lines,
        stderr_lines=(),
        result=context.to_jsonable(summary),
    )


def _execute_runs(
    command: TerminalCommandSpec,
    normalized_command: str,
    context: TerminalExecutionContext,
    args: list[str],
) -> TerminalExecution:
    limit = _parse_limit(args, default=10, maximum=50, normalized_command=normalized_command)
    runs = context.service.metadata_repository.list_runs(limit=limit)
    stdout_lines = tuple(
        f"{run.run_id} {run.status.value} {run.dataset_name} {run.created_at.isoformat()}"
        for run in runs
    ) or ("No runs found.",)
    return TerminalExecution(
        command_name=command.name,
        normalized_command=normalized_command,
        status="succeeded",
        mutating=command.mutating,
        exit_code=0,
        stdout_lines=stdout_lines,
        stderr_lines=(),
        result={"runs": context.to_jsonable(runs), "limit": limit},
    )


def _execute_dispatches(
    command: TerminalCommandSpec,
    normalized_command: str,
    context: TerminalExecutionContext,
    args: list[str],
) -> TerminalExecution:
    if len(args) > 1:
        raise TerminalCommandRejected(
            f"Expected zero or one dispatch status for '{normalized_command}'.",
            normalized_command=normalized_command,
        )
    status = args[0].lower() if args else None
    if status is not None and status not in _VALID_DISPATCH_STATUSES:
        raise TerminalCommandRejected(
            "Dispatch status must be one of: enqueued, running, completed, failed.",
            normalized_command=normalized_command,
        )
    dispatches = context.config_repository.list_schedule_dispatches(status=status)
    stdout_lines = tuple(
        f"{record.dispatch_id} {record.status} {record.schedule_id} {record.enqueued_at.isoformat()}"
        for record in dispatches
    ) or ("No dispatches found.",)
    return TerminalExecution(
        command_name=command.name,
        normalized_command=normalized_command,
        status="succeeded",
        mutating=command.mutating,
        exit_code=0,
        stdout_lines=stdout_lines,
        stderr_lines=(),
        result={
            "dispatches": context.to_jsonable(dispatches),
            "status": status,
        },
    )


def _execute_heartbeats(
    command: TerminalCommandSpec,
    normalized_command: str,
    context: TerminalExecutionContext,
) -> TerminalExecution:
    heartbeats = context.config_repository.list_worker_heartbeats()
    now = datetime.now(UTC)
    stdout_lines = tuple(
        (
            f"{heartbeat.worker_id} {heartbeat.status} "
            f"observed={heartbeat.observed_at.isoformat()} "
            f"age_seconds={int((now - heartbeat.observed_at).total_seconds())}"
        )
        for heartbeat in heartbeats
    ) or ("No worker heartbeats found.",)
    return TerminalExecution(
        command_name=command.name,
        normalized_command=normalized_command,
        status="succeeded",
        mutating=command.mutating,
        exit_code=0,
        stdout_lines=stdout_lines,
        stderr_lines=(),
        result={"heartbeats": context.to_jsonable(heartbeats)},
    )


def _execute_freshness(
    command: TerminalCommandSpec,
    normalized_command: str,
    context: TerminalExecutionContext,
) -> TerminalExecution:
    datasets = _build_source_freshness(context.service)
    stdout_lines = tuple(
        (
            f"{dataset['dataset_name']} {dataset['status']} "
            f"run={dataset['latest_run_id']} at={dataset['landed_at']}"
        )
        for dataset in datasets
    ) or ("No source freshness records found.",)
    return TerminalExecution(
        command_name=command.name,
        normalized_command=normalized_command,
        status="succeeded",
        mutating=command.mutating,
        exit_code=0,
        stdout_lines=stdout_lines,
        stderr_lines=(),
        result={"datasets": datasets},
    )


def _execute_schedules(
    command: TerminalCommandSpec,
    normalized_command: str,
    context: TerminalExecutionContext,
    args: list[str],
) -> TerminalExecution:
    limit = _parse_limit(args, default=10, maximum=50, normalized_command=normalized_command)
    schedules = context.config_repository.list_execution_schedules(
        include_archived=True
    )[:limit]
    stdout_lines = tuple(
        (
            f"{record.schedule_id} "
            f"{'enabled' if record.enabled else 'paused'} "
            f"{'archived' if record.archived else 'active'} "
            f"next_due={record.next_due_at.isoformat() if record.next_due_at else 'n/a'} "
            f"target={record.target_kind}:{record.target_ref}"
        )
        for record in schedules
    ) or ("No execution schedules found.",)
    return TerminalExecution(
        command_name=command.name,
        normalized_command=normalized_command,
        status="succeeded",
        mutating=command.mutating,
        exit_code=0,
        stdout_lines=stdout_lines,
        stderr_lines=(),
        result={"schedules": context.to_jsonable(schedules), "limit": limit},
    )


def _execute_tokens(
    command: TerminalCommandSpec,
    normalized_command: str,
    context: TerminalExecutionContext,
    args: list[str],
) -> TerminalExecution:
    limit = _parse_limit(args, default=10, maximum=50, normalized_command=normalized_command)
    now = datetime.now(UTC)
    tokens = context.config_repository.list_service_tokens(include_revoked=True)[:limit]
    stdout_lines = tuple(
        (
            f"{token.token_id} {token.role.value} {_service_token_status(token, now)} "
            f"name={token.token_name} last_used={token.last_used_at.isoformat() if token.last_used_at else 'never'}"
        )
        for token in tokens
    ) or ("No service tokens found.",)
    return TerminalExecution(
        command_name=command.name,
        normalized_command=normalized_command,
        status="succeeded",
        mutating=command.mutating,
        exit_code=0,
        stdout_lines=stdout_lines,
        stderr_lines=(),
        result={"service_tokens": context.to_jsonable(tokens), "limit": limit},
    )


def _execute_audit(
    command: TerminalCommandSpec,
    normalized_command: str,
    context: TerminalExecutionContext,
    args: list[str],
) -> TerminalExecution:
    limit = _parse_limit(args, default=10, maximum=50, normalized_command=normalized_command)
    events = context.config_repository.list_auth_audit_events(limit=limit)
    stdout_lines = tuple(
        (
            f"{event.occurred_at.isoformat()} {event.event_type} "
            f"actor={event.actor_username or 'system'} success={str(event.success).lower()}"
        )
        for event in events
    ) or ("No auth audit events found.",)
    return TerminalExecution(
        command_name=command.name,
        normalized_command=normalized_command,
        status="succeeded",
        mutating=command.mutating,
        exit_code=0,
        stdout_lines=stdout_lines,
        stderr_lines=(),
        result={"auth_audit_events": context.to_jsonable(events), "limit": limit},
    )


def _execute_publication_audit(
    command: TerminalCommandSpec,
    normalized_command: str,
    context: TerminalExecutionContext,
    args: list[str],
) -> TerminalExecution:
    limit = _parse_limit(args, default=10, maximum=50, normalized_command=normalized_command)
    publication_audit = context.config_repository.list_publication_audit()[:limit]
    stdout_lines = tuple(
        (
            f"{record.published_at.isoformat()} {record.publication_key} "
            f"{record.status} run={record.run_id}"
        )
        for record in publication_audit
    ) or ("No publication audit records found.",)
    return TerminalExecution(
        command_name=command.name,
        normalized_command=normalized_command,
        status="succeeded",
        mutating=command.mutating,
        exit_code=0,
        stdout_lines=stdout_lines,
        stderr_lines=(),
        result={"publication_audit": context.to_jsonable(publication_audit), "limit": limit},
    )


def _execute_users(
    command: TerminalCommandSpec,
    normalized_command: str,
    context: TerminalExecutionContext,
    args: list[str],
) -> TerminalExecution:
    limit = _parse_limit(args, default=10, maximum=50, normalized_command=normalized_command)
    users = context.config_repository.list_local_users()[:limit]
    stdout_lines = tuple(
        (
            f"{user.user_id} {user.username} {user.role.value} "
            f"{'enabled' if user.enabled else 'disabled'} "
            f"last_login={user.last_login_at.isoformat() if user.last_login_at else 'never'}"
        )
        for user in users
    ) or ("No local users found.",)
    return TerminalExecution(
        command_name=command.name,
        normalized_command=normalized_command,
        status="succeeded",
        mutating=command.mutating,
        exit_code=0,
        stdout_lines=stdout_lines,
        stderr_lines=(),
        result={"local_users": context.to_jsonable(users), "limit": limit},
    )


def _execute_source_systems(
    command: TerminalCommandSpec,
    normalized_command: str,
    context: TerminalExecutionContext,
    args: list[str],
) -> TerminalExecution:
    limit = _parse_limit(args, default=10, maximum=50, normalized_command=normalized_command)
    source_systems = context.config_repository.list_source_systems()[:limit]
    stdout_lines = tuple(
        (
            f"{record.source_system_id} {record.source_type} {record.transport} "
            f"schedule={record.schedule_mode} enabled={str(record.enabled).lower()}"
        )
        for record in source_systems
    ) or ("No source systems found.",)
    return TerminalExecution(
        command_name=command.name,
        normalized_command=normalized_command,
        status="succeeded",
        mutating=command.mutating,
        exit_code=0,
        stdout_lines=stdout_lines,
        stderr_lines=(),
        result={"source_systems": context.to_jsonable(source_systems), "limit": limit},
    )


def _execute_source_assets(
    command: TerminalCommandSpec,
    normalized_command: str,
    context: TerminalExecutionContext,
    args: list[str],
) -> TerminalExecution:
    limit = _parse_limit(args, default=10, maximum=50, normalized_command=normalized_command)
    source_assets = context.config_repository.list_source_assets(include_archived=True)[:limit]
    stdout_lines = tuple(
        (
            f"{record.source_asset_id} {record.asset_type} "
            f"source={record.source_system_id} dataset={record.dataset_contract_id} "
            f"{'enabled' if record.enabled else 'disabled'} "
            f"{'archived' if record.archived else 'active'}"
        )
        for record in source_assets
    ) or ("No source assets found.",)
    return TerminalExecution(
        command_name=command.name,
        normalized_command=normalized_command,
        status="succeeded",
        mutating=command.mutating,
        exit_code=0,
        stdout_lines=stdout_lines,
        stderr_lines=(),
        result={"source_assets": context.to_jsonable(source_assets), "limit": limit},
    )


def _execute_ingestion_definitions(
    command: TerminalCommandSpec,
    normalized_command: str,
    context: TerminalExecutionContext,
    args: list[str],
) -> TerminalExecution:
    limit = _parse_limit(args, default=10, maximum=50, normalized_command=normalized_command)
    definitions = context.config_repository.list_ingestion_definitions(include_archived=True)[:limit]
    stdout_lines = tuple(
        (
            f"{record.ingestion_definition_id} {record.transport} {record.schedule_mode} "
            f"asset={record.source_asset_id} "
            f"{'enabled' if record.enabled else 'disabled'} "
            f"{'archived' if record.archived else 'active'}"
        )
        for record in definitions
    ) or ("No ingestion definitions found.",)
    return TerminalExecution(
        command_name=command.name,
        normalized_command=normalized_command,
        status="succeeded",
        mutating=command.mutating,
        exit_code=0,
        stdout_lines=stdout_lines,
        stderr_lines=(),
        result={"ingestion_definitions": context.to_jsonable(definitions), "limit": limit},
    )


def _execute_publication_definitions(
    command: TerminalCommandSpec,
    normalized_command: str,
    context: TerminalExecutionContext,
    args: list[str],
) -> TerminalExecution:
    limit = _parse_limit(args, default=10, maximum=50, normalized_command=normalized_command)
    definitions = context.config_repository.list_publication_definitions(include_archived=True)[:limit]
    stdout_lines = tuple(
        (
            f"{record.publication_definition_id} {record.publication_key} "
            f"package={record.transformation_package_id} "
            f"{'archived' if record.archived else 'active'}"
        )
        for record in definitions
    ) or ("No publication definitions found.",)
    return TerminalExecution(
        command_name=command.name,
        normalized_command=normalized_command,
        status="succeeded",
        mutating=command.mutating,
        exit_code=0,
        stdout_lines=stdout_lines,
        stderr_lines=(),
        result={"publication_definitions": context.to_jsonable(definitions), "limit": limit},
    )


def _execute_lineage(
    command: TerminalCommandSpec,
    normalized_command: str,
    context: TerminalExecutionContext,
    args: list[str],
) -> TerminalExecution:
    limit = _parse_limit(args, default=10, maximum=50, normalized_command=normalized_command)
    lineage = context.config_repository.list_source_lineage()[:limit]
    stdout_lines = tuple(
        (
            f"{record.lineage_id} {record.target_layer}:{record.target_name} "
            f"run={record.input_run_id or 'n/a'} rows={record.row_count if record.row_count is not None else 'n/a'} "
            f"at={record.recorded_at.isoformat()}"
        )
        for record in lineage
    ) or ("No source lineage records found.",)
    return TerminalExecution(
        command_name=command.name,
        normalized_command=normalized_command,
        status="succeeded",
        mutating=command.mutating,
        exit_code=0,
        stdout_lines=stdout_lines,
        stderr_lines=(),
        result={"source_lineage": context.to_jsonable(lineage), "limit": limit},
    )


def _execute_verify_config(
    command: TerminalCommandSpec,
    normalized_command: str,
    context: TerminalExecutionContext,
) -> TerminalExecution:
    report = run_config_preflight(
        context.config_repository,
        extension_registry=context.extension_registry,
        function_registry=context.function_registry,
        promotion_handler_registry=context.promotion_handler_registry,
    )
    stdout_lines = (
        (
            f"checked source_assets={report.checked.source_assets} "
            f"ingestion_definitions={report.checked.ingestion_definitions} "
            f"publication_definitions={report.checked.publication_definitions}"
        ),
        f"issues={len(report.issues)}",
    )
    stderr_lines = tuple(
        f"{issue.entity_type}:{issue.entity_id} {issue.code} :: {issue.message}"
        for issue in report.issues
    )
    return TerminalExecution(
        command_name=command.name,
        normalized_command=normalized_command,
        status="succeeded" if report.passed else "failed",
        mutating=command.mutating,
        exit_code=0 if report.passed else 1,
        stdout_lines=stdout_lines,
        stderr_lines=stderr_lines,
        result={"report": context.to_jsonable(report)},
    )


def _execute_enqueue_due(
    command: TerminalCommandSpec,
    normalized_command: str,
    context: TerminalExecutionContext,
    args: list[str],
) -> TerminalExecution:
    limit = _parse_limit(args, default=10, maximum=100, normalized_command=normalized_command)
    dispatches = context.config_repository.enqueue_due_execution_schedules(limit=limit)
    stdout_lines = tuple(
        f"{dispatch.dispatch_id} enqueued schedule={dispatch.schedule_id}"
        for dispatch in dispatches
    ) or ("No due schedules were enqueued.",)
    return TerminalExecution(
        command_name=command.name,
        normalized_command=normalized_command,
        status="succeeded",
        mutating=command.mutating,
        exit_code=0,
        stdout_lines=stdout_lines,
        stderr_lines=(),
        result={"dispatches": context.to_jsonable(dispatches), "limit": limit},
    )


def _build_source_freshness(service: AccountTransactionService) -> list[dict[str, str]]:
    recent_runs = service.metadata_repository.list_runs()
    seen: set[str] = set()
    datasets: list[dict[str, str]] = []
    for run in recent_runs:
        if run.dataset_name in seen:
            continue
        seen.add(run.dataset_name)
        datasets.append(
            {
                "dataset_name": run.dataset_name,
                "latest_run_id": run.run_id,
                "status": run.status.value,
                "landed_at": run.created_at.isoformat(),
            }
        )
    return datasets


def _service_token_status(token: Any, now: datetime) -> str:
    if token.revoked_at is not None:
        return "revoked"
    if token.expires_at is not None and token.expires_at <= now:
        return "expired"
    return "active"
