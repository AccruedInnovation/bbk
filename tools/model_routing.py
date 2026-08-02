#!/usr/bin/env python3
"""Validate, normalize, and resolve BBK sub-agent model-routing configuration."""
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
SUPPORTED_SCHEMAS = {"bbk.model-routing.v1", "bbk.model-routing.v2"}
HOST_SPECS: dict[str, tuple[set[str], str]] = {
    "omp": ({"model", "thinkingLevel"}, "thinkingLevel"),
    "codex": ({"model", "model_reasoning_effort"}, "model_reasoning_effort"),
    "claude": ({"model", "effort"}, "effort"),
}
ROLE_NAME_PATTERN = re.compile(r"bbk_[a-z][a-z0-9_]*")
PROFILE_NAME_PATTERN = re.compile(r"[a-z][a-z0-9_-]*")


class ModelRoutingError(ValueError):
    """Raised when a model-routing configuration is invalid."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _nonempty_string(value: Any, where: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{where} must be a non-empty string")


def _validate_host_route(where: str, host: str, value: Any, errors: list[str]) -> None:
    required_fields, effort_field = HOST_SPECS[host]
    host_where = f"{where}.{host}"
    if not isinstance(value, dict):
        errors.append(f"{host_where} must be an object")
        return
    missing = sorted(required_fields - set(value))
    extra = sorted(set(value) - required_fields)
    if missing:
        errors.append(f"{host_where} missing fields: {missing}")
    if extra:
        errors.append(f"{host_where} unexpected fields: {extra}")
    _nonempty_string(value.get("model"), f"{host_where}.model", errors)
    _nonempty_string(value.get(effort_field), f"{host_where}.{effort_field}", errors)


def _validate_route(
    where: str,
    value: Any,
    errors: list[str],
    *,
    description: str,
) -> None:
    """Validate one host-route object.

    ``description`` is one of ``required``, ``optional``, or ``forbidden``.
    """
    if not isinstance(value, dict):
        errors.append(f"{where} must be an object")
        return
    expected = set(HOST_SPECS)
    if description in {"required", "optional"}:
        expected.add("description")
    missing = sorted(set(HOST_SPECS) - set(value))
    if description == "required" and "description" not in value:
        missing.append("description")
    extra = sorted(set(value) - expected)
    if missing:
        errors.append(f"{where} missing fields: {sorted(missing)}")
    if extra:
        errors.append(f"{where} unexpected fields: {extra}")
    if description == "required" or (description == "optional" and "description" in value):
        _nonempty_string(value.get("description"), f"{where}.description", errors)
    for host in HOST_SPECS:
        _validate_host_route(where, host, value.get(host), errors)


def _validate_role_coverage(
    configured: set[str], role_names: set[str], where: str, errors: list[str]
) -> None:
    missing_roles = sorted(role_names - configured)
    extra_roles = sorted(configured - role_names)
    if missing_roles:
        errors.append(f"{where} missing roles: {missing_roles}")
    if extra_roles:
        errors.append(f"{where} references unknown roles: {extra_roles}")


def _validate_v1(value: Mapping[str, Any], *, role_names: set[str], errors: list[str]) -> None:
    expected_top = {"schema_version", "package_version", "description", "profiles", "role_profiles"}
    missing_top = sorted(expected_top - set(value))
    extra_top = sorted(set(value) - expected_top)
    if missing_top:
        errors.append(f"model-routing root missing fields: {missing_top}")
    if extra_top:
        errors.append(f"model-routing root unexpected fields: {extra_top}")

    profiles = value.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        errors.append("profiles must be a non-empty object")
        profiles = {}
    for profile_name, profile in sorted(profiles.items()):
        if not isinstance(profile_name, str) or not PROFILE_NAME_PATTERN.fullmatch(profile_name):
            errors.append(f"invalid profile name: {profile_name!r}")
            continue
        _validate_route(f"profiles.{profile_name}", profile, errors, description="required")

    role_profiles = value.get("role_profiles")
    if not isinstance(role_profiles, dict):
        errors.append("role_profiles must be an object")
        role_profiles = {}
    _validate_role_coverage(set(role_profiles), role_names, "role_profiles", errors)
    for role_name, profile_name in sorted(role_profiles.items()):
        if not isinstance(profile_name, str) or profile_name not in profiles:
            errors.append(f"role_profiles.{role_name} references unknown profile {profile_name!r}")


def _validate_v2(value: Mapping[str, Any], *, role_names: set[str], errors: list[str]) -> None:
    expected_top = {"schema_version", "package_version", "description", "roles"}
    missing_top = sorted(expected_top - set(value))
    extra_top = sorted(set(value) - expected_top)
    if missing_top:
        errors.append(f"model-routing root missing fields: {missing_top}")
    if extra_top:
        errors.append(f"model-routing root unexpected fields: {extra_top}")

    roles = value.get("roles")
    if not isinstance(roles, dict) or not roles:
        errors.append("roles must be a non-empty object")
        roles = {}
    _validate_role_coverage(set(roles), role_names, "roles", errors)
    for role_name, route in sorted(roles.items()):
        if not isinstance(role_name, str) or not ROLE_NAME_PATTERN.fullmatch(role_name):
            errors.append(f"invalid role route name: {role_name!r}")
            continue
        _validate_route(f"roles.{role_name}", route, errors, description="optional")


def validate_model_routing(value: Any, *, version: str, role_names: set[str]) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["model-routing root must be an object"]
    schema = value.get("schema_version")
    if schema not in SUPPORTED_SCHEMAS:
        errors.append("schema_version must equal bbk.model-routing.v1 or bbk.model-routing.v2")
    if value.get("package_version") != version:
        errors.append(f"package_version {value.get('package_version')!r} != {version!r}")
    _nonempty_string(value.get("description"), "description", errors)
    if schema == "bbk.model-routing.v1":
        _validate_v1(value, role_names=role_names, errors=errors)
    elif schema == "bbk.model-routing.v2":
        _validate_v2(value, role_names=role_names, errors=errors)
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
        role.get("name")
        for role in role_spec.get("roles", [])
        if isinstance(role, dict) and isinstance(role.get("name"), str)
    }
    errors = validate_model_routing(value, version=version, role_names=role_names)
    if errors:
        raise ModelRoutingError("\n".join(errors))
    return value


def routing_mode(routing: Mapping[str, Any]) -> str:
    return "per-role" if routing.get("schema_version") == "bbk.model-routing.v2" else "profiles"


def profile_name_for_role(routing: Mapping[str, Any], role_name: str) -> str | None:
    if routing.get("schema_version") == "bbk.model-routing.v2":
        if role_name not in routing.get("roles", {}):
            raise ModelRoutingError(f"no model route configured for role {role_name!r}")
        return None
    try:
        return str(routing["role_profiles"][role_name])
    except KeyError as exc:
        raise ModelRoutingError(f"no model-routing profile configured for role {role_name!r}") from exc


def direct_routes(routing: Mapping[str, Any]) -> dict[str, dict[str, dict[str, str]]]:
    """Return exact per-role host routes for either supported policy schema."""
    if routing.get("schema_version") == "bbk.model-routing.v2":
        raw_roles = routing.get("roles")
        if not isinstance(raw_roles, Mapping):
            raise ModelRoutingError("roles must be an object")
        result: dict[str, dict[str, dict[str, str]]] = {}
        for role_name, route in sorted(raw_roles.items()):
            if not isinstance(route, Mapping):
                raise ModelRoutingError(f"roles.{role_name} must be an object")
            result[str(role_name)] = {host: dict(route[host]) for host in HOST_SPECS}
        return result

    profiles = routing.get("profiles")
    role_profiles = routing.get("role_profiles")
    if not isinstance(profiles, Mapping) or not isinstance(role_profiles, Mapping):
        raise ModelRoutingError("v1 policy requires profiles and role_profiles")
    result = {}
    for role_name, profile_name in sorted(role_profiles.items()):
        try:
            profile = profiles[profile_name]
        except KeyError as exc:
            raise ModelRoutingError(
                f"role_profiles.{role_name} references unknown profile {profile_name!r}"
            ) from exc
        result[str(role_name)] = {host: dict(profile[host]) for host in HOST_SPECS}
    return result


def _route_description(routing: Mapping[str, Any], role_name: str) -> str | None:
    if routing.get("schema_version") == "bbk.model-routing.v2":
        raw = routing.get("roles", {}).get(role_name) if isinstance(routing.get("roles"), Mapping) else None
        if isinstance(raw, Mapping) and isinstance(raw.get("description"), str):
            return str(raw["description"])
        return None
    profile_name = profile_name_for_role(routing, role_name)
    profiles = routing.get("profiles")
    if profile_name and isinstance(profiles, Mapping):
        raw = profiles.get(profile_name)
        if isinstance(raw, Mapping) and isinstance(raw.get("description"), str):
            return f"Migrated from profile {profile_name}: {raw['description']}"
    return None


def as_v2(
    routing: Mapping[str, Any],
    *,
    package_version: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Normalize a validated v1 or v2 policy into the direct per-role v2 shape."""
    roles: dict[str, dict[str, Any]] = {}
    for role_name, route in direct_routes(routing).items():
        entry: dict[str, Any] = {host: dict(route[host]) for host in HOST_SPECS}
        route_description = _route_description(routing, role_name)
        if route_description:
            entry["description"] = route_description
        roles[role_name] = entry
    return {
        "schema_version": "bbk.model-routing.v2",
        "package_version": package_version or str(routing.get("package_version") or ""),
        "description": description or str(routing.get("description") or "Per-role BBK model routing."),
        "roles": roles,
    }


def merge_host_routes(
    selected: Mapping[str, Any],
    preserved: Mapping[str, Any],
    *,
    selected_hosts: set[str],
    package_version: str,
    description: str,
) -> dict[str, Any]:
    """Build one v2 policy with selected hosts from one policy and others preserved."""
    unknown_hosts = selected_hosts - set(HOST_SPECS)
    if unknown_hosts:
        raise ModelRoutingError(f"unknown model-routing hosts: {sorted(unknown_hosts)}")
    selected_routes = direct_routes(selected)
    preserved_routes = direct_routes(preserved)
    if set(selected_routes) != set(preserved_routes):
        missing = sorted(set(selected_routes) - set(preserved_routes))
        extra = sorted(set(preserved_routes) - set(selected_routes))
        raise ModelRoutingError(
            f"cannot merge policies with different role catalogues; missing={missing}, extra={extra}"
        )
    roles: dict[str, dict[str, Any]] = {}
    for role_name in sorted(selected_routes):
        entry: dict[str, Any] = {
            host: dict(
                selected_routes[role_name][host]
                if host in selected_hosts
                else preserved_routes[role_name][host]
            )
            for host in HOST_SPECS
        }
        route_description = _route_description(selected, role_name) or _route_description(preserved, role_name)
        if route_description:
            entry["description"] = route_description
        roles[role_name] = entry
    return {
        "schema_version": "bbk.model-routing.v2",
        "package_version": package_version,
        "description": description,
        "roles": roles,
    }


def routing_statistics(routing: Mapping[str, Any]) -> dict[str, Any]:
    routes = direct_routes(routing)
    profiles = routing.get("profiles") if isinstance(routing.get("profiles"), Mapping) else {}
    role_profiles = (
        routing.get("role_profiles") if isinstance(routing.get("role_profiles"), Mapping) else {}
    )
    return {
        "schema_version": routing.get("schema_version"),
        "mode": routing_mode(routing),
        "route_count": len(routes),
        "profile_count": len(profiles),
        "role_profile_counts": {
            name: sum(1 for value in role_profiles.values() if value == name)
            for name in sorted(profiles)
        },
    }


def route_for_role(routing: Mapping[str, Any], role_name: str) -> dict[str, Any]:
    routes = direct_routes(routing)
    try:
        route = routes[role_name]
    except KeyError as exc:
        raise ModelRoutingError(f"no model route configured for role {role_name!r}") from exc
    return {
        "route_id": role_name,
        "mode": routing_mode(routing),
        "profile": profile_name_for_role(routing, role_name),
        "omp": dict(route["omp"]),
        "codex": dict(route["codex"]),
        "claude": dict(route["claude"]),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=str(DEFAULT_PATH), help="model-routing JSON to validate")
    parser.add_argument("--check", action="store_true", help="validate and report the canonical routing")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable summary")
    args = parser.parse_args(argv)
    try:
        routing = load_model_routing(Path(args.path).expanduser().resolve())
        stats = routing_statistics(routing)
    except ModelRoutingError as exc:
        print("BBK model-routing errors:", file=sys.stderr)
        for line in str(exc).splitlines():
            print(f"- {line}", file=sys.stderr)
        return 1
    summary = {
        "schema": "bbk.model-routing-validation.v2",
        "status": "PASS",
        "path": Path(args.path).expanduser().resolve().as_posix(),
        "sha256": sha256(routing),
        "policy_schema": stats["schema_version"],
        "routing_mode": stats["mode"],
        "route_count": stats["route_count"],
        "role_count": stats["route_count"],
        "profile_count": stats["profile_count"],
        "profiles": stats["role_profile_counts"],
    }
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    elif summary["routing_mode"] == "per-role":
        print(
            f"OK: {summary['role_count']} roles have individual model routes "
            f"in {Path(args.path).name} ({summary['sha256']})"
        )
    else:
        print(
            f"OK: {summary['role_count']} roles resolve through {summary['profile_count']} model profiles "
            f"in {Path(args.path).name} ({summary['sha256']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
