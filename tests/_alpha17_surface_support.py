from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from tests._fake_executable import write_python_executable
from tests._vcs_fixture import init_jj, prepare_git_seed

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
JJ = (
    os.environ.get("BBK_TEST_JJ")
    or shutil.which("jj")
    or "/mnt/data/bbk-alpha17-18-work/toolkit/blueprint-one-shot-toolkit-linux-x86_64/bin/jj"
)

# ``referencing.Registry`` is immutable, so completed registries can safely be
# reused within this test process.  The key includes a content fingerprint of
# every schema-root JSON file (including relative paths), which invalidates the
# cache when a referenced dependency or schema file changes.  Nothing is
# persisted outside this process.
_SCHEMA_REGISTRY_CACHE: dict[tuple[str, str], Registry] = {}
_SCHEMA_DOCUMENT_CACHE: dict[tuple[str, str], tuple[tuple[str, Any], ...]] = {}


def _schema_bundle(schema_root: Path) -> tuple[str, tuple[tuple[str, Any], ...], Registry]:
    root = schema_root.resolve()
    fingerprint, files = _schema_root_snapshot(root)
    key = (str(root), fingerprint)
    documents = _SCHEMA_DOCUMENT_CACHE.get(key)
    registry = _SCHEMA_REGISTRY_CACHE.get(key)
    if documents is None:
        documents = tuple(
            (path.relative_to(root).as_posix(), json.loads(contents.decode("utf-8")))
            for path, contents in files
        )
        _SCHEMA_DOCUMENT_CACHE[key] = documents
    if registry is None:
        resources = [
            (value["$id"], Resource.from_contents(value))
            for _name, value in documents
            if isinstance(value, dict) and value.get("$id")
        ]
        registry = Registry().with_resources(resources)
        _SCHEMA_REGISTRY_CACHE[key] = registry
    return fingerprint, documents, registry


def _schema_root_snapshot(schema_root: Path) -> tuple[str, list[tuple[Path, bytes]]]:
    """Return an exact content fingerprint and bytes for the schema root."""

    root = schema_root.resolve()
    files = [(path, path.read_bytes()) for path in sorted(root.rglob("*.json"))]
    digest = hashlib.sha256()
    for path, contents in files:
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(contents)
        digest.update(b"\0")
    return digest.hexdigest(), files


def _schema_registry(schema_root: Path) -> Registry:
    return _schema_bundle(schema_root)[2]


def _schema_documents(schema_root: Path) -> tuple[str, tuple[tuple[str, Any], ...]]:
    """Return one immutable, content-bound parsed schema inventory.

    The registry and root documents share the same fingerprint.  A changed
    nested schema therefore creates a new inventory even when its mtime or
    size happens to be unchanged, while callers on an unchanged tree reuse
    the exact parsed objects and immutable ``Registry`` instance.
    """

    fingerprint, documents, _registry = _schema_bundle(schema_root)
    return fingerprint, documents


def schema_validator(schema_name: str, schema_root: Path | None = None) -> Draft202012Validator:
    """Build a validator from the shared content-invalidated schema cache."""

    root = (schema_root or ROOT / "spec" / "schemas").resolve()
    _fingerprint, documents, registry = _schema_bundle(root)
    try:
        schema = next(value for name, value in documents if name == schema_name)
    except StopIteration as exc:
        raise FileNotFoundError(root / schema_name) from exc
    return Draft202012Validator(schema, registry=registry)


def schema_validate(instance: Any, schema_name: str) -> None:
    schema_validator(schema_name).validate(instance)


def init_candidate(path: Path, *, task_body: str = "printf pass", with_jj: bool = True) -> Path:
    """Build the historical candidate shape from an isolated plain-Git seed.

    JJ is initialized only for callers whose semantic operation uses it; the
    underlying prepared seed never copies or shares hidden metadata.
    """
    seed = prepare_git_seed(
        path,
        files={
            "src/product.txt": b"baseline\n",
            "mise.toml": ('[tasks."verify:candidate"]\nrun = ' + json.dumps(task_body) + "\n").encode("utf-8"),
        },
        fixture_id="candidate",
    )
    if with_jj:
        init_jj(seed, jj_path=JJ)
    return seed.root


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
