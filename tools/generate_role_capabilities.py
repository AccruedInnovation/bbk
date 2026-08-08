#!/usr/bin/env python3
"""Compile canonical BBK roles into deterministic governed capability manifests."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "spec" / "policies" / "role-capabilities-v1.json"
CATALOG_PATH = ROOT / "spec" / "roles" / "catalog.json"
OUTPUT_ROOT = ROOT / "spec" / "role-capabilities"
INDEX_PATH = OUTPUT_ROOT / "manifest.json"
GENERATOR_REF = "tools/generate_role_capabilities.py"


class RoleCapabilityError(RuntimeError):
    """A canonical role/capability projection is invalid or out of sync."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RoleCapabilityError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RoleCapabilityError(f"{path} must contain a JSON object")
    return value


def _role_entries(catalog: Mapping[str, Any]) -> dict[str, Path]:
    entries = catalog.get("role_entries")
    if not isinstance(entries, list) or not entries:
        raise RoleCapabilityError("role catalog has no role_entries")
    result: dict[str, Path] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise RoleCapabilityError("role_entries must contain objects")
        name = entry.get("name")
        raw_path = entry.get("file")
        if not isinstance(name, str) or not name or not isinstance(raw_path, str) or not raw_path:
            raise RoleCapabilityError("every role entry requires name and file")
        if name in result:
            raise RoleCapabilityError(f"duplicate canonical role {name}")
        role_path = (ROOT / raw_path).resolve()
        if ROOT.resolve() not in role_path.parents or not role_path.is_file():
            raise RoleCapabilityError(f"canonical role file is missing or outside the package: {raw_path}")
        role_value = read_json(role_path)
        if role_value.get("name") != name:
            raise RoleCapabilityError(f"role entry {name} does not match {raw_path}")
        result[name] = role_path
    return result


def _sorted_unique_strings(value: Any, field: str, role: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise RoleCapabilityError(f"{role}.{field} must be a string list")
    if len(value) != len(set(value)):
        raise RoleCapabilityError(f"{role}.{field} contains duplicates")
    return sorted(value)


def _normalized_scope(value: Any, role: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise RoleCapabilityError(f"{role}.scope_rules must be an object")
    required = {"workspace_source", "path_scope", "semantic_scope", "sealed_paths"}
    if set(value) != required:
        raise RoleCapabilityError(f"{role}.scope_rules must contain exactly {sorted(required)}")
    return {key: str(value[key]) for key in sorted(required)}


def _capability(role: str, role_path: Path, policy: Mapping[str, Any]) -> dict[str, Any]:
    roles = policy.get("roles")
    if not isinstance(roles, Mapping) or role not in roles:
        raise RoleCapabilityError(f"canonical role {role} has no capability policy")
    raw = roles[role]
    if not isinstance(raw, Mapping):
        raise RoleCapabilityError(f"capability policy for {role} must be an object")
    profile = policy.get("profile")
    policy_version = policy.get("policy_version")
    if not isinstance(profile, str) or not profile or not isinstance(policy_version, str) or not policy_version:
        raise RoleCapabilityError("capability policy requires profile and policy_version")
    body = {
        "schema": "bbk.role-capability.v1",
        "role": role,
        "profile": profile,
        "policy_version": policy_version,
        "allowed_tools": _sorted_unique_strings(raw.get("allowed_tools"), "allowed_tools", role),
        "allowed_mutation_classes": _sorted_unique_strings(raw.get("allowed_mutation_classes"), "allowed_mutation_classes", role),
        "scope_rules": _normalized_scope(raw.get("scope_rules"), role),
        "forbidden_effects": _sorted_unique_strings(raw.get("forbidden_effects"), "forbidden_effects", role),
        "required_bindings": _sorted_unique_strings(raw.get("required_bindings"), "required_bindings", role),
        "source_role_digest": f"sha256:{sha256_file(role_path)}",
        "generated_by": GENERATOR_REF,
    }
    body["manifest_digest"] = f"sha256:{sha256_bytes(canonical_json_bytes(body))}"
    return body


def compile_manifests() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    policy = read_json(POLICY_PATH)
    catalog = read_json(CATALOG_PATH)
    if policy.get("schema") != "bbk.role-capability-policy.v1":
        raise RoleCapabilityError("unsupported role capability policy schema")
    roles = _role_entries(catalog)
    policy_roles = policy.get("roles")
    if not isinstance(policy_roles, Mapping):
        raise RoleCapabilityError("role capability policy has no roles map")
    extra = sorted(set(policy_roles) - set(roles))
    missing = sorted(set(roles) - set(policy_roles))
    if missing or extra:
        raise RoleCapabilityError(f"role capability coverage mismatch; missing={missing}, extra={extra}")

    manifests = {role: _capability(role, path, policy) for role, path in sorted(roles.items())}
    records = [
        {
            "role": role,
            "path": f"spec/role-capabilities/{role}.json",
            "manifest_digest": manifests[role]["manifest_digest"],
            "source_role_digest": manifests[role]["source_role_digest"],
        }
        for role in sorted(manifests)
    ]
    index_body: dict[str, Any] = {
        "schema": "bbk.role-capability-manifest.v1",
        "profile": policy["profile"],
        "policy_version": policy["policy_version"],
        "source_policy_digest": f"sha256:{sha256_file(POLICY_PATH)}",
        "source_catalog_digest": f"sha256:{sha256_file(CATALOG_PATH)}",
        "generator": GENERATOR_REF,
        "role_count": len(records),
        "roles": records,
    }
    index_body["manifest_digest"] = f"sha256:{sha256_bytes(canonical_json_bytes(index_body))}"
    return manifests, index_body


def render_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_outputs() -> dict[str, Any]:
    manifests, index = compile_manifests()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    expected = {OUTPUT_ROOT / f"{role}.json" for role in manifests} | {INDEX_PATH}
    for path in OUTPUT_ROOT.glob("*.json"):
        if path not in expected:
            path.unlink()
    for role, value in manifests.items():
        (OUTPUT_ROOT / f"{role}.json").write_text(render_json(value), encoding="utf-8")
    INDEX_PATH.write_text(render_json(index), encoding="utf-8")
    return index


def check_outputs() -> list[str]:
    manifests, index = compile_manifests()
    errors: list[str] = []
    expected = {OUTPUT_ROOT / f"{role}.json": render_json(value) for role, value in manifests.items()}
    expected[INDEX_PATH] = render_json(index)
    actual_paths = set(OUTPUT_ROOT.glob("*.json")) if OUTPUT_ROOT.exists() else set()
    for path, content in expected.items():
        if not path.is_file():
            errors.append(f"missing generated capability manifest: {path.relative_to(ROOT)}")
        elif path.read_text(encoding="utf-8") != content:
            errors.append(f"stale generated capability manifest: {path.relative_to(ROOT)}")
    for path in sorted(actual_paths - set(expected)):
        errors.append(f"unexpected generated capability manifest: {path.relative_to(ROOT)}")
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when generated outputs differ")
    args = parser.parse_args(argv)
    try:
        if args.check:
            errors = check_outputs()
            if errors:
                for error in errors:
                    print(error, file=sys.stderr)
                return 1
            print(f"Role capability projection is current ({len(compile_manifests()[0])} roles)")
        else:
            index = write_outputs()
            print(f"Generated {index['role_count']} role capability manifests")
    except RoleCapabilityError as exc:
        print(f"role capability generation failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
