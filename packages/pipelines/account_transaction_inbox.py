from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from packages.pipelines.account_transaction_service import AccountTransactionService


@dataclass(frozen=True)
class InboxProcessResult:
    discovered_files: int
    processed_files: int
    rejected_files: int


def process_account_transaction_inbox(
    service: AccountTransactionService,
    inbox_dir: Path,
    processed_dir: Path,
    failed_dir: Path,
    source_name: str = "folder-watch",
) -> InboxProcessResult:
    inbox_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    discovered_files = 0
    processed_files = 0
    rejected_files = 0

    for source_path in sorted(inbox_dir.glob("*.csv")):
        discovered_files += 1
        run = service.ingest_file(source_path, source_name=source_name)
        if run.passed:
            destination_path = processed_dir / f"{run.run_id}-{source_path.name}"
            processed_files += 1
        else:
            destination_path = failed_dir / f"{run.run_id}-{source_path.name}"
            rejected_files += 1
        source_path.replace(destination_path)

    return InboxProcessResult(
        discovered_files=discovered_files,
        processed_files=processed_files,
        rejected_files=rejected_files,
    )
