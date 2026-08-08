#!/usr/bin/env python3
"""Build the deterministic Alpha.17 Windows real-provider qualification kit."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from runtime_requirements import enforce_supported_python

enforce_supported_python(program="BBK OMP manual qualification kit builder")

import dependencies

VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
TEMPLATE = ROOT / "tools" / "qualification" / "manual-kit-template"
FIXED_TIME = (2026, 8, 5, 0, 0, 0)
TOKEN_RE = re.compile(r"@BBK_[A-Z_]+@")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def rc_identity() -> tuple[str, str]:
    if VERSION == "0.1.0-alpha.17":
        return "FINAL", "final"
    if VERSION == "0.1.0-alpha.17.0.2":
        return "ALPHA17.0.2", "0-2"
    match = re.search(r"\+rc\.(\d+)$", VERSION)
    if not match:
        raise ValueError(f"VERSION is not an Alpha.17 candidate, final, or supported successor release: {VERSION}")
    number = match.group(1)
    return f"RC{number}", f"rc{number}"


def replace_tokens(root: Path, replacements: dict[str, str]) -> None:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for token, value in replacements.items():
            text = text.replace(token, value)
        unresolved = TOKEN_RE.findall(text)
        if unresolved:
            raise ValueError(f"unresolved manual-kit tokens in {path.relative_to(root)}: {sorted(set(unresolved))}")
        path.write_text(text, encoding="utf-8", newline="\n")


def file_record(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, FIXED_TIME)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    return info


def build_zip(source: Path, output: Path) -> None:
    root_name = source.name
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source.rglob("*"), key=lambda item: item.relative_to(source).as_posix()):
            relative = path.relative_to(source)
            if path.is_file() and "__pycache__" not in relative.parts and path.suffix != ".pyc":
                name = f"{root_name}/{relative.as_posix()}"
                archive.writestr(zip_info(name), path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def validate_kit(kit: Path, archive_name: str, archive_sha: str, package_root_sha: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, detail: Any = None) -> None:
        checks.append({"name": name, "status": "PASS" if condition else "FAIL", "detail": detail})
        if not condition:
            raise ValueError(f"manual-kit validation failed: {name}: {detail}")

    check("archive-present", (kit / archive_name).is_file())
    check("archive-digest", sha256(kit / archive_name) == archive_sha)
    manifest = json.loads((kit / f"bbk-{VERSION}-package-manifest.json").read_text(encoding="utf-8"))
    check("package-version", manifest.get("version") == VERSION, manifest.get("version"))
    check("package-root", manifest.get("root_sha256") == package_root_sha, manifest.get("root_sha256"))
    expected = json.loads((kit / "expected-invariants.json").read_text(encoding="utf-8"))
    check("sixteen-invariants", [item["id"] for item in expected["invariants"]] == [f"M17-{i:03d}" for i in range(1, 17)])
    start = (kit / "start-alpha17-qualification.ps1").read_text(encoding="utf-8")
    check("skills-disabled", "--no-skills" in start)
    check("rules-disabled", "--no-rules" in start)
    check("broken-no-extensions-flag-absent", "'--no-extensions'" not in start)
    overlay = kit / "omp-qualification-overlay.yml"
    check("extension-overlay-present", overlay.is_file())
    check("configured-extensions-cleared", "extensions: []" in overlay.read_text(encoding="utf-8"))
    check("extension-overlay-applied", "'--config', $overlay" in start)
    check("explicit-extension-order", start.index("'--extension', $extension") < start.index("'--extension', $helper"))
    check("manual-command-emitter", "launch-alpha17-qualification-command.ps1" in start and "No OMP process was started" in start)
    check("no-process-launch", all(value not in start for value in ("System.Diagnostics.Process", "Start-Process", "$process.WaitForExit()", "Invoke-ForegroundInteractive")))
    prompt = (kit / "EXACT-OMP-PROMPT.md").read_text(encoding="utf-8")
    check("validated-return-builder-required", all(value in prompt for value in ("bbk_return_template", "bbk_return_prepare", "yield_input")))
    collector = (kit / "collect-evidence.ps1").read_text(encoding="utf-8")
    check("full-gate-analyzer", all(value in collector for value in ("--full-gate", "--result-record-template", "--result-record-output", "RESULT-RECORD.json")))
    analyzer = (kit / "analyze-session.py").read_text(encoding="utf-8")
    check("nested-session-return-analysis", all(value in analyzer for value in ("flatten_session_entries", "analyze_role_returns", "analyze_verification_economy", "populate_result_record")))
    template_scripts = [
        kit / "install-isolated-rc.ps1", kit / "start-alpha17-qualification.ps1",
        kit / "collect-evidence.ps1", kit / "redact-and-package.ps1", kit / "rollback-isolated-rc.ps1",
    ]
    stale_versions = [path.name for path in template_scripts if re.search(r"alpha17-rc(?:3|4|5|6|7|8)(?![0-9])", path.read_text(encoding="utf-8"), re.I)]
    check("no-stale-rc-paths", not stale_versions, stale_versions)
    redact = (kit / "redact-and-package.ps1").read_text(encoding="utf-8")
    rollback = (kit / "rollback-isolated-rc.ps1").read_text(encoding="utf-8")
    check("current-redacted-archive-name", f"bbk-alpha17-{rc_identity()[1]}-redacted-evidence.zip" in redact)
    check("current-rollback-root", f"bbk-alpha17-{rc_identity()[1]}-manual" in rollback)
    helper = kit / "manual-bootstrap-extension.mjs"
    _unused, node_environment = dependencies.command_with_node_runtime((), environment=os.environ)
    node = node_environment["BBK_TEST_NODE"]
    completed = subprocess.run(
        dependencies.command_argv(node, ("--check", str(helper)), environment=node_environment),
        env=node_environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    check("helper-syntax", completed.returncode == 0, completed.stderr)
    for path in (kit / "bootstrap-binding.py", kit / "manual-integration.py", kit / "redact-evidence.py", kit / "analyze-session.py", kit / "qualification" / "verify_candidate.py"):
        completed = subprocess.run([sys.executable, "-m", "py_compile", str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        check(f"python-syntax:{path.name}", completed.returncode == 0, completed.stderr)
    for path in sorted(kit.rglob("*.json")):
        json.loads(path.read_text(encoding="utf-8-sig"))
    check("json-parse", True)
    token_hits: list[str] = []
    for path in sorted(kit.rglob("*")):
        if not path.is_file() or path.suffix == ".zip":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if TOKEN_RE.search(text):
            token_hits.append(path.relative_to(kit).as_posix())
    check("no-template-tokens", not token_hits, token_hits)
    return {
        "schema": "bbk.alpha17-manual-kit-validation.v2",
        "version": VERSION,
        "status": "PASS",
        "check_count": len(checks),
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    release_dir = Path(args.release_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    label, slug = rc_identity()
    archive_name = f"bbk-{VERSION}.zip"
    archive = release_dir / archive_name
    manifest_source = release_dir / f"bbk-{VERSION}-package-manifest.json"
    notes_source = release_dir / f"bbk-{VERSION}-release-notes.md"
    for path in (archive, manifest_source, notes_source):
        if not path.is_file():
            raise FileNotFoundError(path)
    archive_sha = sha256(archive)
    manifest = json.loads(manifest_source.read_text(encoding="utf-8"))
    package_root_sha = str(manifest.get("root_sha256") or "")
    if manifest.get("version") != VERSION or not re.fullmatch(r"[0-9a-f]{64}", package_root_sha):
        raise ValueError("release package manifest identity is invalid")

    kit_name = f"manual-qualification-kit-alpha17-{slug}"
    destination = output_dir / kit_name
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(TEMPLATE, destination)
    replacements = {
        "@BBK_VERSION@": VERSION,
        "@BBK_RC_LABEL@": label,
        "@BBK_RC_SLUG@": slug,
        "@BBK_ARCHIVE_SHA256@": archive_sha,
        "@BBK_PACKAGE_ROOT_SHA256@": package_root_sha,
    }
    replace_tokens(destination, replacements)

    shutil.copy2(archive, destination / archive_name)
    manifest_name = f"bbk-{VERSION}-package-manifest.json"
    notes_name = f"bbk-{VERSION}-release-notes.md"
    shutil.copy2(manifest_source, destination / manifest_name)
    shutil.copy2(notes_source, destination / notes_name)
    checksum_name = f"{archive_name}.sha256"
    (destination / checksum_name).write_text(f"{archive_sha}  {archive_name}\n", encoding="utf-8")

    expected = json.loads((destination / "expected-invariants.json").read_text(encoding="utf-8"))
    kit_record = {
        "schema": "bbk.manual-qualification-kit.v2",
        "created_at": "2026-08-05T00:00:00Z",
        "release_candidate": {
            "version": VERSION,
            "archive": archive_name,
            "archive_sha256": archive_sha,
            "package_root_sha256": package_root_sha,
            "package_manifest": manifest_name,
            "release_notes": notes_name,
            "qualified_omp_host": "omp/16.4.8",
        },
        "gate": {
            "manual_qualification": "VER-037",
            "operator_packet": "VER-038",
            "finalization_guard": "VER-039",
            "alpha17_final_authorized": VERSION == "0.1.0-alpha.17",
        },
        "expected_invariants": {
            "path": "expected-invariants.json",
            "count": len(expected["invariants"]),
            "ids": [item["id"] for item in expected["invariants"]],
            "sha256": sha256(destination / "expected-invariants.json"),
        },
        "launch_contract": {
            "manual_command_emitter": True,
            "starts_omp_process": False,
            "omp_16_4_8_no_extensions_flag_forbidden": True,
            "configured_extension_list_replaced": True,
            "extension_overlay": "omp-qualification-overlay.yml",
            "explicit_extension_order": ["bbk_rc", "manual_helper"],
            "skill_discovery_disabled": True,
            "rule_discovery_disabled": True,
            "extension_runtime_required": "bbk.omp-runtime.v1",
            "persistent_mode_activated_by_helper": True,
            "provider_prompt_receipt_required": True,
        },
        "toolchain": {
            "direct_operator_prerequisites": ["python", "git", "mise", "omp"],
            "global_jj_or_bd_required": False,
            "isolated_mise_state": True,
            "managed_tools": [
                {"execution_mode": "MISE_MANAGED", "tool_spec": "jj@0.43.0", "executable": "jj"},
                {"execution_mode": "MISE_MANAGED", "tool_spec": "github:gastownhall/beads@1.1.0", "executable": "bd"},
            ],
        },
        "coordination_contract": {
            "event_delivery_preferred": True,
            "blocking_empty_wait_allowed": True,
            "specific_job_poll_forbidden": True,
            "minimum_nonblocking_probe_interval_seconds": 300,
        },
        "checksums": {
            "rc_archive": {"path": archive_name, "sha256": archive_sha},
            "rc_checksum_file": {"path": checksum_name, "sha256": sha256(destination / checksum_name)},
            "package_manifest": {"path": manifest_name, "sha256": sha256(destination / manifest_name)},
            "release_notes": {"path": notes_name, "sha256": sha256(destination / notes_name)},
        },
        "redaction_policy": {
            "automatic_residual_secret_scan_required": True,
            "manual_inspection_required": True,
            "excluded_sensitive_material": ["API keys", "OAuth tokens", "cookies", "credential files", "private keys", "raw environment dumps"],
        },
    }
    write_json(destination / "manual-qualification-kit.json", kit_record)

    payload_files = [
        path for path in sorted(destination.rglob("*"), key=lambda item: item.relative_to(destination).as_posix())
        if path.is_file() and path.name not in {"KIT-MANIFEST.json", "SHA256SUMS.txt"}
        and "__pycache__" not in path.parts and path.suffix != ".pyc"
    ]
    # py_compile validation must not leak caches into the kit.
    for cache in list(destination.rglob("__pycache__")):
        shutil.rmtree(cache)
    payload_files = [path for path in payload_files if path.exists()]
    kit_manifest = {
        "schema": "bbk.manual-kit-manifest.v2",
        "version": VERSION,
        "file_count": len(payload_files),
        "files": [file_record(path, destination) for path in payload_files],
    }
    kit_manifest["root_sha256"] = hashlib.sha256(canonical({"version": VERSION, "files": kit_manifest["files"]})).hexdigest()
    write_json(destination / "KIT-MANIFEST.json", kit_manifest)

    checksum_files = [path for path in sorted(destination.rglob("*"), key=lambda item: item.relative_to(destination).as_posix()) if path.is_file() and path.name != "SHA256SUMS.txt"]
    (destination / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256(path)}  {path.relative_to(destination).as_posix()}\n" for path in checksum_files),
        encoding="utf-8",
    )

    validation = validate_kit(destination, archive_name, archive_sha, package_root_sha)
    # Syntax validation creates interpreter caches. They are non-product, path- and
    # time-sensitive material and must never enter the deterministic operator kit.
    for cache in list(destination.rglob("__pycache__")):
        shutil.rmtree(cache)
    for compiled in list(destination.rglob("*.pyc")):
        compiled.unlink()
    validation_path = output_dir / f"bbk-{VERSION}-manual-kit-validation.json"
    write_json(validation_path, validation)

    output_zip = output_dir / f"bbk-{VERSION}-manual-qualification-kit.zip"
    if output_zip.exists():
        output_zip.unlink()
    build_zip(destination, output_zip)
    digest = sha256(output_zip)
    checksum = output_dir / f"{output_zip.name}.sha256"
    checksum.write_text(f"{digest}  {output_zip.name}\n", encoding="utf-8")
    print(f"Built: {output_zip}")
    print(f"SHA-256: {digest}")
    print(f"Kit root SHA-256: {kit_manifest['root_sha256']}")
    print(f"Validation checks: {validation['check_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
