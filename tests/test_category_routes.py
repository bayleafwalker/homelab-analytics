"""Category route tests: reads go through the reporting layer, writes stay on transformation."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.routes.category_routes import register_category_routes
from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore


class _RecordingReportingService(ReportingService):
    def __init__(self, transformation_service: TransformationService) -> None:
        super().__init__(transformation_service)
        self.category_reads = 0

    def get_current_categories(self) -> list[dict[str, Any]]:
        self.category_reads += 1
        return super().get_current_categories()


def test_list_categories_reads_through_reporting_service() -> None:
    ts = TransformationService(DuckDBStore.memory())
    reporting = _RecordingReportingService(ts)
    app = FastAPI()
    register_category_routes(
        app,
        transformation_service=ts,
        resolved_reporting_service=reporting,
        to_jsonable=lambda value: value,
    )
    client = TestClient(app)

    response = client.get("/api/categories")

    assert response.status_code == 200
    assert reporting.category_reads == 1
    assert response.json()["categories"] == ts.get_current_dimension_rows("dim_category")


def test_operator_category_is_visible_immediately_after_create() -> None:
    ts = TransformationService(DuckDBStore.memory())
    reporting = _RecordingReportingService(ts)
    app = FastAPI()
    register_category_routes(
        app,
        transformation_service=ts,
        resolved_reporting_service=reporting,
        to_jsonable=lambda value: value,
    )
    client = TestClient(app)

    created = client.post(
        "/api/categories",
        json={"category_id": "groceries_organic", "display_name": "Organic groceries"},
    )
    listed = client.get("/api/categories").json()["categories"]

    assert created.status_code == 201
    assert "groceries_organic" in {row["category_id"] for row in listed}


def test_list_categories_without_reporting_service_falls_back_to_reporting_layer() -> None:
    ts = TransformationService(DuckDBStore.memory())
    app = FastAPI()
    register_category_routes(
        app,
        transformation_service=ts,
        to_jsonable=lambda value: value,
    )

    response = TestClient(app).get("/api/categories")

    assert response.status_code == 200
    assert response.json()["categories"] == ts.get_current_dimension_rows("dim_category")


def test_list_categories_without_transformation_service_returns_404() -> None:
    app = FastAPI()
    register_category_routes(app, transformation_service=None, to_jsonable=lambda value: value)

    assert TestClient(app).get("/api/categories").status_code == 404


def test_list_categories_with_reporting_but_no_transformation_service_returns_404() -> None:
    reporting = _RecordingReportingService(TransformationService(DuckDBStore.memory()))
    app = FastAPI()
    register_category_routes(
        app,
        transformation_service=None,
        resolved_reporting_service=reporting,
        to_jsonable=lambda value: value,
    )

    assert TestClient(app).get("/api/categories").status_code == 404
    assert reporting.category_reads == 0
