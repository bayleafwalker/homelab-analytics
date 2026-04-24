from __future__ import annotations

import csv
import hashlib
import html
import json
import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
from typing import Literal, TypedDict, cast

DEMO_SEED = 20260324
DEMO_GENERATED_AT = "2026-03-24T00:00:00+00:00"
MANIFEST_NAME = "manifest.json"
JOURNEY_NAME = "journey.json"

PERSONAL_ACCOUNT_ARTIFACT_ID = "op_personal_account_csv"
COMMON_ACCOUNT_ARTIFACT_ID = "op_common_account_csv"
REVOLUT_ACCOUNT_ARTIFACT_ID = "revolut_account_csv"
ACCOUNT_TRANSACTIONS_CANONICAL_ARTIFACT_ID = "account_transactions_canonical_csv"
SUBSCRIPTIONS_CANONICAL_ARTIFACT_ID = "subscriptions_canonical_csv"
CONTRACT_PRICES_CANONICAL_ARTIFACT_ID = "contract_prices_canonical_csv"
UTILITY_BILLS_CANONICAL_ARTIFACT_ID = "utility_bills_canonical_csv"
BUDGETS_CANONICAL_ARTIFACT_ID = "budgets_canonical_csv"
LOAN_REPAYMENTS_CANONICAL_ARTIFACT_ID = "loan_repayments_canonical_csv"
LOAN_REGISTRY_HTML_ARTIFACT_ID = "loan_registry_html"
LOAN_REGISTRY_TEXT_ARTIFACT_ID = "loan_registry_text"
CREDIT_CARD_STATEMENT_ARTIFACT_IDS = (
    "credit_card_statement_2026_01",
    "credit_card_statement_2026_02",
    "credit_card_statement_2026_03",
)
CsvQuoting = Literal[0, 1, 2, 3]
CSV_QUOTE_MINIMAL: CsvQuoting = 0
CSV_QUOTE_ALL: CsvQuoting = 1
DemoCsvRow = dict[str, str]


class DemoManifestRow(TypedDict):
    artifact_id: str
    relative_path: str
    source_family: str
    format: str
    intended_dataset_name: str
    ingest_support: str
    source_name: str | None
    sha256: str
    size_bytes: int


class DemoManifest(TypedDict):
    generated_at: str
    seed: int
    artifacts: list[DemoManifestRow]


class LoanRegistryLoan(TypedDict):
    loan_type: str
    currency: str
    purpose: str
    agreement_date: str
    lender: str
    loan_id: str
    principal: str
    balance: str
    monthly_payment: str


class LoanRegistryPayload(TypedDict):
    statement_date: str
    requestor_name: str
    requestor_id: str
    reference_id: str
    person_id_masked: str
    loans: list[LoanRegistryLoan]


class DemoProfile(TypedDict):
    transactions: tuple[DemoTransaction, ...]
    subscriptions: list[DemoCsvRow]
    contract_prices: list[DemoCsvRow]
    utility_bills: list[DemoCsvRow]
    budgets: list[DemoCsvRow]
    loan_repayments: list[DemoCsvRow]
    loan_registry: LoanRegistryPayload


@dataclass(frozen=True)
class DemoTransaction:
    booked_at: date
    account_id: str
    counterparty_name: str
    amount: Decimal
    currency: str
    description: str
    source_family: str
    source_kind: str


@dataclass(frozen=True)
class CreditCardStatement:
    artifact_id: str
    statement_date: date
    period_start: date
    period_end: date
    due_date: date
    previous_balance: Decimal
    payments_total: Decimal
    purchases_total: Decimal
    interest_amount: Decimal
    service_fee: Decimal
    minimum_due: Decimal
    ending_balance: Decimal
    transactions: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class DemoArtifact:
    artifact_id: str
    relative_path: str
    source_family: str
    format: str
    intended_dataset_name: str
    ingest_support: str
    content: bytes
    source_name: str | None = None

    def manifest_row(self) -> DemoManifestRow:
        return {
            "artifact_id": self.artifact_id,
            "relative_path": self.relative_path,
            "source_family": self.source_family,
            "format": self.format,
            "intended_dataset_name": self.intended_dataset_name,
            "ingest_support": self.ingest_support,
            "source_name": self.source_name,
            "sha256": hashlib.sha256(self.content).hexdigest(),
            "size_bytes": len(self.content),
        }


@dataclass(frozen=True)
class DemoBundle:
    artifacts: tuple[DemoArtifact, ...]


def canonical_demo_files() -> dict[str, bytes]:
    bundle = build_demo_bundle(include_template_artifacts=False)
    canonical: dict[str, bytes] = {}
    for artifact in bundle.artifacts:
        if artifact.source_family != "canonical":
            continue
        canonical[artifact.intended_dataset_name] = artifact.content
    return canonical


def build_demo_bundle(*, include_template_artifacts: bool = True) -> DemoBundle:
    profile = _build_demo_profile()
    artifacts = [
        DemoArtifact(
            artifact_id=ACCOUNT_TRANSACTIONS_CANONICAL_ARTIFACT_ID,
            relative_path="canonical/account_transactions.csv",
            source_family="canonical",
            format="csv",
            intended_dataset_name="account_transactions",
            ingest_support="supported_now",
            content=_render_csv(
                (
                    "booked_at",
                    "account_id",
                    "counterparty_name",
                    "amount",
                    "currency",
                    "description",
                ),
                [
                    {
                        "booked_at": transaction.booked_at.isoformat(),
                        "account_id": transaction.account_id,
                        "counterparty_name": transaction.counterparty_name,
                        "amount": _format_decimal(transaction.amount),
                        "currency": transaction.currency,
                        "description": transaction.description,
                    }
                    for transaction in profile["transactions"]
                ],
            ),
        ),
        DemoArtifact(
            artifact_id=SUBSCRIPTIONS_CANONICAL_ARTIFACT_ID,
            relative_path="canonical/subscriptions.csv",
            source_family="canonical",
            format="csv",
            intended_dataset_name="subscriptions",
            ingest_support="supported_now",
            content=_render_csv(
                (
                    "service_name",
                    "provider",
                    "billing_cycle",
                    "amount",
                    "currency",
                    "start_date",
                    "end_date",
                ),
                profile["subscriptions"],
            ),
        ),
        DemoArtifact(
            artifact_id=CONTRACT_PRICES_CANONICAL_ARTIFACT_ID,
            relative_path="canonical/contract_prices.csv",
            source_family="canonical",
            format="csv",
            intended_dataset_name="contract_prices",
            ingest_support="supported_now",
            content=_render_csv(
                (
                    "contract_name",
                    "provider",
                    "contract_type",
                    "price_component",
                    "billing_cycle",
                    "unit_price",
                    "currency",
                    "quantity_unit",
                    "valid_from",
                    "valid_to",
                ),
                profile["contract_prices"],
            ),
        ),
        DemoArtifact(
            artifact_id=UTILITY_BILLS_CANONICAL_ARTIFACT_ID,
            relative_path="canonical/utility_bills.csv",
            source_family="canonical",
            format="csv",
            intended_dataset_name="utility_bills",
            ingest_support="supported_now",
            content=_render_csv(
                (
                    "meter_id",
                    "meter_name",
                    "provider",
                    "utility_type",
                    "location",
                    "billing_period_start",
                    "billing_period_end",
                    "billed_amount",
                    "currency",
                    "billed_quantity",
                    "usage_unit",
                    "invoice_date",
                ),
                profile["utility_bills"],
            ),
        ),
        DemoArtifact(
            artifact_id=BUDGETS_CANONICAL_ARTIFACT_ID,
            relative_path="canonical/budgets.csv",
            source_family="canonical",
            format="csv",
            intended_dataset_name="budgets",
            ingest_support="supported_now",
            content=_render_csv(
                (
                    "budget_name",
                    "category",
                    "period_type",
                    "target_amount",
                    "currency",
                    "effective_from",
                    "effective_to",
                ),
                profile["budgets"],
            ),
        ),
        DemoArtifact(
            artifact_id=LOAN_REPAYMENTS_CANONICAL_ARTIFACT_ID,
            relative_path="canonical/loan_repayments.csv",
            source_family="canonical",
            format="csv",
            intended_dataset_name="loan_repayments",
            ingest_support="supported_now",
            content=_render_csv(
                (
                    "loan_id",
                    "loan_name",
                    "lender",
                    "loan_type",
                    "principal",
                    "annual_rate",
                    "term_months",
                    "start_date",
                    "payment_frequency",
                    "repayment_date",
                    "payment_amount",
                    "principal_portion",
                    "interest_portion",
                    "extra_amount",
                    "currency",
                ),
                profile["loan_repayments"],
            ),
        ),
    ]

    if include_template_artifacts:
        artifacts.extend(
            [
                DemoArtifact(
                    artifact_id=PERSONAL_ACCOUNT_ARTIFACT_ID,
                    relative_path="sources/personal account/tapahtumat20250101-20251231.csv",
                    source_family="personal account",
                    format="csv",
                    intended_dataset_name="account_transactions",
                    ingest_support="supported_now",
                    source_name="demo-op-personal",
                    content=_render_op_account_csv(
                        [
                            transaction
                            for transaction in profile["transactions"]
                            if transaction.source_family == "personal account"
                        ]
                    ),
                ),
                DemoArtifact(
                    artifact_id=COMMON_ACCOUNT_ARTIFACT_ID,
                    relative_path="sources/common account/tapahtumat20250101-20251231.csv",
                    source_family="common account",
                    format="csv",
                    intended_dataset_name="account_transactions",
                    ingest_support="supported_now",
                    source_name="demo-op-common",
                    content=_render_op_account_csv(
                        [
                            transaction
                            for transaction in profile["transactions"]
                            if transaction.source_family == "common account"
                        ]
                    ),
                ),
                DemoArtifact(
                    artifact_id=REVOLUT_ACCOUNT_ARTIFACT_ID,
                    relative_path=(
                        "sources/revolut/"
                        "account-statement_2025-01-01_2025-12-31_en-us_demo.csv"
                    ),
                    source_family="revolut",
                    format="csv",
                    intended_dataset_name="account_transactions",
                    ingest_support="supported_now",
                    source_name="demo-revolut",
                    content=_render_revolut_csv(
                        [
                            transaction
                            for transaction in profile["transactions"]
                            if transaction.source_family == "revolut"
                        ]
                    ),
                ),
                DemoArtifact(
                    artifact_id=LOAN_REGISTRY_HTML_ARTIFACT_ID,
                    relative_path=(
                        "sources/loans/"
                        "Luottotietorekisteriote - Positiivinen luottotietorekisteri.html"
                    ),
                    source_family="loans",
                    format="html",
                    intended_dataset_name="loan_registry_snapshot",
                    ingest_support="template_only",
                    content=_render_loan_registry_html(profile["loan_registry"]),
                ),
                DemoArtifact(
                    artifact_id=LOAN_REGISTRY_TEXT_ARTIFACT_ID,
                    relative_path="sources/loans/luottorekisteriote.txt",
                    source_family="loans",
                    format="txt",
                    intended_dataset_name="loan_registry_snapshot",
                    ingest_support="template_only",
                    content=_render_loan_registry_text(profile["loan_registry"]),
                ),
            ]
        )

        for statement in _build_credit_card_statements():
            relative_pdf_path = (
                f"sources/credit card/Lasku_{statement.statement_date.strftime('%d%m%Y')}.pdf"
            )
            relative_json_path = (
                "sources/credit card/"
                f"Lasku_{statement.statement_date.strftime('%d%m%Y')}.summary.json"
            )
            artifacts.append(
                DemoArtifact(
                    artifact_id=statement.artifact_id,
                    relative_path=relative_pdf_path,
                    source_family="credit card",
                    format="pdf",
                    intended_dataset_name="card_statement_document",
                    ingest_support="template_only",
                    content=_render_credit_card_pdf(statement),
                )
            )
            artifacts.append(
                DemoArtifact(
                    artifact_id=f"{statement.artifact_id}_summary",
                    relative_path=relative_json_path,
                    source_family="credit card",
                    format="json",
                    intended_dataset_name="card_statement_document",
                    ingest_support="template_only",
                    content=(
                        json.dumps(
                            {
                                "statement_date": statement.statement_date.isoformat(),
                                "period_start": statement.period_start.isoformat(),
                                "period_end": statement.period_end.isoformat(),
                                "due_date": statement.due_date.isoformat(),
                                "previous_balance": _format_decimal(
                                    statement.previous_balance
                                ),
                                "payments_total": _format_decimal(statement.payments_total),
                                "purchases_total": _format_decimal(statement.purchases_total),
                                "interest_amount": _format_decimal(
                                    statement.interest_amount
                                ),
                                "service_fee": _format_decimal(statement.service_fee),
                                "minimum_due": _format_decimal(statement.minimum_due),
                                "ending_balance": _format_decimal(statement.ending_balance),
                                "transactions": list(statement.transactions),
                            },
                            indent=2,
                        )
                        + "\n"
                    ).encode("utf-8"),
                )
            )

    ordered_artifacts = tuple(sorted(artifacts, key=lambda artifact: artifact.relative_path))
    return DemoBundle(artifacts=ordered_artifacts)


def build_journey() -> dict[str, object]:
    """Return the scripted operator journey metadata for the demo bundle.

    The journey describes the intended upload sequence, what each step unlocks,
    and which metrics / attention items to highlight during a walkthrough.
    """
    return {
        "title": "Household Operating Platform — Scripted Operator Journey",
        "description": (
            "A step-by-step walkthrough using the demo bundle to prove the product loop "
            "from first upload to a populated Operating Picture."
        ),
        "data_period": "2025-01 to 2025-12",
        "steps": [
            {
                "step": 1,
                "title": "Upload personal account transactions (OP CSV)",
                "artifact_ids": [PERSONAL_ACCOUNT_ARTIFACT_ID],
                "upload_path": "/upload",
                "action": "Drag-and-drop the personal OP export CSV onto the upload page. "
                           "The wizard detects 'OP personal account' with high confidence.",
                "unlocks": [
                    "Monthly Cashflow (12 months of income and spending)",
                    "Spend by Category baseline",
                    "Salary detection: Employer Corp, EUR 3 200/month",
                ],
                "publication_keys": [
                    "monthly_cashflow",
                    "spend_by_category_monthly",
                    "household_overview",
                ],
                "attention_items": [
                    "Card payment to OP-Korttiyhtiö each month (~EUR 260–320) — credit card loop",
                    "Regular transfer to Demo Shared Household — shared account contribution",
                ],
            },
            {
                "step": 2,
                "title": "Upload common household account (OP CSV)",
                "artifact_ids": [COMMON_ACCOUNT_ARTIFACT_ID],
                "upload_path": "/upload",
                "action": "Upload the common household account CSV. "
                           "Wizard detects 'OP common account' binding.",
                "unlocks": [
                    "Household overview enriched with shared spending",
                    "Grocery and utilities spend visible",
                    "Counterparty categories: Supermarket Plus, City Power, Metro Transport",
                ],
                "publication_keys": [
                    "household_overview",
                    "spend_by_category_monthly",
                ],
                "attention_items": [
                    "Utilities spend (City Power): EUR 35–63/month with clear seasonal pattern",
                    "Grocery spend: EUR 250–320/month — largest discretionary line",
                ],
            },
            {
                "step": 3,
                "title": "Upload Revolut card account (Revolut CSV)",
                "artifact_ids": [REVOLUT_ACCOUNT_ARTIFACT_ID],
                "upload_path": "/upload",
                "action": "Upload the Revolut export. Wizard detects Revolut format.",
                "unlocks": [
                    "Entertainment spend: Netflix EUR 15.99/month",
                    "Health spend: Pharmacy Central",
                    "Full cashflow with all three account streams reconciled",
                ],
                "publication_keys": [
                    "monthly_cashflow",
                    "account_balance_trend",
                ],
                "attention_items": [
                    "Revolut top-ups match exactly to OP personal account outflows — reconciliation proof",
                ],
            },
            {
                "step": 4,
                "title": "Upload utility bills (canonical CSV)",
                "artifact_ids": [UTILITY_BILLS_CANONICAL_ARTIFACT_ID],
                "upload_path": "/upload",
                "action": "Upload canonical utility bills CSV from the demo bundle via the configured-CSV wizard.",
                "unlocks": [
                    "Utility Cost Summary (electricity + water, 12 months)",
                    "kWh and liter usage trends",
                    "Unit price comparison across periods",
                ],
                "publication_keys": [
                    "utility_cost_summary",
                    "utility_cost_trend_monthly",
                ],
                "attention_items": [
                    "Electricity peaks in winter (Dec: 421 kWh vs summer trough Jun: 257 kWh)",
                    "Total annual electricity: ~3 762 kWh",
                ],
            },
            {
                "step": 5,
                "title": "Upload subscriptions (canonical CSV)",
                "artifact_ids": [SUBSCRIPTIONS_CANONICAL_ARTIFACT_ID],
                "upload_path": "/upload",
                "action": "Upload canonical subscriptions CSV via the configured-CSV wizard.",
                "unlocks": [
                    "Subscription Summary: recurring monthly obligations",
                    "Renewal calendar in Operating Picture upcoming-actions strip",
                ],
                "publication_keys": [
                    "subscription_summary",
                    "upcoming_fixed_costs_30d",
                ],
                "attention_items": [
                    "Review subscription list against Revolut spend for unregistered recurring charges",
                ],
            },
            {
                "step": 6,
                "title": "Upload contract prices (canonical CSV)",
                "artifact_ids": [CONTRACT_PRICES_CANONICAL_ARTIFACT_ID],
                "upload_path": "/upload",
                "action": "Upload canonical contract prices CSV via the configured-CSV wizard.",
                "unlocks": [
                    "Contract Price Current: active tariffs and unit costs",
                    "Cost model comparison in Operating Picture",
                ],
                "publication_keys": [
                    "contract_price_current",
                ],
                "attention_items": [],
            },
            {
                "step": 7,
                "title": "Upload budgets (canonical CSV)",
                "artifact_ids": [BUDGETS_CANONICAL_ARTIFACT_ID],
                "upload_path": "/upload",
                "action": "Upload canonical budgets CSV via the configured-CSV wizard.",
                "unlocks": [
                    "Budget Variance: planned vs actual by category",
                    "Budget status synthetic sensor in Home Assistant",
                ],
                "publication_keys": [],
                "attention_items": [
                    "Compare groceries budget to actual — expect overage in most months",
                ],
            },
            {
                "step": 8,
                "title": "Upload loan repayments (canonical CSV)",
                "artifact_ids": [LOAN_REPAYMENTS_CANONICAL_ARTIFACT_ID],
                "upload_path": "/upload",
                "action": "Upload canonical loan repayments CSV via the configured-CSV wizard.",
                "unlocks": [
                    "Loan Overview: outstanding balance and amortisation schedule",
                    "Affordability ratio with debt service included",
                ],
                "publication_keys": [],
                "attention_items": [
                    "Monthly payment visible — appears in upcoming obligations strip",
                ],
            },
        ],
        "operating_picture_headline": {
            "money": {
                "headline_metric": "Net cashflow last 3 months",
                "trend": "stable",
                "attention": "Card payment loop — credit card charges visible monthly",
            },
            "utilities": {
                "headline_metric": "Electricity + water cost YTD",
                "trend": "seasonal",
                "attention": "Winter electricity peak (~EUR 63/month) vs summer trough (~EUR 36)",
            },
            "operations": {
                "headline_metric": "Active subscriptions",
                "trend": "stable",
                "attention": "Renewal calendar: check subscriptions for upcoming end dates",
            },
        },
        "demo_data_highlights": [
            "12 months of household transaction history (2025)",
            "Three account sources covering personal, shared, and card spending",
            "Seasonal utility usage data with realistic kWh and volume figures",
            "Salary, transfer, and card payment flows visible for reconciliation",
            "All canonical dataset types covered: transactions, subscriptions, contract prices, "
            "utility bills, budgets, loan repayments",
        ],
    }


def write_demo_bundle(output_dir: Path) -> DemoManifest:
    bundle = build_demo_bundle()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[DemoManifestRow] = []
    for artifact in bundle.artifacts:
        artifact_path = output_dir / artifact.relative_path
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(artifact.content)
        manifest_rows.append(artifact.manifest_row())

    manifest: DemoManifest = {
        "generated_at": DEMO_GENERATED_AT,
        "seed": DEMO_SEED,
        "artifacts": manifest_rows,
    }
    (output_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / JOURNEY_NAME).write_text(
        json.dumps(build_journey(), indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def load_demo_manifest(input_dir: Path) -> DemoManifest:
    return cast(
        DemoManifest,
        json.loads((input_dir / MANIFEST_NAME).read_text(encoding="utf-8")),
    )


def _build_demo_profile() -> DemoProfile:
    rng = random.Random(DEMO_SEED)
    transactions: list[DemoTransaction] = []

    for month in range(1, 13):
        month_start = date(2025, month, 1)
        salary_amount = Decimal("3200.00")
        shared_transfer = Decimal(90000 + rng.randint(0, 9000)) / Decimal("100")
        revolut_topup = Decimal(15000 + rng.randint(0, 3500)) / Decimal("100")
        card_payment = Decimal(18500 + rng.randint(0, 8500)) / Decimal("100")
        groceries = Decimal(25000 + rng.randint(0, 7000)) / Decimal("100")
        utilities = Decimal(7600 + rng.randint(0, 2200)) / Decimal("100")
        transport = Decimal(5400 + rng.randint(0, 1400)) / Decimal("100")
        dining = Decimal(3800 + rng.randint(0, 1800)) / Decimal("100")
        pharmacy = Decimal(1800 + rng.randint(0, 900)) / Decimal("100")

        transactions.extend(
            [
                DemoTransaction(
                    booked_at=month_start + timedelta(days=2),
                    account_id="PERS-001",
                    counterparty_name="Employer Corp",
                    amount=salary_amount,
                    currency="EUR",
                    description="Monthly salary",
                    source_family="personal account",
                    source_kind="salary",
                ),
                DemoTransaction(
                    booked_at=month_start + timedelta(days=3),
                    account_id="PERS-001",
                    counterparty_name="Demo Shared Household",
                    amount=-shared_transfer,
                    currency="EUR",
                    description="Own transfer",
                    source_family="personal account",
                    source_kind="transfer_out",
                ),
                DemoTransaction(
                    booked_at=month_start + timedelta(days=4),
                    account_id="PERS-001",
                    counterparty_name="Revolut Top Up",
                    amount=-revolut_topup,
                    currency="EUR",
                    description="Card top up",
                    source_family="personal account",
                    source_kind="transfer_out",
                ),
                DemoTransaction(
                    booked_at=month_start + timedelta(days=24),
                    account_id="PERS-001",
                    counterparty_name="OP-Korttiyhtiö Oyj",
                    amount=-card_payment,
                    currency="EUR",
                    description="OP Gold payment",
                    source_family="personal account",
                    source_kind="card_payment",
                ),
                DemoTransaction(
                    booked_at=month_start + timedelta(days=4),
                    account_id="COMM-001",
                    counterparty_name="Demo Personal Household",
                    amount=shared_transfer,
                    currency="EUR",
                    description="Shared household transfer",
                    source_family="common account",
                    source_kind="transfer_in",
                ),
                DemoTransaction(
                    booked_at=month_start + timedelta(days=6),
                    account_id="COMM-001",
                    counterparty_name="Supermarket Plus",
                    amount=-groceries,
                    currency="EUR",
                    description="groceries",
                    source_family="common account",
                    source_kind="card_payment",
                ),
                DemoTransaction(
                    booked_at=month_start + timedelta(days=8),
                    account_id="COMM-001",
                    counterparty_name="City Power",
                    amount=-utilities,
                    currency="EUR",
                    description="utilities",
                    source_family="common account",
                    source_kind="card_payment",
                ),
                DemoTransaction(
                    booked_at=month_start + timedelta(days=10),
                    account_id="COMM-001",
                    counterparty_name="Metro Transport",
                    amount=-transport,
                    currency="EUR",
                    description="transport",
                    source_family="common account",
                    source_kind="card_payment",
                ),
                DemoTransaction(
                    booked_at=month_start + timedelta(days=12),
                    account_id="COMM-001",
                    counterparty_name="Restaurant Roma",
                    amount=-dining,
                    currency="EUR",
                    description="dining",
                    source_family="common account",
                    source_kind="card_payment",
                ),
                DemoTransaction(
                    booked_at=month_start + timedelta(days=4),
                    account_id="REV-001",
                    counterparty_name="Google Pay deposit by *8221",
                    amount=revolut_topup,
                    currency="EUR",
                    description="Top up",
                    source_family="revolut",
                    source_kind="deposit",
                ),
                DemoTransaction(
                    booked_at=month_start + timedelta(days=14),
                    account_id="REV-001",
                    counterparty_name="Netflix Inc.",
                    amount=Decimal("-15.99"),
                    currency="EUR",
                    description="entertainment",
                    source_family="revolut",
                    source_kind="card_payment",
                ),
                DemoTransaction(
                    booked_at=month_start + timedelta(days=16),
                    account_id="REV-001",
                    counterparty_name="Pharmacy Central",
                    amount=-pharmacy,
                    currency="EUR",
                    description="health",
                    source_family="revolut",
                    source_kind="card_payment",
                ),
            ]
        )

    transactions.sort(
        key=lambda transaction: (
            transaction.booked_at,
            transaction.source_family,
            transaction.counterparty_name,
        )
    )

    utility_amounts = [48.08, 52.30, 61.45, 57.20, 42.10, 38.50, 35.90, 38.20, 44.10, 53.80, 59.40, 63.15]
    water_amounts = [19.35, 18.90, 20.10, 21.50, 22.80, 24.10, 25.30, 24.90, 22.40, 20.80, 19.60, 18.75]
    elec_kwh = [320.5, 348.7, 409.7, 381.3, 280.7, 256.7, 239.3, 254.7, 294.0, 358.7, 396.0, 421.0]
    water_liters = [11900, 11600, 12400, 13200, 14000, 14800, 15600, 15300, 13800, 12800, 12000, 11500]

    utility_bills: list[DemoCsvRow] = []
    for index in range(12):
        period_start = date(2025, index + 1, 1)
        if index == 11:
            period_end = date(2025, 12, 31)
        else:
            period_end = date(2025, index + 2, 1) - timedelta(days=1)
        invoice_date = period_end + timedelta(days=5)
        utility_bills.extend(
            [
                {
                    "meter_id": "elec-001",
                    "meter_name": "Main Electricity Meter",
                    "provider": "City Power",
                    "utility_type": "electricity",
                    "location": "home",
                    "billing_period_start": period_start.isoformat(),
                    "billing_period_end": period_end.isoformat(),
                    "billed_amount": f"{utility_amounts[index]:.2f}",
                    "currency": "EUR",
                    "billed_quantity": f"{elec_kwh[index]:.1f}",
                    "usage_unit": "kWh",
                    "invoice_date": invoice_date.isoformat(),
                },
                {
                    "meter_id": "water-001",
                    "meter_name": "Cold Water Meter",
                    "provider": "City Water",
                    "utility_type": "water",
                    "location": "home",
                    "billing_period_start": period_start.isoformat(),
                    "billing_period_end": period_end.isoformat(),
                    "billed_amount": f"{water_amounts[index]:.2f}",
                    "currency": "EUR",
                    "billed_quantity": str(water_liters[index]),
                    "usage_unit": "liter",
                    "invoice_date": invoice_date.isoformat(),
                },
            ]
        )

    loan_registry: LoanRegistryPayload = {
        "statement_date": "2026-03-02",
        "requestor_name": "Demo Pankki Oyj",
        "requestor_id": "1234567-8",
        "reference_id": "b7341e6a-6e6a-4fcb-91b9-2d75ab1e9c10",
        "person_id_masked": "010190-XXXX",
        "loans": [
            {
                "loan_type": "Asuntolaina",
                "currency": "EUR",
                "purpose": "Vakituinen asunto",
                "agreement_date": "2022-01-01",
                "lender": "Ensiasunto Pankki Oyj",
                "loan_id": "mortgage-001",
                "principal": "280000.00",
                "balance": "251420.11",
                "monthly_payment": "1557.00",
            },
            {
                "loan_type": "Kulutusluotto",
                "currency": "EUR",
                "purpose": "Kodinkoneet",
                "agreement_date": "2024-09-15",
                "lender": "Koti Luotto Oy",
                "loan_id": "consumer-002",
                "principal": "4200.00",
                "balance": "2895.40",
                "monthly_payment": "126.00",
            },
        ],
    }

    return {
        "transactions": tuple(transactions),
        "subscriptions": [
            {
                "service_name": "Netflix",
                "provider": "Netflix Inc.",
                "billing_cycle": "monthly",
                "amount": "15.99",
                "currency": "EUR",
                "start_date": "2023-01-15",
                "end_date": "",
            },
            {
                "service_name": "Spotify",
                "provider": "Spotify AB",
                "billing_cycle": "monthly",
                "amount": "9.99",
                "currency": "EUR",
                "start_date": "2022-06-01",
                "end_date": "",
            },
            {
                "service_name": "iCloud 50GB",
                "provider": "Apple Inc.",
                "billing_cycle": "monthly",
                "amount": "1.29",
                "currency": "EUR",
                "start_date": "2021-03-10",
                "end_date": "",
            },
            {
                "service_name": "GitHub Pro",
                "provider": "GitHub Inc.",
                "billing_cycle": "annual",
                "amount": "48.00",
                "currency": "USD",
                "start_date": "2023-07-01",
                "end_date": "",
            },
        ],
        "contract_prices": [
            {
                "contract_name": "Helen Spot",
                "provider": "Helen",
                "contract_type": "electricity",
                "price_component": "energy",
                "billing_cycle": "per_kwh",
                "unit_price": "0.0825",
                "currency": "EUR",
                "quantity_unit": "kWh",
                "valid_from": "2025-01-01",
                "valid_to": "",
            },
            {
                "contract_name": "Helen Spot",
                "provider": "Helen",
                "contract_type": "electricity",
                "price_component": "base_fee",
                "billing_cycle": "monthly",
                "unit_price": "5.99",
                "currency": "EUR",
                "quantity_unit": "",
                "valid_from": "2025-01-01",
                "valid_to": "",
            },
            {
                "contract_name": "Fiber 1000",
                "provider": "ISP Oy",
                "contract_type": "broadband",
                "price_component": "monthly_fee",
                "billing_cycle": "monthly",
                "unit_price": "39.90",
                "currency": "EUR",
                "quantity_unit": "",
                "valid_from": "2024-06-01",
                "valid_to": "",
            },
        ],
        "utility_bills": utility_bills,
        "budgets": [
            {
                "budget_name": "Monthly Budget",
                "category": "groceries",
                "period_type": "monthly",
                "target_amount": "350.00",
                "currency": "EUR",
                "effective_from": "2025-01",
                "effective_to": "",
            },
            {
                "budget_name": "Monthly Budget",
                "category": "entertainment",
                "period_type": "monthly",
                "target_amount": "50.00",
                "currency": "EUR",
                "effective_from": "2025-01",
                "effective_to": "",
            },
            {
                "budget_name": "Monthly Budget",
                "category": "transport",
                "period_type": "monthly",
                "target_amount": "80.00",
                "currency": "EUR",
                "effective_from": "2025-01",
                "effective_to": "",
            },
            {
                "budget_name": "Monthly Budget",
                "category": "utilities",
                "period_type": "monthly",
                "target_amount": "120.00",
                "currency": "EUR",
                "effective_from": "2025-01",
                "effective_to": "",
            },
            {
                "budget_name": "Monthly Budget",
                "category": "dining",
                "period_type": "monthly",
                "target_amount": "60.00",
                "currency": "EUR",
                "effective_from": "2025-01",
                "effective_to": "",
            },
        ],
        "loan_repayments": [
            {
                "loan_id": "mortgage-001",
                "loan_name": "Home Mortgage",
                "lender": "First National Bank",
                "loan_type": "mortgage",
                "principal": "280000.00",
                "annual_rate": "0.045",
                "term_months": "300",
                "start_date": "2022-01-01",
                "payment_frequency": "monthly",
                "repayment_date": "2025-10-01",
                "payment_amount": "1557.00",
                "principal_portion": "514.50",
                "interest_portion": "1042.50",
                "extra_amount": "",
                "currency": "EUR",
            },
            {
                "loan_id": "mortgage-001",
                "loan_name": "Home Mortgage",
                "lender": "First National Bank",
                "loan_type": "mortgage",
                "principal": "280000.00",
                "annual_rate": "0.045",
                "term_months": "300",
                "start_date": "2022-01-01",
                "payment_frequency": "monthly",
                "repayment_date": "2025-11-01",
                "payment_amount": "1557.00",
                "principal_portion": "516.43",
                "interest_portion": "1040.57",
                "extra_amount": "",
                "currency": "EUR",
            },
            {
                "loan_id": "mortgage-001",
                "loan_name": "Home Mortgage",
                "lender": "First National Bank",
                "loan_type": "mortgage",
                "principal": "280000.00",
                "annual_rate": "0.045",
                "term_months": "300",
                "start_date": "2022-01-01",
                "payment_frequency": "monthly",
                "repayment_date": "2025-12-01",
                "payment_amount": "1557.00",
                "principal_portion": "518.37",
                "interest_portion": "1038.63",
                "extra_amount": "",
                "currency": "EUR",
            },
        ],
        "loan_registry": loan_registry,
    }


def _build_credit_card_statements() -> tuple[CreditCardStatement, ...]:
    rng = random.Random(DEMO_SEED + 99)
    statements: list[CreditCardStatement] = []
    previous_balance = Decimal("3240.00")

    for index, statement_date in enumerate((date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1))):
        period_end = statement_date
        if statement_date.month == 1:
            period_start = date(statement_date.year - 1, 12, 2)
        else:
            period_start = date(statement_date.year, statement_date.month - 1, 2)

        payments_total = Decimal(35000 + rng.randint(0, 12000)) / Decimal("100")
        purchases_total = Decimal(42000 + rng.randint(0, 16000)) / Decimal("100")
        interest_amount = Decimal(1800 + rng.randint(0, 700)) / Decimal("100")
        service_fee = Decimal("3.50")
        ending_balance = previous_balance - payments_total + purchases_total + interest_amount + service_fee
        minimum_due = (ending_balance * Decimal("0.03")).quantize(Decimal("0.01"))

        transactions = (
            {
                "posted_at": (period_start + timedelta(days=5)).isoformat(),
                "merchant": "K-Ruoka Tampere",
                "amount": _format_decimal(Decimal("124.80")),
            },
            {
                "posted_at": (period_start + timedelta(days=11)).isoformat(),
                "merchant": "Gigantti Ideapark",
                "amount": _format_decimal(Decimal("189.00")),
            },
            {
                "posted_at": (period_start + timedelta(days=18)).isoformat(),
                "merchant": "Prisma Kaleva",
                "amount": _format_decimal(Decimal("96.40")),
            },
        )
        statements.append(
            CreditCardStatement(
                artifact_id=CREDIT_CARD_STATEMENT_ARTIFACT_IDS[index],
                statement_date=statement_date,
                period_start=period_start,
                period_end=period_end,
                due_date=statement_date + timedelta(days=23),
                previous_balance=previous_balance,
                payments_total=payments_total,
                purchases_total=purchases_total,
                interest_amount=interest_amount,
                service_fee=service_fee,
                minimum_due=minimum_due,
                ending_balance=ending_balance.quantize(Decimal("0.01")),
                transactions=transactions,
            )
        )
        previous_balance = ending_balance.quantize(Decimal("0.01"))

    return tuple(statements)


def _render_csv(
    fieldnames: tuple[str, ...],
    rows: Sequence[DemoCsvRow],
    *,
    delimiter: str = ",",
    quoting: CsvQuoting = CSV_QUOTE_MINIMAL,
) -> bytes:
    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        delimiter=delimiter,
        lineterminator="\n",
        quoting=quoting,
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _render_op_account_csv(transactions: Sequence[DemoTransaction]) -> bytes:
    rows: list[DemoCsvRow] = []
    for index, transaction in enumerate(sorted(transactions, key=lambda item: item.booked_at), start=1):
        rows.append(
            {
                "Kirjauspäivä": transaction.booked_at.isoformat(),
                "Arvopäivä": transaction.booked_at.isoformat(),
                "Määrä EUROA": _format_finnish_decimal(transaction.amount),
                "Laji": _op_type_code(transaction.source_kind),
                "Selitys": _op_description(transaction.source_kind),
                "Saaja/Maksaja": transaction.counterparty_name,
                "Saajan tilinumero": "",
                "Saajan pankin BIC": "",
                "Viite": "ref=",
                "Viesti": _op_message(transaction),
                "Arkistointitunnus": f"{transaction.booked_at.strftime('%Y%m%d')}/DEMO/{index:06d}",
            }
        )
    return _render_csv(
        (
            "Kirjauspäivä",
            "Arvopäivä",
            "Määrä EUROA",
            "Laji",
            "Selitys",
            "Saaja/Maksaja",
            "Saajan tilinumero",
            "Saajan pankin BIC",
            "Viite",
            "Viesti",
            "Arkistointitunnus",
        ),
        rows,
        delimiter=";",
        quoting=CSV_QUOTE_ALL,
    )


def _render_revolut_csv(transactions: Sequence[DemoTransaction]) -> bytes:
    rows: list[DemoCsvRow] = []
    balance = Decimal("0.00")
    for index, transaction in enumerate(sorted(transactions, key=lambda item: item.booked_at), start=1):
        started_at = datetime.combine(
            transaction.booked_at,
            time(hour=8 + (index % 9), minute=(index * 7) % 60, second=0),
        )
        completed_at = started_at + timedelta(minutes=3)
        balance += transaction.amount
        rows.append(
            {
                "Type": "Deposit" if transaction.amount >= 0 else "Card Payment",
                "Product": "Current",
                "Started Date": started_at.strftime("%Y-%m-%d %H:%M:%S"),
                "Completed Date": completed_at.strftime("%Y-%m-%d %H:%M:%S"),
                "Description": transaction.counterparty_name,
                "Amount": _format_decimal(transaction.amount),
                "Fee": "0.00",
                "Currency": transaction.currency,
                "State": "COMPLETED",
                "Balance": _format_decimal(balance),
            }
        )
    return _render_csv(
        (
            "Type",
            "Product",
            "Started Date",
            "Completed Date",
            "Description",
            "Amount",
            "Fee",
            "Currency",
            "State",
            "Balance",
        ),
        rows,
    )


def _render_credit_card_pdf(statement: CreditCardStatement) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError(
            "Generating demo credit-card PDFs requires the reportlab package."
        ) from exc

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, invariant=1)

    first_page_lines = [
        "Lasku",
        "OP Gold Demo",
        "",
        f"Päivämäärä {statement.statement_date.strftime('%-d.%-m.%Y')}",
        f"Laskutuskausi {statement.period_start.strftime('%d.%m.%Y')} - {statement.period_end.strftime('%d.%m.%Y')}",
        f"Eräpäivä {statement.due_date.strftime('%-d.%-m.%Y')}",
        "",
        "Aino Nieminen",
        "Katajatie 12 A 3",
        "33100 TAMPERE",
        "",
        f"Velkasaldo edellisellä laskulla {statement.previous_balance} EUR",
        f"Suoritukset yhteensä -{statement.payments_total} EUR",
        f"Laskutuskauden tapahtumat {statement.purchases_total} EUR",
        f"Tilinhoitomaksu {statement.service_fee} EUR",
        f"Korko {statement.interest_amount} EUR",
        "",
        f"Velkasaldo yhteensä {statement.ending_balance} EUR",
        f"Maksettava vähintään {statement.minimum_due} EUR",
    ]

    text = pdf.beginText(42, 800)
    text.setLeading(16)
    for line in first_page_lines:
        text.textLine(line)
    pdf.drawText(text)
    pdf.showPage()

    second_page_lines = [
        "Laskutuskauden tapahtumat",
        "",
    ]
    second_page_lines.extend(
        [
            f"{transaction['posted_at']}  {transaction['merchant']}  {transaction['amount']} EUR"
            for transaction in statement.transactions
        ]
    )
    second_page_lines.extend(
        [
            "",
            "Tämä on synteettinen demo-lasku.",
            "Henkilö- ja tilitiedot ovat kuvitteellisia.",
        ]
    )
    text = pdf.beginText(42, 800)
    text.setLeading(16)
    for line in second_page_lines:
        text.textLine(line)
    pdf.drawText(text)
    pdf.showPage()

    pdf.save()
    return buffer.getvalue()


def _render_loan_registry_html(payload: LoanRegistryPayload) -> bytes:
    loans_html = "".join(
        [
            """
            <section class="loan">
              <h2>{loan_type}</h2>
              <p>Luotonantaja: {lender}</p>
              <p>Luoton tunniste: {loan_id}</p>
              <p>Luotto myönnetty: {agreement_date}</p>
              <p>Pääoma: {principal} EUR</p>
              <p>Jäljellä oleva saldo: {balance} EUR</p>
              <p>Kuukausierä: {monthly_payment} EUR</p>
            </section>
            """.format(
                loan_type=html.escape(str(loan["loan_type"])),
                lender=html.escape(str(loan["lender"])),
                loan_id=html.escape(str(loan["loan_id"])),
                agreement_date=html.escape(str(loan["agreement_date"])),
                principal=html.escape(str(loan["principal"])),
                balance=html.escape(str(loan["balance"])),
                monthly_payment=html.escape(str(loan["monthly_payment"])),
            )
            for loan in payload["loans"]
        ]
    )

    document = f"""<!DOCTYPE html>
<html lang="fi">
  <head>
    <meta charset="utf-8" />
    <title>Luottotietorekisteriote - Positiivinen luottotietorekisteri</title>
  </head>
  <body>
    <h1>Luottotietorekisteriote - Positiivinen luottotietorekisteri</h1>
    <p>Muodostettu {html.escape(str(payload["statement_date"]))}</p>
    <p>Tilaaja: {html.escape(str(payload["requestor_name"]))} ({html.escape(str(payload["requestor_id"]))})</p>
    <p>Otteen viite: {html.escape(str(payload["reference_id"]))}</p>
    <p>Henkilötunnus: {html.escape(str(payload["person_id_masked"]))}</p>
    {loans_html}
    <p>Tämä tiedosto on synteettinen demoaineisto.</p>
  </body>
</html>
"""
    return document.encode("utf-8")


def _render_loan_registry_text(payload: LoanRegistryPayload) -> bytes:
    lines = [
        f"Luottotietorekisteriote - {payload['requestor_name']}, {payload['statement_date']}",
        "Tämä ote on synteettinen demoaineisto.",
        "",
        "Tilauksen tiedot",
        f"Tilaajan tunniste: {payload['requestor_id']}",
        f"Otteen viite: {payload['reference_id']}",
        f"Henkilötunnus: {payload['person_id_masked']}",
        "",
    ]
    for index, loan in enumerate(payload["loans"], start=1):
        lines.extend(
            [
                f"Luotto {index}",
                f"Luoton tyyppi: {loan['loan_type']}",
                f"Luotonantaja: {loan['lender']}",
                f"Luoton tunniste: {loan['loan_id']}",
                f"Luotto myönnetty: {loan['agreement_date']}",
                f"Pääoma: {loan['principal']} EUR",
                f"Saldo: {loan['balance']} EUR",
                f"Kuukausierä: {loan['monthly_payment']} EUR",
                "",
            ]
        )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _format_decimal(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


def _format_finnish_decimal(value: Decimal) -> str:
    return _format_decimal(value).replace(".", ",")


def _op_type_code(source_kind: str) -> str:
    if source_kind in {"salary", "transfer_in", "deposit"}:
        return "506"
    if source_kind == "transfer_out":
        return "105"
    if source_kind == "card_payment":
        return "162"
    return "129"


def _op_description(source_kind: str) -> str:
    if source_kind in {"salary", "transfer_in", "transfer_out"}:
        return "TILISIIRTO"
    return "PKORTTIMAKSU"


def _op_message(transaction: DemoTransaction) -> str:
    if transaction.source_kind == "salary":
        return "SEPA-MAKSU Viesti: SALARY DEMO"
    if transaction.source_kind in {"transfer_in", "transfer_out"}:
        return "Viesti: Own transfer"
    if transaction.source_kind == "card_payment":
        return f"Viesti: DEMO CARD PURCHASE {transaction.counterparty_name}"
    return transaction.description
