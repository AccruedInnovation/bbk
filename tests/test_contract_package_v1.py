from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

if os.environ.get('BBK_EXTERNAL_SCHEMA', '1') == '0':
    jsonschema = None  # type: ignore[assignment]
else:
    try:  # Optional runtime capability; ordinary BBK tests remain self-contained.
        import jsonschema  # type: ignore  # noqa: E402
    except ImportError:  # pragma: no cover - exercised through the -S subprocess regression
        jsonschema = None  # type: ignore[assignment]

from generate_agents import instruction_text  # noqa: E402
from return_contracts import (  # noqa: E402
    COMMON_FIELDS,
    FIELD_KINDS,
    LEGACY_ONLY,
    OPERATIONAL_DISPOSITIONS,
    check_or_write,
    expected_outputs,
    field_schema,
    load_package,
    modes_for,
    render_return_contract_prompt,
    validate_document,
)
from validate_contract_package import (  # noqa: E402
    EXPECTED_CAPABILITIES,
    EXPECTED_PROHIBITED_CHANGES,
    EXPECTED_STATUS_VOCABULARY,
    BOUNDARY_TEMPLATE,
    ENVELOPE_TEMPLATE,
    PERMIT_TEMPLATE,
    POLICY,
    field_example,
    representative_role_return,
    representative_role_return_v2,
    schema_registry,
    validate_boundary,
    validate_local_discovery,
    validate_package,
)


class ContractPackageV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog, cls.roles, cls.entries = load_package(ROOT)
        cls.by_name = {role["name"]: role for role in cls.roles}
        cls.spec = json.loads((ROOT / "spec" / "roles.json").read_text(encoding="utf-8"))
        cls.contract_catalog = json.loads(
            (ROOT / "spec" / "contracts" / "catalog.json").read_text(encoding="utf-8")
        )
        cls.capability = json.loads(
            (ROOT / "spec" / "capability-status.json").read_text(encoding="utf-8")
        )
        cls.policy = json.loads((ROOT / POLICY).read_text(encoding="utf-8"))
        cls.boundary = json.loads((ROOT / BOUNDARY_TEMPLATE).read_text(encoding="utf-8"))
        cls.envelope = json.loads((ROOT / ENVELOPE_TEMPLATE).read_text(encoding="utf-8"))
        cls.permit = json.loads((ROOT / PERMIT_TEMPLATE).read_text(encoding="utf-8"))
        if jsonschema is None:
            cls.jsonschema_module, cls.registry, cls.schemas = None, None, []
        else:
            cls.jsonschema_module, cls.registry, cls.schemas = schema_registry(ROOT)

    def _representative(self, role_name: str) -> dict:
        return representative_role_return(
            self.by_name[role_name], self.entries[role_name]
        )

    def _assert_invalid_return(self, role_name: str, mutate) -> None:
        if jsonschema is None:
            self.skipTest("optional jsonschema/referencing capability is unavailable")
        document = self._representative(role_name)
        mutate(document)
        with self.assertRaises(jsonschema.ValidationError):
            validate_document(document, role_name, ROOT)

    def test_all_nineteen_roles_have_one_normalized_contract(self) -> None:
        expected_keys = {
            "contract_id", "envelope_schema", "return_schema", "result_schema",
            "v2_contract_id", "v2_envelope_schema", "v2_return_schema",
            "compact_result_schema", "compact_result_fields", "full_detail_triggers",
            "semantic_state_name", "allowed_invocation_modes",
            "allowed_return_kinds", "allowed_operational_dispositions",
            "allowed_semantic_states", "supplemental_enums", "result_fields",
            "requirements", "readiness_rule", "authority_boundary",
        }
        self.assertEqual(len(self.roles), 19)
        contract_ids = set()
        schema_paths = set()
        for role in self.roles:
            with self.subTest(role=role["name"]):
                contract = role["return_contract"]
                self.assertEqual(set(contract), expected_keys)
                self.assertEqual(
                    contract["allowed_operational_dispositions"],
                    OPERATIONAL_DISPOSITIONS,
                )
                self.assertFalse(set(contract["allowed_operational_dispositions"]) & LEGACY_ONLY)
                self.assertEqual(
                    contract["allowed_invocation_modes"],
                    modes_for(self.entries[role["name"]]),
                )
                self.assertTrue(set(contract["result_fields"]).isdisjoint(COMMON_FIELDS))
                contract_ids.add(contract["contract_id"])
                self.assertEqual(contract["v2_contract_id"], contract["contract_id"].removesuffix(".v1") + ".v2")
                self.assertTrue(set(contract["compact_result_fields"]) <= set(contract["result_fields"]))
                self.assertTrue(contract["full_detail_triggers"])
                schema_paths.update([
                    contract["return_schema"], contract["result_schema"],
                    contract["v2_return_schema"], contract["compact_result_schema"],
                ])
        self.assertEqual(len(contract_ids), 19)
        self.assertEqual(len(schema_paths), 76)

    def test_role_field_kind_vocabulary_is_consistent_across_generator_schema_and_assembler(self) -> None:
        role_schema = json.loads(
            (ROOT / "spec" / "schemas" / "bbk-role-v4.schema.json").read_text(encoding="utf-8")
        )
        schema_kinds = set(role_schema["$defs"]["resultField"]["properties"]["kind"]["enum"])
        self.assertEqual(schema_kinds, FIELD_KINDS)
        assembler = (ROOT / "tools" / "assemble_roles.py").read_text(encoding="utf-8")
        for kind in sorted(FIELD_KINDS):
            self.assertIn(f'"{kind}"', assembler)

    @unittest.skipUnless(jsonschema is not None, "optional jsonschema/referencing capability is unavailable")
    def test_declared_nullability_matches_role_contract_prose_and_schema(self) -> None:
        for role in self.roles:
            role_name = role["name"]
            for field_name, field in role["return_contract"]["result_fields"].items():
                with self.subTest(role=role_name, field=field_name):
                    description_mentions_null = "null" in field["description"].lower().split()
                    if description_mentions_null:
                        self.assertTrue(field["nullable"])
                    schema = field_schema(field)
                    validator = jsonschema.Draft202012Validator(schema, registry=self.registry)
                    if field["nullable"]:
                        validator.validate(None)
                    else:
                        with self.assertRaises(jsonschema.ValidationError):
                            validator.validate(None)

    def test_generated_return_and_result_schemas_are_deterministic_and_current(self) -> None:
        catalog, roles, outputs = expected_outputs(ROOT)
        self.assertEqual(catalog["package_version"], (ROOT / "VERSION").read_text(encoding="utf-8").strip())
        self.assertEqual(len(roles), 19)
        self.assertEqual(len(outputs), 79)
        self.assertEqual(check_or_write(ROOT, write=False), [])
        for path, expected in outputs.items():
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                self.assertEqual(path.read_bytes(), expected)

    def test_registry_binds_all_role_sources_and_generated_schemas(self) -> None:
        import hashlib

        registries = [
            ("role-return-registry.json", "bbk.role-return-registry.v1", ("source", "return_schema", "result_schema")),
            ("role-return-registry-v2.json", "bbk.role-return-registry.v2", ("source", "return_schema", "compact_result_schema", "full_result_schema")),
        ]
        for filename, schema, record_keys in registries:
            with self.subTest(registry=filename):
                registry = json.loads((ROOT / "spec" / "contracts" / filename).read_text(encoding="utf-8"))
                self.assertEqual(registry["schema"], schema)
                self.assertEqual(registry["role_count"], 19)
                self.assertEqual(registry["operational_dispositions"], OPERATIONAL_DISPOSITIONS)
                self.assertEqual({entry["role"] for entry in registry["entries"]}, set(self.by_name))
                if schema.endswith(".v2"):
                    self.assertEqual(registry["default_detail_level"], "COMPACT")
                    self.assertEqual(registry["allowed_detail_levels"], ["COMPACT", "FULL"])
                for entry in registry["entries"]:
                    for key in record_keys:
                        record = entry[key]
                        payload = (ROOT / record["path"]).read_bytes()
                        self.assertEqual(record["bytes"], len(payload))
                        self.assertEqual(record["sha256"], hashlib.sha256(payload).hexdigest())

    @unittest.skipUnless(jsonschema is not None, "optional jsonschema/referencing capability is unavailable")
    def test_representative_return_for_every_role_validates(self) -> None:
        for role in self.roles:
            entry = self.entries[role["name"]]
            documents = [
                self._representative(role["name"]),
                representative_role_return_v2(role, entry, detail_level="COMPACT"),
                representative_role_return_v2(role, entry, detail_level="FULL"),
            ]
            for document in documents:
                with self.subTest(role=role["name"], schema=document["schema"], detail=document.get("detail_level")):
                    validate_document(document, role["name"], ROOT)

    @unittest.skipUnless(jsonschema is not None, "optional jsonschema/referencing capability is unavailable")
    def test_exact_role_contract_discriminators_reject_drift_for_every_role(self) -> None:
        mutations = {
            "contract": lambda d: d.__setitem__("contract", "bbk.wrong-return.v1"),
            "role": lambda d: d.__setitem__("role", "bbk_wrong"),
            "invocation_mode": lambda d: d.__setitem__("invocation_mode", "WRONG_MODE"),
            "return_kind": lambda d: d.__setitem__("return_kind", "WRONG_KIND"),
            "operational_disposition": lambda d: d.__setitem__("operational_disposition", "READY_FOR_VALIDATION"),
            "semantic_state_name": lambda d: d["semantic_state"].__setitem__("name", "wrong_state"),
            "semantic_state_value": lambda d: d["semantic_state"].__setitem__("value", "WRONG_STATE"),
            "parent": lambda d: (d["parent_ref"].__setitem__("id", "wrong_parent"), d["parent_ref"].__setitem__("role", "bbk_wrong") if d["parent_ref"]["kind"] == "canonical_role" else None),
        }
        for role in self.roles:
            for name, mutate in mutations.items():
                with self.subTest(role=role["name"], mutation=name):
                    self._assert_invalid_return(role["name"], mutate)

    @unittest.skipUnless(jsonschema is not None, "optional jsonschema/referencing capability is unavailable")
    def test_result_payload_is_closed_and_every_declared_field_is_required(self) -> None:
        for role in self.roles:
            role_name = role["name"]
            first_field = next(iter(role["return_contract"]["result_fields"]))
            with self.subTest(role=role_name, case="missing"):
                self._assert_invalid_return(
                    role_name, lambda d, field=first_field: d["result"].pop(field)
                )
            with self.subTest(role=role_name, case="extra"):
                self._assert_invalid_return(
                    role_name, lambda d: d["result"].__setitem__("undeclared_field", True)
                )

    @unittest.skipUnless(jsonschema is not None, "optional jsonschema/referencing capability is unavailable")
    def test_supplemental_enum_fields_are_exact_machine_discriminators(self) -> None:
        expected_roles = {
            "bbk_question_guide", "bbk_reviewer", "bbk_validator",
            "bbk_prototyper", "bbk_validator_orchestrator",
        }
        self.assertTrue(expected_roles <= set(self.by_name))
        for role_name in sorted(expected_roles):
            role = self.by_name[role_name]
            enum_fields = {
                name: field
                for name, field in role["return_contract"]["result_fields"].items()
                if field["kind"] in {"ENUM", "ENUM_LIST"}
            }
            self.assertTrue(enum_fields, role_name)
            for field_name, field in enum_fields.items():
                with self.subTest(role=role_name, field=field_name):
                    value = ["NOT_A_DECLARED_VALUE"] if field["kind"] == "ENUM_LIST" else "NOT_A_DECLARED_VALUE"
                    self._assert_invalid_return(
                        role_name,
                        lambda d, field_name=field_name, value=value: d["result"].__setitem__(field_name, value),
                    )

    @unittest.skipUnless(jsonschema is not None, "optional jsonschema/referencing capability is unavailable")
    def test_all_supported_field_kinds_have_schema_valid_examples(self) -> None:
        self.assertEqual(
            FIELD_KINDS,
            {
                "STRING", "STRING_LIST", "BOOLEAN", "INTEGER", "NUMBER",
                "REFERENCE", "REFERENCE_LIST", "ARTIFACT_REFERENCE",
                "ARTIFACT_REFERENCE_LIST", "STRUCTURED", "STRUCTURED_LIST",
                "ENUM", "ENUM_LIST",
            },
        )
        for kind in sorted(FIELD_KINDS):
            field = {"kind": kind, "nullable": False, "description": "example"}
            if kind in {"ENUM", "ENUM_LIST"}:
                field["enum_values"] = ["A", "B"]
            sample = field_example(field)
            with self.subTest(kind=kind):
                jsonschema.Draft202012Validator(
                    field_schema(field), registry=self.registry
                ).validate(sample)

    def test_prompt_renderer_projects_the_exact_contract(self) -> None:
        role = self.by_name["bbk_worker"]
        rendered = render_return_contract_prompt(role)
        contract = role["return_contract"]
        self.assertIn(contract["v2_contract_id"], rendered)
        self.assertIn(contract["v2_return_schema"], rendered)
        self.assertIn(contract["compact_result_schema"], rendered)
        self.assertIn(contract["result_schema"], rendered)
        self.assertIn(contract["return_schema"], rendered)
        self.assertIn("`CANDIDATE_PRODUCTION`", rendered)
        self.assertIn("`PROTOTYPE_SUPPORT`", rendered)
        for field_name in contract["compact_result_fields"]:
            self.assertIn(f"`{field_name}`", rendered)
        self.assertIn("v1 remains consume-compatible", rendered)
        self.assertIn("COMPACT", rendered)
        self.assertIn("FULL", rendered)

    def test_generic_and_omp_prompt_sources_use_the_correct_projection_strategy(self) -> None:
        role = copy.deepcopy(next(item for item in self.spec["roles"] if item["name"] == "bbk_worker"))
        # The compiled-procedure contract is now a release gate. Keep the
        # canonical mandatory set while exercising the host-specific return-
        # contract projection branch.
        generic = instruction_text(self.spec, role, host="generic")
        omp = instruction_text(self.spec, role, host="omp")
        self.assertIn("## Exact role-return contract", generic)
        self.assertIn("bbk.worker-return.v2", generic)
        self.assertIn("COMPACT", generic)
        self.assertIn("## Exact role-return contract", omp)
        self.assertIn("bbk.worker-return.v2", omp)
        self.assertIn("COMPACT", omp)

    def test_host_adapter_and_manifest_sources_are_contract_aware(self) -> None:
        omp = (ROOT / "omp" / "extension" / "index.js").read_text(encoding="utf-8")
        generator = (ROOT / "tools" / "generate_agents.py").read_text(encoding="utf-8")
        installer = (ROOT / "tools" / "install.py").read_text(encoding="utf-8")
        self.assertIn("bbk.roles.v4", omp)
        self.assertIn("exactRoleReturnContractBlock", omp)
        self.assertIn("ROLE_RETURN_FIELD_KINDS", omp)
        self.assertIn("return invocation modes do not match the catalogue", omp)
        self.assertIn("describes null but rejects it", omp)
        self.assertIn("contract_package", omp)
        self.assertIn("BBK_ALLOW_STAGED_ROLE_PACKAGE", omp)
        self.assertIn('"return_contract": role.get("return_contract", {})', generator)
        self.assertIn('"role_return_registry": "spec/contracts/role-return-registry.json"', generator)
        self.assertIn('"role_return_registry_v2": "spec/contracts/role-return-registry-v2.json"', generator)
        self.assertIn('"default_role_return_version": "v2"', generator)
        self.assertIn("return_contract", installer)
        self.assertIn("role_return_registry", installer)

    def test_contract_catalog_declares_exact_execution_contract_set_and_owners(self) -> None:
        records = {item["contract_id"]: item for item in self.contract_catalog["execution_contracts"]}
        self.assertEqual(
            set(records),
            {
                "bbk.territory-execution-boundary.v1",
                "bbk.local-discovery-policy.v1",
                "bbk.local-discovery-envelope.v1",
                "bbk.local-discovery-permit.v1",
                "bbk.assurance-mode.v1",
            },
        )
        self.assertEqual(records["bbk.territory-execution-boundary.v1"]["lifecycle_owner"], "bbk_root_orchestrator")
        for contract_id in (
            "bbk.local-discovery-policy.v1",
            "bbk.local-discovery-envelope.v1",
            "bbk.local-discovery-permit.v1",
        ):
            self.assertEqual(records[contract_id]["lifecycle_owner"], "bbk_territory_orchestrator")
        self.assertEqual(records["bbk.assurance-mode.v1"]["lifecycle_owner"], "bbk_planning_wayfinder")

    @unittest.skipUnless(jsonschema is not None, "optional jsonschema/referencing capability is unavailable")
    def test_execution_contract_examples_validate_against_published_schemas(self) -> None:
        pairs = [
            ("templates/contracts/territory-execution-boundary.json", "spec/schemas/bbk-territory-execution-boundary-v1.schema.json"),
            ("spec/policies/local-discovery-v1.json", "spec/schemas/bbk-local-discovery-policy-v1.schema.json"),
            ("templates/contracts/local-discovery-envelope.json", "spec/schemas/bbk-local-discovery-envelope-v1.schema.json"),
            ("templates/contracts/local-discovery-permit.json", "spec/schemas/bbk-local-discovery-permit-v1.schema.json"),
            ("templates/contracts/assurance-mode.json", "spec/schemas/bbk-assurance-mode-v1.schema.json"),
        ]
        for instance_path, schema_path in pairs:
            with self.subTest(instance=instance_path):
                instance = json.loads((ROOT / instance_path).read_text(encoding="utf-8"))
                schema = json.loads((ROOT / schema_path).read_text(encoding="utf-8"))
                jsonschema.Draft202012Validator(
                    schema, registry=self.registry, format_checker=jsonschema.FormatChecker()
                ).validate(instance)

    def test_territory_execution_boundary_owners_immutability_and_successor_rule_are_exact(self) -> None:
        errors: list[str] = []
        validate_boundary(self.boundary, errors)
        self.assertEqual(errors, [])
        changed = copy.deepcopy(self.boundary)
        changed["admission"]["compiled_by_role"] = "bbk_territory_orchestrator"
        changed["immutability"]["successor_required_for_change"] = False
        changed["completion_contract"]["completion_owner_role"] = "bbk_root_orchestrator"
        errors = []
        validate_boundary(changed, errors)
        text = "\n".join(errors)
        self.assertIn("Root Orchestrator must compile", text)
        self.assertIn("require a successor", text)
        self.assertIn("Territory Orchestrator must own boundary completion", text)

    def test_local_discovery_defaults_to_zero_and_has_one_exact_issuer(self) -> None:
        self.assertEqual(self.policy["default_allowance"], "ZERO_WITHOUT_ACTIVE_ENVELOPE_AND_PERMIT")
        self.assertEqual(self.policy["issuer_role"], "bbk_territory_orchestrator")
        self.assertEqual(self.policy["proposer_roles"], ["bbk_worker_orchestrator", "bbk_worker"])
        self.assertEqual(self.envelope["issued_by"]["role"], "bbk_territory_orchestrator")
        self.assertEqual(self.permit["issued_by"]["role"], "bbk_territory_orchestrator")
        self.assertEqual(self.permit["budget_charge"]["item_units"], 1)

    def test_local_discovery_budget_units_and_floor_arithmetic_are_exact(self) -> None:
        budget = self.policy["budget"]
        self.assertEqual(budget["item_unit"], "DISCOVERY_ITEM")
        self.assertEqual(budget["max_items_per_envelope"], 2)
        self.assertEqual(budget["effort_unit"], "PLANNED_EFFORT_UNIT")
        self.assertEqual(budget["effort_unit_semantics"], "COHORT_CHARTER_RELATIVE_NONNEGATIVE_INTEGER")
        self.assertEqual(budget["denominator_source"], "COMPILED_COHORT_CHARTER")
        self.assertEqual(budget["denominator_binding"], "EXACT_COHORT_ID_REVISION_SHA256_AND_DECLARED_TOTAL")
        self.assertEqual(budget["max_effort_basis_points"], 1000)
        self.assertEqual(budget["rounding"], "FLOOR")
        self.assertEqual(budget["missing_denominator_allowance"], 0)
        envelope_budget = self.envelope["budget"]
        self.assertEqual(envelope_budget["denominator_source"], "COMPILED_COHORT_CHARTER")
        self.assertEqual(envelope_budget["denominator_ref"], self.envelope["cohort_ref"])
        self.assertRegex(self.envelope["cohort_ref"]["digest"], r"^[0-9a-f]{64}$")
        expected = envelope_budget["planned_effort_units"] * envelope_budget["effort_limit_basis_points"] // 10000
        self.assertEqual(envelope_budget["effort_limit_units"], expected)

    def test_local_discovery_lifecycle_companions_and_policy_triggers_are_exact(self) -> None:
        self.assertEqual(
            self.envelope["invalidation_triggers"],
            self.policy["expiry_and_revocation"]["automatic_invalidation_triggers"],
        )
        cases = []
        revoked_envelope = copy.deepcopy(self.envelope)
        revoked_envelope["lifecycle_state"] = "REVOKED"
        revoked_envelope["revoked_at"] = None
        cases.append((revoked_envelope, self.permit, "revoked envelope requires revoked_at"))
        superseded_permit = copy.deepcopy(self.permit)
        superseded_permit["lifecycle_state"] = "SUPERSEDED"
        superseded_permit["superseded_by_ref"] = None
        cases.append((self.envelope, superseded_permit, "superseded permit requires successor reference"))
        exhausted_envelope = copy.deepcopy(self.envelope)
        exhausted_envelope["lifecycle_state"] = "EXHAUSTED"
        cases.append((exhausted_envelope, self.permit, "exhausted envelope must have no remaining"))
        for envelope, permit, expected in cases:
            with self.subTest(expected=expected):
                errors = []
                validate_local_discovery(self.policy, envelope, permit, self.boundary, errors)
                self.assertIn(expected, "\n".join(errors))

    def test_local_discovery_cross_object_validation_rejects_budget_issuer_and_governance_drift(self) -> None:
        envelope = copy.deepcopy(self.envelope)
        permit = copy.deepcopy(self.permit)
        envelope["budget"]["effort_limit_units"] += 1
        envelope["budget"]["denominator_ref"]["digest"] = "8" * 64
        envelope["issued_by"]["role"] = "bbk_worker_orchestrator"
        permit["governance_impact"][next(iter(permit["governance_impact"]))] = True
        errors: list[str] = []
        validate_local_discovery(self.policy, envelope, permit, self.boundary, errors)
        text = "\n".join(errors)
        self.assertIn("must issue the envelope", text)
        self.assertIn("does not use FLOOR", text)
        self.assertIn("denominator reference must exactly equal", text)
        self.assertIn("may not change a prohibited governance dimension", text)

    def test_post_freeze_discovery_requires_successor_candidate_and_cohort_or_recharter(self) -> None:
        permit = copy.deepcopy(self.permit)
        impact = permit["candidate_and_validation_impact"]
        impact["candidate_state"] = "FROZEN_CANDIDATE"
        impact["requires_successor_candidate"] = False
        impact["requires_successor_cohort_or_parent_recharter"] = False
        errors: list[str] = []
        validate_local_discovery(self.policy, self.envelope, permit, self.boundary, errors)
        text = "\n".join(errors)
        self.assertIn("post-freeze permit must require successor candidate", text)
        self.assertIn("successor cohort or recharter", text)

    def test_local_discovery_prohibited_governance_set_is_complete_and_identical(self) -> None:
        self.assertEqual(self.policy["scope"]["prohibited_changes"], EXPECTED_PROHIBITED_CHANGES)
        self.assertEqual(self.envelope["prohibited_changes"], EXPECTED_PROHIBITED_CHANGES)
        expected_permit_fields = {f"changes_{item.lower()}" for item in EXPECTED_PROHIBITED_CHANGES}
        self.assertEqual(set(self.permit["governance_impact"]), expected_permit_fields)
        self.assertTrue(all(value is False for value in self.permit["governance_impact"].values()))

    def test_worker_validation_batch_is_retired_and_replaced_by_separate_lifecycles(self) -> None:
        records = {item["capability_id"]: item for item in self.capability["entries"]}
        retired = records["WorkerValidationBatch"]
        self.assertEqual(retired["status"], "RETIRED_NOT_IMPLEMENTED")
        self.assertEqual(retired["owner_roles"], [])
        self.assertEqual(retired["consumer_roles"], [])
        self.assertEqual(
            retired["replacement_refs"],
            ["candidate-producing Worker cohort", "immutable candidate identity", "candidate-assurance run"],
        )
        active_paths = [
            ROOT / "spec" / "method-content.json",
            ROOT / "spec" / "contracts" / "catalog.json",
            ROOT / "spec" / "policies" / "local-discovery-v1.json",
            *sorted((ROOT / "spec" / "roles").glob("bbk_*-role.json")),
        ]
        for path in active_paths:
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                self.assertNotIn("WorkerValidationBatch", path.read_text(encoding="utf-8"))

    def test_capability_inventory_is_complete_and_uses_declared_status_vocabulary(self) -> None:
        self.assertEqual(self.capability["status_vocabulary"], EXPECTED_STATUS_VOCABULARY)
        records = {item["capability_id"]: item for item in self.capability["entries"]}
        self.assertEqual(set(records), EXPECTED_CAPABILITIES)
        for record in records.values():
            self.assertIn(record["status"], EXPECTED_STATUS_VOCABULARY)
            self.assertTrue(record["source_refs"])
            self.assertTrue(record["enforcement"].strip())
            self.assertTrue(record["limitations"])

    def test_canonical_procedures_reference_formal_execution_objects_and_separate_assurance_runs(self) -> None:
        method = json.loads((ROOT / "spec" / "method-content.json").read_text(encoding="utf-8"))
        body = "\n".join(method["skills"].values())
        for token in (
            "TerritoryExecutionBoundary",
            "bbk.local-discovery-envelope.v1",
            "bbk.local-discovery-permit.v1",
            "candidate-assurance run",
            "successor candidate",
        ):
            self.assertIn(token, body)
        self.assertNotIn("WorkerValidationBatch", body)

    def test_gate3_contract_validator_reports_no_source_errors(self) -> None:
        self.assertEqual(validate_package(ROOT), [])

    def test_targeted_contract_commands_pass_without_generating_release_artifacts(self) -> None:
        commands = [
            [sys.executable, "-S", "tools/return_contracts.py", "--check"],
            [sys.executable, "-S", "tools/assemble_roles.py", "--check"],
            [sys.executable, "-S", "tools/validate_contract_package.py", "--check"],
        ]
        for command in commands:
            with self.subTest(command=" ".join(command)):
                completed = subprocess.run(
                    command, cwd=ROOT, check=False, text=True, encoding="utf-8",
                    errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=60,
                )
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

        required = subprocess.run(
            [sys.executable, "-S", "tools/validate_contract_package.py", "--check", "--require-jsonschema"],
            cwd=ROOT, check=False, text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
            env={**os.environ, "PYTHONPATH": "", "BBK_QUALIFIED_PYTHONPATH": "", "PYTHONNOUSERSITE": "1"},
        )
        self.assertNotEqual(required.returncode, 0)
        self.assertIn("jsonschema and referencing are required", required.stdout + required.stderr)


if __name__ == "__main__":
    unittest.main()

# Deterministic fast/standard/release selection used by tools/run_tests.py.
from tests._test_profiles import load_profiled_tests as load_tests
