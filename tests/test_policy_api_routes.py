"""Tests for /control/policies CRUD routes and control.policy.read/write permissions."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.platform.auth.contracts import UserRole
from packages.platform.auth.permission_registry import (
    KNOWN_PERMISSIONS,
    PERMISSION_CONTROL_POLICY_READ,
    PERMISSION_CONTROL_POLICY_WRITE,
    permissions_for_role,
)
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository


def _build_client(temp_dir: str) -> TestClient:
    temp_root = Path(temp_dir)
    service = AccountTransactionService(
        landing_root=temp_root / "landing",
        metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
    )
    config_repository = IngestionConfigRepository(temp_root / "config.db")
    app = create_app(service, config_repository=config_repository, enable_unsafe_admin=True)
    return TestClient(app)


_VALID_RULE = {
    "rule_kind": "publication_value_comparison",
    "publication_key": "monthly_cashflow",
    "field_name": "net",
    "operator": "lt",
    "threshold": 0,
    "unit": "currency",
}


class PolicyPermissionTests(unittest.TestCase):
    def test_policy_permissions_in_known_permissions(self) -> None:
        assert PERMISSION_CONTROL_POLICY_READ in KNOWN_PERMISSIONS
        assert PERMISSION_CONTROL_POLICY_WRITE in KNOWN_PERMISSIONS

    def test_admin_has_policy_read_and_write(self) -> None:
        admin_perms = permissions_for_role(UserRole.ADMIN)
        assert PERMISSION_CONTROL_POLICY_READ in admin_perms
        assert PERMISSION_CONTROL_POLICY_WRITE in admin_perms

    def test_reader_does_not_have_policy_permissions(self) -> None:
        reader_perms = permissions_for_role(UserRole.READER)
        assert PERMISSION_CONTROL_POLICY_READ not in reader_perms
        assert PERMISSION_CONTROL_POLICY_WRITE not in reader_perms

    def test_operator_does_not_have_policy_permissions(self) -> None:
        operator_perms = permissions_for_role(UserRole.OPERATOR)
        assert PERMISSION_CONTROL_POLICY_READ not in operator_perms
        assert PERMISSION_CONTROL_POLICY_WRITE not in operator_perms


class PolicyCrudRouteTests(unittest.TestCase):
    def test_list_policies_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            response = client.get("/control/policies")
        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json()["policies"])

    def test_create_policy_returns_201(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            response = client.post(
                "/control/policies",
                json={
                    "display_name": "Net cashflow alert",
                    "policy_kind": "publication_value_comparison",
                    "rule_document": _VALID_RULE,
                    "creator": "test-user",
                },
            )
        self.assertEqual(201, response.status_code)
        data = response.json()
        self.assertEqual("Net cashflow alert", data["display_name"])
        self.assertEqual("operator", data["source_kind"])
        self.assertEqual(True, data["enabled"])
        self.assertIn("policy_id", data)
        self.assertEqual(_VALID_RULE["rule_kind"], data["rule_document"]["rule_kind"])

    def test_create_policy_rejects_unknown_rule_kind(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            response = client.post(
                "/control/policies",
                json={
                    "display_name": "Evil policy",
                    "policy_kind": "exec",
                    "rule_document": {"rule_kind": "exec_python", "code": "os.system('whoami')"},
                },
            )
        self.assertEqual(422, response.status_code)

    def test_create_policy_rejects_extra_rule_fields(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            bad_rule = dict(_VALID_RULE, injected="malicious")
            response = client.post(
                "/control/policies",
                json={
                    "display_name": "Bad policy",
                    "policy_kind": "publication_value_comparison",
                    "rule_document": bad_rule,
                },
            )
        self.assertEqual(422, response.status_code)

    def test_get_policy(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            create_resp = client.post(
                "/control/policies",
                json={
                    "display_name": "My policy",
                    "policy_kind": "publication_value_comparison",
                    "rule_document": _VALID_RULE,
                },
            )
            policy_id = create_resp.json()["policy_id"]
            get_resp = client.get(f"/control/policies/{policy_id}")
        self.assertEqual(200, get_resp.status_code)
        self.assertEqual(policy_id, get_resp.json()["policy_id"])

    def test_get_policy_not_found(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            response = client.get("/control/policies/nonexistent-id")
        self.assertEqual(404, response.status_code)

    def test_list_policies_after_create(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            client.post(
                "/control/policies",
                json={
                    "display_name": "P1",
                    "policy_kind": "publication_value_comparison",
                    "rule_document": _VALID_RULE,
                },
            )
            client.post(
                "/control/policies",
                json={
                    "display_name": "P2",
                    "policy_kind": "publication_value_comparison",
                    "rule_document": _VALID_RULE,
                },
            )
            response = client.get("/control/policies")
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(response.json()["policies"]))

    def test_update_policy_enabled_state(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            create_resp = client.post(
                "/control/policies",
                json={
                    "display_name": "Disable me",
                    "policy_kind": "publication_value_comparison",
                    "rule_document": _VALID_RULE,
                },
            )
            policy_id = create_resp.json()["policy_id"]
            patch_resp = client.patch(
                f"/control/policies/{policy_id}",
                json={"enabled": False},
            )
        self.assertEqual(200, patch_resp.status_code)
        self.assertFalse(patch_resp.json()["enabled"])

    def test_update_policy_rule_document_validated(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            create_resp = client.post(
                "/control/policies",
                json={
                    "display_name": "My policy",
                    "policy_kind": "publication_value_comparison",
                    "rule_document": _VALID_RULE,
                },
            )
            policy_id = create_resp.json()["policy_id"]
            patch_resp = client.patch(
                f"/control/policies/{policy_id}",
                json={"rule_document": {"rule_kind": "exec_python", "code": "bad"}},
            )
        self.assertEqual(422, patch_resp.status_code)

    def test_update_policy_not_found(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            response = client.patch(
                "/control/policies/ghost",
                json={"display_name": "New name"},
            )
        self.assertEqual(404, response.status_code)

    def test_delete_policy(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            create_resp = client.post(
                "/control/policies",
                json={
                    "display_name": "Delete me",
                    "policy_kind": "publication_value_comparison",
                    "rule_document": _VALID_RULE,
                },
            )
            policy_id = create_resp.json()["policy_id"]
            del_resp = client.delete(f"/control/policies/{policy_id}")
            self.assertEqual(204, del_resp.status_code)
            get_resp = client.get(f"/control/policies/{policy_id}")
        self.assertEqual(404, get_resp.status_code)

    def test_delete_policy_not_found(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            response = client.delete("/control/policies/ghost")
        self.assertEqual(404, response.status_code)

    def test_list_policies_enabled_only_filter(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            create_resp = client.post(
                "/control/policies",
                json={
                    "display_name": "Active",
                    "policy_kind": "publication_value_comparison",
                    "rule_document": _VALID_RULE,
                },
            )
            policy_id = create_resp.json()["policy_id"]
            client.patch(f"/control/policies/{policy_id}", json={"enabled": False})
            client.post(
                "/control/policies",
                json={
                    "display_name": "Also Active",
                    "policy_kind": "publication_value_comparison",
                    "rule_document": _VALID_RULE,
                },
            )
            response = client.get("/control/policies?enabled_only=true")
        self.assertEqual(200, response.status_code)
        results = response.json()["policies"]
        self.assertEqual(1, len(results))
        self.assertEqual("Also Active", results[0]["display_name"])


class PolicyPublicationReferenceValidationTests(unittest.TestCase):
    def test_create_with_unknown_publication_key_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            bad_rule = dict(_VALID_RULE, publication_key="no_such_publication")
            response = client.post(
                "/control/policies",
                json={
                    "display_name": "Bad Ref",
                    "policy_kind": "declarative_rule",
                    "rule_document": bad_rule,
                },
            )
            self.assertEqual(422, response.status_code)
            self.assertIn("Unknown publication reference", response.json()["detail"])

    def test_create_with_known_publication_key_is_accepted(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            response = client.post(
                "/control/policies",
                json={
                    "display_name": "Good Ref",
                    "policy_kind": "declarative_rule",
                    "rule_document": _VALID_RULE,
                },
            )
            self.assertEqual(201, response.status_code)

    def test_enable_revalidates_stored_references(self) -> None:
        import json as _json

        from packages.storage.control_plane import PolicyDefinitionCreate

        with TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            service = AccountTransactionService(
                landing_root=temp_root / "landing",
                metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
            )
            config_repository = IngestionConfigRepository(temp_root / "config.db")
            # A legacy/seeded row referencing a publication that no longer
            # exists bypasses route-time validation; enabling it must fail.
            bad_rule = dict(_VALID_RULE, publication_key="retired_publication")
            config_repository.create_policy_definition(
                PolicyDefinitionCreate(
                    policy_id="legacy_bad_ref",
                    display_name="Legacy",
                    policy_kind="declarative_rule",
                    rule_schema_version="1.0",
                    rule_document=_json.dumps(bad_rule),
                    enabled=False,
                    source_kind="operator",
                )
            )
            app = create_app(
                service,
                config_repository=config_repository,
                enable_unsafe_admin=True,
            )
            client = TestClient(app)
            response = client.patch(
                "/control/policies/legacy_bad_ref", json={"enabled": True}
            )
            self.assertEqual(422, response.status_code)
            record = config_repository.get_policy_definition("legacy_bad_ref")
            self.assertFalse(record.enabled)


class PolicyReferenceablePublicationsTests(unittest.TestCase):
    """The authoring surface must only ever be offered usable publications."""

    def test_every_offered_key_is_accepted_by_create(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            listing = client.get("/control/policies/referenceable-publications")
            self.assertEqual(200, listing.status_code)
            publications = listing.json()["publications"]
            self.assertTrue(publications, "expected at least one referenceable publication")

            for publication in publications:
                rule = {
                    "rule_kind": "publication_freshness_comparison",
                    "publication_key": publication["publication_key"],
                    "operator": "gt",
                    "threshold_hours": 24.0,
                }
                response = client.post(
                    "/control/policies",
                    json={
                        "display_name": f"Freshness {publication['publication_key']}",
                        "policy_kind": "declarative_rule",
                        "rule_document": rule,
                    },
                )
                self.assertEqual(
                    201,
                    response.status_code,
                    f"offered key {publication['publication_key']!r} was rejected on create",
                )

    def test_offered_set_matches_what_evaluation_can_resolve(self) -> None:
        # The create-time allowlist and the evaluator's relation map are built
        # from one function, so a key an operator may reference is always a key
        # evaluation can turn into a relation. Without that, a policy would be
        # accepted at create and then evaluate unavailable forever.
        from packages.pipelines.composition.builtin_packs import (
            BUILTIN_CAPABILITY_PACKS,
        )
        from packages.pipelines.composition.publication_contract_inputs import (
            build_policy_referenceable_contracts,
        )

        contracts = build_policy_referenceable_contracts(BUILTIN_CAPABILITY_PACKS)
        self.assertTrue(contracts)
        relation_by_key = {
            contract.publication_key: contract.relation_name for contract in contracts
        }
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            offered = {
                publication["publication_key"]
                for publication in client.get(
                    "/control/policies/referenceable-publications"
                ).json()["publications"]
            }
        self.assertEqual(set(relation_by_key), offered)
        self.assertTrue(all(relation_by_key.values()))

    def test_dimension_contracts_are_not_offered(self) -> None:
        # /contracts/publications advertises current-dimension contracts that
        # policy evaluation cannot resolve; the authoring list must not.
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            offered = {
                publication["publication_key"]
                for publication in client.get(
                    "/control/policies/referenceable-publications"
                ).json()["publications"]
            }
            self.assertTrue(offered)
            self.assertEqual(
                set(),
                {key for key in offered if key.startswith("dim_")},
            )

    def test_decimal_columns_are_marked_comparable(self) -> None:
        # DECIMAL carries json_type "string"; the monetary rules compare it,
        # so comparability must not be keyed off json_type.
        from apps.api.routes.policy_routes import _is_comparable

        self.assertTrue(_is_comparable("DECIMAL(18, 2)"))
        self.assertTrue(_is_comparable("DECIMAL(18, 2) NOT NULL"))
        self.assertTrue(_is_comparable("INTEGER"))
        self.assertFalse(_is_comparable("VARCHAR(64)"))
        self.assertFalse(_is_comparable("DATE"))


class PolicyPreviewRouteTests(unittest.TestCase):
    """Preview validates like create but writes nothing."""

    def _client_with_evaluator(self, temp_dir: str, evaluator: object) -> TestClient:
        temp_root = Path(temp_dir)
        service = AccountTransactionService(
            landing_root=temp_root / "landing",
            metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
        )
        config_repository = IngestionConfigRepository(temp_root / "config.db")
        app = create_app(
            service,
            config_repository=config_repository,
            enable_unsafe_admin=True,
            ha_policy_evaluator=evaluator,
        )
        return TestClient(app)

    def test_preview_returns_verdict_and_reason(self) -> None:
        from packages.pipelines.ha_policy import HaPolicyEvaluator

        evaluator = HaPolicyEvaluator(
            lambda: {},
            publication_fetch_fn=lambda keys: {
                "publication_monthly_cashflow": [{"net": "-250"}]
            },
        )
        with TemporaryDirectory() as tmp:
            client = self._client_with_evaluator(tmp, evaluator)
            response = client.post(
                "/control/policies/preview", json={"rule_document": _VALID_RULE}
            )
            self.assertEqual(200, response.status_code)
            preview = response.json()["preview"]
            self.assertEqual("breach", preview["verdict"])
            self.assertTrue(preview["reason"])

    def test_preview_does_not_create_a_policy(self) -> None:
        from packages.pipelines.ha_policy import HaPolicyEvaluator

        evaluator = HaPolicyEvaluator(lambda: {}, publication_fetch_fn=lambda keys: {})
        with TemporaryDirectory() as tmp:
            client = self._client_with_evaluator(tmp, evaluator)
            client.post("/control/policies/preview", json={"rule_document": _VALID_RULE})
            listing = client.get("/control/policies")
            self.assertEqual([], listing.json()["policies"])

    def test_preview_rejects_invalid_rule_document(self) -> None:
        from packages.pipelines.ha_policy import HaPolicyEvaluator

        evaluator = HaPolicyEvaluator(lambda: {})
        with TemporaryDirectory() as tmp:
            client = self._client_with_evaluator(tmp, evaluator)
            response = client.post(
                "/control/policies/preview",
                json={"rule_document": {"rule_kind": "exec_python"}},
            )
            self.assertEqual(422, response.status_code)

    def test_preview_rejects_unknown_publication_reference(self) -> None:
        from packages.pipelines.ha_policy import HaPolicyEvaluator

        evaluator = HaPolicyEvaluator(lambda: {})
        unknown = dict(_VALID_RULE, publication_key="not_a_publication")
        with TemporaryDirectory() as tmp:
            client = self._client_with_evaluator(tmp, evaluator)
            response = client.post(
                "/control/policies/preview", json={"rule_document": unknown}
            )
            self.assertEqual(422, response.status_code)

    def test_preview_without_an_evaluator_is_explicitly_unavailable(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            response = client.post(
                "/control/policies/preview", json={"rule_document": _VALID_RULE}
            )
            self.assertEqual(503, response.status_code)


class ShippedPolicyTemplateTests(unittest.TestCase):
    """Every shipped template must be expressible against real publications.

    The templates live in the frontend, but whether they are honest is a
    backend fact: the publication must exist, the field must be numerically
    comparable, and a completed rule must be accepted while an incomplete one
    is refused. Parsed from the source so the two cannot drift.
    """

    _TEMPLATES_PATH = (
        Path(__file__).resolve().parents[1]
        / "apps"
        / "web"
        / "frontend"
        / "lib"
        / "policy-templates.js"
    )

    def _template_rules(self) -> list[dict[str, str]]:
        import re

        source = self._TEMPLATES_PATH.read_text()
        rules = []
        for block in re.findall(r"rule:\s*\{(.*?)\}", source, re.DOTALL):
            rule = dict(re.findall(r'(\w+):\s*"([^"]*)"', block))
            numeric = dict(re.findall(r"(\w+):\s*(-?\d+(?:\.\d+)?)\s*[,\n]", block))
            rule.update(numeric)
            rules.append(rule)
        return rules

    def test_templates_are_parsed(self) -> None:
        rules = self._template_rules()
        self.assertEqual(3, len(rules), f"expected three shipped templates, got {rules}")

    def test_value_template_fields_exist_and_are_comparable(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            publications = {
                publication["publication_key"]: publication
                for publication in client.get(
                    "/control/policies/referenceable-publications"
                ).json()["publications"]
            }

        for rule in self._template_rules():
            if rule.get("rule_kind") != "publication_value_comparison":
                continue
            publication = publications.get(rule["publication_key"])
            self.assertIsNotNone(
                publication,
                f"template reads unknown publication {rule['publication_key']!r}",
            )
            column = next(
                (
                    candidate
                    for candidate in publication["columns"]
                    if candidate["name"] == rule["field_name"]
                ),
                None,
            )
            self.assertIsNotNone(
                column,
                f"{rule['publication_key']} has no field {rule['field_name']!r}",
            )
            self.assertTrue(
                column["comparable"],
                f"{rule['field_name']} is not numerically comparable, so a value "
                "rule against it would always evaluate unavailable",
            )

    def test_completed_templates_are_accepted(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            for rule in self._template_rules():
                completed = dict(rule)
                # Stand in for the inputs the operator must supply.
                if completed.get("rule_kind") == "publication_value_comparison":
                    completed.setdefault("threshold", 0)
                    completed["threshold"] = float(completed["threshold"])
                if completed.get("rule_kind") == "publication_freshness_comparison":
                    completed.setdefault("publication_key", "household_overview")
                    completed["threshold_hours"] = 48.0
                response = client.post(
                    "/control/policies",
                    json={
                        "display_name": f"Template {completed.get('field_name', '')}",
                        "policy_kind": "declarative_rule",
                        "rule_document": completed,
                    },
                )
                self.assertEqual(
                    201,
                    response.status_code,
                    f"template rule {completed} was rejected: {response.text}",
                )

    def test_incomplete_templates_are_refused(self) -> None:
        # A template missing a required input must not be creatable, which is
        # what makes "cannot be enabled until configured" true at the API and
        # not only in the form.
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            for rule in self._template_rules():
                if rule.get("rule_kind") == "publication_value_comparison":
                    incomplete = {k: v for k, v in rule.items() if k != "threshold"}
                elif rule.get("rule_kind") == "publication_freshness_comparison":
                    incomplete = dict(rule)
                else:
                    continue
                response = client.post(
                    "/control/policies",
                    json={
                        "display_name": "Incomplete",
                        "policy_kind": "declarative_rule",
                        "rule_document": incomplete,
                    },
                )
                self.assertEqual(
                    422,
                    response.status_code,
                    f"incomplete template rule {incomplete} was accepted",
                )
