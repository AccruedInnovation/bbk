from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import bbk_jsonl_analyzer as analyzer  # noqa: E402
import evaluate_alpha17_gates as evaluator  # noqa: E402


def rec(timestamp: str, record_type: str, payload: dict) -> str:
    return json.dumps({"timestamp": timestamp, "type": record_type, "payload": payload}, separators=(",", ":")) + "\n"


class Alpha17GateEvaluatorTests(unittest.TestCase):
    def _write_inputs(self, root: Path, *, catalog: list[str] | None = None) -> tuple[Path, Path, Path, Path, dict, dict]:
        catalog = ["optional-helper"] if catalog is None else catalog
        prompt = "base\n\n### Compiled primary procedure: `bbk-work-unit-execution`\nbody\n\n## End compiled procedures\n"
        prompt_digest = hashlib.sha256(prompt.encode()).hexdigest()
        catalog_digest = evaluator.compact_digest(catalog)
        manifest = {
            "schema": "bbk.compiled-procedure-manifest.v1", "role": "bbk_worker", "harness": "CODEX",
            "compiled_prompt_sha256": prompt_digest, "effective_external_catalog_sha256": catalog_digest,
            "procedures": [{
                "id": "bbk-work-unit-execution", "selection_reason": "PRIMARY",
                "catalog_visibility": "SUPPRESSED", "state": "COMPILED_COMPLETE", "ordering": 0,
            }],
            "catalog_suppression_set": ["bbk-work-unit-execution"],
        }
        readiness = {
            "schema": "bbk.planning-readiness.v1", "readiness": ["ROADMAP_READY", "FRONTIER_READY"],
            "execution_admissible": True, "frontier_ref": {"id": "frontier"},
            "deferred_refinements": [{"id": "later", "status": "DEFERRED_UNTIL_FRONTIER"}],
        }
        paths = (root / "manifest.json", root / "catalog.json", root / "readiness.json", root / "prompt.txt")
        paths[0].write_text(json.dumps(manifest), encoding="utf-8")
        paths[1].write_text(json.dumps(catalog), encoding="utf-8")
        paths[2].write_text(json.dumps(readiness), encoding="utf-8")
        paths[3].write_text(prompt, encoding="utf-8")
        return *paths, manifest, readiness

    def _analyze(self, root: Path, content: str) -> Path:
        log = root / "run.jsonl"
        log.write_text(content, encoding="utf-8")
        analysis = root / "analysis"
        instance = analyzer.Analyzer(analyzer.load_config(str(HERE / "alpha17-config.json")))
        instance.analyze_sources(analyzer.discover_sources([str(log)]))
        instance.write_report(analysis, "synthetic-alpha17")
        return analysis

    def test_typed_acceptance_report_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path, catalog_path, readiness_path, prompt_path, manifest, readiness = self._write_inputs(root)
            compile_event = {
                "schema": "bbk.prompt-compilation-event.v1", "event": "PROMPT_COMPILED",
                "logical_child_id": "child:worker", "physical_attempt_id": "attempt:1",
                "identity_kind": "ROLE", "role": "bbk_worker", "harness": "CODEX",
                "effective_prompt_sha256": manifest["compiled_prompt_sha256"],
                "procedure_ids": ["bbk-work-unit-execution"],
                "external_catalog_sha256": manifest["effective_external_catalog_sha256"],
                "source_reads_by_compiler": 1, "procedure_reads_by_model": 0, "reused": False,
            }
            reuse_event = dict(compile_event, event="PROMPT_REUSED", source_reads_by_compiler=0, reused=True)
            worker_event = {
                "schema": "bbk.child-event.v1", "child_ref": "child:worker:execution", "state": "STARTED",
                "detail": {"role": "bbk_worker"}, "observed_at": "2026-08-06T00:00:04Z", "poll_required": False,
            }
            content = rec("2026-08-06T00:00:00Z", "session_meta", {"id": "root", "session_id": "root", "thread_source": "user"})
            content += rec("2026-08-06T00:00:01Z", "event_msg", compile_event)
            content += rec("2026-08-06T00:00:02Z", "response_item", {"type": "function_call", "name": "followup_task", "namespace": "collaboration", "call_id": "f1", "arguments": json.dumps({"target": "child:worker", "message": "continue"})})
            content += rec("2026-08-06T00:00:03Z", "event_msg", reuse_event)
            content += rec("2026-08-06T00:00:04Z", "event_msg", readiness)
            content += rec("2026-08-06T00:00:05Z", "event_msg", worker_event)
            analysis = self._analyze(root, content)
            report = evaluator.evaluate(analysis_dir=analysis, manifest_path=manifest_path, catalog_path=catalog_path, readiness_path=readiness_path, prompt_path=prompt_path)
            self.assertEqual("PASS", report["status"])
            self.assertFalse(report["failed_gate_ids"])

    def test_magic_words_in_message_text_do_not_pass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path, catalog_path, readiness_path, prompt_path, _, _ = self._write_inputs(root)
            content = rec("2026-08-06T00:00:00Z", "session_meta", {"id": "root", "session_id": "root", "thread_source": "user"})
            content += rec("2026-08-06T00:00:01Z", "response_item", {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "COMPILED_COMPLETE FOLLOWUP_REUSED source_read_count 0 ROADMAP_READY FRONTIER_READY DEFERRED_UNTIL_FRONTIER worker_started"}]})
            analysis = self._analyze(root, content)
            report = evaluator.evaluate(analysis_dir=analysis, manifest_path=manifest_path, catalog_path=catalog_path, readiness_path=readiness_path, prompt_path=prompt_path)
            self.assertEqual("FAIL", report["status"])
            self.assertIn("A17-CP-TYPED-COMPILE", report["failed_gate_ids"])
            self.assertIn("A17-CP-FOLLOWUP-REUSE", report["failed_gate_ids"])
            self.assertIn("A17-RW-FRONTIER-EXECUTION", report["failed_gate_ids"])

    def test_test_specific_gate_subset(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path, catalog_path, readiness_path, prompt_path, manifest, _ = self._write_inputs(root)
            event = {
                "schema": "bbk.prompt-compilation-event.v1", "event": "PROMPT_COMPILED",
                "logical_child_id": "child:worker", "physical_attempt_id": "attempt:1", "identity_kind": "ROLE",
                "role": "bbk_worker", "harness": "CODEX", "effective_prompt_sha256": manifest["compiled_prompt_sha256"],
                "procedure_ids": ["bbk-work-unit-execution"], "external_catalog_sha256": manifest["effective_external_catalog_sha256"],
                "source_reads_by_compiler": 1, "procedure_reads_by_model": 0, "reused": False,
            }
            analysis = self._analyze(root, rec("2026-08-06T00:00:01Z", "event_msg", event))
            report = evaluator.evaluate(analysis_dir=analysis, manifest_path=manifest_path, catalog_path=catalog_path, readiness_path=readiness_path, prompt_path=prompt_path, test_id="MH-CODEX-01")
            self.assertEqual("PASS", report["status"])

    def test_catalog_overlap_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path, catalog_path, readiness_path, prompt_path, _, _ = self._write_inputs(root, catalog=["bbk-work-unit-execution"])
            analysis = self._analyze(root, "")
            report = evaluator.evaluate(analysis_dir=analysis, manifest_path=manifest_path, catalog_path=catalog_path, readiness_path=readiness_path, prompt_path=prompt_path, test_id="MH-CODEX-01")
            failed = {item["id"] for item in report["gates"] if item["status"] == "FAIL"}
            self.assertIn("A17-CP-CATALOG-SUPPRESSED", failed)

    def test_actual_effective_catalog_projection_is_accepted(self):
        value = {"schema": "bbk.effective-procedure-catalog.v2", "available_external_procedures": ["optional-procedure"], "suppressed_compiled_procedures": ["bbk-work-unit-execution"]}
        self.assertEqual(["optional-procedure"], evaluator._catalog_ids(value))


if __name__ == "__main__":
    unittest.main()
