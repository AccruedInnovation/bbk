#!/usr/bin/env python3
"""Inspect and safely change model routing for installed BBK OMP sub-agents."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_BINDING = SCRIPT_DIR / "bbk-package-root.json"
THINKING_LEVELS = {"auto", "off", "minimal", "low", "medium", "high", "xhigh", "max"}
ROLE_PATTERN = re.compile(r"^bbk_[a-z0-9_]+$")
PROFILE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")
PRECEDENCE_NOTE = (
    "These are BBK-managed OMP agent-frontmatter routes. OMP task.agentModelOverrides, "
    "or a higher-precedence project agent definition with the same role name, can supersede them."
)


class RoutingError(RuntimeError):
    """Raised when routing state cannot be validated or safely changed."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def pretty_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def json_path(path: Path) -> str:
    return path.as_posix()


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RoutingError(f"Cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RoutingError(f"{label} must be a JSON object: {path}")
    return value


def atomic_write(path: Path, data: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.bbk-routing-{os.getpid()}")
    temp.write_bytes(data)
    if mode is not None and os.name != "nt":
        os.chmod(temp, mode)
    os.replace(temp, path)


def normalized_path(path: Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path))).replace("\\", "/")


def validate_route(value: Any, where: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise RoutingError(f"{where} must be an object")
    if set(value) != {"model", "thinkingLevel"}:
        raise RoutingError(f"{where} must contain exactly model and thinkingLevel")
    model = value.get("model")
    level = value.get("thinkingLevel")
    if not isinstance(model, str) or not model.strip() or "\n" in model or "\r" in model:
        raise RoutingError(f"{where}.model must be one non-empty line")
    if len(model) > 300:
        raise RoutingError(f"{where}.model is unreasonably long")
    if level not in THINKING_LEVELS:
        raise RoutingError(
            f"{where}.thinkingLevel must be one of {', '.join(sorted(THINKING_LEVELS))}"
        )
    return {"model": model.strip(), "thinkingLevel": str(level)}


def role_names(package_root: Path) -> list[str]:
    value = load_json(package_root / "spec" / "roles.json", "role catalogue")
    names = [
        item.get("name")
        for item in value.get("roles", [])
        if isinstance(item, Mapping) and isinstance(item.get("name"), str)
    ]
    if not names or len(names) != len(set(names)) or any(not ROLE_PATTERN.fullmatch(name) for name in names):
        raise RoutingError("Canonical role catalogue contains invalid or duplicate role names")
    return names


def load_profiles(package_root: Path, version: str, roles: list[str]) -> dict[str, Any]:
    path = package_root / "spec" / "omp-model-routing-profiles.json"
    value = load_json(path, "OMP routing profiles")
    if value.get("schema_version") != "bbk.omp-model-routing-profiles.v1":
        raise RoutingError("Unsupported OMP routing profile catalogue schema")
    if value.get("package_version") != version:
        raise RoutingError(
            f"OMP routing profile catalogue version {value.get('package_version')!r} != {version!r}"
        )
    profiles = value.get("profiles")
    if not isinstance(profiles, Mapping) or not profiles:
        raise RoutingError("OMP routing profile catalogue has no profiles")
    expected = set(roles)
    clean: dict[str, Any] = {}
    for profile_id, raw in sorted(profiles.items()):
        if not isinstance(profile_id, str) or not PROFILE_PATTERN.fullmatch(profile_id):
            raise RoutingError(f"Invalid OMP routing profile id: {profile_id!r}")
        if not isinstance(raw, Mapping):
            raise RoutingError(f"Profile {profile_id} must be an object")
        description = raw.get("description")
        routes = raw.get("roles")
        if not isinstance(description, str) or not description.strip():
            raise RoutingError(f"Profile {profile_id} has no description")
        if not isinstance(routes, Mapping):
            raise RoutingError(f"Profile {profile_id}.roles must be an object")
        missing = sorted(expected - set(routes))
        extra = sorted(set(routes) - expected)
        if missing or extra:
            raise RoutingError(f"Profile {profile_id} role coverage mismatch; missing={missing}, extra={extra}")
        clean[profile_id] = {
            "description": description.strip(),
            "roles": {name: validate_route(routes[name], f"profiles.{profile_id}.roles.{name}") for name in roles},
        }
    return clean


def load_custom_profile(path: Path, version: str, roles: list[str]) -> tuple[str, str, dict[str, dict[str, str]]]:
    value = load_json(path, "custom OMP routing profile")
    if value.get("schema_version") != "bbk.omp-model-routing-profile.v1":
        raise RoutingError("Custom profile schema_version must be bbk.omp-model-routing-profile.v1")
    if value.get("package_version") != version:
        raise RoutingError(
            f"Custom profile package_version {value.get('package_version')!r} != {version!r}"
        )
    profile_id = value.get("id")
    description = value.get("description")
    if not isinstance(profile_id, str) or not PROFILE_PATTERN.fullmatch(profile_id):
        raise RoutingError("Custom profile id is invalid")
    if not isinstance(description, str) or not description.strip():
        raise RoutingError("Custom profile description must be a non-empty string")
    default = validate_route(value.get("default"), "default")
    overrides = value.get("roles")
    if not isinstance(overrides, Mapping):
        raise RoutingError("Custom profile roles must be an object")
    unknown = sorted(set(overrides) - set(roles))
    if unknown:
        raise RoutingError(f"Custom profile references unknown roles: {unknown}")
    routes = {name: dict(default) for name in roles}
    for name, route in overrides.items():
        routes[name] = validate_route(route, f"roles.{name}")
    return profile_id, description.strip(), routes


def load_binding(path: Path) -> dict[str, Any]:
    value = load_json(path, "OMP package binding")
    if value.get("schema") != "bbk.omp-package-binding.v2":
        raise RoutingError(
            "This BBK installation does not expose mutable OMP routing metadata; reinstall alpha.11.3 or later"
        )
    required = {"version", "package_root", "manifest_path", "omp_agents", "state_path"}
    missing = sorted(required - set(value))
    if missing:
        raise RoutingError(f"OMP package binding is missing fields: {missing}")
    return value


def manifest_record_map(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for item in manifest.get("files", []):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise RoutingError("Install manifest contains an invalid file record")
        key = normalized_path(Path(item["path"]))
        if key in records:
            raise RoutingError(f"Install manifest contains duplicate destination {item['path']}")
        records[key] = item
    return records


def require_current(path: Path, record: Mapping[str, Any], label: str) -> bytes:
    if not path.is_file():
        raise RoutingError(f"{label} is missing: {path}")
    data = path.read_bytes()
    actual = sha256_bytes(data)
    expected = record.get("sha256")
    if actual != expected:
        raise RoutingError(
            f"{label} differs from the BBK install manifest: {path}; expected {expected}, found {actual}. "
            "Reinstall or restore it before changing model routing."
        )
    return data


def parse_agent_route(data: bytes, role: str) -> dict[str, str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RoutingError(f"OMP agent {role} is not valid UTF-8: {exc}") from exc
    if not text.startswith("---\n"):
        raise RoutingError(f"OMP agent {role} has no YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise RoutingError(f"OMP agent {role} has unterminated YAML frontmatter")
    front = text[4:end]
    found: dict[str, str] = {}
    for key in ("name", "model", "thinkingLevel"):
        matches = re.findall(rf"(?m)^{re.escape(key)}:\s*(.+?)\s*$", front)
        if len(matches) != 1:
            raise RoutingError(f"OMP agent {role} must contain exactly one {key} field")
        raw = matches[0]
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw.strip().strip('"').strip("'")
        if not isinstance(parsed, str):
            raise RoutingError(f"OMP agent {role} field {key} is not a string")
        found[key] = parsed
    if found["name"] != role:
        raise RoutingError(f"OMP agent filename role {role} contains name {found['name']!r}")
    return validate_route(
        {"model": found["model"], "thinkingLevel": found["thinkingLevel"]},
        f"installed agent {role}",
    )


def patch_agent_route(data: bytes, role: str, route: Mapping[str, str]) -> bytes:
    text = data.decode("utf-8")
    for key in ("model", "thinkingLevel"):
        replacement = f"{key}: {json.dumps(route[key], ensure_ascii=False)}"
        text, count = re.subn(rf"(?m)^{re.escape(key)}:\s*.*$", replacement, text, count=1)
        if count != 1:
            raise RoutingError(f"Cannot update {key} in OMP agent {role}")
    result = text.encode("utf-8")
    parsed = parse_agent_route(result, role)
    if parsed != dict(route):
        raise RoutingError(f"Post-update route validation failed for {role}")
    return result


def compact_counts(routes: Mapping[str, Mapping[str, str]]) -> list[dict[str, Any]]:
    counts: dict[tuple[str, str], int] = {}
    for route in routes.values():
        key = (str(route["model"]), str(route["thinkingLevel"]))
        counts[key] = counts.get(key, 0) + 1
    return [
        {"model": model, "thinkingLevel": level, "roles": count}
        for (model, level), count in sorted(counts.items())
    ]


def load_context(binding_path: Path) -> dict[str, Any]:
    binding = load_binding(binding_path.resolve())
    package_root = Path(binding["package_root"]).expanduser().resolve()
    manifest_path = Path(binding["manifest_path"]).expanduser().resolve()
    agents_dir = Path(binding["omp_agents"]).expanduser().resolve()
    state_path = Path(binding["state_path"]).expanduser().resolve()
    version = str(binding["version"])
    if (package_root / "VERSION").read_text(encoding="utf-8").strip() != version:
        raise RoutingError("OMP package binding does not match its installed package root")
    roles = role_names(package_root)
    profiles = load_profiles(package_root, version, roles)
    manifest = load_json(manifest_path, "BBK install manifest")
    if manifest.get("schema") != "bbk.install-manifest.v1" or manifest.get("version") != version:
        raise RoutingError("BBK install manifest does not match the bound package version")
    if not manifest.get("omp"):
        raise RoutingError("The bound BBK installation does not own OMP agents")
    records = manifest_record_map(manifest)
    state_record = records.get(normalized_path(state_path))
    if state_record is None:
        raise RoutingError(f"Install manifest does not own OMP routing state {state_path}")
    state_bytes = require_current(state_path, state_record, "OMP routing state")
    try:
        state = json.loads(state_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RoutingError(f"OMP routing state is invalid: {exc}") from exc
    if not isinstance(state, dict) or state.get("schema") != "bbk.omp-model-routing-state.v1":
        raise RoutingError("Unsupported OMP routing state schema")
    if state.get("package_version") != version:
        raise RoutingError("OMP routing state package version mismatch")
    agent_files: dict[str, Path] = {name: agents_dir / f"{name}.md" for name in roles}
    agent_records: dict[str, dict[str, Any]] = {}
    agent_bytes: dict[str, bytes] = {}
    actual_routes: dict[str, dict[str, str]] = {}
    for name, path in agent_files.items():
        record = records.get(normalized_path(path))
        if record is None:
            raise RoutingError(f"Install manifest does not own OMP agent {name}: {path}")
        data = require_current(path, record, f"OMP agent {name}")
        agent_records[name] = record
        agent_bytes[name] = data
        actual_routes[name] = parse_agent_route(data, name)
    state_routes = state.get("roles")
    if state_routes != actual_routes:
        raise RoutingError("OMP routing state does not match the installed agent frontmatter")
    baseline = state.get("installation_default")
    if not isinstance(baseline, Mapping) or set(baseline) != set(roles):
        raise RoutingError("OMP routing state has no complete installation_default")
    clean_baseline = {name: validate_route(baseline[name], f"installation_default.{name}") for name in roles}
    return {
        "binding": binding,
        "binding_path": binding_path.resolve(),
        "package_root": package_root,
        "manifest_path": manifest_path,
        "agents_dir": agents_dir,
        "state_path": state_path,
        "version": version,
        "roles": roles,
        "profiles": profiles,
        "manifest": manifest,
        "records": records,
        "state": state,
        "state_record": state_record,
        "agent_files": agent_files,
        "agent_records": agent_records,
        "agent_bytes": agent_bytes,
        "actual_routes": actual_routes,
        "baseline": clean_baseline,
    }


def state_payload(
    context: Mapping[str, Any],
    routes: Mapping[str, Mapping[str, str]],
    *,
    active_profile: str,
    source: str,
    description: str,
) -> dict[str, Any]:
    clean_routes = {name: dict(routes[name]) for name in context["roles"]}
    return {
        "schema": "bbk.omp-model-routing-state.v1",
        "package_version": context["version"],
        "active_profile": active_profile,
        "source": source,
        "description": description,
        "updated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "installation_default": context["baseline"],
        "roles": clean_routes,
        "routes_sha256": sha256_bytes(canonical_json_bytes(clean_routes)),
    }


def apply_routes(
    context: dict[str, Any],
    routes: Mapping[str, Mapping[str, str]],
    *,
    active_profile: str,
    source: str,
    description: str,
) -> dict[str, Any]:
    expected = set(context["roles"])
    if set(routes) != expected:
        raise RoutingError("Applied route set must cover every canonical role exactly once")
    clean = {name: validate_route(routes[name], f"roles.{name}") for name in context["roles"]}
    changed = [name for name in context["roles"] if clean[name] != context["actual_routes"][name]]
    new_agent_bytes = {
        name: patch_agent_route(context["agent_bytes"][name], name, clean[name])
        for name in changed
    }
    new_state = state_payload(
        context,
        clean,
        active_profile=active_profile,
        source=source,
        description=description,
    )
    new_state_bytes = pretty_json_bytes(new_state)
    manifest = json.loads(json.dumps(context["manifest"]))
    records = manifest_record_map(manifest)
    for name, data in new_agent_bytes.items():
        record = records[normalized_path(context["agent_files"][name])]
        record["sha256"] = sha256_bytes(data)
        record["routing_profile"] = active_profile
    state_record = records[normalized_path(context["state_path"])]
    state_record["sha256"] = sha256_bytes(new_state_bytes)
    state_record["routing_profile"] = active_profile
    manifest["omp_runtime_routing"] = {
        "schema": "bbk.omp-runtime-routing.v1",
        "active_profile": active_profile,
        "source": source,
        "description": description,
        "state_path": json_path(context["state_path"]),
        "routes_sha256": new_state["routes_sha256"],
        "changed_role_count": len(changed),
        "updated_at": new_state["updated_at"],
    }
    new_manifest_bytes = pretty_json_bytes(manifest)

    originals: dict[Path, bytes] = {
        context["state_path"]: context["state_path"].read_bytes(),
        context["manifest_path"]: context["manifest_path"].read_bytes(),
    }
    originals.update({context["agent_files"][name]: context["agent_bytes"][name] for name in changed})
    try:
        for name in changed:
            path = context["agent_files"][name]
            mode = path.stat().st_mode & 0o777 if os.name != "nt" else None
            atomic_write(path, new_agent_bytes[name], mode)
        state_mode = context["state_path"].stat().st_mode & 0o777 if os.name != "nt" else None
        atomic_write(context["state_path"], new_state_bytes, state_mode)
        manifest_mode = context["manifest_path"].stat().st_mode & 0o777 if os.name != "nt" else None
        atomic_write(context["manifest_path"], new_manifest_bytes, manifest_mode)
    except Exception as exc:
        for path, data in originals.items():
            try:
                mode = path.stat().st_mode & 0o777 if os.name != "nt" and path.exists() else None
                atomic_write(path, data, mode)
            except Exception:
                pass
        raise RoutingError(f"OMP routing update failed and rollback was attempted: {exc}") from exc

    return {
        "schema": "bbk.omp-model-routing-result.v1",
        "status": "APPLIED",
        "active_profile": active_profile,
        "source": source,
        "description": description,
        "changed_roles": changed,
        "changed_role_count": len(changed),
        "routes_sha256": new_state["routes_sha256"],
        "routes": clean,
        "summary": compact_counts(clean),
        "note": (
            "Future BBK OMP spawns use the new BBK-managed route; already-running sub-agents are "
            f"unaffected. {PRECEDENCE_NOTE}"
        ),
        "precedence_note": PRECEDENCE_NOTE,
    }


def status_result(context: Mapping[str, Any]) -> dict[str, Any]:
    state = context["state"]
    return {
        "schema": "bbk.omp-model-routing-status.v1",
        "status": "PASS",
        "package_version": context["version"],
        "active_profile": state.get("active_profile"),
        "source": state.get("source"),
        "description": state.get("description"),
        "routes_sha256": state.get("routes_sha256"),
        "roles": context["actual_routes"],
        "summary": compact_counts(context["actual_routes"]),
        "available_profiles": [
            {
                "id": "installation-default",
                "description": "Restore the exact OMP routes selected when this BBK installation was created.",
                "summary": compact_counts(context["baseline"]),
            },
            *[
                {
                    "id": profile_id,
                    "description": profile["description"],
                    "summary": compact_counts(profile["roles"]),
                }
                for profile_id, profile in context["profiles"].items()
            ],
        ],
        "binding_path": json_path(context["binding_path"]),
        "manifest_path": json_path(context["manifest_path"]),
        "state_path": json_path(context["state_path"]),
        "omp_agents": json_path(context["agents_dir"]),
        "route_surface": "bbk-managed-agent-frontmatter",
        "precedence_note": PRECEDENCE_NOTE,
    }


def apply_profile(context: dict[str, Any], profile_id: str) -> dict[str, Any]:
    if profile_id == "installation-default":
        return apply_routes(
            context,
            context["baseline"],
            active_profile="installation-default",
            source="installation-default",
            description="Exact OMP routes selected when this BBK installation was created.",
        )
    profile = context["profiles"].get(profile_id)
    if profile is None:
        raise RoutingError(
            f"Unknown profile {profile_id!r}; available: installation-default, "
            + ", ".join(context["profiles"])
        )
    return apply_routes(
        context,
        profile["roles"],
        active_profile=profile_id,
        source=f"bundled-profile:{profile_id}",
        description=profile["description"],
    )


def set_role(context: dict[str, Any], role: str, model: str, thinking_level: str) -> dict[str, Any]:
    if role not in context["roles"]:
        raise RoutingError(f"Unknown BBK role {role!r}")
    route = validate_route({"model": model, "thinkingLevel": thinking_level}, f"roles.{role}")
    routes = {name: dict(value) for name, value in context["actual_routes"].items()}
    routes[role] = route
    return apply_routes(
        context,
        routes,
        active_profile="custom",
        source=f"interactive-role-edit:{role}",
        description=f"Custom OMP routing with an explicit override for {role}.",
    )


def apply_file(context: dict[str, Any], path: Path) -> dict[str, Any]:
    profile_id, description, routes = load_custom_profile(path.resolve(), context["version"], context["roles"])
    return apply_routes(
        context,
        routes,
        active_profile=profile_id,
        source=f"profile-file:{json_path(path.resolve())}",
        description=description,
    )


def export_profile(context: Mapping[str, Any], path: Path, profile_id: str, description: str) -> dict[str, Any]:
    if not PROFILE_PATTERN.fullmatch(profile_id):
        raise RoutingError("Export profile id is invalid")
    if not description.strip():
        raise RoutingError("Export description must not be empty")
    routes = context["actual_routes"]
    counts: dict[tuple[str, str], int] = {}
    for route in routes.values():
        key = (route["model"], route["thinkingLevel"])
        counts[key] = counts.get(key, 0) + 1
    default_key = sorted(counts, key=lambda key: (-counts[key], key))[0]
    default = {"model": default_key[0], "thinkingLevel": default_key[1]}
    overrides = {name: route for name, route in routes.items() if route != default}
    value = {
        "schema_version": "bbk.omp-model-routing-profile.v1",
        "package_version": context["version"],
        "id": profile_id,
        "description": description.strip(),
        "default": default,
        "roles": overrides,
    }
    output = path.expanduser().resolve()
    if output.exists() and not output.is_file():
        raise RoutingError(f"Export destination is not a regular file: {output}")
    atomic_write(output, pretty_json_bytes(value), 0o644 if os.name != "nt" else None)
    return {
        "schema": "bbk.omp-model-routing-export.v1",
        "status": "EXPORTED",
        "path": json_path(output),
        "id": profile_id,
        "default": default,
        "override_count": len(overrides),
        "sha256": sha256_file(output),
    }


def human(value: Mapping[str, Any]) -> str:
    schema = value.get("schema")
    if schema == "bbk.omp-model-routing-status.v1":
        lines = [
            f"BBK OMP routing: {value.get('active_profile')}",
            f"Source: {value.get('source')}",
            "Routes:",
        ]
        for item in value.get("summary", []):
            lines.append(
                f"- {item['roles']} roles: {item['model']} / {item['thinkingLevel']}"
            )
        lines.append("Profiles: " + ", ".join(item["id"] for item in value.get("available_profiles", [])))
        if value.get("precedence_note"):
            lines.append(f"Precedence: {value['precedence_note']}")
        return "\n".join(lines)
    if schema == "bbk.omp-model-routing-result.v1":
        return (
            f"BBK OMP routing applied: {value.get('active_profile')}\n"
            f"Changed roles: {value.get('changed_role_count')}\n"
            f"Routes SHA-256: {value.get('routes_sha256')}\n"
            f"{value.get('note')}"
        )
    if schema == "bbk.omp-model-routing-export.v1":
        return f"BBK OMP routing profile exported: {value.get('path')}"
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--binding", default=str(DEFAULT_BINDING), help="installed bbk-package-root.json binding")
    result.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="show effective OMP routes and available profiles")
    apply_parser = sub.add_parser("apply-profile", help="apply a bundled profile or installation-default")
    apply_parser.add_argument("profile_id")
    role_parser = sub.add_parser("set-role", help="set one installed BBK OMP agent route")
    role_parser.add_argument("role")
    role_parser.add_argument("--model", required=True)
    role_parser.add_argument("--thinking-level", required=True, choices=sorted(THINKING_LEVELS))
    file_parser = sub.add_parser("apply-file", help="apply a bbk.omp-model-routing-profile.v1 file")
    file_parser.add_argument("path")
    export_parser = sub.add_parser("export", help="export the effective route as an editable profile")
    export_parser.add_argument("path")
    export_parser.add_argument("--id", default="exported-profile")
    export_parser.add_argument("--description", default="Exported BBK OMP routing profile.")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        context = load_context(Path(args.binding).expanduser())
        if args.command == "status":
            value = status_result(context)
        elif args.command == "apply-profile":
            value = apply_profile(context, args.profile_id)
        elif args.command == "set-role":
            value = set_role(context, args.role, args.model, args.thinking_level)
        elif args.command == "apply-file":
            value = apply_file(context, Path(args.path).expanduser())
        elif args.command == "export":
            value = export_profile(context, Path(args.path), args.id, args.description)
        else:
            raise RoutingError(f"Unsupported command: {args.command}")
    except RoutingError as exc:
        error = {"schema": "bbk.omp-model-routing-error.v1", "status": "ERROR", "error": str(exc)}
        if args.json:
            print(json.dumps(error, indent=2, ensure_ascii=False, sort_keys=True))
        else:
            print(f"BBK OMP model routing error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(human(value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
