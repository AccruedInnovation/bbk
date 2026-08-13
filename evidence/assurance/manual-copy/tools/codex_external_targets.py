#!/usr/bin/env python3
"""Resolve an explicitly requested DeepSeek Codex target without side effects.

The resolver is deliberately pure: it consumes supplied registry, request and
qualification objects and returns canonical, schema-shaped JSON.  It never
looks up an environment variable (only the configured variable *name* is
returned), writes files, or falls back to a default target.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "spec" / "codex-external-targets.json"
DEFAULT_QUALIFICATION = ROOT / "evidence" / "qualification" / "deepseek-codex-provider-seam-r4" / "qualification-receipt.json"
QUALIFIED_DISPOSITIONS = {"QUALIFIED_MOCK_LIVE", "QUALIFIED_MOCK_LIVE_DEFERRED"}
TARGETS = {"deepseek-v4-pro", "deepseek-v4-flash"}
SCHEMA = "bbk.codex-resolved-external-target.v1"
CURRENT_QUALIFICATION_SHA256 = "c3b0e71ed86f73a8db8a9a8e92a3b68962fcabcda2452d7c255400726a543a2e"
CURRENT_CANDIDATE_SHA256 = "c10931a296124bee553aa2a5c2454cc8ceba002286fbb24ca572844cb428c27d"


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_json(value: Any) -> str:
    return digest_bytes(canonical_json_bytes(value))


def _reject(code: str, reason: str, *, details: Any = None, request: Any = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "REJECTED",
        "selection": {"mode": "EXPLICIT", "target_id": request if isinstance(request, str) else None},
        "rejection": {"reason_code": code, "reason": reason},
        "invariants": {
            "parent_and_defaults_unchanged": True,
            "silent_fallback": False,
            "user_config_mutated": False,
        },
    }
    if details is not None:
        result["rejection"]["details"] = details
    return result


def _value(obj: Mapping[str, Any], key: str, where: str) -> Any:
    if key not in obj:
        raise ValueError(f"{where} missing {key}")
    return obj[key]


def resolve_target(
    registry: Mapping[str, Any],
    request: Mapping[str, Any] | str,
    qualification: Mapping[str, Any],
    *,
    registry_sha256: str | None = None,
    qualification_sha256: str | None = None,
) -> dict[str, Any]:
    """Resolve one target.  All malformed inputs become typed rejections."""
    target_hint = request if isinstance(request, str) else request.get("target_id") if isinstance(request, Mapping) else None
    try:
        if not isinstance(registry, Mapping):
            return _reject("MALFORMED_REGISTRY", "registry must be an object", request=target_hint)
        if not isinstance(qualification, Mapping):
            return _reject("MALFORMED_QUALIFICATION", "qualification receipt must be an object", request=target_hint)
        if isinstance(request, str):
            request = {"mode": "EXPLICIT", "target_id": request}
        if not isinstance(request, Mapping):
            return _reject("MALFORMED_REQUEST", "request must be an object or target id", request=target_hint)
        mode = request.get("mode")
        target_id = request.get("target_id")
        if mode != "EXPLICIT":
            return _reject("EXPLICIT_SELECTION_REQUIRED", "selection mode must be EXPLICIT", request=target_id)
        if not isinstance(target_id, str) or not target_id:
            return _reject("MALFORMED_TARGET", "target_id must be a non-empty string", request=target_id)
        if target_id not in TARGETS:
            return _reject("UNKNOWN_TARGET", f"unknown target: {target_id}", request=target_id)

        if registry.get("schema_version") != "bbk.codex-external-target-registry.v1":
            return _reject("MALFORMED_REGISTRY", "unsupported registry schema", request=target_id)
        if registry.get("activation") != "ACTIVATION_NEUTRAL":
            return _reject("REGISTRY_NOT_ACTIVATION_NEUTRAL", "registry activation must remain neutral", request=target_id)
        providers = registry.get("providers")
        targets = registry.get("targets")
        capabilities = registry.get("capabilities")
        if not isinstance(providers, list) or not isinstance(targets, list) or not isinstance(capabilities, list):
            return _reject("MALFORMED_REGISTRY", "registry providers, targets and capabilities must be arrays", request=target_id)
        provider = next((p for p in providers if isinstance(p, Mapping) and p.get("id") == "deepseek"), None)
        target = next((t for t in targets if isinstance(t, Mapping) and t.get("id") == target_id), None)
        if provider is None or target is None:
            return _reject("UNKNOWN_TARGET", "target or provider is not registered", request=target_id)
        if target.get("selection") != "EXPLICIT_ONLY" or target.get("provider") != "deepseek" or target.get("model") != target_id:
            return _reject("UNSUPPORTED_TARGET", "target is not an explicit DeepSeek target", request=target_id)

        # enabled=false is intentionally not consulted for an explicit request.
        transport = provider.get("transport")
        credential = provider.get("credential_source")
        if not isinstance(transport, Mapping) or transport.get("wire_api") != "responses":
            return _reject("MALFORMED_PROVIDER", "provider responses transport is required", request=target_id)
        if not isinstance(credential, Mapping) or credential.get("kind") != "environment" or credential.get("env_key") != "DEEPSEEK_API_KEY" or credential.get("value_persisted") is not False:
            return _reject("MALFORMED_CREDENTIAL_REFERENCE", "only the non-persisted environment reference is supported", request=target_id)

        requested = request.get("capabilities", [])
        if requested is None:
            requested = []
        if not isinstance(requested, list) or any(not isinstance(x, str) or not x for x in requested):
            return _reject("MALFORMED_CAPABILITIES", "capabilities must be a list of names", request=target_id)
        provider_caps = [c for c in capabilities if isinstance(c, Mapping) and c.get("provider") == "deepseek"]
        by_id = {str(c.get("id")): c for c in provider_caps}
        unknown = sorted(set(requested) - set(by_id))
        unsupported = sorted(c for c in requested if c in by_id and by_id[c].get("supported") is not True)
        if unknown:
            return _reject("UNKNOWN_CAPABILITY", "requested capability is not registered", details={"unknown": unknown}, request=target_id)
        if unsupported:
            return _reject("UNSUPPORTED_CAPABILITY", "requested capability is unsupported", details={"unsupported": unsupported}, request=target_id)

        if qualification.get("schema") != "bbk.deepseek-codex-provider-seam-qualification.v1":
            return _reject("MALFORMED_QUALIFICATION", "qualification receipt schema is not recognized", request=target_id)
        q_work = qualification.get("work_unit_ref")
        q_subject = qualification.get("subject")
        if not isinstance(q_work, Mapping) or q_work.get("id") != "WU-DS-01C-LOCAL-PROVIDER-MOCK-SEAM" or q_work.get("revision") != 3:
            return _reject("STALE_QUALIFICATION", "qualification work-unit binding is stale", request=target_id)
        if not isinstance(q_subject, Mapping) or q_subject.get("candidate_content_sha256") != CURRENT_CANDIDATE_SHA256:
            return _reject("STALE_QUALIFICATION", "qualification candidate binding is stale", request=target_id)
        if qualification_sha256 is not None and qualification_sha256 != CURRENT_QUALIFICATION_SHA256:
            return _reject("STALE_QUALIFICATION", "qualification receipt digest is stale", request=target_id)
        if qualification.get("disposition") not in QUALIFIED_DISPOSITIONS:
            return _reject("NONQUALIFYING_RECEIPT", "qualification receipt is not eligible", request=target_id)
        suff = qualification.get("resolver_input_sufficiency")
        if not isinstance(suff, Mapping) or suff.get("sufficient") is not True:
            return _reject("INSUFFICIENT_QUALIFICATION", "qualification receipt lacks sufficient resolver inputs", request=target_id)
        if suff.get("provider_id") != "deepseek" or suff.get("model_id") != qualification.get("provider", {}).get("model"):
            return _reject("STALE_QUALIFICATION", "qualification provider/model binding is stale", request=target_id)
        qcred = suff.get("credential_ref")
        if qcred != {"kind": "environment", "env_key": "DEEPSEEK_API_KEY", "value_persisted": False}:
            return _reject("MALFORMED_CREDENTIAL_REFERENCE", "qualification credential reference is not secret-free", request=target_id)
        if qualification.get("credential", {}).get("value_observed") is not False:
            return _reject("CREDENTIAL_VALUE_EXPOSURE", "qualification must not observe a credential value", request=target_id)
        if registry_sha256 is None:
            registry_sha256 = digest_json(registry)
        if qualification_sha256 is None:
            qualification_sha256 = digest_json(qualification)
        receipt_id = qualification.get("work_unit_ref", {}).get("id") or "QUALIFICATION-RECEIPT-WU-DS-01C-R4"
        requested_supported = sorted(requested)
        supported_all = sorted(str(c.get("id")) for c in provider_caps if c.get("supported") is True)
        unsupported_all = sorted(str(c.get("id")) for c in provider_caps if c.get("supported") is not True)
        projection = {
            "model_provider": "deepseek",
            "model": target_id,
            "provider_name": provider.get("name", "DeepSeek"),
            "base_url": transport.get("base_url"),
            "wire_api": "responses",
            "credential_ref": {"kind": "environment", "env_key": "DEEPSEEK_API_KEY", "value_persisted": False},
        }
        return {
            "schema": SCHEMA,
            "status": "RESOLVED",
            "rejection": {"reason_code": "NONE", "reason": "no rejection; explicit target resolved"},
            "registry_ref": {"id": registry.get("id"), "revision": registry.get("revision"), "sha256": registry_sha256},
            "selection": {"mode": "EXPLICIT", "target_id": target_id},
            "provider": {
                "id": provider.get("id"), "name": provider.get("name"), "base_url": transport.get("base_url"),
                "wire_api": "responses", "responses_path_joining_disposition": suff.get("responses_path_joining"),
                "observed_or_qualified_request_path": qualification.get("provider", {}).get("request_path"),
            },
            "model": {"id": target_id},
            "credential_source": {"kind": "environment", "env_key": "DEEPSEEK_API_KEY", "value_persisted": False},
            "capabilities": {"supported": supported_all, "unsupported": unsupported_all, "requested": requested_supported},
            "isolated_codex_projection": projection,
            "qualification_ref": {"id": receipt_id, "sha256": qualification_sha256, "disposition": qualification.get("disposition")},
            "invariants": {"parent_and_defaults_unchanged": True, "silent_fallback": False, "user_config_mutated": False},
        }
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return _reject("MALFORMED_INPUT", str(exc), request=target_hint)


def resolve_external_target(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Compatibility alias for callers using the interface's longer name."""
    return resolve_target(*args, **kwargs)


resolve = resolve_target


def _load(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8")), digest_bytes(raw)


def load_registry(path: Path = DEFAULT_REGISTRY) -> tuple[dict[str, Any], str]:
    return _load(path)


def load_qualification(path: Path = DEFAULT_QUALIFICATION) -> tuple[dict[str, Any], str]:
    return _load(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target_pos", nargs="?", help="explicit target id (alternative to --target)")
    parser.add_argument("--target", dest="target_id")
    parser.add_argument("--mode", default="EXPLICIT")
    parser.add_argument("--capability", action="append", dest="capabilities", default=[])
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--qualification", default=str(DEFAULT_QUALIFICATION))
    parser.add_argument("--json", action="store_true", help="emit canonical JSON (default)")
    args = parser.parse_args(argv)
    target_id = args.target_id or args.target_pos
    if not target_id:
        result = _reject("MISSING_TARGET", "an explicit --target is required")
    else:
        try:
            registry, registry_digest = _load(Path(args.registry))
            qualification, qualification_digest = _load(Path(args.qualification))
            result = resolve_target(registry, {"mode": args.mode, "target_id": target_id, "capabilities": args.capabilities}, qualification, registry_sha256=registry_digest, qualification_sha256=qualification_digest)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            result = _reject("INPUT_READ_ERROR", str(exc), request=target_id)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result.get("status") == "RESOLVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
