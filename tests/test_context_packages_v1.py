from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import artifact_packages
import context_packages
import host_preflight
from strict_json import load_path


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(artifact_packages.canonical_json_bytes(value))


def profile_lock() -> dict:
    return {
        "schema": "bbk.profile-lock.v1",
        "bbkVersion": "0.1.0-alpha.16.1",
        "profileId": "python",
        "profileVersion": "1",
        "profileRootDigest": "1" * 64,
        "effectiveDigest": "2" * 64,
        "inputs": {"source": "test"},
    }


def preflight(*, blocked: bool = False) -> dict:
    requirement = (
        {"id": "required-live", "kind": "LIVE", "required": True, "description": "confirm exact live target"}
        if blocked
        else {"id": "python", "kind": "COMMAND", "required": True, "command": Path(sys.executable).name, "versionArgs": ["--version"]}
    )
    return host_preflight.run_preflight({
        "schema": "bbk.host-preflight-request.v1",
        "requestId": "HP-CONTEXT",
        "freshnessSeconds": 0,
        "requirements": [requirement],
    }, use_cache=False)


def worker() -> dict:
    return json.loads((ROOT / "templates" / "work-unit.json").read_text(encoding="utf-8"))


def make_candidate(base: Path, *, package_id: str = "CAND-1") -> Path:
    draft = base / "candidate-draft"
    draft.mkdir(parents=True)
    semantic = {
        "schema": "bbk.candidate-package.v1",
        "id": package_id,
        "subject": {"kind": "candidate", "id": package_id, "revision": "1"},
        "summary": "Integrated candidate for exact review.",
        "governingReferences": ["SOF-1@r1"],
        "includedArtifacts": ["candidate-record"],
        "authorityBoundary": "This candidate is not accepted or released merely because it is sealed.",
    }
    write_json(draft / "candidate.json", semantic)
    write_json(draft / artifact_packages.DRAFT_FILE, {
        "schema": "bbk.artifact-package-draft.v1",
        "packageId": package_id,
        "revision": "1",
        "profile": {"id": "candidate-package-v1", "version": "1"},
        "subject": semantic["subject"],
        "predecessor": None,
        "artifacts": [{
            "artifactId": "candidate-record",
            "path": "candidate.json",
            "schema": "bbk.candidate-package.v1",
            "role": "candidate",
            "references": [],
        }],
        "metadata": {"test": True},
    })
    sealed = base / "candidate-sealed"
    artifact_packages.seal_draft(draft, sealed)
    return sealed


def review_request(mode: str = "REVIEW") -> dict:
    assurance = json.loads((ROOT / "templates" / "contracts" / "assurance-mode.json").read_text(encoding="utf-8"))
    assurance["mode"] = "FOCUSED"
    assurance["independent_review_required"] = True
    assurance["review_focus"] = ["candidate claim"]
    base = {"schema": "bbk.review-package-request.v1", "mode": mode, "assuranceMode": assurance}
    if mode == "REVIEW":
        base.update({"exactFocus": {"claim": "candidate claim"}, "applicableFloors": ["no release claim"], "priorFindings": []})
    else:
        base.update({
            "finding": {"id": "F-1", "statement": "exact defect"},
            "affectedScope": ["candidate.json#/summary"],
            "relevantEvidence": ["E-1"],
            "reopeningTriggers": ["candidate digest changes outside affected scope"],
            "semanticChange": False,
        })
    return base


class ContextPackageV1Tests(unittest.TestCase):
    def test_complete_worker_context_is_sealed_and_exactly_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "worker-package"
            result = context_packages.compile_worker_context(worker(), profile_lock(), preflight(), output_root=output)
            self.assertEqual(result["status"], "COMPILED")
            self.assertEqual(result["admissionStatus"], "ELIGIBLE")
            self.assertEqual(artifact_packages.verify_package(output)["status"], "PASS")
            value = load_path(output / "worker-context.json")
            self.assertEqual(value["compiledFrom"]["workUnitId"], "WU-QUERY-SERVICE")
            self.assertEqual(value["profileLock"]["effectiveDigest"], "2" * 64)
            self.assertEqual(value["hostPreflight"]["host"]["digest"], preflight()["host"]["digest"])
            self.assertIn("does not create authority", value["authorityBoundary"])

    def test_incomplete_semantics_return_specialist_without_output_mutation(self) -> None:
        value = worker()
        value.pop("authorityGrant")
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "must-not-exist"
            result = context_packages.compile_worker_context(value, profile_lock(), preflight(), output_root=output)
            self.assertEqual(result["status"], "SPECIALIST_DESIGN_REQUIRED")
            self.assertIn("work_unit.authorityGrant", result["missingOrAmbiguousSemantics"])
            self.assertFalse(output.exists())

    def test_tampered_host_identity_is_not_admitted(self) -> None:
        host = preflight()
        host["host"]["node"] = "tampered"
        with tempfile.TemporaryDirectory() as temp:
            result = context_packages.compile_worker_context(worker(), profile_lock(), host, output_root=Path(temp) / "out")
        self.assertEqual(result["status"], "SPECIALIST_DESIGN_REQUIRED")
        self.assertTrue(any("host.digest" in item for item in result["missingOrAmbiguousSemantics"]))

    def test_required_host_blocker_is_preserved_without_inventing_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "blocked"
            result = context_packages.compile_worker_context(worker(), profile_lock(), preflight(blocked=True), output_root=output)
            self.assertEqual(result["status"], "COMPILED")
            self.assertEqual(result["admissionStatus"], "BLOCKED_BY_HOST_PREFLIGHT")
            value = load_path(output / "worker-context.json")
            self.assertEqual(value["admission"]["blockers"][0]["capabilityId"], "required-live")
            self.assertEqual(value["smallestValidNextAction"], "Resolve required host blockers before mutation.")

    def test_prototype_work_requires_a_valid_v2_charter(self) -> None:
        value = worker()
        value["role"] = "prototyper"
        value["taskProfile"] = "prototype"
        charter = json.loads((ROOT / "templates" / "prototype-charter-v2.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            missing = context_packages.compile_worker_context(value, profile_lock(), preflight(), output_root=base / "missing")
            self.assertEqual(missing["status"], "SPECIALIST_DESIGN_REQUIRED")
            invalid = copy.deepcopy(charter); invalid.pop("fallback")
            rejected = context_packages.compile_worker_context(value, profile_lock(), preflight(), prototype_charter=invalid, output_root=base / "invalid")
            self.assertEqual(rejected["status"], "SPECIALIST_DESIGN_REQUIRED")
            compiled = context_packages.compile_worker_context(value, profile_lock(), preflight(), prototype_charter=charter, output_root=base / "valid")
            self.assertEqual(compiled["status"], "COMPILED")

    def test_review_package_is_candidate_digest_bound_and_reviewer_does_not_author_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            candidate = make_candidate(base)
            output = base / "review"
            result = context_packages.compile_review_package(candidate, review_request(), output_root=output)
            self.assertEqual(result["status"], "COMPILED")
            self.assertEqual(artifact_packages.verify_package(output)["status"], "PASS")
            value = load_path(output / "review-package.json")
            candidate_control = load_path(candidate / "bbk-package.json")
            self.assertEqual(value["candidate"]["contentSha256"], candidate_control["contentSha256"])
            self.assertIn("findings", value["reviewerOutputContract"]["produce"])
            self.assertIn("candidate mutation", value["reviewerOutputContract"]["prohibited"])

    def test_focused_recheck_is_finding_scoped_and_broader_context_requires_semantic_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            candidate = make_candidate(base)
            exact = review_request("FOCUSED_RECHECK")
            output = base / "recheck"
            result = context_packages.compile_review_package(candidate, exact, output_root=output)
            self.assertEqual(result["status"], "COMPILED")
            value = load_path(output / "review-package.json")
            self.assertEqual(set(value["recheck"]), {"finding", "successorCandidate", "affectedScope", "relevantEvidence", "reopeningTriggers", "semanticChange"})
            broad = review_request("FOCUSED_RECHECK")
            broad["broaderReviewContext"] = {"scope": ["unaffected subsystem"]}
            rejected = context_packages.compile_review_package(candidate, broad, output_root=base / "must-not-exist")
            self.assertEqual(rejected["status"], "SPECIALIST_DESIGN_REQUIRED")
            self.assertFalse((base / "must-not-exist").exists())
            broad["semanticChange"] = True
            accepted = context_packages.compile_review_package(candidate, broad, output_root=base / "broad")
            self.assertEqual(accepted["status"], "COMPILED")

    def test_invalid_or_tampered_candidate_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            candidate = make_candidate(base)
            (candidate / "candidate.json").write_text("tampered", encoding="utf-8")
            with self.assertRaises(context_packages.ContextPackageError):
                context_packages.compile_review_package(candidate, review_request(), output_root=base / "review")
            self.assertFalse((base / "review").exists())

    def test_review_request_template_validates(self) -> None:
        value = json.loads((ROOT / "templates" / "review-package-request.json").read_text(encoding="utf-8"))
        self.assertEqual(artifact_packages.validate_schema_instance(value, "bbk.review-package-request.v1"), [])


if __name__ == "__main__":
    unittest.main()
