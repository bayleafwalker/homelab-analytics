"""Category dimension API routes.

Exposes:
  GET  /api/categories              → list all current dim_category rows
  POST /api/categories              → create an operator sub-category (is_system=False)

System categories are seeded at init and are immutable — POST returns 409
if the requested category_id collides with a system category slug.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from packages.domains.finance.pipelines.category_seed import SYSTEM_CATEGORY_IDS
from packages.domains.finance.pipelines.subscription_models import DIM_CATEGORY
from packages.pipelines.transformation_service import TransformationService

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_]*$")


class CreateCategoryRequest(BaseModel):
    category_id: str          # stable slug, e.g. "groceries_organic"
    display_name: str
    parent_id: str | None = None
    domain: str = "finance"
    is_budget_eligible: bool = True


def register_category_routes(
    app: FastAPI,
    *,
    transformation_service: TransformationService | None,
    to_jsonable: Callable[[Any], Any],
) -> None:
    def _ts() -> TransformationService:
        if transformation_service is None:
            raise HTTPException(
                status_code=404,
                detail="Category management requires a transformation service.",
            )
        return transformation_service

    @app.get("/api/categories")
    async def list_categories() -> dict[str, Any]:
        rows = _ts().get_current_categories()
        return {"categories": to_jsonable(rows)}

    @app.post("/api/categories", status_code=201)
    async def create_category(body: CreateCategoryRequest) -> dict[str, Any]:
        ts = _ts()

        if not _SLUG_RE.match(body.category_id):
            raise HTTPException(
                status_code=422,
                detail=(
                    "category_id must be a lowercase slug "
                    "(letters, digits, underscores; must start with a letter or digit)."
                ),
            )

        if body.category_id in SYSTEM_CATEGORY_IDS:
            raise HTTPException(
                status_code=409,
                detail=f"'{body.category_id}' is a system category and cannot be overwritten.",
            )

        ts._store.upsert_dimension_rows(
            DIM_CATEGORY,
            [
                {
                    "category_id": body.category_id,
                    "display_name": body.display_name,
                    "parent_id": body.parent_id,
                    "domain": body.domain,
                    "is_budget_eligible": body.is_budget_eligible,
                    "is_system": False,
                }
            ],
        )
        return {
            "category_id": body.category_id,
            "display_name": body.display_name,
            "parent_id": body.parent_id,
            "domain": body.domain,
            "is_budget_eligible": body.is_budget_eligible,
            "is_system": False,
        }
