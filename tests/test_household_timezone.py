"""HOMELAB_ANALYTICS_HOUSEHOLD_TIMEZONE: setting, heatmap, wallboard, brief.

Europe/Helsinki is the DST fixture: EET (+02:00) / EEST (+03:00), switching at
01:00 UTC on the last Sunday of March (local 03:00 -> 04:00) and of October
(local 04:00 -> 03:00). In 2026 those are 29 March and 25 October.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.app import create_app
from apps.api.routes.briefing_routes import register_briefing_routes
from packages.application.use_cases.morning_brief import (
    BriefInputs,
    SourceEvidence,
    compose_morning_brief,
)
from packages.application.use_cases.morning_brief_sections import (
    default_brief_section_registry,
)
from packages.application.use_cases.wallboard import build_power_series, power_window_start
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.domains.finance.pipelines.spend_heatmap import (
    build_spend_heatmap,
    spend_heatmap_mart_range,
)
from packages.pipelines.transformation_service import TransformationService
from packages.shared.household_time import household_zone, local_date
from packages.shared.settings import AppSettings
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository

HELSINKI = "Europe/Helsinki"


# ---------------------------------------------------------------------------
# Setting
# ---------------------------------------------------------------------------


def test_setting_defaults_to_utc() -> None:
    settings = AppSettings.from_env({})
    assert settings.household_timezone == "UTC"
    assert settings.resolved_household_timezone.key == "UTC"


def test_setting_accepts_an_iana_name() -> None:
    settings = AppSettings.from_env({"HOMELAB_ANALYTICS_HOUSEHOLD_TIMEZONE": " Europe/Helsinki "})
    assert settings.household_timezone == HELSINKI
    assert settings.resolved_household_timezone.key == HELSINKI


@pytest.mark.parametrize("bad", ["Mars/Olympus_Mons", "../../etc/passwd", "/etc/localtime", "EET+2"])
def test_setting_rejects_unknown_zones_at_startup(bad: str) -> None:
    with pytest.raises(ValueError, match="HOMELAB_ANALYTICS_HOUSEHOLD_TIMEZONE"):
        AppSettings.from_env({"HOMELAB_ANALYTICS_HOUSEHOLD_TIMEZONE": bad})


def test_settings_constructed_directly_are_validated_too() -> None:
    base = AppSettings.from_env({})
    with pytest.raises(ValueError, match="IANA"):
        AppSettings(**{**base.__dict__, "household_timezone": "Nowhere/Land"})


def test_local_date_treats_naive_as_utc() -> None:
    zone = household_zone(HELSINKI)
    assert local_date(datetime(2026, 10, 18, 22, 30), zone) == date(2026, 10, 19)
    assert local_date(datetime(2026, 10, 18, 20, 59, tzinfo=UTC), zone) == date(2026, 10, 18)


# ---------------------------------------------------------------------------
# Spend heatmap
# ---------------------------------------------------------------------------


def _mart_row(booked_at: str, hour: int | None, amount: str) -> dict[str, object]:
    day = date.fromisoformat(booked_at)
    return {
        "booked_at": day,
        "day_of_week": day.isoweekday(),
        "hour_of_day": hour,
        "total_expense": amount,
        "transaction_count": 1,
    }


def test_heatmap_default_is_utc_and_says_so() -> None:
    payload = build_spend_heatmap([_mart_row("2026-03-02", 18, "42.00")])
    assert payload["timezone"] == "UTC"
    assert payload["hour_basis"] == "utc"
    assert payload["cells"][0][18] == "42.00"


def test_heatmap_moves_hours_weekdays_and_dates_onto_the_household_clock() -> None:
    # Monday 2026-03-02 22:00 UTC is Tuesday 00:00 in Helsinki (+02:00).
    payload = build_spend_heatmap(
        [_mart_row("2026-03-02", 22, "10.00"), _mart_row("2026-03-02", 7, "5.00")],
        timezone=HELSINKI,
    )
    assert payload["timezone"] == HELSINKI
    assert payload["hour_basis"] == "local"
    assert payload["cells"][1][0] == "10.00"  # Tue 00
    assert payload["cells"][0][9] == "5.00"  # Mon 09
    assert payload["cells"][0][22] == "0.00"
    assert payload["data_through"] == "2026-03-03"


def test_heatmap_date_only_rows_keep_their_booking_date() -> None:
    payload = build_spend_heatmap([_mart_row("2026-03-02", None, "8.00")], timezone=HELSINKI)
    assert payload["untimed"][0] == "8.00"
    assert payload["data_through"] == "2026-03-02"


def test_heatmap_window_is_on_local_dates() -> None:
    # 23:00 UTC on 3 March is 01:00 on 4 March in Helsinki: outside a window
    # ending 3 March, inside one ending 4 March.
    rows = [_mart_row("2026-03-03", 23, "7.00")]
    ending_3rd = build_spend_heatmap(rows, window_days=1, end=date(2026, 3, 3), timezone=HELSINKI)
    ending_4th = build_spend_heatmap(rows, window_days=1, end=date(2026, 3, 4), timezone=HELSINKI)
    assert ending_3rd["totals"]["transaction_count"] == 0
    assert ending_4th["cells"][2][1] == "7.00"  # Wed 01
    assert spend_heatmap_mart_range(date(2026, 3, 4), 1) == (date(2026, 3, 3), date(2026, 3, 5))


def test_heatmap_spring_forward_skips_the_missing_local_hour() -> None:
    # Sunday 29 March 2026: UTC 00:00 -> 02:00 EET, UTC 01:00 -> 04:00 EEST.
    rows = [_mart_row("2026-03-29", hour, "1.00") for hour in (0, 1, 2)]
    payload = build_spend_heatmap(rows, timezone=HELSINKI)
    sunday = payload["cells"][6]
    assert sunday[2] == "1.00"
    assert sunday[3] == "0.00"  # 03:00 never happened
    assert sunday[4] == "1.00"
    assert sunday[5] == "1.00"
    assert payload["totals"]["timed_expense"] == "3.00"


def test_heatmap_fall_back_folds_the_repeated_local_hour() -> None:
    # Sunday 25 October 2026: UTC 00:00 -> 03:00 EEST, UTC 01:00 -> 03:00 EET.
    rows = [_mart_row("2026-10-25", hour, "1.00") for hour in (0, 1, 2)]
    payload = build_spend_heatmap(rows, timezone=HELSINKI)
    sunday = payload["cells"][6]
    assert sunday[3] == "2.00"
    assert payload["counts"][6][3] == 2
    assert sunday[4] == "1.00"
    assert payload["totals"]["timed_expense"] == "3.00"


def test_heatmap_fractional_offset_uses_the_local_hour_each_utc_hour_starts_in() -> None:
    payload = build_spend_heatmap([_mart_row("2026-03-02", 10, "3.00")], timezone="Asia/Kolkata")
    assert payload["cells"][0][15] == "3.00"  # 10:00Z = 15:30 IST


def _tx(booked_at: str, counterparty: str, amount: str) -> dict[str, object]:
    return {
        "booked_at": booked_at,
        "account_id": "CHK-001",
        "counterparty_name": counterparty,
        "amount": amount,
        "currency": "EUR",
        "description": "",
    }


def test_heatmap_endpoint_reports_in_the_household_zone() -> None:
    with TemporaryDirectory() as temp_dir:
        service = TransformationService(DuckDBStore.memory())
        service.load_transactions(
            [_tx("2026-03-02T22:30:00Z", "Night Grocer", "-12.00")], run_id="run-001"
        )
        service.refresh_publications(["mart_spend_by_weekday_hour"])
        client = TestClient(
            create_app(
                AccountTransactionService(
                    landing_root=Path(temp_dir) / "landing",
                    metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
                ),
                transformation_service=service,
                household_timezone=HELSINKI,
            )
        )
        body = client.get("/reports/spend-heatmap").json()
        assert body["timezone"] == HELSINKI
        assert body["hour_basis"] == "local"
        assert body["cells"][1][0] == "12.00"  # Tuesday 00:30 local
        assert body["window_end"] == "2026-03-03"

        # as_of is a local date: the UTC-Monday purchase is Tuesday's.
        tuesday = client.get(
            "/reports/spend-heatmap", params={"window": 1, "as_of": "2026-03-03"}
        ).json()
        assert tuesday["cells"][1][0] == "12.00"
        monday = client.get(
            "/reports/spend-heatmap", params={"window": 1, "as_of": "2026-03-02"}
        ).json()
        assert monday["totals"]["transaction_count"] == 0


# ---------------------------------------------------------------------------
# Wallboard power buckets
# ---------------------------------------------------------------------------


def _reading(at: datetime, value: str) -> dict[str, str]:
    return {"changed_at": at.isoformat(), "state": value}


def test_power_buckets_are_labelled_on_the_household_clock() -> None:
    now = datetime(2026, 10, 18, 12, 30, tzinfo=UTC)
    buckets = build_power_series([], unit="kWh", now=now, zone=household_zone(HELSINKI))
    assert buckets[-1]["hour_start"] == "2026-10-18T15:00:00+03:00"
    assert buckets[-1]["hour_end"] == "2026-10-18T16:00:00+03:00"
    assert buckets[-1]["partial"] is True
    assert buckets[0]["hour_start"] == "2026-10-17T16:00:00+03:00"


def test_power_buckets_across_spring_forward_skip_the_missing_hour() -> None:
    zone = household_zone(HELSINKI)
    now = datetime(2026, 3, 29, 3, 30, tzinfo=UTC)  # 06:30 EEST
    readings = [
        _reading(datetime(2026, 3, 29, 0, 30, tzinfo=UTC), "100.0"),
        _reading(datetime(2026, 3, 29, 1, 30, tzinfo=UTC), "101.0"),
    ]
    buckets = build_power_series(readings, unit="kWh", now=now, window_hours=6, zone=zone)
    assert [bucket["hour_start"] for bucket in buckets] == [
        "2026-03-29T00:00:00+02:00",
        "2026-03-29T01:00:00+02:00",
        "2026-03-29T02:00:00+02:00",
        "2026-03-29T04:00:00+03:00",
        "2026-03-29T05:00:00+03:00",
        "2026-03-29T06:00:00+03:00",
    ]
    # Every bucket is one real hour, so the 1 kWh across the switch splits evenly.
    for bucket in buckets:
        span = datetime.fromisoformat(bucket["hour_end"]) - datetime.fromisoformat(
            bucket["hour_start"]
        )
        assert span == timedelta(hours=1)
    by_start = {bucket["hour_start"]: bucket["kwh"] for bucket in buckets}
    assert by_start["2026-03-29T02:00:00+02:00"] == 0.5
    assert by_start["2026-03-29T04:00:00+03:00"] == 0.5


def test_power_buckets_across_fall_back_repeat_the_hour_with_distinct_offsets() -> None:
    zone = household_zone(HELSINKI)
    now = datetime(2026, 10, 25, 3, 30, tzinfo=UTC)  # 05:30 EET
    readings = [
        _reading(datetime(2026, 10, 25, 0, 0, tzinfo=UTC), "10.0"),
        _reading(datetime(2026, 10, 25, 1, 0, tzinfo=UTC), "10.4"),
        _reading(datetime(2026, 10, 25, 2, 0, tzinfo=UTC), "11.0"),
    ]
    buckets = build_power_series(readings, unit="kWh", now=now, window_hours=6, zone=zone)
    starts = [bucket["hour_start"] for bucket in buckets]
    assert starts == [
        "2026-10-25T01:00:00+03:00",
        "2026-10-25T02:00:00+03:00",
        "2026-10-25T03:00:00+03:00",
        "2026-10-25T03:00:00+02:00",
        "2026-10-25T04:00:00+02:00",
        "2026-10-25T05:00:00+02:00",
    ]
    assert len(set(starts)) == 6
    by_start = {bucket["hour_start"]: bucket["kwh"] for bucket in buckets}
    assert by_start["2026-10-25T03:00:00+03:00"] == 0.4
    assert by_start["2026-10-25T03:00:00+02:00"] == 0.6


def test_power_buckets_follow_half_hour_offsets() -> None:
    zone = household_zone("Asia/Kolkata")
    now = datetime(2026, 10, 18, 12, 40, tzinfo=UTC)  # 18:10 IST
    assert power_window_start(now, 1, zone) == datetime(2026, 10, 18, 12, 30, tzinfo=UTC)
    buckets = build_power_series([], unit="kWh", now=now, window_hours=2, zone=zone)
    assert [bucket["hour_start"] for bucket in buckets] == [
        "2026-10-18T17:00:00+05:30",
        "2026-10-18T18:00:00+05:30",
    ]


def test_power_endpoint_states_its_timezone(tmp_path: Path) -> None:
    service = AccountTransactionService(
        landing_root=tmp_path / "landing",
        metadata_repository=RunMetadataRepository(tmp_path / "runs.db"),
    )
    ts = TransformationService(DuckDBStore.memory())
    client = TestClient(
        create_app(service, transformation_service=ts, household_timezone=HELSINKI)
    )
    power = client.get("/api/wallboard/power").json()
    assert power["timezone"] == HELSINKI
    assert power["buckets"][-1]["hour_start"][-6:] in {"+02:00", "+03:00"}

    default = TestClient(create_app(service, transformation_service=ts))
    assert default.get("/api/wallboard/power").json()["timezone"] == "UTC"


# ---------------------------------------------------------------------------
# Morning brief dates
# ---------------------------------------------------------------------------


def _brief_client(now: datetime, zone: str) -> TestClient:
    app = FastAPI()
    register_briefing_routes(
        app,
        resolved_reporting_service=None,
        control_plane=None,
        metadata_repository=None,
        clock=lambda: now,
        household_timezone=zone,
    )
    return TestClient(app)


def test_brief_as_of_is_the_household_date() -> None:
    late_utc = datetime(2026, 10, 18, 22, 30, tzinfo=UTC)  # 01:30 on the 19th in Helsinki
    local = _brief_client(late_utc, HELSINKI).get("/api/briefing").json()
    assert local["as_of"] == "2026-10-19"
    assert local["timezone"] == HELSINKI
    utc = _brief_client(late_utc, "UTC").get("/api/briefing").json()
    assert utc["as_of"] == "2026-10-18"
    assert utc["timezone"] == "UTC"
    assert local["content_hash"] != utc["content_hash"]


def test_brief_source_dates_are_household_dates() -> None:
    source = SourceEvidence(
        source_asset_id="bank",
        name="Bank export",
        dataset_name="account_transactions",
        freshness_state="overdue",
        latest_run_id=None,
        latest_status=None,
        landed_at=datetime(2026, 10, 16, 21, 30, tzinfo=UTC),  # 17th 00:30 local
        next_expected_at=datetime(2026, 10, 17, 22, 0, tzinfo=UTC),  # 18th 01:00 local
        covered_through=None,
        suggested_action="upload",
    )

    def detail(zone: str) -> str:
        brief = compose_morning_brief(
            BriefInputs(
                as_of=date(2026, 10, 19),
                generated_at=datetime(2026, 10, 18, 22, 30, tzinfo=UTC),
                sources=(source,),
                timezone=zone,
            ),
            default_brief_section_registry(),
        )
        items = [item for section in brief.sections for item in section.items]
        return next(item.detail for item in items if item.item_id == "sources:bank") or ""

    assert detail(HELSINKI) == "Last ingest 2026-10-17, next expected 2026-10-18."
    assert detail("UTC") == "Last ingest 2026-10-16, next expected 2026-10-17."
