from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from assemble_roles import RolePackageError, assemble, canonical_bytes  # noqa: E402
from create_method_content import expected as expected_method_assets  # noqa: E402
from generate_agents import expected_files, instruction_text  # noqa: E402
from prompt_modules import (  # noqa: E402
    PromptModuleError,
    compact_skill_template,
    expand_skill_template,
    load_prompt_modules,
    mandatory_procedure_exception_measurement,
    module_directives,
    role_skill_module_requirements,
    source_manifest,
    validate_skill_templates,
)


EXCLUSIVE_MODULE_ROLES = {
    "bbk-prompt-human-request": {
        "bbk_root_wayfinder", "bbk_questioning_wayfinder", "bbk_question_guide",
    },
    "bbk-prompt-handoff-protocol": {
        "bbk_architect", "bbk_phase_wayfinder", "bbk_planning_wayfinder",
        "bbk_prototyper", "bbk_reviewer", "bbk_root_orchestrator",
        "bbk_synthesizer", "bbk_territory_orchestrator", "bbk_validator",
        "bbk_validator_orchestrator", "bbk_verification_designer", "bbk_worker",
        "bbk_worker_designer", "bbk_worker_orchestrator",
    },
    "bbk-prompt-execution-slicing": {
        "bbk_planning_wayfinder", "bbk_phase_wayfinder",
    },
    "bbk-prompt-profile-dispatch": {"bbk_worker_designer"},
    "bbk-prompt-evidence-receipts": {
        "bbk_reviewer", "bbk_validator", "bbk_validator_orchestrator",
        "bbk_verification_designer",
    },
    "bbk-prompt-finding-lifecycle": {
        "bbk_reviewer", "bbk_validator", "bbk_validator_orchestrator",
        "bbk_verification_designer",
    },
}



ROLE_SPECIFIC_PROTOCOL_FRAGMENTS = {
    "bbk_phase_wayfinder": (
        "ACCEPTED", "DELEGATED", "CONSTRAINT_DRIVEN", "PROPOSED",
        "ASSUMED", "STALE", "CONTRADICTORY", "MISSING",
    ),
    "bbk_synthesizer": (
        "source ID and type", "canonical owner", "provenance and derivation chain",
        "ACTIVE_CONTROLLING", "INCLUDED_SUPPORTING",
        "DERIVATIVE_COPY_OR_PROJECTION", "SUPERSEDED_HISTORY",
        "REJECTED_ALTERNATIVE", "DISSENT", "OPEN_FINDING",
        "STALE_OR_INVALIDATED", "UNRESOLVED_CONFLICT", "OUT_OF_SCOPE",
        "UNAVAILABLE", "OMITTED_BY_CHARTER",
        "synthesis statement → source statement or derivation record",
        "declared source → represented location or explicit disposition",
    ),
    "bbk_verification_designer": (
        "ACCEPTED_REQUIREMENT_OR_DECISION", "PROTECTED_FLOOR",
        "CONSTRAINT_DRIVEN_OBLIGATION", "DERIVED_VERIFICATION_OBLIGATION",
        "DELEGATED_ASSURANCE_FREEDOM", "PROPOSAL_REQUIRING_APPROVAL",
        "IMPLEMENTATION_OR_OPERATIONAL_OBSERVATION", "ASSUMPTION_OR_UNKNOWN",
        "REJECTED_OR_SUPERSEDED", "UNRESOLVED_CONFLICT",
        "ROUTINE", "MATERIAL", "CONSEQUENTIAL", "CRITICAL",
        "EvidenceReceipt", "AssertionEvaluation", "Aggregate or gate disposition",
        "HIDDEN", "TARGETED", "FULL", "NOT_APPLICABLE",
    ),
    "bbk_worker_designer": (
        "hard bbk_worker role maximum", "∩ canonical or qualified definition defaults",
        "= effective invocation grant", "Worker focused check",
        "≠ independent review", "≠ candidate-bound validation",
        "≠ operational validation", "≠ risk acceptance or release",
    ),
    "bbk_reviewer": (
        "EXPLORATORY", "ALTERNATIVE", "REPLICATION", "ROBUSTNESS",
        "TARGETED_CLOSURE", "ADJUDICATION", "CONFIRMATORY",
        "HIDDEN", "TARGETED", "FULL", "NOT_APPLICABLE",
    ),
    "bbk_root_orchestrator": (
        "physical root attempt", "host job or session", "territory semantic run",
        "territory physical attempt", "root role maximum",
        "= effective child grant", "candidate created", "quality gate passed",
        "assertion evaluated", "finding dispositioned", "territory completed",
        "completion report ready", "operational outcome observed",
        "outcome accepted", "release authorized", "EXPECTED_SILENCE",
        "FAILED_ATTEMPT", "→ probe", "→ contain", "→ classify",
        "→ reconcile", "Did the authorized implementation campaign finish",
        "Did the exact candidates and integrations satisfy",
        "Did the user's operational outcome improve",
    ),
    "bbk_territory_orchestrator": (
        "root physical attempt", "territory physical attempt",
        "Worker Orchestrator semantic run and attempt",
        "Validator Orchestrator semantic run and attempt", "Reviewer run",
        "Worker or Validator leaf session", "candidate and successor candidate",
        "child role maximum", "∩ worker or validator cohort contract",
        "∩ local-discovery permit where applicable", "= effective child grant",
        "EXPECTED_SILENCE",
    ),
    "bbk_worker_orchestrator": (
        "bbk manifest create", "bbk manifest compare", "bbk candidate freeze",
        "bbk candidate check", "bbk candidate status", "bbk candidate verify",
        "universal BBK integrity obligations",
        "+ repository quality profile", "+ WorkUnit and interface obligations",
        "+ active verification and gate policy",
    ),
    "bbk_validator_orchestrator": (
        "CURRENT_ACCEPTED_OR_AUTHORIZED", "CURRENT_NONAUTHORITATIVE",
        "PROPOSED", "STALE", "SUPERSEDED", "CONTRADICTORY",
        "UNAVAILABLE", "UNQUALIFIED", "UNTRUSTED", "NOT_APPLICABLE",
        "∩ assurance-run or execution authorization",
        "= effective evaluator envelope", "EXPLORATORY", "ALTERNATIVE",
        "REPLICATION", "ROBUSTNESS", "TARGETED_CLOSURE", "ADJUDICATION",
        "CONFIRMATORY", "replacement invocation", "CandidateProducingCohort",
        "CandidateAssuranceRun", "FindingDisposition", "ReviewAggregate",
        "+ successor manifest", "+ applicable prerequisite worker-quality attestation",
        "+ successor ReviewRun", "CANDIDATE_OR_CONTEXT_INTEGRITY_FAILURE",
    ),
    "bbk_worker": (
        "hard bbk_worker maximum", "∩ accepted execution or experiment authority",
        "∩ parent Territory boundary or experiment charter",
        "∩ current Worker invocation contract",
        "∩ workspace and mutation ownership",
        "Worker focused check and self-review",
        "independent Reviewer judgment", "accountable acceptance or release",
    ),
    "bbk_validator": (
        "CANDIDATE_OR_CONTRACT_DEFECT", "EVIDENCE_DEFECT", "CONTEXT_DEFECT",
        "TOOL_PROFILE_OR_ADAPTER_FAILURE",
        "ENVIRONMENT_CONSUMER_DEVICE_OR_FACILITY_FAILURE",
        "EVALUATOR_OR_RESULT_FAILURE",
        "AUTHORITY_OR_GOVERNING_DECISION_BLOCKER",
        "IDENTITY_OR_INTEGRITY_FAILURE", "CAPACITY_OR_HOST_WINDOW_PAUSE",
        "TRANSPORT_FAILURE", "Remediation proposal", "Authorized repair",
        "bbk.evidence-receipt.v2", "bbk.review-finding.v1",
    ),
}


GATE5_PRODUCT_NEUTRAL_SUBSTITUTIONS = {
    ("bbk-root-execution", "### Current BBK substrate rule"): {
        "deterministic core object": "deterministic Blueprint-core object",
    },
}

AUXILIARY_PROCEDURE_MODULES = {
    "bbk-context-routing": {
        "bbk-prompt-context-human-relay", "bbk-prompt-human-request",
        "bbk-prompt-profile-qualification",
    },
    "bbk-handoff": {
        "bbk-prompt-durable-handoff", "bbk-prompt-handoff-protocol",
        "bbk-prompt-state-claim-truth", "bbk-prompt-context-human-relay",
        "bbk-prompt-invocation-binding", "bbk-prompt-liveness-recovery",
    },
    "bbk-evidence": {
        "bbk-prompt-evidence-lineage", "bbk-prompt-evidence-receipts",
        "bbk-prompt-durable-handoff", "bbk-prompt-profile-qualification",
    },
    "bbk-review-findings": {
        "bbk-prompt-finding-lifecycle", "bbk-prompt-profile-qualification",
        "bbk-prompt-evidence-lineage", "bbk-prompt-assurance-integrity",
    },
    "bbk-execution-slicing": {
        "bbk-prompt-execution-slicing", "bbk-prompt-profile-qualification",
    },
    "bbk-profile-routing": {
        "bbk-prompt-profile-qualification", "bbk-prompt-profile-dispatch",
    },
}


def normalized_frontmatter(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        return ""
    end = normalized.find("\n---\n", 4)
    if end < 0:
        raise AssertionError("unterminated frontmatter")
    return normalized[: end + 5]


def heading_sections(text: str) -> list[tuple[str, str]]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.startswith("#")]
    sections: list[tuple[str, str]] = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        sections.append((lines[start].strip(), "".join(lines[start:end]).strip()))
    return sections


def is_subsequence(expected: list[str], actual: list[str]) -> bool:
    cursor = iter(actual)
    return all(any(item == candidate for candidate in cursor) for item in expected)


class PromptModulePackageV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.package = load_prompt_modules(ROOT)
        cls.role_package = assemble(ROOT)
        cls.roles = list(cls.role_package.roles)
        cls.spec = cls.role_package.projection
        cls.method_path = ROOT / "spec" / "method-content.json"
        cls.method = json.loads(cls.method_path.read_text(encoding="utf-8"))
        cls.baseline = json.loads(
            (ROOT / "tests" / "fixtures" / "alpha13-gate3-prompt-baseline.json")
            .read_text(encoding="utf-8")
        )

    def _minimal_copy(self, target: Path) -> None:
        (target / "spec").mkdir(parents=True)
        shutil.copy2(self.method_path, target / "spec" / "method-content.json")
        shutil.copytree(ROOT / "spec" / "roles", target / "spec" / "roles")
        shutil.copytree(ROOT / "spec" / "prompt-modules", target / "spec" / "prompt-modules")
        shutil.copytree(ROOT / "spec" / "schemas", target / "spec" / "schemas")
        shutil.copytree(ROOT / "spec" / "contracts", target / "spec" / "contracts")
        shutil.copy2(ROOT / "spec" / "roles.json", target / "spec" / "roles.json")

    def test_catalog_and_module_schemas_are_valid_draft_2020_12(self) -> None:
        try:
            import jsonschema
        except ImportError as exc:  # pragma: no cover
            self.skipTest(f"optional Draft 2020-12 validator unavailable: {exc}")
        catalog_schema = json.loads(
            (ROOT / "spec" / "schemas" / "bbk-prompt-module-catalog-v1.schema.json")
            .read_text(encoding="utf-8")
        )
        module_schema = json.loads(
            (ROOT / "spec" / "schemas" / "bbk-prompt-module-v1.schema.json")
            .read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator.check_schema(catalog_schema)
        jsonschema.Draft202012Validator.check_schema(module_schema)
        jsonschema.Draft202012Validator(catalog_schema).validate(self.package.catalog)
        validator = jsonschema.Draft202012Validator(module_schema)
        for module in self.package.modules:
            validator.validate(module)

    def test_module_inventory_order_and_clause_identities_are_unique(self) -> None:
        self.assertEqual(len(self.package.modules), 21)
        self.assertEqual(len(self.package.ordered_ids), len(set(self.package.ordered_ids)))
        clause_ids = [
            clause["id"]
            for module in self.package.modules
            for clause in module["clauses"]
        ]
        self.assertEqual(len(clause_ids), len(set(clause_ids)))
        self.assertTrue(all(module["id"].startswith("bbk-prompt-") for module in self.package.modules))

    def test_prompt_module_source_manifest_binds_catalog_and_every_module(self) -> None:
        manifest = source_manifest(self.package)
        self.assertEqual(manifest["schema_version"], "bbk.prompt-modules.v1")
        self.assertEqual(len(manifest["sources"]), 1 + len(self.package.modules))
        for record in manifest["sources"]:
            payload = (ROOT / record["path"]).read_bytes()
            self.assertEqual(record["bytes"], len(payload))
            self.assertEqual(record["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(manifest["sources"], self.spec["source_manifest"]["prompt_modules"])

    def test_method_content_v2_references_only_known_modules(self) -> None:
        self.assertEqual(self.method["schema"], "bbk.method-content.v2")
        self.assertEqual(self.method["prompt_module_source"], "spec/prompt-modules/catalog.json")
        self.assertEqual(validate_skill_templates(self.method, self.package), [])
        self.assertGreater(len(self.method["skills"]), 0)

    def test_standalone_skill_expands_each_referenced_module_exactly_once(self) -> None:
        for name, template in self.method["skills"].items():
            with self.subTest(skill=name):
                expanded = expand_skill_template(template, self.package)
                self.assertNotIn("{{bbk-module:", expanded)
                for module_id in module_directives(template):
                    marker = f"<!-- BBK prompt module {module_id}: expanded from canonical source -->"
                    self.assertEqual(expanded.count(marker), 1)
                    self.assertEqual(
                        expanded.count(f"<!-- End BBK prompt module {module_id} -->"), 1,
                    )

    def test_compact_skill_templates_reference_but_do_not_duplicate_module_bodies(self) -> None:
        for name, template in self.method["skills"].items():
            with self.subTest(skill=name):
                compact = compact_skill_template(template, self.package)
                self.assertNotIn("{{bbk-module:", compact)
                for module_id in module_directives(template):
                    self.assertIn(f"already embedded `{module_id}`", compact)
                    self.assertNotIn(self.package.by_id[module_id]["description"], compact)

    def test_generated_standalone_assets_are_computed_from_canonical_templates(self) -> None:
        assets = expected_method_assets(allow_staged=True)
        self.assertGreaterEqual(len(assets), len(self.method["skills"]))
        for name, template in self.method["skills"].items():
            path = ROOT / "shared" / "skills" / name / "SKILL.md"
            self.assertEqual(
                assets[path].decode("utf-8"),
                expand_skill_template(template, self.package),
            )

    def test_auxiliary_procedures_are_compositions_of_canonical_modules(self) -> None:
        for skill, expected in AUXILIARY_PROCEDURE_MODULES.items():
            with self.subTest(skill=skill):
                self.assertEqual(set(module_directives(self.method["skills"][skill])), expected)

    def test_policy_has_no_arbitrary_maximum_and_current_roles_need_one_primary_procedure(self) -> None:
        policy = self.package.catalog["compilation_policy"]
        self.assertEqual(policy["mandatory_procedure_default"], 1)
        self.assertIsNone(policy["mandatory_procedure_maximum"])
        self.assertIn("measured", policy["additional_mandatory_procedure_rule"].lower())
        self.assertEqual(policy["additional_mandatory_procedure_exceptions"], {})
        for role in self.roles:
            with self.subTest(role=role["name"]):
                self.assertEqual(role["mandatory_skills"], [role["primary_skill"]])
                self.assertIn(role["primary_skill"], role["skills"])

    def test_role_modules_are_known_ordered_and_cover_primary_procedure_requirements(self) -> None:
        order = list(self.package.ordered_ids)
        for role in self.roles:
            with self.subTest(role=role["name"]):
                selected = set(role["prompt_modules"])
                self.assertEqual(
                    role["prompt_modules"],
                    [module_id for module_id in order if module_id in selected],
                )
                required = set(role_skill_module_requirements(role, self.method["skills"]))
                self.assertTrue(required <= selected)

    def test_behavior_specific_modules_have_exact_role_ownership(self) -> None:
        for module_id, expected in EXCLUSIVE_MODULE_ROLES.items():
            with self.subTest(module=module_id):
                actual = {
                    role["name"] for role in self.roles
                    if module_id in role["prompt_modules"]
                }
                self.assertEqual(actual, expected)

    def test_tagged_hosts_embed_each_assigned_module_once(self) -> None:
        for host in ("omp", "claude", "generic"):
            for role in self.roles:
                with self.subTest(host=host, role=role["name"]):
                    rendered = instruction_text(self.spec, role, host=host)
                    self.assertNotIn("{{bbk-module:", rendered)
                    self.assertEqual(
                        rendered.count('<bbk-prompt-module id="'),
                        len(role["prompt_modules"]),
                    )
                    for module_id in role["prompt_modules"]:
                        self.assertEqual(
                            rendered.count(f'<bbk-prompt-module id="{module_id}">'), 1,
                        )
                        for clause in self.package.by_id[module_id]["clauses"]:
                            self.assertEqual(rendered.count(clause["text"]), 1)

    def test_codex_embeds_module_bodies_once_without_xml_like_tags(self) -> None:
        for role in self.roles:
            with self.subTest(role=role["name"]):
                rendered = instruction_text(self.spec, role, host="codex")
                self.assertNotIn("<bbk-prompt-module", rendered)
                for module_id in role["prompt_modules"]:
                    module = self.package.by_id[module_id]
                    heading = f'### Shared module: `{module_id}` — {module["title"]}'
                    self.assertEqual(rendered.count(heading), 1)
                    for clause in module["clauses"]:
                        self.assertEqual(rendered.count(clause["text"]), 1)

    def test_every_role_prompt_inlines_only_declared_mandatory_procedures(self) -> None:
        for host in ("omp", "claude", "generic"):
            for role in self.roles:
                with self.subTest(host=host, role=role["name"]):
                    rendered = instruction_text(self.spec, role, host=host)
                    self.assertEqual(
                        rendered.count('<bbk-inlined-skill name="'),
                        len(role["mandatory_skills"]),
                    )
                    for skill in role["mandatory_skills"]:
                        self.assertEqual(
                            rendered.count(f'<bbk-inlined-skill name="{skill}"'), 1,
                        )
        for role in self.roles:
            rendered = instruction_text(self.spec, role, host="codex")
            self.assertEqual(
                rendered.count("### Mandatory procedure: `"),
                len(role["mandatory_skills"]),
            )

    def test_role_behavior_contracts_are_unchanged_from_gate3(self) -> None:
        excluded = {"primary_skill", "mandatory_skills", "prompt_modules"}
        for role in self.roles:
            behavior = {key: value for key, value in role.items() if key not in excluded}
            digest = hashlib.sha256(
                json.dumps(
                    behavior, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            self.assertEqual(
                digest, self.baseline["roles"][role["name"]]["behavior_sha256"], role["name"],
            )

    def test_gate3_frontmatter_and_headings_are_preserved(self) -> None:
        for name, baseline in self.baseline["skills"].items():
            with self.subTest(skill=name):
                current = self.method["skills"][name]
                frontmatter_sha = hashlib.sha256(
                    normalized_frontmatter(current).encode("utf-8")
                ).hexdigest()
                self.assertEqual(frontmatter_sha, baseline["frontmatter_sha256"])
                current_headings = [heading for heading, _section in heading_sections(current)]
                self.assertTrue(is_subsequence(baseline["headings"], current_headings))

    def test_gate3_sections_not_replaced_by_modules_are_byte_semantically_unchanged(self) -> None:
        for name, baseline in self.baseline["skills"].items():
            current_sections = heading_sections(self.method["skills"][name])
            cursor = 0
            for old in baseline["sections"]:
                while cursor < len(current_sections) and current_sections[cursor][0] != old["heading"]:
                    cursor += 1
                self.assertLess(cursor, len(current_sections), f"{name}: missing {old['heading']}")
                heading, section = current_sections[cursor]
                cursor += 1
                if "bbk-prompt-" in section or "> Apply" in section:
                    continue
                for current_text, gate3_text in GATE5_PRODUCT_NEUTRAL_SUBSTITUTIONS.get(
                    (name, heading), {}
                ).items():
                    self.assertIn(current_text, section)
                    self.assertNotIn(gate3_text, section)
                    section = section.replace(current_text, gate3_text)
                digest = hashlib.sha256(section.encode("utf-8")).hexdigest()
                self.assertEqual(digest, old["sha256"], f"{name}: {old['heading']}")


    def test_gate3_role_specific_structured_protocols_remain_explicit(self) -> None:
        role_index = {role["name"]: role for role in self.roles}
        for role_name, fragments in ROLE_SPECIFIC_PROTOCOL_FRAGMENTS.items():
            rendered = instruction_text(self.spec, role_index[role_name], host="generic")
            for fragment in fragments:
                with self.subTest(role=role_name, fragment=fragment):
                    self.assertIn(fragment, rendered)

    def test_critical_typed_protocol_vocabulary_is_preserved_in_modules(self) -> None:
        module_text = "\n".join(
            clause["text"]
            for module in self.package.modules
            for clause in module["clauses"]
        )
        required_tokens = (
            ".bbk/handoffs/", "bbk.handoff.v1", "READY_FOR_VALIDATION",
            "BLOCKED_TECHNICAL", "READY_FOR_PARENT_INTEGRATION",
            "SolutionOutcomeFit", "State–Decision–Effect", "BBK_PROFILE_PATH",
            "PROFILE.json.skills", "bbk.profile-capability.v1", "runTools",
            "EvidenceReceipt", "stdout", "stderr", "SAME_DEFECT",
            "PROBABLE_DUPLICATE", "SHARED_ROOT_CAUSE", "OVERLAPPING_IMPACT",
            "CONTRADICTORY_ASSESSMENT", "UNRELATED", "FIXED", "REBUTTED",
            "ACCEPTED_RISK", "FALSE_POSITIVE", "DUPLICATE_OF", "SUPERSEDED",
            "DEFERRED", "OUT_OF_SCOPE", "REMAINS_OPEN", "DECISION", "AUTHORITY",
            "PRIVATE_CONTEXT", "ACCEPTANCE", "PROTECTED_FLOOR_EXCEPTION", "replyTo",
            "IMPLEMENTED_DETERMINISTIC", "IMPLEMENTED_BOOTSTRAP",
            "SCHEMA_DEFINED_COMPANION", "HOST_PROVIDED_OPTIONAL", "TARGET_ONLY",
            "RETIRED_NOT_IMPLEMENTED",
        )
        for token in required_tokens:
            with self.subTest(token=token):
                self.assertIn(token, module_text)

    def test_prompt_compilation_reduces_aggregate_role_prompt_size_without_a_hidden_threshold(self) -> None:
        old_total = 0
        new_total = 0
        for role in self.roles:
            old_total += self.baseline["generic_prompt_characters"][role["name"]]
            new_total += len(instruction_text(self.spec, role, host="generic"))
        self.assertLess(new_total, old_total)

    def test_projection_manifest_v8_binds_method_and_module_sources(self) -> None:
        _outputs, manifest = expected_files()
        self.assertEqual(manifest["schema"], "bbk.projection-manifest.v8")
        self.assertEqual(manifest["method_content_source"], "spec/method-content.json")
        self.assertEqual(manifest["prompt_module_package"], "spec/prompt-modules/catalog.json")
        self.assertEqual(
            len(manifest["prompt_module_sources"]), 1 + len(self.package.modules),
        )
        self.assertRegex(manifest["method_content_source_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(manifest["prompt_module_source_sha256"], r"^[0-9a-f]{64}$")
        for role in self.roles:
            agent = manifest["agents"][role["name"]]
            self.assertEqual(agent["primary_skill"], role["primary_skill"])
            self.assertEqual(agent["prompt_modules"], role["prompt_modules"])

    def test_unknown_role_module_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._minimal_copy(root)
            path = root / "spec" / "roles" / "bbk_worker-role.json"
            role = json.loads(path.read_text(encoding="utf-8"))
            role["prompt_modules"].append("bbk-prompt-does-not-exist")
            path.write_bytes(canonical_bytes(role))
            with self.assertRaises(RolePackageError) as caught:
                assemble(root)
            self.assertIn("unknown prompt modules", "\n".join(caught.exception.errors))

    def test_misordered_role_modules_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._minimal_copy(root)
            path = root / "spec" / "roles" / "bbk_worker-role.json"
            role = json.loads(path.read_text(encoding="utf-8"))
            role["prompt_modules"][0], role["prompt_modules"][1] = (
                role["prompt_modules"][1], role["prompt_modules"][0],
            )
            path.write_bytes(canonical_bytes(role))
            with self.assertRaises(RolePackageError) as caught:
                assemble(root)
            self.assertIn("prompt_modules must follow catalog order", "\n".join(caught.exception.errors))

    def test_exclusive_module_assigned_to_wrong_role_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._minimal_copy(root)
            path = root / "spec" / "roles" / "bbk_worker-role.json"
            role = json.loads(path.read_text(encoding="utf-8"))
            selected = set(role["prompt_modules"]) | {"bbk-prompt-human-request"}
            role["prompt_modules"] = [
                module_id for module_id in self.package.ordered_ids if module_id in selected
            ]
            path.write_bytes(canonical_bytes(role))
            with self.assertRaises(RolePackageError) as caught:
                assemble(root)
            self.assertIn("bbk-prompt-human-request role ownership", "\n".join(caught.exception.errors))

    def test_additional_mandatory_procedure_requires_measured_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._minimal_copy(root)
            role_path = root / "spec" / "roles" / "bbk_worker-role.json"
            role = json.loads(role_path.read_text(encoding="utf-8"))
            role["mandatory_skills"].append("bbk-handoff")
            role_path.write_bytes(canonical_bytes(role))
            with self.assertRaises(RolePackageError) as caught:
                assemble(root)
            self.assertIn("require an explicit measured exception", "\n".join(caught.exception.errors))

    def test_measured_exception_can_authorize_more_than_three_mandatory_procedures(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._minimal_copy(root)
            role_path = root / "spec" / "roles" / "bbk_worker-role.json"
            role = json.loads(role_path.read_text(encoding="utf-8"))
            additions = ["bbk-handoff", "bbk-recover", "bbk-implementation-structure"]
            self.assertTrue(set(additions) <= set(role["skills"]))
            role["mandatory_skills"] = [role["primary_skill"], *additions]
            role_path.write_bytes(canonical_bytes(role))

            catalog_path = root / "spec" / "prompt-modules" / "catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            package = load_prompt_modules(root)
            method_path = root / "spec" / "method-content.json"
            method = json.loads(method_path.read_text(encoding="utf-8"))
            catalog["compilation_policy"]["additional_mandatory_procedure_exceptions"][role["name"]] = {
                "mandatory_skills": role["mandatory_skills"],
                "distinct_behavior": {
                    "bbk-handoff": "The synthetic contract requires the full standalone carrier lifecycle.",
                    "bbk-recover": "The synthetic contract requires an independent recovery procedure.",
                    "bbk-implementation-structure": "The synthetic contract requires independent structural compilation.",
                },
                "measurement": mandatory_procedure_exception_measurement(
                    role["mandatory_skills"], method["skills"], package,
                    method_path.read_bytes(),
                ),
                "rationale": "Synthetic fixture proving that correctness-driven measured exceptions may exceed three procedures.",
            }
            catalog_path.write_bytes(canonical_bytes(catalog))
            package = assemble(root)
            compiled = next(item for item in package.roles if item["name"] == role["name"])
            self.assertEqual(len(compiled["mandatory_skills"]), 4)

    def test_stale_mandatory_procedure_measurement_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._minimal_copy(root)
            role_path = root / "spec" / "roles" / "bbk_worker-role.json"
            role = json.loads(role_path.read_text(encoding="utf-8"))
            role["mandatory_skills"] = [role["primary_skill"], "bbk-handoff"]
            role_path.write_bytes(canonical_bytes(role))
            method_path = root / "spec" / "method-content.json"
            method = json.loads(method_path.read_text(encoding="utf-8"))
            package = load_prompt_modules(root)
            measurement = mandatory_procedure_exception_measurement(
                role["mandatory_skills"], method["skills"], package, method_path.read_bytes(),
            )
            measurement["incremental_body_bytes"] += 1
            catalog_path = root / "spec" / "prompt-modules" / "catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["compilation_policy"]["additional_mandatory_procedure_exceptions"][role["name"]] = {
                "mandatory_skills": role["mandatory_skills"],
                "distinct_behavior": {
                    "bbk-handoff": "Synthetic independent handoff lifecycle.",
                },
                "measurement": measurement,
                "rationale": "Synthetic stale-measurement rejection fixture.",
            }
            catalog_path.write_bytes(canonical_bytes(catalog))
            with self.assertRaises(RolePackageError) as caught:
                assemble(root)
            self.assertTrue(
                any("measurement" in item for item in caught.exception.errors),
                "\n".join(caught.exception.errors),
            )

    def test_missing_module_required_by_primary_procedure_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._minimal_copy(root)
            path = root / "spec" / "roles" / "bbk_worker-role.json"
            role = json.loads(path.read_text(encoding="utf-8"))
            required = next(iter(role_skill_module_requirements(role, self.method["skills"])))
            role["prompt_modules"].remove(required)
            path.write_bytes(canonical_bytes(role))
            with self.assertRaises(RolePackageError) as caught:
                assemble(root)
            self.assertIn(
                "mandatory procedures require unassigned prompt modules",
                "\n".join(caught.exception.errors),
            )

    def test_malformed_skill_module_directive_is_rejected(self) -> None:
        method = copy.deepcopy(self.method)
        method["skills"]["bbk-wayfind"] += "\n\n{{bbk-module:not-valid}}\n"
        errors = validate_skill_templates(method, self.package)
        self.assertTrue(any("malformed prompt-module directive" in error for error in errors))

    def test_omp_adapter_is_prompt_module_and_measurement_aware_and_syntax_valid(self) -> None:
        source = (ROOT / "omp" / "extension" / "index.js").read_text(encoding="utf-8")
        for token in (
            "bbk.prompt-modules.v1", "prompt_module_package", "prompt_modules",
            "must embed prompt module", "mandatory_procedure_maximum",
            "distinct_behavior", "method_content_sha256", "incremental_body_bytes",
            "duplicated_prompt_module_bodies", "spec\", \"method-content.json",
        ):
            self.assertIn(token, source)
        node = shutil.which("node")
        if node:
            completed = subprocess.run(
                [node, "--check", ROOT / "omp" / "extension" / "index.js"],
                cwd=ROOT, check=False, text=True, encoding="utf-8", errors="replace",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
