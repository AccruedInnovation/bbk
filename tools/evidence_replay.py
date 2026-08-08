#!/usr/bin/env python3
"""Bounded evidence-capture replay and wrapper preflight contracts."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


class ReplayError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def invocation_identity(executable: str, arguments: Sequence[str], inputs: Any, environment_constraints: Any) -> dict[str, str]:
    if not executable.strip():
        raise ReplayError("BBK-REPLAY-011", "executable is required")
    return {
        "executable": executable,
        "arguments_sha256": _sha(list(arguments)),
        "inputs_sha256": _sha(inputs),
        "environment_constraints_sha256": _sha(environment_constraints),
    }


def evaluate_replay(attempt: Mapping[str, Any], *, candidate_frozen: bool = False) -> dict[str, Any]:
    """Return a typed replay admission decision for one physical attempt."""
    reasons: list[str] = []
    physical = int(attempt.get("physical_command_attempt") or 0)
    effects = attempt.get("effects_observed") if isinstance(attempt.get("effects_observed"), Mapping) else {}
    cleanup = attempt.get("cleanup") if isinstance(attempt.get("cleanup"), Mapping) else {}
    identity = attempt.get("invocation_identity") if isinstance(attempt.get("invocation_identity"), Mapping) else {}
    identity_valid = bool(str(identity.get("executable") or "").strip()) and all(
        isinstance(identity.get(key), str) and re.fullmatch(r"[0-9a-f]{64}", str(identity.get(key)))
        for key in ("arguments_sha256", "inputs_sha256", "environment_constraints_sha256")
    )
    checks = [
        (attempt.get("effect_class") in {"READ_ONLY", "IDEMPOTENT_DISPOSABLE"}, "BBK-REPLAY-001", "effect class is not replay-safe"),
        (attempt.get("disposition") == "EVIDENCE_CAPTURE_FAILED", "BBK-REPLAY-002", "failure was not limited to evidence capture"),
        (effects.get("product_mutation") == "NONE", "BBK-REPLAY-003", "product mutation is not proven NONE"),
        (effects.get("external_effect") == "NONE", "BBK-REPLAY-004", "external effect is not proven NONE"),
        (cleanup.get("state") == "COMPLETE", "BBK-REPLAY-005", "cleanup is not COMPLETE"),
        (cleanup.get("remaining_processes_or_handles") is False, "BBK-REPLAY-006", "processes or handles remain"),
        (identity_valid, "BBK-REPLAY-008", "invocation identity is missing or incomplete"),
        (not candidate_frozen, "BBK-REPLAY-007", "candidate is frozen"),
        (physical == 1, "BBK-REPLAY-009", "only physical attempt 1 may be replayed"),
    ]
    first_code = None
    for passed, code, message in checks:
        if not passed:
            reasons.append(message)
            first_code = first_code or code
    eligible = not reasons
    semantic_id = str(attempt.get("semantic_command_id") or "")
    execution_ref = str(attempt.get("execution_attempt_ref") or "")
    result = {
        "schema": "bbk.command-replay-admission.v1",
        "status": "PASS" if eligible else "BLOCKED",
        "code": "BBK-REPLAY-ADMITTED" if eligible else first_code,
        "semantic_command_id": semantic_id,
        "execution_attempt_ref": execution_ref,
        "eligible": eligible,
        "physical_command_attempt": physical,
        "next_physical_command_attempt": 2 if eligible else None,
        "replay_of_physical_attempt": 1 if eligible else None,
        "maximum_replays": 1,
        "same_execution_attempt": True if eligible else None,
        "reasons": reasons,
        "planning_reopen_permitted": False,
    }
    return result


def replay_attempt(previous: Mapping[str, Any], *, candidate_frozen: bool = False) -> dict[str, Any]:
    decision = evaluate_replay(previous, candidate_frozen=candidate_frozen)
    if not decision["eligible"]:
        raise ReplayError(str(decision["code"]), "; ".join(decision["reasons"]))
    result = json.loads(json.dumps(previous))
    result["physical_command_attempt"] = 2
    result["disposition"] = "PLANNED"
    result["replay"] = {
        "eligible": False,
        "reason": "This is the single permitted repaired replay; no further replay is available.",
        "maximum_replays": 1,
        "replay_of_physical_attempt": 1,
    }
    result["evidence_refs"] = list(previous.get("evidence_refs") or [])
    return result


def powershell_capture_preflight(script_text: str, receipt_dir: Path) -> dict[str, Any]:
    """Perform deterministic static and filesystem preflight for a PS wrapper."""
    reserved = {
        "args", "error", "erroractionpreference", "false", "home", "host", "input",
        "lastexitcode", "matches", "null", "pid", "profile", "pshome", "pwd", "shellid", "true",
    }
    assigned = {match.group(1).lower() for match in re.finditer(r"(?m)^\s*\$([A-Za-z_][A-Za-z0-9_]*)\s*=", script_text)}
    collisions = sorted(assigned & reserved)
    checks: list[dict[str, Any]] = []
    checks.append({"id": "reserved-variable-collisions", "status": "PASS" if not collisions else "FAIL", "details": collisions})

    aliases = {match.group(1).lower() for match in re.finditer(r"(?im)^\s*(?:Set-Alias|New-Alias)\s+(?:-Name\s+)?['\"]?([A-Za-z_][A-Za-z0-9_-]*)", script_text)}
    selected_names = assigned | {match.group(1).lower() for match in re.finditer(r"(?im)^\s*function\s+([A-Za-z_][A-Za-z0-9_-]*)", script_text)}
    alias_collisions = sorted(aliases & selected_names)
    checks.append({"id": "alias-shadowing", "status": "PASS" if not alias_collisions else "FAIL", "details": alias_collisions})

    unsafe_native = "$ErrorActionPreference = 'Stop'" in script_text and "PSNativeCommandUseErrorActionPreference" not in script_text
    checks.append({"id": "native-stderr-policy", "status": "FAIL" if unsafe_native else "PASS", "details": "native stderr may terminate wrapper" if unsafe_native else None})
    captures_exit = "$LASTEXITCODE" in script_text or ".ExitCode" in script_text
    checks.append({"id": "exit-code-capture", "status": "PASS" if captures_exit else "FAIL", "details": None})
    captures_output = "2>&1" in script_text or ("RedirectStandardError" in script_text and "RedirectStandardOutput" in script_text)
    checks.append({"id": "stdout-stderr-capture", "status": "PASS" if captures_output else "FAIL", "details": None})

    quoting = bool(re.search(r"&\s+\$[A-Za-z_]\w*\s+@\w+", script_text)) or "ArgumentList" in script_text or "ProcessStartInfo" in script_text
    checks.append({"id": "executable-argument-quoting", "status": "PASS" if quoting else "FAIL", "details": None})
    timeout = bool(re.search(r"(?i)WaitForExit\s*\(|Wait-Job\b[^\n]*-Timeout|Timeout(?:Seconds|Milliseconds)?", script_text))
    checks.append({"id": "timeout-control", "status": "PASS" if timeout else "FAIL", "details": None})
    cleanup = bool(re.search(r"(?i)\.Kill\s*\(|Stop-Process|taskkill|Remove-Job|\.Dispose\s*\(", script_text))
    checks.append({"id": "child-process-cleanup", "status": "PASS" if cleanup else "FAIL", "details": None})
    output_bound = bool(re.search(r"(?i)Max(?:imum)?Capture|MAX_CAPTURE|\.Length\s*-gt|Substring\s*\(", script_text))
    checks.append({"id": "bounded-output-capture", "status": "PASS" if output_bound else "FAIL", "details": None})
    encoding = bool(re.search(r"(?i)UTF8Encoding|-Encoding\s+utf8|Encoding\]::UTF8", script_text))
    checks.append({"id": "canonical-utf8-encoding", "status": "PASS" if encoding else "FAIL", "details": None})
    terminal_newline = bool(re.search(r"(?i)TrimEnd\s*\(|terminal.?newline|\+\s*[\"']`n[\"']", script_text))
    checks.append({"id": "terminal-newline-policy", "status": "PASS" if terminal_newline else "FAIL", "details": None})

    receipt_dir.mkdir(parents=True, exist_ok=True)
    writable = False
    atomic = False
    try:
        fd, name = tempfile.mkstemp(prefix=".bbk-preflight-", dir=receipt_dir)
        os.close(fd)
        source = Path(name)
        target = source.with_suffix(".receipt")
        os.replace(source, target)
        atomic = target.is_file()
        target.unlink(missing_ok=True)
        writable = True
    except OSError:
        pass
    checks.append({"id": "receipt-path-writable", "status": "PASS" if writable else "FAIL", "details": receipt_dir.as_posix()})
    checks.append({"id": "atomic-rename", "status": "PASS" if atomic else "FAIL", "details": receipt_dir.as_posix()})
    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    return {
        "schema": "bbk.capture-wrapper-preflight.v1",
        "status": status,
        "checks": checks,
        "mechanical_repair_permitted": status == "FAIL",
        "outcome_bearing_command_started": False,
        "effect_class": "READ_ONLY",
        "atomic_receipt_tested": atomic,
        "replay_legal": True,
    }

