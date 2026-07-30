#!/usr/bin/env python3
"""Validate and resolve BBK sub-agent model-routing configuration."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "spec" / "model-routing.json"
ROLE_SPEC_PATH = ROOT / "spec" / "roles.json"

class ModelRoutingError(ValueError):
    """Raised when the canonical model-routing configuration is invalid."""



def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _nonempty_string(value: Any, where: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{where} must be a non-empty string")


def _validate_host_profile(
    profile_name: str,
    host: str,
    value: Any,
    required_fields: set[str],
    effort_field: str,
    errors: list[str],
) -> None:
    where = f"profiles.{profile_name}.{host}"
    if not isinstance(value, dict):
        errors.append(f"{where} must be an object")
        return
    missing = sorted(required_fields - set(value))
    extra = sorted(set(value) - required_fields)
    if missing:
        errors.append(f"{where} missing fields: {missing}")
    if extra:
        errors.append(f"{where} unexpected fields: {extra}")
    _nonempty_string(value.get("model"), f"{where}.model", errors)
    _nonempty_string(value.get(effort_field), f"{where}.{effort_field}", errors)


def validate_model_routing(value: Any, *, version: str, role_names: set[str]) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["model-routing root must be an object"]
    expected_top = {"schema_version", "package_version", "description", "profiles", "role_profiles"}
    missing_top = sorted(expected_top - set(value))
    extra_top = sorted(set(value) - expected_top)
    if missing_top:
        errors.append(f"model-routing root missing fields: {missing_top}")
    if extra_top:
        errors.append(f"model-routing root unexpected fields: {extra_top}")
    if value.get("schema_version") != "bbk.model-routing.v1":
        errors.append("schema_version must equal bbk.model-routing.v1")
    if value.get("package_version") != version:
        errors.append(f"package_version {value.get('package_version')!r} != {version!r}")
    _nonempty_string(value.get("description"), "description", errors)

    profiles = value.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        errors.append("profiles must be a non-empty object")
        profiles = {}
    for profile_name, profile in sorted(profiles.items()):
        if not isinstance(profile_name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", profile_name):
            errors.append(f"invalid profile name: {profile_name!r}")
            continue
        where = f"profiles.{profile_name}"
        if not isinstance(profile, dict):
            errors.append(f"{where} must be an object")
            continue
        expected = {"description", "omp", "codex", "claude"}
        missing = sorted(expected - set(profile))
        extra = sorted(set(profile) - expected)
        if missing:
            errors.append(f"{where} missing fields: {missing}")
        if extra:
            errors.append(f"{where} unexpected fields: {extra}")
        _nonempty_string(profile.get("description"), f"{where}.description", errors)
        _validate_host_profile(
            profile_name, "omp", profile.get("omp"), {"model", "thinkingLevel"},
            "thinkingLevel", errors,
        )
        _validate_host_profile(
            profile_name, "codex", profile.get("codex"), {"model", "model_reasoning_effort"},
            "model_reasoning_effort", errors,
        )
        _validate_host_profile(
            profile_name, "claude", profile.get("claude"), {"model", "effort"},
            "effort", errors,
        )

    role_profiles = value.get("role_profiles")
    if not isinstance(role_profiles, dict):
        errors.append("role_profiles must be an object")
        role_profiles = {}
    configured_roles = set(role_profiles)
    missing_roles = sorted(role_names - configured_roles)
    extra_roles = sorted(configured_roles - role_names)
    if missing_roles:
        errors.append(f"role_profiles missing roles: {missing_roles}")
    if extra_roles:
        errors.append(f"role_profiles references unknown roles: {extra_roles}")
    for role_name, profile_name in sorted(role_profiles.items()):
        if not isinstance(profile_name, str) or profile_name not in profiles:
            errors.append(f"role_profiles.{role_name} references unknown profile {profile_name!r}")
    return errors


def load_model_routing(
    path: Path = DEFAULT_PATH,
    *,
    root: Path = ROOT,
    role_spec: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelRoutingError(f"cannot read model-routing configuration {path}: {exc}") from exc
    if role_spec is None:
        try:
            role_spec = json.loads((root / "spec" / "roles.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelRoutingError(f"cannot read canonical role catalogue: {exc}") from exc
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    role_names = {
        role.get("name") for role in role_spec.get("roles", [])
        if isinstance(role, dict) and isinstance(role.get("name"), str)
    }
    errors = validate_model_routing(value, version=version, role_names=role_names)
    if errors:
        raise ModelRoutingError("\n".join(errors))
    return value


def profile_name_for_role(routing: Mapping[str, Any], role_name: str) -> str:
    try:
        return str(routing["role_profiles"][role_name])
    except KeyError as exc:
        raise ModelRoutingError(f"no model-routing profile configured for role {role_name!r}") from exc


def route_for_role(routing: Mapping[str, Any], role_name: str) -> dict[str, Any]:
    profile_name = profile_name_for_role(routing, role_name)
    profile = routing["profiles"][profile_name]
    return {
        "profile": profile_name,
        "omp": dict(profile["omp"]),
        "codex": dict(profile["codex"]),
        "claude": dict(profile["claude"]),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=str(DEFAULT_PATH), help="model-routing JSON to validate")
    parser.add_argument("--check", action="store_true", help="validate and report the canonical routing")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable summary")
    args = parser.parse_args(argv)
    try:
        routing = load_model_routing(Path(args.path).expanduser().resolve())
    except ModelRoutingError as exc:
        print("BBK model-routing errors:", file=sys.stderr)
        for line in str(exc).splitlines():
            print(f"- {line}", file=sys.stderr)
        return 1
    summary = {
        "schema": "bbk.model-routing-validation.v1",
        "status": "PASS",
        "path": Path(args.path).expanduser().resolve().as_posix(),
        "sha256": sha256(routing),
        "profile_count": len(routing["profiles"]),
        "role_count": len(routing["role_profiles"]),
        "profiles": {
            name: sum(1 for value in routing["role_profiles"].values() if value == name)
            for name in sorted(routing["profiles"])
        },
    }
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(
            f"OK: {summary['role_count']} roles resolve through {summary['profile_count']} model profiles "
            f"in {Path(args.path).name} ({summary['sha256']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
