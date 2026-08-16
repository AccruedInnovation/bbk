"""Canonical typed identity graph derivation and fail-closed adapters for M4."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

IDENTITY_KINDS = (
    "PRODUCT_PAYLOAD", "COMPLETE_PACKAGE", "CARRIER", "METHOD",
    "ENVIRONMENT_OR_MIRROR", "ASSURANCE_ATTEMPT", "EVIDENCE_BUNDLE",
    "PUBLICATION", "HANDOFF",
)
RELATION_KINDS = ("DERIVED_FROM", "DEPENDS_ON", "INVALIDATES", "EVIDENCE_FOR", "SEALED_BY", "VERIFIED_BY")
POLICY = {
    "canonicalization": "JCS_SORTED_UTF8",
    "product_successor_rule": "PRODUCT_PAYLOAD_OR_DECLARED_PRODUCT_DEPENDENCY",
    "zero_payload_rule": "FAIL_CLOSED",
    "external_verification_rule": "VERIFICATION_AND_FRESHNESS_REMAIN_EXTERNAL",
}
SCHEMA = "bbk.identity-graph.v1"
_HEX = set("0123456789abcdef")


class IdentityGraphError(ValueError):
    """A deterministic identity graph rejection with a stable code."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_value(value: Any) -> str:
    return sha256_bytes(value if isinstance(value, bytes) else canonical_bytes(value))


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in _HEX for ch in value):
        raise IdentityGraphError("IDENTITY_DIGEST_INVALID", f"{label} must be a lowercase SHA-256 digest")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise IdentityGraphError("IDENTITY_FIELD_REQUIRED", f"{label} must be a non-empty string")
    return value


def _kind(value: Any) -> str:
    if value not in IDENTITY_KINDS:
        raise IdentityGraphError("IDENTITY_KIND_INVALID", f"identity kind is not closed: {value!r}")
    return str(value)


def subject_ref(subject: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(subject, Mapping):
        raise IdentityGraphError("IDENTITY_SUBJECT_INVALID", "subject must be an object")
    return {
        "kind": _text(subject.get("kind"), "subject.kind"),
        "id": _text(subject.get("id"), "subject.id"),
        "revision": _text(subject.get("revision"), "subject.revision"),
        "digest": _sha(subject.get("digest"), "subject.digest"),
    }


def _ref(value: Mapping[str, Any], label: str = "reference") -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise IdentityGraphError("IDENTITY_REFERENCE_INVALID", f"{label} must be an object")
    return {
        "node_id": _text(value.get("node_id"), f"{label}.node_id"),
        "kind": _kind(value.get("kind")),
        "revision": _text(value.get("revision"), f"{label}.revision"),
        "digest": _sha(value.get("digest"), f"{label}.digest"),
    }


def _node_basis(kind: str, subject: Mapping[str, Any], revision: str,
                derivation_inputs: Sequence[Mapping[str, Any]],
                dependency_edges: Sequence[Mapping[str, Any]], metadata: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind,
        "subject": dict(subject),
        "revision": revision,
        "derivation_inputs": list(derivation_inputs),
        "dependency_edges": list(dependency_edges),
        "metadata": dict(metadata),
    }


def _node_id(kind: str, subject: Mapping[str, Any], node_id: str | None) -> str:
    return _text(node_id or f"{kind.lower()}.{subject['id']}", "node_id")


def derive_identity(
    kind: str,
    *,
    subject: Mapping[str, Any],
    revision: str,
    payload: bytes | bytearray | str | Mapping[str, Any] | Sequence[Any] | None = None,
    derivation_inputs: Iterable[Mapping[str, Any]] = (),
    dependency_edges: Iterable[Mapping[str, Any]] = (),
    content_sha256: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    node_id: str | None = None,
) -> dict[str, Any]:
    """Derive one exact typed node without replacing package identity semantics."""
    kind = _kind(kind)
    subject_value = subject_ref(subject)
    revision = _text(revision, "revision")
    inputs = [_ref(value, "derivation_inputs") for value in derivation_inputs]
    dependencies = [_ref(value, "dependency_edges") for value in dependency_edges]
    meta = dict(metadata or {})
    resolved_node_id = _node_id(kind, subject_value, node_id)
    if payload is None and kind == "PRODUCT_PAYLOAD":
        raise IdentityGraphError("IDENTITY_ZERO_PAYLOAD", "a product semantic successor requires payload bytes")
    if payload is None and not inputs and kind not in {"METHOD", "ENVIRONMENT_OR_MIRROR", "ASSURANCE_ATTEMPT", "CARRIER"} and not (kind == "COMPLETE_PACKAGE" and content_sha256):
        raise IdentityGraphError("IDENTITY_ZERO_PAYLOAD", "a semantic successor requires payload or derivation inputs")
    payload_digest = None
    if payload is not None:
        payload_digest = digest_value(payload)
    if content_sha256 is not None:
        _sha(content_sha256, "contentSha256")
    if kind == "COMPLETE_PACKAGE":
        if payload_digest is None and content_sha256 is None:
            raise IdentityGraphError("IDENTITY_PACKAGE_DIGEST_REQUIRED", "complete packages require contentSha256")
        content_sha256 = content_sha256 or payload_digest
        if payload_digest is not None and content_sha256 != payload_digest:
            raise IdentityGraphError("IDENTITY_INTEGRITY_MISMATCH", "contentSha256 does not match package payload")
    if kind == "HANDOFF":
        _validate_handoff_metadata(meta)
    if kind == "EVIDENCE_BUNDLE":
        evidence_meta = dict(meta)
        evidence_meta.setdefault("node_id", resolved_node_id)
        _validate_evidence_metadata(evidence_meta, subject_value)
    basis = _node_basis(kind, subject_value, revision, inputs, dependencies, meta)
    digest = payload_digest or (content_sha256 if kind == "COMPLETE_PACKAGE" else digest_value(basis))
    node = {
        "node_id": resolved_node_id, "kind": kind, "subject": subject_value,
        "revision": revision, "digest": digest,
        "derivation_inputs": inputs, "dependency_edges": dependencies, "metadata": meta,
    }
    if content_sha256 is not None:
        node["contentSha256"] = content_sha256
    return node


def _validate_handoff_metadata(metadata: Mapping[str, Any]) -> None:
    cutoff = metadata.get("evidence_cutoff")
    if not isinstance(cutoff, int) or cutoff < 0:
        raise IdentityGraphError("IDENTITY_HANDOFF_CUTOFF_REQUIRED", "handoff evidence cutoff must be a non-negative sequence")
    if metadata.get("sealed_after_cutoff") is not True:
        raise IdentityGraphError("IDENTITY_HANDOFF_CUTOFF_ORDER", "handoff evidence cutoff must precede sealing")
    sealed_sequence = metadata.get("sealed_sequence")
    if sealed_sequence is not None and (not isinstance(sealed_sequence, int) or sealed_sequence <= cutoff):
        raise IdentityGraphError("IDENTITY_HANDOFF_CUTOFF_ORDER", "handoff sealing sequence must follow evidence cutoff")
    if metadata.get("verification_external") is not True:
        raise IdentityGraphError("IDENTITY_EXTERNAL_VERIFICATION_REQUIRED", "handoff verification and freshness remain external")
    if metadata.get("freshness_external") is False:
        raise IdentityGraphError("IDENTITY_EXTERNAL_VERIFICATION_REQUIRED", "handoff freshness verification must remain external")


def _validate_evidence_metadata(metadata: Mapping[str, Any], subject: Mapping[str, Any]) -> None:
    if metadata.get("self_attesting") is not False or metadata.get("producer_node_id") == metadata.get("node_id"):
        raise IdentityGraphError("IDENTITY_SELF_ATTESTING_EVIDENCE", "evidence cannot attest its own identity")
    if metadata.get("verification_external") is not True:
        raise IdentityGraphError("IDENTITY_EXTERNAL_VERIFICATION_REQUIRED", "evidence verification must remain external")
    if metadata.get("subject_digest") != subject["digest"]:
        raise IdentityGraphError("IDENTITY_SUBJECT_MISMATCH", "evidence subject digest mismatch")


def validate_node(node: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(node, Mapping):
        raise IdentityGraphError("IDENTITY_NODE_INVALID", "node must be an object")
    kind = _kind(node.get("kind"))
    subject = subject_ref(node.get("subject"))
    revision = _text(node.get("revision"), "node.revision")
    digest = _sha(node.get("digest"), "node.digest")
    result = {
        "node_id": _text(node.get("node_id"), "node_id"), "kind": kind, "subject": subject,
        "revision": revision, "digest": digest,
        "derivation_inputs": [_ref(v, "derivation_inputs") for v in node.get("derivation_inputs", ())],
        "dependency_edges": [_ref(v, "dependency_edges") for v in node.get("dependency_edges", ())],
        "metadata": dict(node.get("metadata") or {}),
    }
    if "contentSha256" in node:
        result["contentSha256"] = _sha(node["contentSha256"], "contentSha256")
    if kind == "COMPLETE_PACKAGE":
        if result.get("contentSha256") != digest:
            raise IdentityGraphError("IDENTITY_INTEGRITY_MISMATCH", "complete-package digest must preserve contentSha256")
    if kind == "HANDOFF":
        _validate_handoff_metadata(result["metadata"])
    if kind == "EVIDENCE_BUNDLE":
        meta = dict(result["metadata"])
        meta.setdefault("node_id", result["node_id"])
        _validate_evidence_metadata(meta, subject)
    return result


def build_graph(graph_id: str, *, subject: Mapping[str, Any], revision: str,
                nodes: Sequence[Mapping[str, Any]], relations: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    graph = {
        "schema": SCHEMA, "graph_id": _text(graph_id, "graph_id"), "revision": _text(revision, "revision"),
        "subject": subject_ref(subject), "nodes": [validate_node(node) for node in nodes],
        "relations": [dict(relation) for relation in relations], "policy": deepcopy(POLICY),
    }
    validate_graph(graph)
    return graph


def validate_graph(graph: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(graph, Mapping) or graph.get("schema") != SCHEMA:
        raise IdentityGraphError("IDENTITY_GRAPH_SCHEMA", "identity graph schema is unsupported")
    subject_ref(graph.get("subject"))
    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise IdentityGraphError("IDENTITY_GRAPH_NODES", "identity graph requires nodes")
    by_id: dict[str, dict[str, Any]] = {}
    for raw in nodes:
        node = validate_node(raw)
        if node["node_id"] in by_id:
            raise IdentityGraphError("IDENTITY_DUPLICATE_NODE", node["node_id"])
        if node["subject"] != graph["subject"] and node["kind"] == "PRODUCT_PAYLOAD":
            raise IdentityGraphError("IDENTITY_SUBJECT_MISMATCH", "product payload subject differs from graph subject")
        by_id[node["node_id"]] = node
    relation_ids: set[str] = set()
    for relation in graph.get("relations", ()):
        if not isinstance(relation, Mapping):
            raise IdentityGraphError("IDENTITY_RELATION_INVALID", "relation must be an object")
        rid = _text(relation.get("relation_id"), "relation_id")
        if rid in relation_ids:
            raise IdentityGraphError("IDENTITY_DUPLICATE_RELATION", rid)
        relation_ids.add(rid)
        if relation.get("kind") not in RELATION_KINDS:
            raise IdentityGraphError("IDENTITY_RELATION_KIND_INVALID", str(relation.get("kind")))
        source, target = relation.get("from_node"), relation.get("to_node")
        if source not in by_id or target not in by_id or source == target:
            raise IdentityGraphError("IDENTITY_RELATION_ENDPOINT", "relation endpoint is missing or self-referential")
        if relation.get("dependency_scope") not in {"PRODUCT", "SUPPORTING", "EXTERNAL"}:
            raise IdentityGraphError("IDENTITY_DEPENDENCY_SCOPE_INVALID", str(relation.get("dependency_scope")))
        source_node, target_node = by_id[source], by_id[target]
        if relation.get("kind") in {"DERIVED_FROM", "DEPENDS_ON", "EVIDENCE_FOR", "SEALED_BY", "VERIFIED_BY"}:
            expected = {"node_id": target_node["node_id"], "kind": target_node["kind"], "revision": target_node["revision"], "digest": target_node["digest"]}
            for field in ("from_node", "to_node"):
                if not isinstance(relation[field], str):
                    raise IdentityGraphError("IDENTITY_RELATION_ENDPOINT", "relation endpoint must be a node id")
        if relation.get("kind") == "INVALIDATES" and source_node["kind"] == target_node["kind"] and source_node["digest"] == target_node["digest"]:
            raise IdentityGraphError("IDENTITY_INVALIDATION_NOOP", "invalidation relation must identify a changed identity")
    policy = graph.get("policy")
    if policy != POLICY:
        raise IdentityGraphError("IDENTITY_POLICY_INVALID", "identity graph policy is not canonical")
    return {"status": "PASS", "schema": SCHEMA, "graph_id": graph["graph_id"], "node_count": len(by_id), "relation_count": len(relation_ids)}


def targeted_invalidation(previous: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    validate_graph(previous)
    validate_graph(current)
    old = {node["node_id"]: node for node in previous["nodes"]}
    new = {node["node_id"]: node for node in current["nodes"]}
    changed: list[dict[str, Any]] = []
    for node_id in sorted(set(old) | set(new)):
        before, after = old.get(node_id), new.get(node_id)
        if before is None or after is None:
            changed.append({"node_id": node_id, "reason": "ADDED_OR_REMOVED", "kind": (after or before)["kind"]})
            continue
        if before["kind"] != after["kind"]:
            raise IdentityGraphError("IDENTITY_KIND_SUBSTITUTION", node_id)
        if before["subject"] != after["subject"]:
            raise IdentityGraphError("IDENTITY_SUBJECT_MISMATCH", node_id)
        if before["digest"] != after["digest"] or before["revision"] != after["revision"]:
            changed.append({"node_id": node_id, "reason": "DIGEST_OR_REVISION", "kind": before["kind"]})
    # DEPENDS_ON points from the dependent identity to its dependency.  Walk
    # only declared edges, preserving carrier/method/environment/attempt and
    # evidence-local invalidation without manufacturing a product successor.
    dependents: dict[str, set[str]] = {}
    for relation in current.get("relations", ()):
        if relation.get("kind") == "DEPENDS_ON":
            dependents.setdefault(relation["to_node"], set()).add(relation["from_node"])
    affected = {item["node_id"] for item in changed}
    queue = list(affected)
    while queue:
        source = queue.pop(0)
        for dependent in sorted(dependents.get(source, ())):
            if dependent not in affected:
                affected.add(dependent)
                queue.append(dependent)
    product_nodes = {node_id for node_id, node in new.items() if node["kind"] == "PRODUCT_PAYLOAD"}
    product_changed = bool(product_nodes & affected)
    return {"status": "PASS", "changed_nodes": changed, "product_successor_required": product_changed,
            "targeted_invalidations": sorted(affected),
            "claims_not_established": ["candidate acceptance", "independent validation", "release"]}


def identity_from_artifact(package: Mapping[str, Any], *, subject: Mapping[str, Any] | None = None) -> dict[str, Any]:
    content = package.get("contentSha256") or package.get("content_sha256")
    if not isinstance(content, str):
        raise IdentityGraphError("IDENTITY_PACKAGE_DIGEST_REQUIRED", "artifact package contentSha256 is required")
    package_id = package.get("packageId") or package.get("package_id") or "complete-package"
    subject = subject or {"kind": "complete-package", "id": str(package_id), "revision": str(package.get("revision", "1")), "digest": content}
    return derive_identity("COMPLETE_PACKAGE", subject=subject, revision=str(package.get("revision", "1")), content_sha256=content, derivation_inputs=package.get("derivation_inputs", ()), metadata={"adapter": "artifact"})


def identity_from_evidence(receipt: Mapping[str, Any], *, subject: Mapping[str, Any]) -> dict[str, Any]:
    metadata = dict(receipt.get("metadata") or {})
    metadata.update({"adapter": "evidence", "subject_digest": metadata.get("subject_digest", subject.get("digest"))})
    if "verification_external" not in metadata:
        metadata["verification_external"] = receipt.get("verification_external")
    if "self_attesting" not in metadata:
        metadata["self_attesting"] = receipt.get("self_attesting")
    return derive_identity("EVIDENCE_BUNDLE", subject=subject, revision=str(receipt.get("revision") or receipt.get("completedAt") or "1"), derivation_inputs=receipt.get("derivation_inputs", ()), metadata=metadata, node_id=str(receipt.get("receiptId") or "evidence-bundle"))


def identity_from_handoff(handoff: Mapping[str, Any], *, subject: Mapping[str, Any]) -> dict[str, Any]:
    metadata = dict(handoff.get("metadata") or {})
    if "evidence_cutoff" not in metadata and "evidence_cutoff" in handoff:
        metadata["evidence_cutoff"] = handoff["evidence_cutoff"]
    if "sealed_after_cutoff" not in metadata and "sealed_after_cutoff" in handoff:
        metadata["sealed_after_cutoff"] = handoff["sealed_after_cutoff"]
    if "verification_external" not in metadata and "verification_external" in handoff:
        metadata["verification_external"] = handoff["verification_external"]
    if "freshness_external" not in metadata and "freshness_external" in handoff:
        metadata["freshness_external"] = handoff["freshness_external"]
    if "freshness_external" not in metadata and metadata.get("verification_external") is True:
        metadata["freshness_external"] = True
    metadata["adapter"] = "handoff"
    return derive_identity("HANDOFF", subject=subject, revision=str(handoff.get("revision") or "1"), derivation_inputs=handoff.get("derivation_inputs", ()), metadata=metadata, node_id=str(handoff.get("id") or "handoff"))


def identity_from_candidate(candidate: Mapping[str, Any], *, subject: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Adapt a candidate package while keeping complete-package identity intact."""
    content = candidate.get("contentSha256") or candidate.get("content_sha256")
    if not isinstance(content, str):
        raise IdentityGraphError("IDENTITY_PACKAGE_DIGEST_REQUIRED", "candidate contentSha256 is required")
    candidate_id = str(candidate.get("candidateId") or candidate.get("candidate_id") or "candidate")
    package = identity_from_artifact({**candidate, "contentSha256": content}, subject=subject)
    package["metadata"]["adapter"] = "candidate"
    package["metadata"]["candidate_id"] = candidate_id
    return package


def _supporting_adapter(kind: str, value: Mapping[str, Any], *, subject: Mapping[str, Any], node_id_key: str, adapter: str) -> dict[str, Any]:
    metadata = dict(value.get("metadata") or {})
    metadata["adapter"] = adapter
    return derive_identity(kind, subject=subject, revision=str(value.get("revision") or "1"), payload=value.get("payload"), derivation_inputs=value.get("derivation_inputs", ()), dependency_edges=value.get("dependency_edges", ()), metadata=metadata, node_id=str(value.get(node_id_key) or adapter))


def identity_from_method(method: Mapping[str, Any], *, subject: Mapping[str, Any]) -> dict[str, Any]:
    return _supporting_adapter("METHOD", method, subject=subject, node_id_key="method_id", adapter="method")


def identity_from_environment(environment: Mapping[str, Any], *, subject: Mapping[str, Any]) -> dict[str, Any]:
    return _supporting_adapter("ENVIRONMENT_OR_MIRROR", environment, subject=subject, node_id_key="environment_id", adapter="environment")


def identity_from_attempt(attempt: Mapping[str, Any], *, subject: Mapping[str, Any]) -> dict[str, Any]:
    return _supporting_adapter("ASSURANCE_ATTEMPT", attempt, subject=subject, node_id_key="attempt_id", adapter="attempt")


def identity_from_carrier(carrier: Mapping[str, Any], *, subject: Mapping[str, Any]) -> dict[str, Any]:
    return _supporting_adapter("CARRIER", carrier, subject=subject, node_id_key="carrier_id", adapter="carrier")


def identity_from_publication(publication: Mapping[str, Any], *, subject: Mapping[str, Any]) -> dict[str, Any]:
    return _supporting_adapter("PUBLICATION", publication, subject=subject, node_id_key="publication_id", adapter="publication")


def validate_file(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return validate_graph(value)
    except IdentityGraphError:
        raise
    except Exception as exc:
        raise IdentityGraphError("IDENTITY_GRAPH_INPUT", str(exc)) from exc


def run_identity_graph(subject: Path) -> dict[str, Any]:
    result = validate_file(subject)
    return {"schema": "bbk.identity-graph-validation.v1", **result}
