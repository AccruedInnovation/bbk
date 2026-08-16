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
    clauses_for_harness,
    compact_skill_template,
    compile_standalone_skill,
    expand_skill_template,
    load_prompt_modules,
    mandatory_procedure_exception_measurement,
    module_directives,
    prompt_size_report,
    role_skill_module_requirements,
    skill_module_dependency,
    source_manifest,
    validate_skill_templates,
)
from tests._role_spec_fixture import materialize_role_assembly_fixture


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
    "bbk-prompt-executable-baseline": {
        "bbk_architect", "bbk_phase_wayfinder", "bbk_planning_wayfinder",
        "bbk_prototyper", "bbk_reviewer", "bbk_root_orchestrator",
        "bbk_root_wayfinder", "bbk_territory_orchestrator",
        "bbk_territory_wayfinder", "bbk_verification_designer",
        "bbk_worker", "bbk_worker_designer", "bbk_worker_orchestrator",
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
    "bbk-prompt-execution-autonomy": {
        "bbk_phase_wayfinder", "bbk_planning_wayfinder", "bbk_prototyper",
        "bbk_root_orchestrator", "bbk_root_wayfinder",
        "bbk_territory_orchestrator", "bbk_territory_wayfinder", "bbk_worker",
        "bbk_worker_designer", "bbk_worker_orchestrator",
    },
    "bbk-prompt-user-attention": {
        "bbk_question_guide", "bbk_questioning_wayfinder",
        "bbk_root_wayfinder", "bbk_territory_wayfinder",
    },
    "bbk-prompt-baseline-transition": {
        "bbk_root_orchestrator", "bbk_root_wayfinder", "bbk_territory_wayfinder",
    },
    "bbk-prompt-evidence-subject-identity": {
        "bbk_architect", "bbk_phase_wayfinder", "bbk_planning_wayfinder",
        "bbk_prototyper", "bbk_question_guide", "bbk_questioning_wayfinder",
        "bbk_researcher", "bbk_reviewer", "bbk_root_orchestrator",
        "bbk_root_wayfinder", "bbk_synthesizer", "bbk_territory_orchestrator",
        "bbk_territory_wayfinder", "bbk_validator", "bbk_validator_orchestrator",
        "bbk_verification_designer", "bbk_worker", "bbk_worker_designer",
        "bbk_worker_orchestrator",
    },
    "bbk-prompt-specialist-disposition": {
        "bbk_architect", "bbk_phase_wayfinder", "bbk_planning_wayfinder",
        "bbk_prototyper", "bbk_root_orchestrator", "bbk_root_wayfinder",
        "bbk_territory_orchestrator", "bbk_territory_wayfinder",
        "bbk_validator_orchestrator", "bbk_worker_orchestrator",
    },
    "bbk-prompt-product-first-proportionality": {
        "bbk_architect", "bbk_phase_wayfinder", "bbk_planning_wayfinder",
        "bbk_prototyper", "bbk_researcher", "bbk_reviewer",
        "bbk_root_orchestrator", "bbk_root_wayfinder", "bbk_synthesizer",
        "bbk_territory_orchestrator", "bbk_territory_wayfinder", "bbk_validator",
        "bbk_validator_orchestrator", "bbk_verification_designer", "bbk_worker",
        "bbk_worker_designer", "bbk_worker_orchestrator",
    },
    "bbk-prompt-mechanical-admission": {
        "bbk_architect", "bbk_phase_wayfinder", "bbk_planning_wayfinder",
        "bbk_reviewer", "bbk_root_orchestrator", "bbk_root_wayfinder",
        "bbk_territory_orchestrator", "bbk_territory_wayfinder", "bbk_validator",
        "bbk_validator_orchestrator", "bbk_verification_designer", "bbk_worker",
        "bbk_worker_designer", "bbk_worker_orchestrator",
    },
    "bbk-prompt-assurance-modes": {
        "bbk_phase_wayfinder", "bbk_planning_wayfinder", "bbk_prototyper",
        "bbk_reviewer", "bbk_root_orchestrator", "bbk_root_wayfinder",
        "bbk_territory_orchestrator", "bbk_territory_wayfinder", "bbk_validator",
        "bbk_validator_orchestrator", "bbk_verification_designer", "bbk_worker",
        "bbk_worker_designer", "bbk_worker_orchestrator",
    },
    "bbk-prompt-candidate-focused-review": {
        "bbk_phase_wayfinder", "bbk_planning_wayfinder", "bbk_reviewer",
        "bbk_root_orchestrator", "bbk_territory_orchestrator", "bbk_validator",
        "bbk_validator_orchestrator", "bbk_verification_designer", "bbk_worker",
        "bbk_worker_designer", "bbk_worker_orchestrator",
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

ALPHA132_BEADS_OWNER_ROLES = {
    "bbk_root_wayfinder", "bbk_territory_wayfinder",
    "bbk_planning_wayfinder", "bbk_phase_wayfinder",
    "bbk_root_orchestrator", "bbk_territory_orchestrator",
    "bbk_worker_orchestrator", "bbk_questioning_wayfinder",
}

ALPHA132_INTENTIONAL_SKILL_REPLACEMENTS = {"bbk-beads"}

ALPHA14_INTENTIONAL_ROLE_CHANGES = {
    "bbk_architect", "bbk_phase_wayfinder", "bbk_planning_wayfinder",
    "bbk_questioning_wayfinder", "bbk_researcher", "bbk_root_orchestrator",
    "bbk_root_wayfinder", "bbk_territory_orchestrator", "bbk_worker",
    "bbk_worker_designer", "bbk_worker_orchestrator",
}


ALPHA15_INTENTIONAL_ROLE_CHANGES = {
    "bbk_root_wayfinder", "bbk_territory_wayfinder", "bbk_questioning_wayfinder",
    "bbk_planning_wayfinder", "bbk_phase_wayfinder", "bbk_question_guide",
    "bbk_researcher", "bbk_prototyper", "bbk_synthesizer", "bbk_architect",
    "bbk_verification_designer", "bbk_worker_designer", "bbk_reviewer",
    "bbk_root_orchestrator", "bbk_territory_orchestrator",
    "bbk_worker_orchestrator", "bbk_validator_orchestrator", "bbk_worker",
    "bbk_validator",
}

ALPHA14_INTENTIONAL_SKILL_CHANGES = {
    "bbk", "bbk-architecture", "bbk-evidence", "bbk-handoff",
    "bbk-implementation-structure", "bbk-phase-plan", "bbk-question-branch",
    "bbk-research", "bbk-root-execution", "bbk-wayfind", "bbk-work-graph",
    "bbk-worker-design", "bbk-worker-execution",
}

ALPHA15_INTENTIONAL_SKILL_CHANGES = {
    "bbk", "bbk-architecture", "bbk-assertion-validation",
    "bbk-execution-slicing", "bbk-phase-plan", "bbk-prototype",
    "bbk-research", "bbk-review", "bbk-review-context", "bbk-review-plan",
    "bbk-root-execution", "bbk-synthesize", "bbk-territory-execution",
    "bbk-validation-orchestration", "bbk-verification-design", "bbk-wayfind",
    "bbk-work-graph", "bbk-work-unit-execution", "bbk-worker-design",
    "bbk-worker-execution", "bbk-handoff",
}

ALPHA1701_INTENTIONAL_SKILL_CHANGES = {
    "bbk-plan", "bbk-wayfind", "bbk-work-graph", "bbk-phase-plan",
    "bbk-architecture", "bbk-root-execution", "bbk-territory-execution",
    "bbk-worker-execution", "bbk-work-unit-execution", "bbk-worker-design",
    "bbk-verification-design", "bbk-installed-profiles",
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
        "bbk-prompt-evidence-subject-identity",
    },
    "bbk-review-findings": {
        "bbk-prompt-finding-lifecycle", "bbk-prompt-profile-qualification",
        "bbk-prompt-evidence-lineage", "bbk-prompt-assurance-integrity",
    },
    "bbk-execution-slicing": {
        "bbk-prompt-execution-slicing", "bbk-prompt-profile-qualification",
        "bbk-prompt-product-first-proportionality",
        "bbk-prompt-mechanical-admission",
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
        self.assertEqual(len(self.package.modules), 43)
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

    def test_standalone_skill_compiler_expands_only_standalone_modules_once(self) -> None:
        for name, template in self.method["skills"].items():
            with self.subTest(skill=name):
                compiled = compile_standalone_skill(
                    name, template, self.package, self.method,
                )
                policy = skill_module_dependency(self.method, name)
                self.assertNotIn("{{bbk-module:", compiled)
                for module_id in policy["requires_prompt_modules"]:
                    marker = f"<!-- BBK prompt module {module_id}: expanded from canonical source -->"
                    self.assertEqual(compiled.count(marker), 0)
                    self.assertIn(f"already embedded `{module_id}`", compiled)
                    self.assertNotIn(self.package.by_id[module_id]["description"], compiled)
                for module_id in policy["standalone_prompt_modules"]:
                    marker = f"<!-- BBK prompt module {module_id}: expanded from canonical source -->"
                    self.assertEqual(compiled.count(marker), 1)
                    self.assertEqual(
                        compiled.count(f"<!-- End BBK prompt module {module_id} -->"), 1,
                    )
                frontmatter = normalized_frontmatter(compiled)
                self.assertIn("requires_prompt_modules:", frontmatter)
                self.assertIn("standalone_prompt_modules:", frontmatter)

    def test_execution_entrypoints_embed_canonical_execution_bias(self) -> None:
        entrypoints = (
            "bbk-wayfind",
            "bbk-work-graph",
            "bbk-phase-plan",
            "bbk-plan",
            "bbk-root-execution",
            "bbk-territory-execution",
            "bbk-worker-execution",
        )
        for name in entrypoints:
            with self.subTest(skill=name):
                policy = skill_module_dependency(self.method, name)
                self.assertIn(
                    "bbk-prompt-critical-path-execution",
                    policy["standalone_prompt_modules"],
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
                compile_standalone_skill(name, template, self.package, self.method),
            )

    def test_hot_path_generated_skills_meet_alpha17_compaction_budget(self) -> None:
        names = (
            "bbk-handoff",
            "bbk-validation-orchestration",
            "bbk-work-unit-execution",
            "bbk-worker-design",
        )
        total = sum(
            len((ROOT / "shared" / "skills" / name / "SKILL.md").read_bytes())
            for name in names
        )
        self.assertLessEqual(total, 72000)

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
                required = set(role_skill_module_requirements(
                    role, self.method["skills"], self.method["skill_module_dependencies"],
                    include_all_loaded_skills=True,
                ))
                self.assertTrue(required <= selected)

    def test_behavior_specific_modules_have_exact_role_ownership(self) -> None:
        for module_id, expected in EXCLUSIVE_MODULE_ROLES.items():
            with self.subTest(module=module_id):
                actual = {
                    role["name"] for role in self.roles
                    if module_id in role["prompt_modules"]
                }
                self.assertEqual(actual, expected)

    def test_alpha14_autonomy_attention_transition_evidence_and_specialist_modules_are_compiled(self) -> None:
        autonomy = {clause["id"]: clause["text"] for clause in self.package.by_id["bbk-prompt-execution-autonomy"]["clauses"]}
        self.assertIn("exactly one safe, realistic", autonomy["AUTONOMY.SINGLE_PATH"])
        self.assertIn("inside current authority", autonomy["AUTONOMY.SINGLE_PATH"])
        self.assertIn("local execution deltas by default", autonomy["AUTONOMY.CHANGE_CLASSIFICATION"])
        self.assertIn("smallest local correction first", autonomy["AUTONOMY.CHANGE_CLASSIFICATION"])
        self.assertIn("at least two viable, materially different paths", autonomy["AUTONOMY.GENUINE_BRANCH"])
        self.assertIn("authority expansion", autonomy["AUTONOMY.AUTHORITY_BOUNDARY"])

        attention = {clause["id"]: clause["text"] for clause in self.package.by_id["bbk-prompt-user-attention"]["clauses"]}
        for value in (
            "ENVIRONMENT_FACT", "CONFIGURATION_PARAMETER",
            "REVERSIBLE_IMPLEMENTATION_CHOICE", "ARCHITECTURAL_DECISION",
            "AUTHORITY_EXPANSION", "USER_RESERVED_PREFERENCE",
        ):
            self.assertIn(value, attention["ATTENTION.CLASSIFY"])
        self.assertIn("one response packet", attention["ATTENTION.BATCH"])

        transition = "\n".join(
            clause["text"] for clause in self.package.by_id["bbk-prompt-baseline-transition"]["clauses"]
        )
        self.assertIn("originating Root Wayfinder owns integration", transition)
        self.assertIn("phase outline", transition)
        self.assertIn("Root Orchestrator consumes exact", transition)
        self.assertNotIn("deterministic gate", transition.lower())

        evidence = "\n".join(
            clause["text"] for clause in self.package.by_id["bbk-prompt-evidence-subject-identity"]["clauses"]
        )
        self.assertIn("exact node or subject", evidence)
        self.assertIn("Do not transfer an observation", evidence)
        self.assertIn("measured, documented, calculated, inferred, or illustrative", evidence)

        specialist = "\n".join(
            clause["text"] for clause in self.package.by_id["bbk-prompt-specialist-disposition"]["clauses"]
        )
        for disposition in ("COMMISSIONED", "INTEGRATED", "DEFERRED", "SUPERSEDED", "REJECTED", "REMAINS_OPEN"):
            self.assertIn(disposition, specialist)
        self.assertIn("confirmation, amendment, or successor", specialist)

        projections, _manifest = expected_files()
        for target in ("codex", "omp", "claude", "generic"):
            path = ROOT / "projections" / target / "agents" / (
                "bbk_root_orchestrator.toml" if target == "codex" else
                "bbk-root-orchestrator.md" if target == "claude" else
                "bbk_root_orchestrator.md"
            )
            text = projections[path].decode("utf-8")
            self.assertIn("A technical blocker is not a user decision", text, target)
            self.assertIn("Root Orchestrator consumes exact accepted-baseline", text, target)

    def test_alpha133_coordination_recovery_and_executable_truth_are_scoped_and_compiled(self) -> None:
        human = self.package.by_id["bbk-prompt-human-request"]
        human_clause = next(
            clause["text"] for clause in human["clauses"]
            if clause["id"] == "HUMAN.CALLBACK_SAFE_CHILDREN"
        )
        delegation = self.package.by_id["bbk-prompt-delegation-return"]
        interrupt_clause = next(
            clause["text"] for clause in delegation["clauses"]
            if clause["id"] == "DELEGATION.INTERRUPT_SAFE_LIFETIME"
        )
        partial_clause = next(
            clause["text"] for clause in delegation["clauses"]
            if clause["id"] == "DELEGATION.CANCELLED_PARTIAL"
        )
        state = self.package.by_id["bbk-prompt-state-claim-truth"]
        transport_clause = next(
            clause["text"] for clause in state["clauses"]
            if clause["id"] == "STATE.TRANSPORT_NOT_INTEGRATION"
        )
        executable = self.package.by_id["bbk-prompt-executable-baseline"]
        executable_text = [clause["text"] for clause in executable["clauses"]]

        human_roles = {
            role["name"] for role in self.roles
            if "bbk-prompt-human-request" in role["prompt_modules"]
        }
        self.assertEqual(human_roles, {
            "bbk_root_wayfinder", "bbk_questioning_wayfinder", "bbk_question_guide",
        })
        for role in self.roles:
            rendered = instruction_text(self.spec, role, host="generic")
            with self.subTest(role=role["name"]):
                self.assertEqual(rendered.count(transport_clause), 1)
                self.assertEqual(
                    rendered.count(human_clause),
                    1 if role["name"] in human_roles else 0,
                )
                if "bbk-prompt-delegation-return" in role["prompt_modules"]:
                    self.assertEqual(rendered.count(interrupt_clause), 1)
                    self.assertEqual(rendered.count(partial_clause), 1)
                else:
                    self.assertNotIn(interrupt_clause, rendered)
                    self.assertNotIn(partial_clause, rendered)
                expects_executable = role["name"] in EXCLUSIVE_MODULE_ROLES[
                    "bbk-prompt-executable-baseline"
                ]
                for clause in executable_text:
                    self.assertEqual(rendered.count(clause), 1 if expects_executable else 0)

        research = self.method["skills"]["bbk-research"]
        self.assertIn("Rank research by decision impact and prerequisite order.", research)
        self.assertIn("primary path and immediate fallback", research)
        self.assertIn("Stop when the parent can make the bounded decision", research)

        candidate = self.package.by_id["bbk-prompt-candidate-integrity"]
        successor = next(
            clause["text"] for clause in candidate["clauses"]
            if clause["id"] == "CANDIDATE.SUCCESSOR"
        )
        self.assertIn("successor identity", successor)
        self.assertIn("invalidates evidence", successor)
        candidate_text = "\n".join(clause["text"] for clause in candidate["clauses"])
        for fragment in (
            "No sealed artifact, no validation admission",
            "sealed `candidate-package-v1`",
            "tool-generated `contentSha256`",
            "ordinary mutable path",
            "read-only `bbk artifact verify`",
            "`bbk artifact successor`",
            "Never correct, amend, replace, or append to an admitted sealed package",
        ):
            self.assertIn(fragment, candidate_text)
        rendered_roles = {
            role["name"]: instruction_text(self.spec, role, host="generic")
            for role in self.roles
            if role["name"] in {
                "bbk_worker", "bbk_worker_orchestrator",
                "bbk_territory_orchestrator", "bbk_validator_orchestrator",
                "bbk_validator",
            }
        }
        sealed_gate = next(
            clause["text"] for clause in candidate["clauses"]
            if clause["id"] == "CANDIDATE.SEALED_ADMISSION_GATE"
        )
        for role_name, rendered in rendered_roles.items():
            with self.subTest(sealed_admission_role=role_name):
                self.assertEqual(rendered.count(sealed_gate), 1)
        reviewer = next(role for role in self.roles if role["name"] == "bbk_reviewer")
        reviewer_invalidation = next(
            responsibility for responsibility in reviewer["responsibilities"]
            if "A material change to the subject" in responsibility
        )
        self.assertIn("invalidates the affected attempt or conclusion", reviewer_invalidation)
        self.assertIn("normally requires a successor attempt", reviewer_invalidation)
        boundary = self.package.by_id["bbk-prompt-role-boundary"]
        self.assertTrue(any(
            clause["id"] == "ROLE.NO_ABSORPTION" and "Do not spawn, imitate, approve, repair, validate, integrate, or decide" in clause["text"]
            for clause in boundary["clauses"]
        ))

        lifetime_doc = (ROOT / "docs" / "OMP-CHILD-LIFETIME.md").read_text(encoding="utf-8")
        for expected in (
            "`async.enabled=true`",
            "`blocking: false`",
            "parent tool-call `AbortSignal`",
            "native OMP path",
            "scheduling fallback",
            "File existence is not a complete specialist return",
            "explicit cancel operations",
        ):
            self.assertIn(expected, lifetime_doc)

    def test_alpha133_omp_agents_explicitly_prefer_native_nonblocking_jobs(self) -> None:
        outputs, _manifest = expected_files()
        omp_outputs = {
            path: payload.decode("utf-8")
            for path, payload in outputs.items()
            if path.parent == ROOT / "projections" / "omp" / "agents"
        }
        self.assertEqual(len(omp_outputs), 19)
        for path, text in omp_outputs.items():
            with self.subTest(agent=path.name):
                frontmatter = normalized_frontmatter(text)
                self.assertEqual(frontmatter.count("\nblocking: false\n"), 1)
                self.assertNotIn("blocking: true", frontmatter)

    def test_tagged_hosts_embed_each_assigned_module_once(self) -> None:
        for host in ("omp", "claude", "generic", "pi"):
            for role in self.roles:
                with self.subTest(host=host, role=role["name"]):
                    rendered = instruction_text(self.spec, role, host=host)
                    self.assertNotIn("{{bbk-module:", rendered)
                    for module_id in role["prompt_modules"]:
                        self.assertEqual(
                            rendered.count(f'<bbk-prompt-module id="{module_id}">'), 1,
                        )
                        opening = f'<bbk-prompt-module id="{module_id}">'
                        closing = "</bbk-prompt-module>"
                        module_body = rendered.split(opening, 1)[1].split(closing, 1)[0]
                        module = self.package.by_id[module_id]
                        applicable = {clause["id"] for clause in clauses_for_harness(module, host)}
                        for clause in module["clauses"]:
                            self.assertEqual(
                                module_body.count(clause["text"]),
                                1 if clause["id"] in applicable else 0,
                            )

    def test_codex_embeds_module_bodies_once_without_xml_like_tags(self) -> None:
        for role in self.roles:
            with self.subTest(role=role["name"]):
                rendered = instruction_text(self.spec, role, host="codex")
                self.assertNotIn("<bbk-prompt-module", rendered)
                for module_id in role["prompt_modules"]:
                    module = self.package.by_id[module_id]
                    heading = f'### `{module_id}`'
                    self.assertEqual(rendered.count(heading), 1)
                    module_body = rendered.split(heading, 1)[1].split("\n### `", 1)[0]
                    applicable = {clause["id"] for clause in clauses_for_harness(module, "codex")}
                    for clause in module["clauses"]:
                        self.assertEqual(
                            module_body.count(clause["text"]),
                            1 if clause["id"] in applicable else 0,
                        )

    def test_exactly_six_clauses_are_canonical_omp_only(self) -> None:
        expected = {
            "CONTEXT.HOST_EDGE",
            "CRITICAL_PATH.ATOMIC_BOUND_SPAWN",
            "CRITICAL_PATH.TOKEN_DISPATCH",
            "HUMAN.REQUEST_TRANSPORT",
            "LIVENESS.EVENT_DELIVERY",
            "HOST.OMP_EXTENSION_GUARD",
        }
        scoped = {
            clause["id"]: tuple(clause.get("hosts", ()))
            for module in self.package.modules
            for clause in module["clauses"]
            if "hosts" in clause
        }
        self.assertEqual({clause_id: ("omp",) for clause_id in expected}, scoped)

    def test_every_role_prompt_compiles_declared_mandatory_procedures_once_at_tail(self) -> None:
        for host in ("omp", "claude", "generic", "codex"):
            for role in self.roles:
                with self.subTest(host=host, role=role["name"]):
                    rendered = instruction_text(self.spec, role, host=host)
                    self.assertEqual(rendered.count("## Compiled procedures manifest"), 1)
                    self.assertEqual(rendered.count("## Compiled procedures\n"), 1)
                    self.assertEqual(rendered.count("## End compiled procedures"), 1)
                    self.assertNotIn("<bbk-inlined-skill", rendered)
                    end = rendered.index("## End compiled procedures")
                    for skill in role["mandatory_skills"]:
                        self.assertEqual(rendered.count(f"- id: {skill}"), 1)
                        heading = (
                            f"### Compiled primary procedure: `{skill}`"
                            if skill == role["primary_skill"]
                            else f"### Compiled procedure: `{skill}`"
                        )
                        self.assertEqual(rendered.count(heading), 1)
                        self.assertLess(rendered.index(heading), end)

    def test_roles_not_intentionally_changed_in_alpha14_retain_gate3_behavior(self) -> None:
        excluded = {"primary_skill", "mandatory_skills", "prompt_modules"}
        for role in self.roles:
            if role["name"] in ALPHA14_INTENTIONAL_ROLE_CHANGES | ALPHA15_INTENTIONAL_ROLE_CHANGES:
                continue
            behavior = {key: value for key, value in role.items() if key not in excluded}
            if role["name"] in ALPHA132_BEADS_OWNER_ROLES:
                behavior["skills"] = [
                    value for value in behavior.get("skills", []) if value != "bbk-beads"
                ]
                behavior["responsibilities"] = [
                    value for value in behavior.get("responsibilities", [])
                    if "bbk-beads" not in value
                ]
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
                if name in ALPHA132_INTENTIONAL_SKILL_REPLACEMENTS | ALPHA14_INTENTIONAL_SKILL_CHANGES | ALPHA15_INTENTIONAL_SKILL_CHANGES | ALPHA1701_INTENTIONAL_SKILL_CHANGES:
                    continue
                current = self.method["skills"][name]
                frontmatter_sha = hashlib.sha256(
                    normalized_frontmatter(current).encode("utf-8")
                ).hexdigest()
                self.assertEqual(frontmatter_sha, baseline["frontmatter_sha256"])
                current_headings = [heading for heading, _section in heading_sections(current)]
                self.assertTrue(is_subsequence(baseline["headings"], current_headings))

    def test_gate3_sections_not_replaced_by_modules_are_byte_semantically_unchanged(self) -> None:
        for name, baseline in self.baseline["skills"].items():
            if name in ALPHA132_INTENTIONAL_SKILL_REPLACEMENTS | ALPHA14_INTENTIONAL_SKILL_CHANGES | ALPHA15_INTENTIONAL_SKILL_CHANGES | ALPHA1701_INTENTIONAL_SKILL_CHANGES:
                continue
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

    def test_alpha132_beads_skill_is_the_normal_role_owned_coordination_projection(self) -> None:
        text = self.method["skills"]["bbk-beads"]
        for required in (
            "Beads is BBK's default coordination projection for newly initialized projects.",
            "Root and Territory Wayfinders: project, territory, and decision records.",
            "Planning and Phase Wayfinders: capability increments, phases, and WorkUnits.",
            "Root, Territory, and Worker Orchestrators: execution-state records and durable-handoff pointers.",
            "Questioning Wayfinder: question records.",
            "bbk beads plan --root <project> --kind <owned-kind>",
            "deterministically and idempotently",
            "never apply last-write-wins reconciliation",
            "The BBK file remains authoritative.",
        ):
            self.assertIn(required, text)


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
            ".bbk/handoffs/", "bbk.handoff.v2", "bbk.handoff.v1", "READY_FOR_VALIDATION",
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

    def test_prompt_compilation_avoids_naive_module_body_duplication_without_a_size_cap(self) -> None:
        compiled_total = 0
        naive_duplicate_total = 0
        for role in self.roles:
            compiled = instruction_text(self.spec, role, host="generic")
            compiled_total += len(compiled)
            duplicate_overhead = 0
            for skill in role["mandatory_skills"]:
                template = self.method["skills"][skill]
                duplicate_overhead += len(expand_skill_template(template, self.package))
                duplicate_overhead -= len(compact_skill_template(template, self.package))
            naive_duplicate_total += len(compiled) + duplicate_overhead
        self.assertGreater(compiled_total, 0)
        self.assertLess(compiled_total, naive_duplicate_total)

    def test_alpha17_critical_path_execution_modules_are_exact(self) -> None:
        critical_clauses = {
            clause["id"]: clause["text"] for clause in
            self.package.by_id["bbk-prompt-critical-path-execution"]["clauses"]
        }
        critical = "\n".join(critical_clauses.values())
        self.assertIn(
            "dispatch it immediately",
            critical_clauses["CRITICAL_PATH.EXECUTION_PRECEDENCE"],
        )
        one_check = critical_clauses["CRITICAL_PATH.ONE_CHECK"]
        self.assertIn("validation or review", one_check)
        self.assertIn("declared invalidation key changed", one_check)
        blocker_repair = critical_clauses["CRITICAL_PATH.LOCAL_BLOCKER_REPAIR"]
        for fragment in (
            "missing inputs",
            "wrong or stale paths",
            "smallest successor WorkUnit",
            "Do not reopen planning unless evidence establishes a material change",
            "exact blocked scope",
            "independent useful frontiers",
        ):
            self.assertIn(fragment, blocker_repair)
        governance = critical_clauses["CRITICAL_PATH.GOVERNANCE_FLOORS"]
        for fragment in (
            "write/effect authority",
            "single mutation ownership",
            "candidate immutability",
            "truthful claim limits",
        ):
            self.assertIn(fragment, governance)
        for fragment in (
            "NO_MATERIAL_SUPPORT_WORK",
            "exactly four blocking facts",
            "Reuse is mandatory",
            "REUSED_RECEIPT",
            "same semantic run and physical attempt",
            "Use the structured role result directly",
            "at most once against the final frozen candidate",
            "named qualitative or cross-cutting product risk",
            "runtime cost tuning, not semantic invalidation",
        ):
            self.assertIn(fragment, critical)

        product = "\n".join(
            clause["text"] for clause in
            self.package.by_id["bbk-prompt-product-first-proportionality"]["clauses"]
        )
        for fragment in (
            "actor-visible product capability",
            "NO_MATERIAL_SUPPORT_WORK",
            "stable semantic interfaces",
            "Duplicate plans, reviews",
            "Stop planning and design when work is executable",
        ):
            self.assertIn(fragment, product)

        mechanical = "\n".join(
            clause["text"] for clause in
            self.package.by_id["bbk-prompt-mechanical-admission"]["clauses"]
        )
        for fragment in (
            "same semantic run and physical attempt",
            "rerun only the affected gate",
            "Do not create successor planning",
            "`bbk artifact successor` against the verified predecessor",
            "smallest affected recheck",
            "Route contradictions of meaning",
        ):
            self.assertIn(fragment, mechanical)

        assurance = "\n".join(
            clause["text"] for clause in
            self.package.by_id["bbk-prompt-assurance-modes"]["clauses"]
        )
        for fragment in (
            "Use INLINE by default",
            "Group compatible assertions",
            "Use FOCUSED",
            "Use FULL",
            "NO_MATERIAL_ASSURANCE_WORK",
            "does not accept a candidate",
        ):
            self.assertIn(fragment, assurance)

        candidate = "\n".join(
            clause["text"] for clause in
            self.package.by_id["bbk-prompt-candidate-focused-review"]["clauses"]
        )
        for fragment in (
            "named qualitative or cross-cutting product risk",
            "exact read-only verified sealed integrated `candidate-package-v1`",
            "Do not rerun tests",
            "rather than rewriting the plan",
            "revalidate failed assertions",
        ):
            self.assertIn(fragment, candidate)

        self.assertEqual(
            set(module_directives(self.method["skills"]["bbk"])),
            {
                "bbk-prompt-user-attention", "bbk-prompt-execution-autonomy",
                "bbk-prompt-host-capability-truth",
                "bbk-prompt-authority-completion-vocabulary",
                "bbk-prompt-baseline-transition",
                "bbk-prompt-critical-path-execution",
                "bbk-prompt-product-first-proportionality",
                "bbk-prompt-mechanical-admission", "bbk-prompt-assurance-modes",
                "bbk-prompt-candidate-focused-review",
                "bbk-prompt-delivery-authority", "bbk-prompt-effect-ownership",
                "bbk-prompt-coordination-economy",
            },
        )

    def test_repair_count_triggers_diagnosis_not_replanning(self) -> None:
        roles = {role["name"]: role for role in self.roles}
        for role_name in (
            "bbk_territory_orchestrator",
            "bbk_worker_orchestrator",
        ):
            with self.subTest(role=role_name):
                text = "\n".join(roles[role_name]["responsibilities"])
                self.assertNotIn("planning review by the third unresolved cycle", text)
                self.assertIn("parent diagnosis by the third unresolved cycle", text)
                self.assertIn("Cycle count alone does not reopen planning", text)
                self.assertIn("request replanning only when evidence establishes", text)

    def test_alpha16_authority_and_completion_vocabulary_is_universal_and_exact(self) -> None:
        module_id = "bbk-prompt-authority-completion-vocabulary"
        clauses = {
            clause["id"]: clause["text"]
            for clause in self.package.by_id[module_id]["clauses"]
        }
        self.assertEqual(
            set(clauses),
            {
                "AUTHORITY.WORKSPACE_IMPLEMENTATION",
                "AUTHORITY.EXTERNAL_EXECUTION",
                "AUTHORITY.PRODUCE_ONLY",
                "AUTHORITY.EXACT_NEXT_EFFECT",
                "COMPLETION.EXACT_CLAIMS",
                "COMPLETION.NO_COLLAPSE",
                "COMPLETION.EVIDENCE_DERIVED",
                "COMPLETION.BYTE_INTEGRITY_CURRENT",
            },
        )
        self.assertIn("inside the exact authorized workspace", clauses["AUTHORITY.WORKSPACE_IMPLEMENTATION"])
        self.assertIn("effects on real hosts or remote systems", self.package.by_id[module_id]["description"])
        self.assertIn("withholding EXTERNAL_EXECUTION", clauses["AUTHORITY.PRODUCE_ONLY"])
        self.assertIn("may not reinterpret a deterministic failure as a pass", clauses["COMPLETION.EVIDENCE_DERIVED"])
        self.assertIn("bbk artifact freshness", clauses["COMPLETION.BYTE_INTEGRITY_CURRENT"])
        for claim in (
            "PLANNING_COMPLETE", "IMPLEMENTATION_ARTIFACTS_COMPLETE",
            "BYTE_INTEGRITY_VERIFIED", "SEMANTIC_REVIEW_COMPLETE",
            "DEPLOYMENT_AUTHORIZED", "DEPLOYMENT_PERFORMED",
            "LIVE_ACCEPTANCE_VERIFIED",
        ):
            self.assertIn(claim, clauses["COMPLETION.EXACT_CLAIMS"])
        self.assertEqual(
            {role["name"] for role in self.roles if module_id in role["prompt_modules"]},
            {role["name"] for role in self.roles},
        )
        for host in ("omp", "codex", "claude", "generic"):
            for role in self.roles:
                rendered = instruction_text(self.spec, role, host=host)
                with self.subTest(host=host, role=role["name"]):
                    self.assertGreaterEqual(rendered.count("WORKSPACE_IMPLEMENTATION"), 2)
                    self.assertIn("PRODUCE_ONLY", rendered)
                    self.assertIn("LIVE_ACCEPTANCE_VERIFIED", rendered)

    def test_alpha15_assurance_mode_contract_enforces_proportional_selection(self) -> None:
        try:
            import jsonschema
        except ImportError as exc:  # pragma: no cover
            self.skipTest(f"optional jsonschema capability unavailable: {exc}")
        schema = json.loads(
            (ROOT / "spec/schemas/bbk-assurance-mode-v1.schema.json").read_text(encoding="utf-8")
        )
        instance = json.loads(
            (ROOT / "templates/contracts/assurance-mode.json").read_text(encoding="utf-8")
        )
        validator = jsonschema.Draft202012Validator(schema)
        validator.validate(instance)

        focused = copy.deepcopy(instance)
        focused.update({
            "mode": "FOCUSED",
            "risk_basis": ["One material interface compatibility risk."],
            "rationale": "The exact interface claim needs independent bounded review.",
            "review_focus": ["Candidate interface compatibility."],
            "recheck_scope": ["The repaired interface and its direct consumers."],
            "independent_review_required": True,
        })
        validator.validate(focused)

        invalid_inline = copy.deepcopy(instance)
        invalid_inline["independent_review_required"] = True
        self.assertTrue(list(validator.iter_errors(invalid_inline)))
        invalid_focused = copy.deepcopy(focused)
        invalid_focused["review_focus"] = []
        self.assertTrue(list(validator.iter_errors(invalid_focused)))

    def test_alpha15_prompt_size_report_is_deterministic_and_measures_all_projections(self) -> None:
        report = prompt_size_report(ROOT)
        recorded = json.loads((ROOT / "PROMPT-SIZE-REPORT.json").read_text(encoding="utf-8"))
        self.assertEqual(report, recorded)
        self.assertEqual(report["size_policy"], "MEASURED_NO_ARBITRARY_CAP")
        self.assertEqual(report["role_count"], 19)
        self.assertEqual(report["hosts"], ["generic", "omp", "codex", "claude", "pi"])
        self.assertGreater(report["aggregate"]["baseline_bytes"], 0)
        self.assertGreater(report["aggregate"]["current_bytes"], 0)
        self.assertEqual(
            report["aggregate"]["delta_bytes"],
            report["aggregate"]["current_bytes"] - report["aggregate"]["baseline_bytes"],
        )
        self.assertEqual(set(report["roles"]), {role["name"] for role in self.roles})

    def test_projection_manifest_v10_binds_method_modules_and_compiled_procedures(self) -> None:
        _outputs, manifest = expected_files()
        self.assertEqual(manifest["schema"], "bbk.projection-manifest.v10")
        self.assertEqual(manifest["method_content_source"], "spec/method-content.json")
        self.assertEqual(manifest["prompt_module_package"], "spec/prompt-modules/catalog.json")
        self.assertEqual(
            len(manifest["prompt_module_sources"]), 1 + len(self.package.modules),
        )
        self.assertRegex(manifest["method_content_source_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(manifest["prompt_module_source_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(manifest["procedure_registry_source"], "spec/procedures/catalog.json")
        self.assertRegex(manifest["procedure_registry_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(manifest["procedure_registry_revision"], r"^[0-9a-f]{64}$")
        for role in self.roles:
            agent = manifest["agents"][role["name"]]
            self.assertEqual(agent["primary_skill"], role["primary_skill"])
            self.assertEqual(agent["prompt_modules"], role["prompt_modules"])
            self.assertEqual(set(agent["compiled_procedures"]), {"codex", "omp", "claude", "generic", "pi"})
            for host, compiled in agent["compiled_procedures"].items():
                expected = list(role["mandatory_skills"])
                if role["primary_skill"] == "bbk-wayfind" and "bbk-plan" not in expected:
                    expected.insert(0, "bbk-plan")
                expected = [item for item in expected if item != role["primary_skill"]] + [role["primary_skill"]]
                self.assertEqual([item["id"] for item in compiled["procedures"]], expected, host)
                self.assertEqual(set(compiled["catalog_suppression_set"]), set(expected))
                catalog = agent["effective_external_catalogs"][host]
                self.assertFalse(set(role["mandatory_skills"]) & set(catalog["available_external_procedures"]))

    def test_unknown_role_module_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            materialize_role_assembly_fixture(ROOT, root)
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
            materialize_role_assembly_fixture(ROOT, root)
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
            materialize_role_assembly_fixture(ROOT, root)
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
            materialize_role_assembly_fixture(ROOT, root)
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
            materialize_role_assembly_fixture(ROOT, root)
            role_path = root / "spec" / "roles" / "bbk_worker-role.json"
            role = json.loads(role_path.read_text(encoding="utf-8"))
            additions = ["bbk-handoff", "bbk-recover", "bbk-implementation-structure"]
            self.assertTrue(set(additions) <= set(role["skills"]))
            role["mandatory_skills"] = [role["primary_skill"], *additions]
            package = load_prompt_modules(root)
            method_path = root / "spec" / "method-content.json"
            method = json.loads(method_path.read_text(encoding="utf-8"))
            required = set(role_skill_module_requirements(
                role, method["skills"], method["skill_module_dependencies"],
            ))
            selected = set(role["prompt_modules"]) | required
            role["prompt_modules"] = [
                module_id for module_id in package.ordered_ids if module_id in selected
            ]
            role_path.write_bytes(canonical_bytes(role))

            catalog_path = root / "spec" / "prompt-modules" / "catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
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
            materialize_role_assembly_fixture(ROOT, root)
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
            materialize_role_assembly_fixture(ROOT, root)
            path = root / "spec" / "roles" / "bbk_worker-role.json"
            role = json.loads(path.read_text(encoding="utf-8"))
            required = next(iter(role_skill_module_requirements(
                role, self.method["skills"], self.method["skill_module_dependencies"],
                include_all_loaded_skills=True,
            )))
            role["prompt_modules"].remove(required)
            path.write_bytes(canonical_bytes(role))
            with self.assertRaises(RolePackageError) as caught:
                assemble(root)
            self.assertIn(
                "loaded skills require unassigned prompt modules",
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

# Deterministic fast/standard/release selection used by tools/run_tests.py.
from tests._test_profiles import load_profiled_tests as load_tests

