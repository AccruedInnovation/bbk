from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from tests._fake_executable import write_python_executable

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
JJ = (
    os.environ.get("BBK_TEST_JJ")
    or shutil.which("jj")
    or "/mnt/data/bbk-alpha17-18-work/toolkit/blueprint-one-shot-toolkit-linux-x86_64/bin/jj"
)


def schema_validate(instance: Any, schema_name: str) -> None:
    schema_root = ROOT / "spec" / "schemas"
    resources = []
    for path in sorted(schema_root.rglob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict) and value.get("$id"):
            resources.append((value["$id"], Resource.from_contents(value)))
    registry = Registry().with_resources(resources)
    schema = json.loads((schema_root / schema_name).read_text(encoding="utf-8"))
    Draft202012Validator(schema, registry=registry).validate(instance)


def init_candidate(path: Path, *, task_body: str = "printf pass") -> Path:
    path.mkdir(parents=True)
    (path / "src").mkdir()
    (path / "src" / "product.txt").write_bytes(b"baseline\n")
    (path / "mise.toml").write_text(
        '[tasks."verify:candidate"]\nrun = ' + json.dumps(task_body) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.name", "BBK Test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "bbk@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=path, check=True)
    subprocess.run(["git", "config", "core.eol", "lf"], cwd=path, check=True)
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(
        [str(JJ), "--no-pager", "--color=never", "git", "init", "--colocate", "."],
        cwd=path,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return path.resolve()


def control_parent(registry: Any, governance_root: Path) -> dict[str, Any]:
    (governance_root / ".bbk" / "coordination").mkdir(parents=True, exist_ok=True)
    return registry.create_initial_binding(
        governance_root,
        {
            "schema": "bbk.invocation-binding-create.v1",
            "session_id": "parent-session-1",
            "invocation_id": "parent-invocation-1",
            "role": "bbk_root_orchestrator",
            "work_unit_id": "WU-CONTROL",
            "attempt_id": "attempt-control-1",
            "baseline_ref": "git:main",
            "candidate_ref": "candidate:control",
            "workspace_ref": str(governance_root.resolve()),
            "authority_ref": "authority:user",
            "scope": {
                "path_prefixes": [str((governance_root / ".bbk" / "coordination").resolve())],
                "mutation_classes": ["COORDINATION_METADATA"],
                "semantic_scope": ["campaign:alpha17"],
            },
            "return_contract": "bbk.root-orchestrator-return.v2",
            "jj_change_id": "control-plane",
            "idempotency_key": "control-binding-1",
        },
        capability_ref="role:bbk_root_orchestrator@1.0.0-alpha.17",
        created_at="2026-08-04T00:00:00Z",
    )[0]


def worker_binding(registry: Any, jj_adapter: Any, governance_root: Path, candidate: Path) -> dict[str, Any]:
    identity = jj_adapter.identity(candidate, jj_path=JJ)
    return registry.create_initial_binding(
        governance_root,
        {
            "schema": "bbk.invocation-binding-create.v1",
            "session_id": "worker-session-1",
            "parent_session_id": "parent-session-1",
            "invocation_id": "worker-invocation-1",
            "role": "bbk_worker",
            "work_unit_id": "WU-WORKER",
            "attempt_id": "attempt-worker-1",
            "baseline_ref": "git:main",
            "candidate_ref": "candidate:worker",
            "workspace_ref": str(candidate.resolve()),
            "authority_ref": "authority:user",
            "scope": {
                "path_prefixes": [str((candidate / "src").resolve())],
                "mutation_classes": ["PRODUCT_CONTENT", "TEST_CONTENT", "BUILD_CONFIGURATION"],
                "semantic_scope": ["component:test"],
            },
            "return_contract": "bbk.worker-return.v2",
            "jj_change_id": identity["jj_change_id"],
            "idempotency_key": "worker-binding-1",
        },
        capability_ref="role:bbk_worker@1.0.0-alpha.17",
        created_at="2026-08-04T00:00:00Z",
    )[0]


def fake_mise(path: Path, *, mutate: bool = False, exit_status: int = 0) -> Path:
    mutation = (
        "    Path('src/product.txt').write_text('changed', encoding='utf-8')\n"
        if mutate
        else ""
    )
    return write_python_executable(
        path,
        "import sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "if args == ['--version']:\n"
        "    print('mise TEST-1.0')\n"
        "    raise SystemExit(0)\n"
        "if len(args) >= 2 and args[:2] == ['run', 'verify:candidate']:\n"
        + mutation
        + "    print('qualified-output')\n"
        + f"    raise SystemExit({exit_status})\n"
        + "raise SystemExit(9)\n",
    )
