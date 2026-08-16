from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import identity_graph


def schema(name: str) -> dict:
    return json.loads((ROOT / "spec" / "schemas" / name).read_text(encoding="utf-8"))


class M4IdentityGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.subject = {"kind": "candidate", "id": "c1", "revision": "r1", "digest": "a" * 64}

    def _node(self, kind: str, node_id: str, *, payload=None, metadata=None, inputs=(), content=None):
        return identity_graph.derive_identity(
            kind,
            subject=self.subject,
            revision="r1",
            payload=payload,
            derivation_inputs=inputs,
            content_sha256=content,
            metadata=metadata,
            node_id=node_id,
        )

    def _graph(self, *, product_payload=b"product-v1", carrier_metadata=None):
        product = self._node("PRODUCT_PAYLOAD", "product", payload=product_payload)
        package = self._node("COMPLETE_PACKAGE", "package", content="b" * 64)
        carrier = self._node("CARRIER", "carrier", metadata=carrier_metadata or {"format": "json"})
        method = self._node("METHOD", "method", metadata={"name": "focused"})
        environment = self._node("ENVIRONMENT_OR_MIRROR", "environment", metadata={"python": "3.13"})
        attempt = self._node("ASSURANCE_ATTEMPT", "attempt", metadata={"sequence": 1})
        evidence = self._node("EVIDENCE_BUNDLE", "evidence", metadata={"verification_external": True, "self_attesting": False, "subject_digest": self.subject["digest"]}, inputs=[{"node_id": "attempt", "kind": "ASSURANCE_ATTEMPT", "revision": "r1", "digest": attempt["digest"]}])
        publication = self._node("PUBLICATION", "publication", inputs=[{"node_id": "package", "kind": "COMPLETE_PACKAGE", "revision": "r1", "digest": package["digest"]}])
        handoff = self._node("HANDOFF", "handoff", metadata={"evidence_cutoff": 1, "sealed_after_cutoff": True, "sealed_sequence": 2, "verification_external": True}, inputs=[{"node_id": "evidence", "kind": "EVIDENCE_BUNDLE", "revision": "r1", "digest": evidence["digest"]}])
        nodes = [product, package, carrier, method, environment, attempt, evidence, publication, handoff]
        rel = []
        for index, (source, target, scope) in enumerate((("package", "product", "PRODUCT"), ("carrier", "package", "SUPPORTING"), ("attempt", "method", "SUPPORTING"), ("attempt", "environment", "SUPPORTING"), ("evidence", "attempt", "SUPPORTING"), ("publication", "package", "EXTERNAL"), ("handoff", "evidence", "EXTERNAL"))):
            rel.append({"relation_id": f"rel-{index}", "kind": "DEPENDS_ON", "from_node": source, "to_node": target, "dependency_scope": scope})
        return identity_graph.build_graph("g1", subject=self.subject, revision="r1", nodes=nodes, relations=rel)

    def test_schema_is_additive_and_closed_to_exact_nine_kinds(self) -> None:
        graph = self._graph()
        jsonschema.Draft202012Validator(schema("bbk-identity-graph-v1.schema.json")).validate(graph)
        self.assertEqual(set(identity_graph.IDENTITY_KINDS), {node["kind"] for node in graph["nodes"]})
        self.assertEqual(len(identity_graph.IDENTITY_KINDS), 9)
        self.assertEqual(graph["nodes"][1]["contentSha256"], "b" * 64)

    def test_product_change_requires_successor_and_transitively_invalidates_dependents(self) -> None:
        previous = self._graph()
        current = self._graph(product_payload=b"product-v2")
        result = identity_graph.targeted_invalidation(previous, current)
        self.assertTrue(result["product_successor_required"])
        self.assertEqual(result["targeted_invalidations"], ["carrier", "package", "product", "publication"])

    def test_carrier_change_is_local_and_does_not_create_product_successor(self) -> None:
        previous = self._graph()
        current = self._graph(carrier_metadata={"format": "cbor"})
        result = identity_graph.targeted_invalidation(previous, current)
        self.assertFalse(result["product_successor_required"])
        self.assertEqual(result["targeted_invalidations"], ["carrier"])

    def test_fail_closed_negative_identity_transitions(self) -> None:
        with self.assertRaisesRegex(identity_graph.IdentityGraphError, "IDENTITY_ZERO_PAYLOAD"):
            self._node("PRODUCT_PAYLOAD", "zero")
        with self.assertRaisesRegex(identity_graph.IdentityGraphError, "IDENTITY_KIND_SUBSTITUTION"):
            previous = self._graph()
            current = self._graph()
            current["nodes"][0]["kind"] = "CARRIER"
            identity_graph.targeted_invalidation(previous, current)
        with self.assertRaisesRegex(identity_graph.IdentityGraphError, "IDENTITY_SUBJECT_MISMATCH"):
            wrong = dict(self.subject, digest="c" * 64)
            self._node("PRODUCT_PAYLOAD", "wrong", payload=b"x", metadata=None)
            identity_graph.validate_graph({**self._graph(), "subject": wrong})
        with self.assertRaisesRegex(identity_graph.IdentityGraphError, "IDENTITY_INTEGRITY_MISMATCH"):
            self._node("COMPLETE_PACKAGE", "bad", content="c" * 64, payload=b"package")
        with self.assertRaisesRegex(identity_graph.IdentityGraphError, "IDENTITY_SELF_ATTESTING_EVIDENCE"):
            self._node("EVIDENCE_BUNDLE", "evidence-self", metadata={"verification_external": True, "self_attesting": True, "subject_digest": self.subject["digest"]}, inputs=[{"node_id": "attempt", "kind": "ASSURANCE_ATTEMPT", "revision": "r1", "digest": "d" * 64}])

    def test_adapters_are_deterministic_and_handoff_requires_external_cutoff(self) -> None:
        artifact = identity_graph.identity_from_artifact({"packageId": "p", "revision": "r1", "contentSha256": "b" * 64}, subject=self.subject)
        candidate = identity_graph.identity_from_candidate({"candidateId": "c", "revision": "r1", "contentSha256": "b" * 64}, subject=self.subject)
        method = identity_graph.identity_from_method({"method_id": "m", "revision": "r1", "metadata": {"name": "m"}}, subject=self.subject)
        environment = identity_graph.identity_from_environment({"environment_id": "env", "metadata": {"os": "windows"}}, subject=self.subject)
        attempt = identity_graph.identity_from_attempt({"attempt_id": "a", "revision": "r1", "metadata": {"seq": 1}}, subject=self.subject)
        evidence = identity_graph.identity_from_evidence({"receiptId": "e", "verification_external": True, "self_attesting": False, "derivation_inputs": [{"node_id": "attempt", "kind": "ASSURANCE_ATTEMPT", "revision": "r1", "digest": "d" * 64}]}, subject=self.subject)
        self.assertEqual(artifact["contentSha256"], candidate["contentSha256"])
        self.assertEqual({artifact["kind"], candidate["kind"], method["kind"], environment["kind"], attempt["kind"], evidence["kind"]}, {"COMPLETE_PACKAGE", "METHOD", "ENVIRONMENT_OR_MIRROR", "ASSURANCE_ATTEMPT", "EVIDENCE_BUNDLE"})
        with self.assertRaisesRegex(identity_graph.IdentityGraphError, "IDENTITY_EXTERNAL_VERIFICATION_REQUIRED"):
            identity_graph.identity_from_handoff({"id": "h", "evidence_cutoff": 1, "sealed_after_cutoff": True, "derivation_inputs": [{"node_id": "e", "kind": "EVIDENCE_BUNDLE", "revision": "r1", "digest": "e" * 64}]}, subject=self.subject)
        handoff = identity_graph.identity_from_handoff({"id": "h", "evidence_cutoff": 1, "sealed_after_cutoff": True, "verification_external": True, "derivation_inputs": [{"node_id": "e", "kind": "EVIDENCE_BUNDLE", "revision": "r1", "digest": "e" * 64}]}, subject=self.subject)
        self.assertEqual(handoff["kind"], "HANDOFF")
        self.assertTrue(handoff["metadata"]["freshness_external"])


if __name__ == "__main__":
    unittest.main()
