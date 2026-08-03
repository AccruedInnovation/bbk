#!/usr/bin/env python3
"""Requirement-scoped, read-only BBK host capability preflight.

Only capabilities named in the request are inspected. Results are evidence
bound to one exact host identity; they never grant execution authority.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from strict_json import load_path
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from strict_json import load_path

STATUSES = (
    "AVAILABLE", "UNAVAILABLE", "VERSION_MISMATCH", "PERMISSION_BLOCKED",
    "UNKNOWN", "REQUIRES_LIVE_PROBE",
)
AUTHORITY_BOUNDARY = (
    "Host preflight records bounded read-only observations for plan-named capabilities. "
    "It is not execution authorization, effect authority, semantic acceptance, or release evidence."
)


class HostPreflightError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _utc_now(now: dt.datetime | None = None) -> str:
    current = now or dt.datetime.now(dt.timezone.utc)
    return current.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def host_identity() -> dict[str, Any]:
    observed = {
        "system": platform.system(),
        "node": platform.node(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "pythonVersion": platform.python_version(),
        "pythonExecutable": str(Path(sys.executable).resolve()),
    }
    return {**observed, "digest": _digest(observed)}


def validate_request(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["request must be an object"]
    if value.get("schema") != "bbk.host-preflight-request.v1":
        errors.append("schema must equal bbk.host-preflight-request.v1")
    if not isinstance(value.get("requestId"), str) or not value.get("requestId"):
        errors.append("requestId must be non-empty")
    freshness = value.get("freshnessSeconds", 3600)
    if not isinstance(freshness, int) or isinstance(freshness, bool) or freshness < 0:
        errors.append("freshnessSeconds must be an integer >= 0")
    requirements = value.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        errors.append("requirements must be a non-empty array")
        return errors
    ids: set[str] = set()
    for index, item in enumerate(requirements):
        where = f"requirements[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where} must be an object")
            continue
        ident = item.get("id")
        if not isinstance(ident, str) or not ident:
            errors.append(f"{where}.id must be non-empty")
        elif ident in ids:
            errors.append(f"{where}.id must be unique")
        else:
            ids.add(ident)
        kind = item.get("kind")
        if kind not in {"COMMAND", "PATH", "ENVIRONMENT", "LIVE"}:
            errors.append(f"{where}.kind is not recognized")
        if not isinstance(item.get("required", True), bool):
            errors.append(f"{where}.required must be boolean")
        if kind == "COMMAND" and (not isinstance(item.get("command"), str) or not item.get("command")):
            errors.append(f"{where}.command must be non-empty")
        if kind == "PATH" and (not isinstance(item.get("path"), str) or not item.get("path")):
            errors.append(f"{where}.path must be non-empty")
        if kind == "ENVIRONMENT" and (not isinstance(item.get("name"), str) or not item.get("name")):
            errors.append(f"{where}.name must be non-empty")
        if kind == "LIVE" and (not isinstance(item.get("description"), str) or not item.get("description")):
            errors.append(f"{where}.description must be non-empty")
    return errors


def _tool_identities(requirements: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in requirements:
        if item.get("kind") != "COMMAND":
            continue
        command = str(item.get("command", ""))
        resolved = shutil.which(command)
        identity: dict[str, Any] = {"command": command, "resolved": resolved}
        if resolved:
            try:
                stat = Path(resolved).stat()
                identity.update({"size": stat.st_size, "mtimeNs": stat.st_mtime_ns})
            except OSError as exc:
                identity["statError"] = type(exc).__name__
        result[str(item.get("id"))] = identity
    return result


def _probe_command(item: Mapping[str, Any], timeout: float) -> tuple[dict[str, Any], str | None]:
    command = str(item["command"])
    resolved = shutil.which(command)
    base = {"id": item["id"], "kind": "COMMAND", "required": item.get("required", True), "command": command}
    if not resolved:
        return {**base, "status": "UNAVAILABLE", "observation": "command not found on PATH"}, None
    path = Path(resolved)
    if not os.access(path, os.X_OK):
        return {**base, "status": "PERMISSION_BLOCKED", "resolved": resolved, "observation": "command is not executable"}, None
    args = item.get("versionArgs", ["--version"])
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        return {**base, "status": "UNKNOWN", "resolved": resolved, "observation": "invalid versionArgs"}, None
    try:
        completed = subprocess.run(
            [resolved, *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False,
            env={**os.environ, "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8"},
        )
    except PermissionError:
        return {**base, "status": "PERMISSION_BLOCKED", "resolved": resolved, "observation": "permission denied"}, None
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {**base, "status": "UNKNOWN", "resolved": resolved, "observation": type(exc).__name__}, None
    output = completed.stdout.strip()[:8192]
    version = output.splitlines()[0] if output else ""
    status = "AVAILABLE" if completed.returncode == 0 else "UNKNOWN"
    expected = item.get("expectedVersionPattern")
    if status == "AVAILABLE" and isinstance(expected, str):
        try:
            if re.search(expected, output) is None:
                status = "VERSION_MISMATCH"
        except re.error:
            status = "UNKNOWN"
    return {
        **base, "status": status, "resolved": resolved,
        "versionCommand": [resolved, *args], "exitCode": completed.returncode,
        "versionOutput": output, "expectedVersionPattern": expected,
    }, version or None


def _probe_path(item: Mapping[str, Any]) -> dict[str, Any]:
    raw = str(item["path"])
    path = Path(raw).expanduser()
    base = {"id": item["id"], "kind": "PATH", "required": item.get("required", True), "path": raw}
    try:
        exists = path.exists()
    except OSError as exc:
        return {**base, "status": "UNKNOWN", "observation": type(exc).__name__}
    if not exists:
        return {**base, "status": "UNAVAILABLE", "observation": "path does not exist"}
    expected_kind = item.get("expectedKind", "ANY")
    if expected_kind == "FILE" and not path.is_file():
        return {**base, "status": "UNAVAILABLE", "observation": "path is not a file"}
    if expected_kind == "DIRECTORY" and not path.is_dir():
        return {**base, "status": "UNAVAILABLE", "observation": "path is not a directory"}
    access = item.get("access", ["READ"])
    modes = {"READ": os.R_OK, "WRITE": os.W_OK, "EXECUTE": os.X_OK}
    if not isinstance(access, list) or any(value not in modes for value in access):
        return {**base, "status": "UNKNOWN", "observation": "invalid access request"}
    denied = [value for value in access if not os.access(path, modes[value])]
    if denied:
        return {**base, "status": "PERMISSION_BLOCKED", "denied": denied, "resolved": str(path.resolve())}
    return {**base, "status": "AVAILABLE", "resolved": str(path.resolve()), "observedKind": "DIRECTORY" if path.is_dir() else "FILE" if path.is_file() else "OTHER"}


def _probe(item: Mapping[str, Any], timeout: float) -> tuple[dict[str, Any], str | None]:
    kind = item["kind"]
    if kind == "COMMAND":
        return _probe_command(item, timeout)
    if kind == "PATH":
        return _probe_path(item), None
    if kind == "ENVIRONMENT":
        name = str(item["name"])
        present = name in os.environ
        return ({"id": item["id"], "kind": kind, "required": item.get("required", True), "name": name,
                 "status": "AVAILABLE" if present else "UNAVAILABLE", "valueRedacted": True}, None)
    return ({"id": item["id"], "kind": "LIVE", "required": item.get("required", True),
             "status": "REQUIRES_LIVE_PROBE", "description": item["description"]}, None)


def run_preflight(
    request: Mapping[str, Any], *, cache_dir: Path | None = None,
    use_cache: bool = True, timeout: float = 5.0, now: dt.datetime | None = None,
) -> dict[str, Any]:
    errors = validate_request(request)
    if errors:
        raise HostPreflightError("; ".join(errors))
    requirements = list(request["requirements"])
    host = host_identity()
    request_basis = {"requestId": request["requestId"], "requirements": requirements, "freshnessSeconds": request.get("freshnessSeconds", 3600)}
    requirements_digest = _digest(request_basis)
    tool_identities = _tool_identities(requirements)
    cache_key = _digest({"hostDigest": host["digest"], "requirementsDigest": requirements_digest, "toolIdentities": tool_identities,
                         "freshnessSeconds": request.get("freshnessSeconds", 3600)})
    current = now or dt.datetime.now(dt.timezone.utc)
    cache_path = cache_dir / f"{cache_key}.json" if cache_dir else None
    if use_cache and cache_path and cache_path.is_file():
        try:
            cached = load_path(cache_path)
            if (isinstance(cached, dict) and cached.get("schema") == "bbk.host-preflight-result.v1"
                    and cached.get("cache", {}).get("key") == cache_key
                    and _parse_time(cached["cache"]["freshUntil"]) >= current.astimezone(dt.timezone.utc)):
                cached = dict(cached)
                cached["cache"] = {**cached["cache"], "hit": True, "path": str(cache_path)}
                return cached
        except (OSError, ValueError, KeyError, TypeError):
            pass
    observations: list[dict[str, Any]] = []
    tool_versions: dict[str, Any] = {}
    for item in requirements:
        observation, version = _probe(item, timeout)
        observations.append(observation)
        if item["kind"] == "COMMAND":
            tool_versions[str(item["id"])] = {
                "version": version,
                "identity": tool_identities.get(str(item["id"])),
            }
    created = current.astimezone(dt.timezone.utc).replace(microsecond=0)
    fresh_until = created + dt.timedelta(seconds=int(request.get("freshnessSeconds", 3600)))
    required_failures = [item["id"] for item in observations if item.get("required", True) and item["status"] != "AVAILABLE"]
    result = {
        "schema": "bbk.host-preflight-result.v1",
        "requestId": request["requestId"],
        "status": "PASS" if not required_failures else "BLOCKED",
        "host": host,
        "requirementsDigest": requirements_digest,
        "toolVersions": tool_versions,
        "observations": observations,
        "requiredCapabilityBlockers": required_failures,
        "cache": {"hit": False, "key": cache_key, "createdAt": _utc_now(created), "freshUntil": _utc_now(fresh_until),
                  "path": str(cache_path) if cache_path else None},
        "authorityBoundary": AUTHORITY_BOUNDARY,
        "claimsNotEstablished": ["execution authorization", "effect authority", "semantic acceptance", "release readiness"],
    }
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp = cache_path.with_suffix(f".tmp-{os.getpid()}")
        temp.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, cache_path)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request")
    parser.add_argument("--output")
    parser.add_argument("--cache-dir")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--timeout", type=float, default=5.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        request = load_path(Path(args.request).expanduser())
        result = run_preflight(request, cache_dir=Path(args.cache_dir).expanduser() if args.cache_dir else None,
                               use_cache=not args.no_cache, timeout=args.timeout)
    except (HostPreflightError, OSError, ValueError) as exc:
        print(json.dumps({"schema": "bbk.host-preflight-error.v1", "status": "REJECTED", "message": str(exc)}, indent=2), file=sys.stderr)
        return 2
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        Path(args.output).expanduser().write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
