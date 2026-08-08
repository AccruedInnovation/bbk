#!/usr/bin/env python3
"""Release-specific, keyless BBK qualification campaigns.

Alpha.17 exercises the governed execution substrate in a disposable local
repository.  It uses real Git, jj, Beads, and mise executables, but no provider,
credential, dependency download, external network service, or mutable user
configuration.  The resulting report is path-normalized and suitable for
release evidence; canonical low-level receipts remain in the disposable
campaign journal while the run is active.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from runtime_requirements import enforce_supported_python

enforce_supported_python(program="BBK release qualification")

try:
    import control_plane
    import governed_filesystem
    from gate_kernel import canonical_digest, canonical_json_bytes
    from governed_state import all_bindings, all_receipts, append_receipt
    from governance_status import query_status
    from omp_binding_registry import (
        activate_spawn_session,
        admit_spawn_dispatch,
        create_initial_binding,
        dispatch_status,
    )
    from qualified_task import execute_bound_task
    from read_only_spawn import compile_read_only_spawn
    from substrate import beads_adapter, git_adapter, jj_adapter, mise_adapter
    from worker_spawn import compile_bound_spawn
except ImportError:  # pragma: no cover - installed-package import fallback
    from . import control_plane, governed_filesystem
    from .gate_kernel import canonical_digest, canonical_json_bytes
    from .governed_state import all_bindings, all_receipts, append_receipt
    from .governance_status import query_status
    from .omp_binding_registry import (
        activate_spawn_session,
        admit_spawn_dispatch,
        create_initial_binding,
        dispatch_status,
    )
    from .qualified_task import execute_bound_task
    from .read_only_spawn import compile_read_only_spawn
    from .substrate import beads_adapter, git_adapter, jj_adapter, mise_adapter
    from .worker_spawn import compile_bound_spawn

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "fixtures" / "alpha17-governed-vertical-slice"
CAPABILITY_ROOT = ROOT / "spec" / "role-capabilities"
ORACLE_QUALIFICATION = ROOT / "evidence" / "qualification" / "session-inspector-oracle-alpha17.json"
OMP_HOST_CONTRACT = ROOT / "evidence" / "qualification" / "omp-host-contract-rc9.json"
HOST_VERSION = "omp/16.4.8"
RELEASE = "0.1.0-alpha.17.0.2"
WORK_UNIT_ID = "WU-017"
GATE_ID = "GATE-017-AUTOMATED"
GATE_REQUIRED_INPUTS = [
    "automated vertical-slice evidence",
    "Session Inspector oracle results",
]
GATE_PASS_CRITERIA = [
    "all invariants pass",
    "orchestrator/reviewer/validator prohibited writes blocked",
    "two worker changes integrated",
]
ASSERTION_ID = "VER-036"
AUTHORITY_REF = "authority:user:alpha17-qualification"

EXPECTED_OUTPUTS: dict[str, dict[str, str]] = {
    "backend/result.json": {
        "component": "backend",
        "owner": "bbk_worker",
        "status": "implemented",
        "work_unit": "WU-FIXTURE-BACKEND",
    },
    "frontend/result.json": {
        "component": "frontend",
        "owner": "bbk_worker",
        "status": "implemented",
        "work_unit": "WU-FIXTURE-FRONTEND",
    },
}


class QualificationError(RuntimeError):
    """A release assertion could not be established truthfully."""

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = dict(details or {})


def _sha256_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _tree_digest(root: Path) -> str:
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            entries.append({"path": relative, "kind": "symlink", "target": os.readlink(path)})
        elif path.is_file():
            entries.append(
                {
                    "path": relative,
                    "kind": "file",
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "mode": stat.S_IMODE(path.stat().st_mode),
                }
            )
    return f"sha256:{canonical_digest({'schema': 'bbk.fixture-tree.v1', 'entries': entries})}"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise QualificationError("QUALIFICATION_JSON_INVALID", f"{path} must contain an object")
    return value


def _capability_ref(role: str) -> str:
    value = _read_json(CAPABILITY_ROOT / f"{role}.json")
    return f"role:{role}@{value['policy_version']}#{value['manifest_digest']}"


def _executable(explicit: str | Path | None, environment_name: str, command: str) -> Path:
    raw = str(explicit) if explicit else os.environ.get(environment_name) or shutil.which(command)
    if not raw:
        raise QualificationError(
            f"SUBSTRATE_{command.upper()}_UNAVAILABLE",
            f"real {command} executable was not supplied through --{command}, {environment_name}, or PATH",
        )
    path = Path(raw).resolve()
    if not path.is_file() or path.is_symlink() or not os.access(path, os.X_OK):
        raise QualificationError(f"SUBSTRATE_{command.upper()}_UNSAFE_PATH", f"unsafe executable path: {path}")
    return path


def _optional_explicit_executable(
    explicit: str | Path | None,
    environment_name: str,
    command: str,
) -> Path | None:
    """Return only an explicit compatibility/test override, never PATH discovery."""
    raw = str(explicit) if explicit else os.environ.get(environment_name)
    if not raw:
        return None
    path = Path(raw).resolve()
    if not path.is_file() or path.is_symlink() or not os.access(path, os.X_OK):
        raise QualificationError(f"SUBSTRATE_{command.upper()}_UNSAFE_PATH", f"unsafe executable path: {path}")
    return path


def _managed_or_explicit_tool_command(
    project: Path,
    executable_name: str,
    explicit: Path | None,
    mise_path: Path,
) -> tuple[list[str], dict[str, str]]:
    if explicit is not None:
        return [str(explicit)], {
            "execution_mode": "EXPLICIT_EXECUTABLE",
            "executable": executable_name,
            f"{executable_name}_path": str(explicit),
        }
    try:
        return mise_adapter.managed_tool_command(
            project,
            executable_name,
            mise_path_value=mise_path,
            environment={**os.environ, "BBK_MISE": str(mise_path)},
        )
    except mise_adapter.MiseAdapterError as exc:
        raise QualificationError(
            f"SUBSTRATE_{executable_name.upper()}_MISE_UNAVAILABLE",
            f"{executable_name} must resolve through canonical mise [tools]: {exc.code}: {exc.message}",
        ) from exc


def _run(
    command: Sequence[str | Path],
    *,
    cwd: Path,
    environment: Mapping[str, str] | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [str(item) for item in command],
        cwd=cwd,
        env={**os.environ, **dict(environment or {}), "NO_COLOR": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="backslashreplace",
        check=False,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise QualificationError(
            "QUALIFICATION_LOCAL_COMMAND_FAILED",
            f"{' '.join(str(item) for item in command)} exited {completed.returncode}",
            details={"stdout": completed.stdout[-4000:], "stderr": completed.stderr[-4000:]},
        )
    return completed


def _tool_identity(path: Path, version_command: Sequence[str]) -> dict[str, Any]:
    completed = _run([path, *version_command], cwd=ROOT)
    version = " ".join((completed.stdout or completed.stderr).split())
    return {
        "path_basename": path.name,
        "sha256": _sha256_file(path),
        "version": version,
        "adapter_class": "REAL_LOCAL_TOOL",
    }


def _bound_tool_identity(
    command_prefix: Sequence[str],
    binding: Mapping[str, str],
    version_command: Sequence[str] = ("--version",),
) -> dict[str, Any]:
    completed = _run([*command_prefix, *version_command], cwd=ROOT)
    version = " ".join((completed.stdout or completed.stderr).split())
    if binding.get("execution_mode") == "EXPLICIT_EXECUTABLE":
        path_value = binding.get("jj_path") or binding.get("bd_path")
        assert path_value is not None
        path = Path(path_value)
        return {
            "path_basename": path.name,
            "sha256": _sha256_file(path),
            "version": version,
            "adapter_class": "REAL_LOCAL_TOOL_EXPLICIT_OVERRIDE",
            "execution_mode": "EXPLICIT_EXECUTABLE",
        }
    mise_path = Path(str(binding["mise_path"]))
    return {
        "launcher_basename": mise_path.name,
        "launcher_sha256": _sha256_file(mise_path),
        "version": version,
        "adapter_class": "REAL_LOCAL_TOOL_MISE_MANAGED",
        "execution_mode": "MISE_MANAGED",
        "tool_key": binding.get("tool_key"),
        "tool_spec": binding.get("tool_spec"),
        "executable": binding.get("executable"),
    }


def _git(project: Path, git_path: Path, *arguments: str, environment: Mapping[str, str] | None = None) -> str:
    return _run([git_path, *arguments], cwd=project, environment=environment).stdout.strip()


def _binding(
    project: Path,
    *,
    role: str,
    session_id: str,
    invocation_id: str,
    work_unit_id: str,
    attempt_id: str,
    workspace: Path,
    candidate_ref: str,
    jj_change_id: str,
    path_prefixes: Sequence[Path],
    mutation_classes: Sequence[str],
    semantic_scope: Sequence[str],
) -> dict[str, Any]:
    request = {
        "schema": "bbk.invocation-binding-create.v1",
        "session_id": session_id,
        "invocation_id": invocation_id,
        "role": role,
        "work_unit_id": work_unit_id,
        "attempt_id": attempt_id,
        "baseline_ref": "git:alpha17-fixture-baseline",
        "candidate_ref": candidate_ref,
        "workspace_ref": str(workspace.resolve()),
        "authority_ref": AUTHORITY_REF,
        "scope": {
            "path_prefixes": [str(path.resolve()) for path in path_prefixes],
            "mutation_classes": list(mutation_classes),
            "semantic_scope": list(semantic_scope),
        },
        "return_contract": f"bbk.{role.removeprefix('bbk_').replace('_', '-')}-return.v2",
        "jj_change_id": jj_change_id,
        "idempotency_key": f"binding:{role}:{work_unit_id}:{attempt_id}",
    }
    return create_initial_binding(project, request, capability_ref=_capability_ref(role))[0]


def _filesystem_envelope(
    binding: Mapping[str, Any],
    *,
    operation: str,
    path: str,
    payload: Mapping[str, Any] | None,
    mutation_class: str,
    idempotency_key: str,
    precondition: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload_value = dict(payload or {})
    request = binding["request"]
    return {
        "schema": "bbk.governed-filesystem-execution.v1",
        "host_version": HOST_VERSION,
        "session_id": request["session_id"],
        "invocation_id": request["invocation_id"],
        "intent": {
            "schema": "bbk.mutation-intent.v1",
            "binding_ref": binding["binding_id"],
            "operation": operation,
            "path": path,
            "content_or_patch_digest": governed_filesystem.payload_digest(payload_value),
            "expected_precondition": dict(precondition or {"kind": "ANY"}),
            "mutation_class": mutation_class,
            "idempotency_key": idempotency_key,
        },
        "payload": payload_value,
    }


def _write_json_payload(value: Mapping[str, Any]) -> dict[str, str]:
    text = json.dumps(dict(value), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return {"content": text, "encoding": "utf-8"}


def _control_common(
    parent: Mapping[str, Any],
    *,
    schema: str,
    work_unit: str,
    attempt: str,
    revision: int,
    ordinal: str,
    summary: str,
) -> dict[str, Any]:
    request = parent["request"]
    return {
        "schema": schema,
        "host_version": HOST_VERSION,
        "session_id": request["session_id"],
        "binding_ref": parent["binding_id"],
        "invocation_id": request["invocation_id"],
        "command_id": f"command:{ordinal}",
        "work_unit_id": work_unit,
        "attempt_id": attempt,
        "correlation_id": f"correlation:{work_unit}:{attempt}",
        "payload_summary": summary,
        "expected_revision": revision,
        "idempotency_key": f"control:{ordinal}",
        "evidence_refs": [],
        "finding_refs": [],
    }


def _update(
    project: Path,
    parent: Mapping[str, Any],
    *,
    work_unit: str,
    attempt: str,
    revision: int,
    transition: str,
    ordinal: str,
    bd_path: Path,
    evidence_refs: Sequence[str] = (),
) -> dict[str, Any]:
    request = {
        **_control_common(
            parent,
            schema="bbk.control-update.v1",
            work_unit=work_unit,
            attempt=attempt,
            revision=revision,
            ordinal=ordinal,
            summary=f"{transition.title()} {work_unit} {attempt}",
        ),
        "transition": transition,
        "evidence_refs": list(evidence_refs),
    }
    return control_plane.execute_control(project, request, bd_path=bd_path)


def _integration_request(
    project: Path,
    parent: Mapping[str, Any],
    *,
    sources: Sequence[str],
    target: str,
    bd_path: Path,
) -> dict[str, Any]:
    request = {
        **_control_common(
            parent,
            schema="bbk.control-integrate-request.v1",
            work_unit="WU-FIXTURE-INTEGRATION",
            attempt="integration-1",
            revision=0,
            ordinal="integration-request",
            summary="Request content-neutral integration of disjoint worker candidates",
        ),
        "source_candidate_refs": list(sources),
        "target_candidate_ref": target,
        "conflict_classification": "CONTENT_NEUTRAL",
    }
    return control_plane.execute_control(project, request, bd_path=bd_path)


def _record_assurance(
    project: Path,
    *,
    kind: str,
    binding: Mapping[str, Any],
    candidate: Mapping[str, Any],
    read_receipts: Sequence[str],
    blocked_write_receipt: str,
) -> dict[str, Any]:
    request_core = {
        "schema": "bbk.assurance-package-request.v1",
        "kind": kind,
        "candidate_ref": candidate["candidate_id"],
        "candidate_digest": candidate["digest"],
        "scope": sorted(EXPECTED_OUTPUTS),
        "assertions_or_findings": ["fixture outputs match the declared integrated contract"],
        "prior_findings": [],
        "binding_ref": binding["binding_id"],
    }
    request_id = f"sha256:{canonical_digest(request_core)}"
    request_receipt, _ = append_receipt(
        project,
        "ASSURANCE_REQUEST",
        request_core,
        receipt_id=request_id,
    )
    record_core = {
        "schema": "bbk.assurance-record.v1",
        "review_or_validation_id": f"{kind.lower()}:{canonical_digest(request_core)[:24]}",
        "kind": kind,
        "request_ref": request_receipt["receipt_id"],
        "candidate_ref": candidate["candidate_id"],
        "candidate_digest": candidate["digest"],
        "findings": [],
        "evidence": list(read_receipts),
        "status": "PASS",
        "write_surface_attestation": {
            "candidate_write_authority": "DENIED",
            "blocked_write_receipt": blocked_write_receipt,
            "candidate_unchanged": True,
        },
    }
    record_id = f"sha256:{canonical_digest(record_core)}"
    receipt, _ = append_receipt(project, "ASSURANCE_RECORD", record_core, receipt_id=record_id)
    return {**record_core, "receipt_ref": receipt["receipt_id"]}


def _check(checks: list[dict[str, Any]], check_id: str, passed: bool, **evidence: Any) -> None:
    checks.append(
        {
            "id": check_id,
            "status": "PASS" if passed else "FAIL",
            "evidence": evidence,
        }
    )
    if not passed:
        raise QualificationError("QUALIFICATION_ASSERTION_FAILED", check_id, details=evidence)


def _normalize_candidate(candidate: Mapping[str, Any], campaign_root: Path) -> dict[str, Any]:
    workspace = Path(str(candidate.get("workspace_path", ""))).resolve()
    try:
        relative = workspace.relative_to(campaign_root.resolve()).as_posix()
        workspace_ref = f"$CAMPAIGN/{relative}"
    except ValueError:
        workspace_ref = "$CAMPAIGN/EXTERNAL_WORKSPACE"
    return {
        "candidate_id": candidate["candidate_id"],
        "digest": candidate["digest"],
        "identity_kind": candidate["identity_kind"],
        "git_commit": candidate.get("git_commit"),
        "git_tree": candidate.get("git_tree"),
        "jj_change_id": candidate.get("jj_change_id"),
        "workspace_ref": workspace_ref,
        "changed_paths": [item["path"] for item in candidate.get("status", [])],
    }


def _blocked_write(
    project: Path,
    binding: Mapping[str, Any],
    *,
    path: str,
    key: str,
    jj_path: Path,
) -> dict[str, Any]:
    result = governed_filesystem.execute(
        project,
        _filesystem_envelope(
            binding,
            operation="WRITE",
            path=path,
            payload={"content": "forbidden\n", "encoding": "utf-8"},
            mutation_class="PRODUCT_CONTENT",
            idempotency_key=key,
        ),
        jj_path=jj_path,
    )
    if result.get("status") != "BLOCK":
        raise QualificationError("QUALIFICATION_NEGATIVE_WRITE_NOT_BLOCKED", f"write unexpectedly returned {result}")
    return result


def _read_candidate(
    project: Path,
    binding: Mapping[str, Any],
    *,
    path: str,
    key: str,
    jj_path: Path,
) -> dict[str, Any]:
    result = governed_filesystem.execute(
        project,
        _filesystem_envelope(
            binding,
            operation="READ",
            path=path,
            payload={},
            mutation_class="PRODUCT_CONTENT",
            idempotency_key=key,
            precondition={"kind": "PRESENT"},
        ),
        jj_path=jj_path,
    )
    if result.get("status") != "PASS":
        raise QualificationError("QUALIFICATION_READ_FAILED", f"read of {path} returned {result}")
    return result


def _receipt_counts(project: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    for receipt in all_receipts(project):
        kind = str(receipt.get("receipt_kind"))
        result[kind] = result.get(kind, 0) + 1
    return dict(sorted(result.items()))


def _isolated_qualified_task_environment(campaign_parent: Path, workspace: Path) -> dict[str, str]:
    """Return a host-neutral environment that cannot leak user mise state."""
    home = campaign_parent / "mise-home"
    config = campaign_parent / "mise-config"
    cache = campaign_parent / "mise-cache"
    data = campaign_parent / "mise-data"
    state = campaign_parent / "mise-state"
    installs = data / "installs"
    downloads = data / "downloads"
    shims = data / "shims"
    roaming = config / "roaming"
    local = data / "local"
    temporary = campaign_parent / "tmp"
    for path in (home, config, cache, data, state, installs, downloads, shims, roaming, local, temporary):
        path.mkdir(parents=True, exist_ok=True)
    global_config = config / "global-config.toml"
    system_config = config / "system-config.toml"
    global_config.write_bytes(b"# isolated BBK qualification config\n")
    system_config.write_bytes(b"# isolated BBK qualification system config\n")
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(home),
        "USERPROFILE": str(home),
        "APPDATA": str(roaming),
        "LOCALAPPDATA": str(local),
        "TMP": str(temporary),
        "TEMP": str(temporary),
        "TMPDIR": str(temporary),
        "XDG_CONFIG_HOME": str(config),
        "XDG_CACHE_HOME": str(cache),
        "XDG_DATA_HOME": str(data),
        "XDG_STATE_HOME": str(state),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "MISE_CONFIG_DIR": str(config),
        "MISE_CACHE_DIR": str(cache),
        "MISE_DATA_DIR": str(data),
        "MISE_STATE_DIR": str(state),
        "MISE_INSTALLS_DIR": str(installs),
        "MISE_DOWNLOADS_DIR": str(downloads),
        "MISE_SHIMS_DIR": str(shims),
        "MISE_GLOBAL_CONFIG_FILE": str(global_config),
        "MISE_SYSTEM_CONFIG_FILE": str(system_config),
        "MISE_CEILING_PATHS": str(campaign_parent),
        "MISE_TRUSTED_CONFIG_PATHS": str(workspace),
        "MISE_AUTO_INSTALL": "0",
        "MISE_EXEC_AUTO_INSTALL": "0",
        "MISE_NOT_FOUND_AUTO_INSTALL": "0",
        "MISE_TASK_RUN_AUTO_INSTALL": "0",
        "MISE_OFFLINE": "1",
        "MISE_LOCKFILE": "0",
        "MISE_NO_HOOKS": "1",
        "MISE_NO_ENV": "1",
        "MISE_NO_DOTENV": "1",
        "MISE_DISABLE_TOOLS": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "NO_COLOR": "1",
        "CLICOLOR": "0",
    }
    for name in ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT"):
        if os.environ.get(name):
            environment[name] = os.environ[name]
    drive, tail = os.path.splitdrive(str(home))
    if drive:
        environment["HOMEDRIVE"] = drive
        environment["HOMEPATH"] = tail or "\\"
    return environment

def _run_alpha17_automated_bound(
    *,
    git_path: str | Path | None = None,
    jj_path: str | Path | None = None,
    bd_path: str | Path | None = None,
    mise_path: str | Path | None = None,
    fixture_root: str | Path = FIXTURE_ROOT,
    temporary_parent: str | Path | None = None,
) -> dict[str, Any]:
    """Run VER-036 against real local substrate tools and return a report."""
    git_executable = _executable(git_path, "BBK_GIT", "git")
    jj_executable = _optional_explicit_executable(jj_path, "BBK_JJ", "jj")
    bd_executable = _optional_explicit_executable(bd_path, "BBK_BD", "bd")
    mise_executable = _executable(mise_path, "BBK_MISE", "mise")
    fixture = Path(fixture_root).resolve()
    if not fixture.is_dir() or fixture.is_symlink():
        raise QualificationError("QUALIFICATION_FIXTURE_INVALID", f"fixture is not a safe directory: {fixture}")

    checks: list[dict[str, Any]] = []
    fixture_digest = _tree_digest(fixture)
    parent_dir = Path(temporary_parent).resolve() if temporary_parent else None
    with tempfile.TemporaryDirectory(prefix="bbk-alpha17-qualification-", dir=parent_dir) as temporary_name:
        campaign_parent = Path(temporary_name).resolve()
        project = campaign_parent / "project"
        workspaces = campaign_parent / "workspaces"
        workspaces.mkdir()
        shutil.copytree(fixture, project)
        jj_command, jj_tool_binding = _managed_or_explicit_tool_command(
            project, "jj", jj_executable, mise_executable
        )
        bd_command, bd_tool_binding = _managed_or_explicit_tool_command(
            project, "bd", bd_executable, mise_executable
        )

        fixed_git_environment = {
            "GIT_AUTHOR_NAME": "BBK Qualification",
            "GIT_AUTHOR_EMAIL": "qualification@example.invalid",
            "GIT_COMMITTER_NAME": "BBK Qualification",
            "GIT_COMMITTER_EMAIL": "qualification@example.invalid",
            "GIT_AUTHOR_DATE": "2026-08-04T00:00:00Z",
            "GIT_COMMITTER_DATE": "2026-08-04T00:00:00Z",
        }
        _git(project, git_executable, "init")
        _git(project, git_executable, "config", "user.name", "BBK Qualification")
        _git(project, git_executable, "config", "user.email", "qualification@example.invalid")
        _git(project, git_executable, "config", "core.autocrlf", "false")
        _git(project, git_executable, "config", "core.eol", "lf")
        _git(project, git_executable, "add", ".")
        _git(project, git_executable, "commit", "-m", "Alpha.17 qualification fixture baseline", environment=fixed_git_environment)
        baseline_commit = _git(project, git_executable, "rev-parse", "HEAD")
        _run([*jj_command, "--no-pager", "--color=never", "git", "init", "--colocate", "."], cwd=project)
        baseline_identity = jj_adapter.identity(project, revision="@-", jj_path=jj_executable)
        _check(
            checks,
            "A17-001-real-colocated-git-jj-baseline",
            baseline_identity["jj_commit_id"] == baseline_commit,
            git_commit=baseline_commit,
            jj_parent_commit=baseline_identity["jj_commit_id"],
        )

        bd_environment = {
            "BD_NON_INTERACTIVE": "1",
            "BEADS_DISABLE_METRICS": "1",
            "NO_COLOR": "1",
        }
        _run(
            [
                *bd_command,
                "--sandbox",
                "--json",
                "init",
                "--non-interactive",
                "--skip-agents",
                "--skip-hooks",
                "--prefix",
                "A17Q",
            ],
            cwd=project,
            environment=bd_environment,
            timeout=180,
        )

        parent_identity = jj_adapter.identity(project, jj_path=jj_executable)
        coordination_path = project / ".bbk" / "coordination"
        parent = _binding(
            project,
            role="bbk_validator_orchestrator",
            session_id="session-alpha17-validator-orchestrator",
            invocation_id="invocation-alpha17-validator-orchestrator",
            work_unit_id="WU-017",
            attempt_id="qualification-1",
            workspace=project,
            candidate_ref="candidate:alpha17-qualification-control",
            jj_change_id=parent_identity["jj_change_id"],
            path_prefixes=[coordination_path],
            mutation_classes=["COORDINATION_METADATA"],
            semantic_scope=["campaign:alpha17", "assertion:VER-036"],
        )
        root_orchestrator = _binding(
            project,
            role="bbk_root_orchestrator",
            session_id="session-alpha17-root-orchestrator",
            invocation_id="invocation-alpha17-root-orchestrator",
            work_unit_id="WU-ROOT-NEGATIVE",
            attempt_id="negative-1",
            workspace=project,
            candidate_ref="candidate:alpha17-root-negative",
            jj_change_id=parent_identity["jj_change_id"],
            path_prefixes=[coordination_path],
            mutation_classes=["COORDINATION_METADATA"],
            semantic_scope=["campaign:alpha17"],
        )

        worker_specs = [
            {
                "name": "backend",
                "work_unit": "WU-FIXTURE-BACKEND",
                "attempt": "backend-1",
                "candidate": "candidate:fixture:backend",
                "path": "backend",
                "session": "session-alpha17-worker-backend",
                "task": "worker-backend",
            },
            {
                "name": "frontend",
                "work_unit": "WU-FIXTURE-FRONTEND",
                "attempt": "frontend-1",
                "candidate": "candidate:fixture:frontend",
                "path": "frontend",
                "session": "session-alpha17-worker-frontend",
                "task": "worker-frontend",
            },
        ]
        workers: list[dict[str, Any]] = []
        for index, spec in enumerate(worker_specs, start=1):
            compiled = compile_bound_spawn(
                project,
                {
                    "schema": "bbk.bound-worker-spawn-create.v1",
                    "host_version": HOST_VERSION,
                    "parent_binding_ref": parent["binding_id"],
                    "parent_session_id": parent["request"]["session_id"],
                    "parent_invocation_id": parent["request"]["invocation_id"],
                    "task_name": spec["task"],
                    "role": "bbk_worker",
                    "work_unit_id": spec["work_unit"],
                    "attempt_id": spec["attempt"],
                    "baseline_ref": "git:alpha17-fixture-baseline",
                    "candidate_ref": spec["candidate"],
                    "authority_ref": AUTHORITY_REF,
                    "return_contract": "bbk.worker-return.v2",
                    "parent_revision": baseline_identity["jj_commit_id"],
                    "workspace_parent": str(workspaces),
                    "path_prefixes": [spec["path"]],
                    "mutation_classes": ["PRODUCT_CONTENT"],
                    "semantic_scope": [f"fixture:{spec['name']}"],
                    "assignment": f"Create only {spec['path']}/result.json for the Alpha.17 local fixture.",
                    "description": f"Alpha.17 {spec['name']} worker",
                    "idempotency_key": f"spawn:{spec['work_unit']}:{spec['attempt']}",
                },
                jj_path=jj_executable,
                bd_path=bd_executable,
            )
            admission = admit_spawn_dispatch(
                project,
                dispatch_ref=compiled["dispatch_ref"],
                dispatch_envelope_digest=compiled["dispatch_envelope_digest"],
                parent_session_id=parent["request"]["session_id"],
                task_name=spec["task"],
                agent="bbk_worker",
                tool_call_id=f"tool-call-worker-{index}",
                host_version=HOST_VERSION,
            )
            activation = activate_spawn_session(
                project,
                planned_binding_ref=compiled["planned_binding_ref"],
                actual_session_id=spec["session"],
                packet_digest=compiled["worker_packet"]["packet_digest"],
                host_version=HOST_VERSION,
            )
            active = activation["binding"]
            assignment = compiled["assignment_projection"]
            start = _update(
                project,
                parent,
                work_unit=spec["work_unit"],
                attempt=spec["attempt"],
                revision=1,
                transition="START",
                ordinal=f"start-{spec['name']}",
                bd_path=bd_executable,
            )
            workers.append(
                {
                    "spec": spec,
                    "compiled": compiled,
                    "admission": admission,
                    "activation": activation,
                    "binding": active,
                    "assignment": assignment,
                    "start": start,
                }
            )

        _check(
            checks,
            "A17-002-two-isolated-workers",
            len({item["binding"]["request"]["session_id"] for item in workers}) == 2
            and len({item["binding"]["request"]["invocation_id"] for item in workers}) == 2
            and len({item["binding"]["request"]["workspace_ref"] for item in workers}) == 2
            and len({item["binding"]["request"]["jj_change_id"] for item in workers}) == 2,
            distinct_sessions=2,
            distinct_invocations=2,
            distinct_workspaces=2,
            distinct_jj_changes=2,
        )
        _check(
            checks,
            "A17-003-orchestrator-control-plane-only",
            all(item["assignment"]["policy"]["product_mutation_authority"] == "DENIED" for item in workers),
            assignment_projection_ids=[item["assignment"]["projection"]["projection_id"] for item in workers],
        )

        root_denied = _blocked_write(
            project,
            root_orchestrator,
            path="backend/orchestrator-forbidden.txt",
            key="negative:root-orchestrator-write",
            jj_path=jj_executable,
        )
        _check(
            checks,
            "A17-004-root-orchestrator-product-write-blocked",
            not (project / "backend" / "orchestrator-forbidden.txt").exists(),
            reason_code=root_denied["reason_code"],
            receipt_ref=root_denied["result"]["receipt_ref"],
        )

        worker_reports: list[dict[str, Any]] = []
        for item in workers:
            spec = item["spec"]
            binding = item["binding"]
            output_path = f"{spec['path']}/result.json"
            write_result = governed_filesystem.execute(
                project,
                _filesystem_envelope(
                    binding,
                    operation="WRITE",
                    path=output_path,
                    payload=_write_json_payload(EXPECTED_OUTPUTS[output_path]),
                    mutation_class="PRODUCT_CONTENT",
                    idempotency_key=f"write:{spec['name']}:result",
                    precondition={"kind": "ABSENT"},
                ),
                jj_path=jj_executable,
            )
            if write_result.get("status") != "PASS":
                raise QualificationError("QUALIFICATION_WORKER_WRITE_FAILED", f"{spec['name']} write returned {write_result}")

            other = "frontend" if spec["name"] == "backend" else "backend"
            cross_result = _blocked_write(
                project,
                binding,
                path=f"{other}/cross-worker-forbidden.txt",
                key=f"negative:{spec['name']}:cross-worker",
                jj_path=jj_executable,
            )
            traversal_code = ""
            try:
                _blocked_write(
                    project,
                    binding,
                    path="../path-escape-forbidden.txt",
                    key=f"negative:{spec['name']}:path-escape",
                    jj_path=jj_executable,
                )
            except governed_filesystem.GovernedFilesystemError as exc:
                traversal_code = exc.code
            if not traversal_code:
                raise QualificationError("QUALIFICATION_PATH_ESCAPE_NOT_BLOCKED", spec["name"])

            complete = _update(
                project,
                parent,
                work_unit=spec["work_unit"],
                attempt=spec["attempt"],
                revision=2,
                transition="COMPLETE",
                ordinal=f"complete-{spec['name']}",
                bd_path=bd_executable,
                evidence_refs=[write_result["result"]["receipt_ref"]],
            )
            changed_paths = write_result["result"].get("changed_paths", [])
            _check(
                checks,
                f"A17-005-{spec['name']}-scoped-write",
                changed_paths == [output_path]
                and cross_result["status"] == "BLOCK"
                and traversal_code == "MUTATION_PATH_TRAVERSAL_FORBIDDEN",
                changed_paths=changed_paths,
                mutation_receipt=write_result["result"]["receipt_ref"],
                cross_worker_reason=cross_result["reason_code"],
                cross_worker_receipt=cross_result["result"]["receipt_ref"],
                path_escape_reason=traversal_code,
            )
            worker_reports.append(
                {
                    "work_unit_id": spec["work_unit"],
                    "attempt_id": spec["attempt"],
                    "candidate_ref": spec["candidate"],
                    "session_id": binding["request"]["session_id"],
                    "invocation_id": binding["request"]["invocation_id"],
                    "jj_change_id": binding["request"]["jj_change_id"],
                    "workspace_label": f"$CAMPAIGN/workspaces/{Path(binding['request']['workspace_ref']).name}",
                    "scope": [spec["path"]],
                    "changed_paths": changed_paths,
                    "filesystem_mutation_receipt": write_result["result"]["receipt_ref"],
                    "vcs_mutation_receipt": write_result["result"]["vcs_reconciliation_ref"],
                    "cross_worker_block_receipt": cross_result["result"]["receipt_ref"],
                    "cross_worker_reason": cross_result["reason_code"],
                    "path_escape_reason": traversal_code,
                    "completion_projection_id": complete["projection"]["projection_id"],
                }
            )

        integration_control = _integration_request(
            project,
            parent,
            sources=[item["spec"]["candidate"] for item in workers],
            target="candidate:fixture:integrated",
            bd_path=bd_executable,
        )
        _check(
            checks,
            "A17-006-content-neutral-route-requested",
            integration_control["policy"]["requested_route"] == "CONTENT_NEUTRAL_INTEGRATION_ADAPTER"
            and integration_control["policy"]["integration_worker_required"] is False
            and integration_control["policy"]["orchestrator_conflict_resolution_authority"] == "DENIED",
            projection_id=integration_control["projection"]["projection_id"],
            route=integration_control["policy"]["requested_route"],
        )

        integrated = jj_adapter.merge_content_neutral(
            project,
            workspaces / "integrated",
            work_unit_id="WU-FIXTURE-INTEGRATION",
            attempt_id="integration-1",
            source_revisions=[item["binding"]["request"]["jj_change_id"] for item in workers],
            parent_revision=baseline_identity["jj_commit_id"],
            description="Alpha.17 content-neutral integration",
            jj_path=jj_executable,
        )
        integrated_workspace = Path(integrated["workspace_path"])
        git_backing_root = jj_adapter.git_repository_root(integrated_workspace, jj_path=jj_executable)
        frozen_before_task = git_adapter.freeze_candidate(
            integrated_workspace,
            candidate_id="candidate:fixture:integrated",
            jj_change_id=integrated["jj_change_id"],
            git_repository_root=git_backing_root,
        )
        _check(
            checks,
            "A17-007-disjoint-candidates-integrated",
            integrated["integration_mode"] == "CONTENT_NEUTRAL_DISJOINT_PATHS"
            and integrated["integrated_paths"] == sorted(EXPECTED_OUTPUTS)
            and [item["path"] for item in frozen_before_task["status"]] == sorted(EXPECTED_OUTPUTS),
            integration_digest=integrated["integration_digest"],
            integrated_paths=integrated["integrated_paths"],
            candidate_digest=frozen_before_task["digest"],
        )
        integration_receipt_core = {
            "schema": "bbk.candidate-integration-receipt.v1",
            "integration_digest": integrated["integration_digest"],
            "source_change_ids": integrated["source_change_ids"],
            "source_commit_ids": integrated["source_commit_ids"],
            "target_candidate_ref": frozen_before_task["candidate_id"],
            "target_candidate_digest": frozen_before_task["digest"],
            "integrated_paths": integrated["integrated_paths"],
            "integration_mode": integrated["integration_mode"],
            "conflict_resolution_authority": integrated["conflict_resolution_authority"],
        }
        integration_receipt_id = f"sha256:{canonical_digest(integration_receipt_core)}"
        append_receipt(
            project,
            "CANDIDATE_INTEGRATION",
            integration_receipt_core,
            receipt_id=integration_receipt_id,
        )
        integrated_identity = jj_adapter.identity(
            integrated_workspace,
            revision=integrated["jj_change_id"],
            jj_path=jj_executable,
        )
        candidate_admission_core = {
            "schema": "bbk.candidate-integration-admission.v1",
            "status": "PASS",
            "integration_receipt_ref": integration_receipt_id,
            "integration_record_digest": f"sha256:{canonical_digest(integration_receipt_core)}",
            "candidate_id": frozen_before_task["candidate_id"],
            "candidate_digest": frozen_before_task["digest"],
            "workspace_ref": frozen_before_task["workspace_path"],
            "jj_change_id": frozen_before_task["jj_change_id"],
            "git_tree": frozen_before_task.get("git_tree"),
            "baseline_revision": baseline_identity["jj_commit_id"],
            "source_change_ids": integrated["source_change_ids"],
            "source_commit_ids": integrated["source_commit_ids"],
            "parent_commit_ids": integrated_identity["parent_commit_ids"],
            "integrated_paths": integrated["integrated_paths"],
            "unresolved_conflicts": False,
            "conflict_resolution_authority": "DENIED",
            "integration_mode": "CONTENT_NEUTRAL_DISJOINT_PATHS",
        }
        candidate_admission_core["admission_digest"] = f"sha256:{canonical_digest(candidate_admission_core)}"
        candidate_admission, _ = append_receipt(
            project,
            "CANDIDATE_INTEGRATION_ADMISSION",
            candidate_admission_core,
        )

        task_environment = _isolated_qualified_task_environment(campaign_parent, integrated_workspace)
        task_binding = _binding(
            project,
            role="bbk_worker",
            session_id="session-alpha17-integration-task",
            invocation_id="invocation-alpha17-integration-task",
            work_unit_id="WU-FIXTURE-INTEGRATION",
            attempt_id="integration-task-1",
            workspace=integrated_workspace,
            candidate_ref="candidate:fixture:integrated",
            jj_change_id=integrated["jj_change_id"],
            path_prefixes=[integrated_workspace / "backend", integrated_workspace / "frontend"],
            mutation_classes=["TEST_CONTENT"],
            semantic_scope=["candidate:fixture:integrated", "qualification:task"],
        )
        task_request = {
            "schema": "bbk.bound-qualified-task-execution.v1",
            "host_version": HOST_VERSION,
            "session_id": task_binding["request"]["session_id"],
            "invocation_id": task_binding["request"]["invocation_id"],
            "binding_ref": task_binding["binding_id"],
            "task": "fixture:verify",
            "idempotency_key": "task:alpha17:fixture-verify",
            "arguments": [],
            "environment_allowlist": [
                "HOME",
                "XDG_CONFIG_HOME",
                "XDG_CACHE_HOME",
                "XDG_DATA_HOME",
                "XDG_STATE_HOME",
                "LANG",
                "MISE_AUTO_INSTALL",
                "MISE_DISABLE_TOOLS",
                "USERPROFILE",
                "APPDATA",
                "LOCALAPPDATA",
                "TMP",
                "TEMP",
                "TMPDIR",
                "MISE_CONFIG_DIR",
                "MISE_CACHE_DIR",
                "MISE_DATA_DIR",
                "MISE_STATE_DIR",
                "MISE_INSTALLS_DIR",
                "MISE_DOWNLOADS_DIR",
                "MISE_SHIMS_DIR",
                "MISE_GLOBAL_CONFIG_FILE",
                "MISE_SYSTEM_CONFIG_FILE",
                "MISE_CEILING_PATHS",
                "MISE_TRUSTED_CONFIG_PATHS",
                "MISE_EXEC_AUTO_INSTALL",
                "MISE_NOT_FOUND_AUTO_INSTALL",
                "MISE_TASK_RUN_AUTO_INSTALL",
                "MISE_OFFLINE",
                "MISE_LOCKFILE",
                "MISE_NO_HOOKS",
                "MISE_NO_ENV",
                "MISE_NO_DOTENV",
                "PYTHONDONTWRITEBYTECODE",
            ],
        }
        task_result = execute_bound_task(
            project,
            task_request,
            git_path=git_executable,
            jj_path=jj_executable,
            mise_path=mise_executable,
            environment=task_environment,
        )
        frozen_after_task = git_adapter.freeze_candidate(
            integrated_workspace,
            candidate_id="candidate:fixture:integrated",
            jj_change_id=integrated["jj_change_id"],
            git_repository_root=git_backing_root,
        )
        _check(
            checks,
            "A17-008-real-mise-task-preserves-candidate",
            task_result["status"] == "PASS"
            and task_result["exit_status"] == 0
            and task_result["candidate_before"]["digest"] == frozen_before_task["digest"]
            and task_result["candidate_after"]["digest"] == frozen_before_task["digest"]
            and task_result["candidate_unchanged"] is True
            and frozen_after_task["digest"] == frozen_before_task["digest"],
            surface="bbk_task_run",
            task="fixture:verify",
            mise_version=task_result["mise_version"],
            task_receipt=task_result["receipt_ref"],
            qualified_task_receipt=task_result["qualified_task_receipt_ref"],
            candidate_digest=frozen_after_task["digest"],
        )

        integration_complete = _update(
            project,
            parent,
            work_unit="WU-FIXTURE-INTEGRATION",
            attempt="integration-1",
            revision=1,
            transition="COMPLETE",
            ordinal="complete-integration",
            bd_path=bd_executable,
            evidence_refs=[
                integration_receipt_id,
                task_result["receipt_ref"],
                task_result["qualified_task_receipt_ref"],
            ],
        )

        assurance_records: list[dict[str, Any]] = []
        assurance_summaries: list[dict[str, Any]] = []
        assurance_binding_refs: list[dict[str, str]] = []
        assurance_bindings: list[dict[str, Any]] = []
        for kind, role, ordinal in (
            ("REVIEW", "bbk_reviewer", "review"),
            ("VALIDATION", "bbk_validator", "validation"),
        ):
            compiled_assurance = compile_read_only_spawn(
                project,
                {
                    "schema": "bbk.bound-read-only-task-create.v1",
                    "host_version": HOST_VERSION,
                    "parent_binding_ref": parent["binding_id"],
                    "parent_session_id": parent["request"]["session_id"],
                    "parent_invocation_id": parent["request"]["invocation_id"],
                    "task_name": f"{ordinal}-integrated-candidate",
                    "role": role,
                    "work_unit_id": f"WU-FIXTURE-{kind}",
                    "attempt_id": f"{ordinal}-1",
                    "baseline_ref": "git:alpha17-fixture-baseline",
                    "candidate_id": "candidate:fixture:integrated",
                    "candidate_admission_ref": candidate_admission["receipt_id"],
                    "authority_ref": AUTHORITY_REF,
                    "return_contract": f"bbk.{role.removeprefix('bbk_').replace('_', '-')}-return.v2",
                    "workspace_ref": str(integrated_workspace),
                    "path_prefixes": ["backend", "frontend"],
                    "semantic_scope": ["candidate:fixture:integrated", kind.lower()],
                    "assignment": f"{kind.title()} the exact integrated Alpha.17 fixture candidate without mutation.",
                    "description": f"Alpha.17 read-only {kind.lower()} qualification",
                    "idempotency_key": f"bind:{ordinal}:integrated",
                },
                git_path=git_executable,
                jj_path=jj_executable,
            )
            assurance_admission = admit_spawn_dispatch(
                project,
                dispatch_ref=compiled_assurance["dispatch_ref"],
                dispatch_envelope_digest=compiled_assurance["dispatch_envelope_digest"],
                parent_session_id=parent["request"]["session_id"],
                task_name=f"{ordinal}-integrated-candidate",
                agent=role,
                tool_call_id=f"tool-call-{ordinal}",
                host_version=HOST_VERSION,
            )
            assurance_activation = activate_spawn_session(
                project,
                planned_binding_ref=compiled_assurance["planned_binding_ref"],
                actual_session_id=f"session-alpha17-{ordinal}",
                packet_digest=compiled_assurance["worker_packet"]["packet_digest"],
                host_version=HOST_VERSION,
            )
            assurance_binding = assurance_activation["binding"]
            assurance_bindings.append(assurance_binding)
            assurance_binding_refs.append(
                {
                    "dispatch_ref": compiled_assurance["dispatch_ref"],
                    "registration_ref": compiled_assurance["task_registration_ref"],
                    "admission_ref": assurance_admission["receipt_ref"],
                    "activation_ref": assurance_activation["receipt_ref"],
                    "binding_ref": assurance_binding["binding_id"],
                }
            )
            read_results = [
                _read_candidate(
                    project,
                    assurance_binding,
                    path=relative,
                    key=f"{ordinal}:read:{relative.replace('/', ':')}",
                    jj_path=jj_executable,
                )
                for relative in sorted(EXPECTED_OUTPUTS)
            ]
            for relative, result in zip(sorted(EXPECTED_OUTPUTS), read_results):
                observed = json.loads(result["content"])
                if observed != EXPECTED_OUTPUTS[relative]:
                    raise QualificationError("QUALIFICATION_ASSURANCE_CONTENT_MISMATCH", relative)
            denied = _blocked_write(
                project,
                assurance_binding,
                path="backend/result.json",
                key=f"negative:{ordinal}:candidate-write",
                jj_path=jj_executable,
            )
            candidate_after_assurance = git_adapter.freeze_candidate(
                integrated_workspace,
                candidate_id="candidate:fixture:integrated",
                jj_change_id=integrated["jj_change_id"],
                git_repository_root=git_backing_root,
            )
            if candidate_after_assurance["digest"] != frozen_after_task["digest"]:
                raise QualificationError("QUALIFICATION_ASSURANCE_MUTATED_CANDIDATE", kind)
            record = _record_assurance(
                project,
                kind=kind,
                binding=assurance_binding,
                candidate=frozen_after_task,
                read_receipts=[result["result"]["receipt_ref"] for result in read_results],
                blocked_write_receipt=denied["result"]["receipt_ref"],
            )
            assurance_records.append(record)
            assurance_summaries.append(
                {
                    "kind": kind,
                    "role": role,
                    "candidate_digest": record["candidate_digest"],
                    "status": record["status"],
                    "read_receipts": record["evidence"],
                    "blocked_write_receipt": denied["result"]["receipt_ref"],
                    "blocked_write_reason": denied["reason_code"],
                    "assurance_record_ref": record["receipt_ref"],
                    "write_surface_attestation": "READ_ONLY_CONFIRMED",
                }
            )

        _check(
            checks,
            "A17-009-read-only-review-and-validation",
            len(assurance_records) == 2
            and all(record["status"] == "PASS" for record in assurance_records)
            and all(record["candidate_digest"] == frozen_after_task["digest"] for record in assurance_records),
            surface="bbk_control_bind",
            assurance_record_refs=[record["receipt_ref"] for record in assurance_records],
            read_only_binding_refs=assurance_binding_refs,
            candidate_digest=frozen_after_task["digest"],
        )

        status_bindings = [parent, task_binding, *assurance_bindings]
        status_bindings_before = all_bindings(project)
        status_receipts_before = all_receipts(project)
        status_journal_digest = f"sha256:{canonical_digest({'bindings': status_bindings_before, 'receipts': status_receipts_before})}"
        governance_status_results = [
            query_status(
                project,
                {
                    "schema": "bbk.governance-status-query.v1",
                    "host_version": HOST_VERSION,
                    "session_id": binding["request"]["session_id"],
                    "invocation_id": binding["request"]["invocation_id"],
                    "binding_ref": binding["binding_id"],
                },
            )
            for binding in status_bindings
        ]
        governance_status_read_only = (
            status_bindings_before == all_bindings(project)
            and status_receipts_before == all_receipts(project)
            and all(item["status"] == "PASS" for item in governance_status_results)
            and all(item["journal"]["canonical_digest"] == status_journal_digest for item in governance_status_results)
        )
        dispatch_lifecycle_results = [
            dispatch_status(project, dispatch_ref=item["compiled"]["dispatch_ref"])
            for item in workers
        ] + [
            dispatch_status(project, dispatch_ref=item["dispatch_ref"])
            for item in assurance_binding_refs
        ]

        counts = _receipt_counts(project)
        expected_coordination = 8  # 2*(assign/start/complete) + integration request/complete
        vcs_receipts = [
            receipt
            for receipt in all_receipts(project)
            if receipt.get("receipt_kind") == "VCS_MUTATION"
        ]
        actual_mutated_paths = sorted(
            {
                path
                for receipt in vcs_receipts
                for path in receipt.get("content", {}).get("changed_paths", [])
            }
        )
        _check(
            checks,
            "A17-010-mutation-and-coordination-receipt-accounting",
            counts.get("COORDINATION_COMMAND") == expected_coordination
            and counts.get("BEADS_COMMAND") == expected_coordination
            and counts.get("BEADS_PROJECTION") == expected_coordination
            and counts.get("VCS_MUTATION") == 2
            and actual_mutated_paths == sorted(EXPECTED_OUTPUTS)
            and counts.get("QUALIFIED_TASK") == 1
            and counts.get("BOUND_QUALIFIED_TASK") == 1
            and counts.get("READ_ONLY_TASK_REGISTRATION") == 2
            and counts.get("CANDIDATE_INTEGRATION_ADMISSION") == 1
            and counts.get("ASSURANCE_RECORD") == 2,
            receipt_counts=counts,
            actual_mutated_paths=actual_mutated_paths,
            expected_mutated_paths=sorted(EXPECTED_OUTPUTS),
        )

        forbidden_files = [
            project / "backend" / "orchestrator-forbidden.txt",
            integrated_workspace / "backend" / "forbidden.txt",
            *(Path(item["binding"]["request"]["workspace_ref"]) / ("frontend" if item["spec"]["name"] == "backend" else "backend") / "cross-worker-forbidden.txt" for item in workers),
        ]
        _check(
            checks,
            "A17-011-no-prohibited-role-product-mutation",
            all(not path.exists() for path in forbidden_files)
            and frozen_after_task["digest"] == frozen_before_task["digest"],
            candidate_digest=frozen_after_task["digest"],
            forbidden_files_absent=len(forbidden_files),
        )

        backend_issues = {
            work_unit: beads_adapter.read_backend_issue(project, work_unit, bd_path=bd_executable)
            for work_unit in (
                "WU-FIXTURE-BACKEND",
                "WU-FIXTURE-FRONTEND",
                "WU-FIXTURE-INTEGRATION",
            )
        }
        _check(
            checks,
            "A17-012-beads-single-writer-projection-visible",
            all(value for value in backend_issues.values()),
            issue_ids=sorted(backend_issues),
            direct_beads_write_authority="DENIED",
        )

        oracle_qualification = _read_json(ORACLE_QUALIFICATION)
        oracle_file_digest = _sha256_file(ORACLE_QUALIFICATION)
        _check(
            checks,
            "A17-013-session-inspector-oracle-bound",
            oracle_qualification.get("release") == RELEASE
            and oracle_qualification.get("work_unit") == "WU-016"
            and oracle_qualification.get("qualification") == "AUTOMATED_PASS"
            and oracle_qualification.get("assertions", {}).get("VER-035") == "PASS",
            evidence_path="evidence/qualification/session-inspector-oracle-alpha17.json",
            evidence_digest=oracle_file_digest,
            assertion="VER-035",
            status=oracle_qualification.get("assertions", {}).get("VER-035"),
        )
        host_contract = _read_json(OMP_HOST_CONTRACT)
        host_contract_digest = _sha256_file(OMP_HOST_CONTRACT)
        _check(
            checks,
            "A17-014-keyless-omp-dispatch-rewrite-bound",
            host_contract.get("status") == "PASS"
            and host_contract.get("qualified_host", {}).get("omp_version_output") == HOST_VERSION
            and host_contract.get("assertions", {}).get("VER-021") == "PASS"
            and any(
                scenario.get("scenario") == "dispatch-rewrite"
                and scenario.get("status") == "PASS"
                and scenario.get("observations", {}).get("presentation_i_absent_at_pre_effect_hook") is True
                and scenario.get("observations", {}).get("resolved_child_started") is True
                and scenario.get("observations", {}).get("compact_marker_absent_from_child_request") is True
                for scenario in host_contract.get("scenarios", [])
                if isinstance(scenario, dict)
            ),
            evidence_path="evidence/qualification/omp-host-contract-rc9.json",
            evidence_digest=host_contract_digest,
            assertion="VER-021",
            status=host_contract.get("assertions", {}).get("VER-021"),
            host=host_contract.get("qualified_host", {}).get("omp_version_output"),
        )
        _check(
            checks,
            "A17-015-keyless-omp-yield-validation-bound",
            host_contract.get("status") == "PASS"
            and host_contract.get("assertions", {}).get("VER-022") == "PASS"
            and any(
                scenario.get("scenario") == "yield-validation"
                and scenario.get("status") == "PASS"
                and scenario.get("observations", {}).get("malformed_yield_blocked_before_acceptance") is True
                and scenario.get("observations", {}).get("complete_prepared_yield_admission_observed") is True
                and scenario.get("observations", {}).get("complete_role_return_observed_by_parent") is True
                and scenario.get("observations", {}).get("unvalidated_malformed_return_absent_from_parent") is True
                for scenario in host_contract.get("scenarios", [])
                if isinstance(scenario, dict)
            ),
            evidence_path="evidence/qualification/omp-host-contract-rc9.json",
            evidence_digest=host_contract_digest,
            assertion="VER-022",
            status=host_contract.get("assertions", {}).get("VER-022"),
            host=host_contract.get("qualified_host", {}).get("omp_version_output"),
        )
        _check(
            checks,
            "A17-016-advertised-governance-surfaces-bound",
            governance_status_read_only
            and task_result["status"] == "PASS"
            and len(assurance_binding_refs) == 2
            and counts.get("BOUND_QUALIFIED_TASK") == 1
            and counts.get("READ_ONLY_TASK_REGISTRATION") == 2
            and len(dispatch_lifecycle_results) == 4
            and all(item.get("status") in {"ACTIVATED", "TERMINAL"} for item in dispatch_lifecycle_results)
            and sum(item.get("status") == "TERMINAL" for item in dispatch_lifecycle_results) == 2,
            surfaces=sorted([
                "bbk_control_bind",
                "bbk_control_dispatch_status",
                "bbk_governance_status",
                "bbk_task_run",
            ]),
            queried_roles=sorted(item["binding"]["role"] for item in governance_status_results),
            dispatch_lifecycles=[
                {
                    "dispatch_ref": item["dispatch_ref"],
                    "status": item["status"],
                    "active_binding_ref": item.get("active_binding_ref"),
                    "actual_session_id": item.get("actual_session_id"),
                }
                for item in dispatch_lifecycle_results
            ],
            journal_digest=status_journal_digest,
            binding_count=governance_status_results[0]["journal"]["binding_count"],
            receipt_count=governance_status_results[0]["journal"]["receipt_count"],
            status_query_mutated_journal=False,
            bound_task_receipt=task_result["receipt_ref"],
            read_only_registration_refs=[item["registration_ref"] for item in assurance_binding_refs],
        )
        _check(
            checks,
            "A17-017-report-inputs-complete",
            all(item["status"] == "PASS" for item in checks),
            prior_check_count=len(checks),
            assertion=ASSERTION_ID,
            gate="GATE-017-AUTOMATED",
        )

        report_core = {
            "schema": "bbk.alpha17-qualification-report.v1",
            "qualification_id": f"alpha17:{canonical_digest({'fixture': fixture_digest, 'candidate': frozen_after_task['digest'], 'assertion': ASSERTION_ID})}",
            "release": RELEASE,
            "work_unit": WORK_UNIT_ID,
            "qualification": "AUTOMATED_PASS",
            "assertion_id": ASSERTION_ID,
            "assertions": {ASSERTION_ID: "PASS"},
            "gate": {
                "gate_id": GATE_ID,
                "decision": "RC_ELIGIBLE",
                "manual_provider_gate": "PENDING_WU_018",
                "required_inputs": list(GATE_REQUIRED_INPUTS),
                "pass_criteria": list(GATE_PASS_CRITERIA),
            },
            "mode": "AUTOMATED_KEYLESS_LOCAL",
            "status": "PASS",
            "observed_at": mise_adapter.utc_now(),
            "fixture": {
                "name": "alpha17-governed-vertical-slice",
                "source_digest": fixture_digest,
                "baseline_git_commit": baseline_commit,
            },
            "session_inspector_oracle": {
                "evidence_path": "evidence/qualification/session-inspector-oracle-alpha17.json",
                "evidence_digest": oracle_file_digest,
                "work_unit": "WU-016",
                "assertions": {"VER-035": "PASS"},
                "qualification": "AUTOMATED_PASS",
            },
            "tools": {
                "git": _tool_identity(git_executable, ("--version",)),
                "jj": _bound_tool_identity(jj_command, jj_tool_binding),
                "bd": _bound_tool_identity(bd_command, bd_tool_binding),
                "mise": _tool_identity(mise_executable, ("--version",)),
                "host_contract": {
                    "version": HOST_VERSION,
                    "mode": "QUALIFIED_KEYLESS_OMP_HOST",
                    "evidence_path": "evidence/qualification/omp-host-contract-rc9.json",
                    "evidence_digest": host_contract_digest,
                    "assertions": host_contract.get("assertions", {}),
                },
            },
            "workers": worker_reports,
            "integration": {
                "control_projection_id": integration_control["projection"]["projection_id"],
                "integration_receipt_ref": integration_receipt_id,
                "candidate_admission_ref": candidate_admission["receipt_id"],
                "integration_digest": integrated["integration_digest"],
                "mode": integrated["integration_mode"],
                "source_change_ids": integrated["source_change_ids"],
                "source_commit_ids": integrated["source_commit_ids"],
                "integrated_paths": integrated["integrated_paths"],
                "candidate": _normalize_candidate(frozen_after_task, campaign_parent),
                "completion_projection_id": integration_complete["projection"]["projection_id"],
            },
            "qualified_task": {
                "task": task_result["task"],
                "status": task_result["status"],
                "exit_status": task_result["exit_status"],
                "candidate_digest": task_result["candidate_after"]["digest"],
                "toolchain_definition_digest": task_result["toolchain_definition_digest"],
                "mise_version": task_result["mise_version"],
                "output_digest": task_result["output_digest"],
                "receipt_ref": task_result["receipt_ref"],
                "candidate_unchanged": task_result["candidate_unchanged"],
            },
            "assurance": assurance_summaries,
            "receipt_accounting": {
                "counts": counts,
                "changed_paths": actual_mutated_paths,
                "all_candidate_changes_receipted": actual_mutated_paths == sorted(EXPECTED_OUTPUTS),
                "beads_backend_writes_via_adapter": True,
            },
            "checks": checks,
            "security": {
                "external_provider_used": False,
                "network_used": False,
                "credentials_used": False,
                "dependency_installation_performed": False,
                "waivers": [],
            },
            "claim_limit": "This automated keyless report establishes VER-036 only. It does not establish the real-provider manual gate, Alpha.17 final release, deployment, publication, or live acceptance.",
            "smallest_next_action": "Build the exact Alpha.17 release candidate and operator-run real-provider qualification packet for VER-037 through VER-039.",
        }
        return {
            **report_core,
            "report_digest": f"sha256:{canonical_digest(report_core)}",
        }


def _error_result(error: BaseException) -> dict[str, Any]:
    if isinstance(error, QualificationError):
        code = error.code
        message = error.message
        details = error.details
    else:
        code = type(error).__name__
        message = str(error)
        details = {}
    core = {
        "schema": "bbk.alpha17-qualification-report.v1",
        "qualification_id": f"alpha17:failed:{canonical_digest({'code': code, 'message': message})}",
        "release": RELEASE,
        "work_unit": WORK_UNIT_ID,
        "assertion_id": ASSERTION_ID,
        "assertions": {ASSERTION_ID: "FAIL"},
        "mode": "AUTOMATED_KEYLESS_LOCAL",
        "qualification": "AUTOMATED_FAIL",
        "status": "FAIL",
        "gate": {
            "gate_id": GATE_ID,
            "decision": "BLOCK_AUTOMATED",
            "manual_provider_gate": "NOT_REACHED",
            "required_inputs": list(GATE_REQUIRED_INPUTS),
            "pass_criteria": list(GATE_PASS_CRITERIA),
        },
        "observed_at": mise_adapter.utc_now(),
        "checks": [],
        "error": {"code": code, "message": message, "details": details},
        "security": {
            "external_provider_used": False,
            "network_used": False,
            "credentials_used": False,
            "dependency_installation_performed": False,
            "waivers": [],
        },
        "claim_limit": "VER-036 is not established by this failed report.",
        "smallest_next_action": "Correct the reported local qualification blocker and rerun the exact automated campaign.",
    }
    return {**core, "report_digest": f"sha256:{canonical_digest(core)}"}


def run_alpha17_automated(
    *,
    git_path: str | Path | None = None,
    jj_path: str | Path | None = None,
    bd_path: str | Path | None = None,
    mise_path: str | Path | None = None,
    fixture_root: str | Path = FIXTURE_ROOT,
    temporary_parent: str | Path | None = None,
) -> dict[str, Any]:
    """Run VER-036 with mise as the normal owner of jj and Beads."""
    mise_executable = _executable(mise_path, "BBK_MISE", "mise")
    previous = os.environ.get("BBK_MISE")
    os.environ["BBK_MISE"] = str(mise_executable)
    try:
        return _run_alpha17_automated_bound(
            git_path=git_path,
            jj_path=jj_path,
            bd_path=bd_path,
            mise_path=mise_executable,
            fixture_root=fixture_root,
            temporary_parent=temporary_parent,
        )
    finally:
        if previous is None:
            os.environ.pop("BBK_MISE", None)
        else:
            os.environ["BBK_MISE"] = previous


def render_human_report(report: Mapping[str, Any]) -> str:
    """Render the path-normalized qualification result for operator review."""
    lines = [
        "# BBK Alpha.17 automated qualification",
        "",
        f"- Release: `{report.get('release', RELEASE)}`",
        f"- Work unit: `{report.get('work_unit', WORK_UNIT_ID)}`",
        f"- Qualification: `{report.get('qualification', 'UNKNOWN')}`",
        f"- Gate: `{report.get('gate', {}).get('gate_id', GATE_ID)}` → `{report.get('gate', {}).get('decision', 'UNKNOWN')}`",
        f"- Assertion: `{report.get('assertion_id', ASSERTION_ID)}` → `{report.get('assertions', {}).get(ASSERTION_ID, 'UNKNOWN')}`",
        f"- Machine-report digest: `{report.get('report_digest', 'UNAVAILABLE')}`",
        "",
    ]
    error = report.get("error")
    if isinstance(error, Mapping):
        lines.extend(
            [
                "## Blocking error",
                "",
                f"- Code: `{error.get('code', 'UNKNOWN')}`",
                f"- Message: {error.get('message', '')}",
                "",
            ]
        )
    workers = report.get("workers")
    if isinstance(workers, list):
        lines.extend(["## Governed workers", ""])
        for worker in workers:
            lines.append(
                "- "
                f"`{worker.get('work_unit_id')}` / `{worker.get('attempt_id')}`: "
                f"session `{worker.get('session_id')}`, jj change `{worker.get('jj_change_id')}`, "
                f"scope `{', '.join(worker.get('scope', []))}`, changed `{', '.join(worker.get('changed_paths', []))}`."
            )
        lines.append("")
    integration = report.get("integration")
    if isinstance(integration, Mapping):
        candidate = integration.get("candidate", {})
        lines.extend(
            [
                "## Integration and qualification",
                "",
                f"- Integration mode: `{integration.get('mode')}`",
                f"- Integrated paths: `{', '.join(integration.get('integrated_paths', []))}`",
                f"- Frozen candidate: `{candidate.get('digest')}`",
            ]
        )
        task = report.get("qualified_task", {})
        lines.extend(
            [
                f"- Real mise task: `{task.get('task')}` → `{task.get('status')}`; candidate unchanged: `{task.get('candidate_unchanged')}`",
                "",
            ]
        )
    assurance = report.get("assurance")
    if isinstance(assurance, list):
        lines.extend(["## Read-only assurance", ""])
        for item in assurance:
            lines.append(
                f"- `{item.get('kind')}` by `{item.get('role')}`: `{item.get('status')}`; "
                f"write attempt `{item.get('blocked_write_reason')}`."
            )
        lines.append("")
    checks = report.get("checks", [])
    lines.extend(["## Checks", ""])
    for item in checks:
        lines.append(f"- `{item.get('id')}`: `{item.get('status')}`")
    lines.extend(
        [
            "",
            "## Qualification boundary",
            "",
            str(report.get("claim_limit", "No claim limit was recorded.")),
            "",
            f"Smallest next action: {report.get('smallest_next_action', 'None recorded.')}",
            "",
        ]
    )
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release", choices=("alpha17",))
    parser.add_argument("--automated", action="store_true", help="run the keyless automated qualification campaign")
    parser.add_argument("--git")
    parser.add_argument("--jj")
    parser.add_argument("--bd")
    parser.add_argument("--mise")
    parser.add_argument("--fixture", default=str(FIXTURE_ROOT))
    parser.add_argument("--output", help="write the machine-readable report to this path instead of stdout only")
    parser.add_argument("--human-output", help="write a concise Markdown qualification report to this path")
    parser.add_argument("--temporary-parent", help="optional parent for the disposable campaign")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.automated:
        result = _error_result(QualificationError("QUALIFICATION_MODE_REQUIRED", "--automated is required for alpha17"))
        status = 2
    else:
        try:
            result = run_alpha17_automated(
                git_path=args.git,
                jj_path=args.jj,
                bd_path=args.bd,
                mise_path=args.mise,
                fixture_root=args.fixture,
                temporary_parent=args.temporary_parent,
            )
            status = 0
        except BaseException as exc:  # return structured local qualification failure
            result = _error_result(exc)
            status = 1
    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    if args.human_output:
        human_output = Path(args.human_output).resolve()
        human_output.parent.mkdir(parents=True, exist_ok=True)
        human_output.write_text(render_human_report(result), encoding="utf-8")
    sys.stdout.write(rendered)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
