#!/usr/bin/env python3
"""Build the deterministic Alpha.17 Codex credentialed qualification kit."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from runtime_requirements import enforce_supported_python

enforce_supported_python(program="BBK Codex manual qualification kit builder")

VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
TEMPLATE = ROOT / "tools" / "qualification" / "codex-manual-kit-template"
ANALYZER = ROOT / "tools" / "jsonl_analyzer"
FIXED_TIME = (2026, 8, 6, 0, 0, 0)
TOKEN_RE = re.compile(r"@BBK_[A-Z_]+@")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def rc_identity() -> tuple[str, str]:
    if VERSION == "0.1.0-alpha.17":
        return "FINAL", "final"
    if VERSION == "0.1.0-alpha.17.0.2.1":
        return "ALPHA17.0.2.1", "0-2-1"
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
        unresolved = sorted(set(TOKEN_RE.findall(text)))
        if unresolved:
            raise ValueError(f"unresolved Codex-kit tokens in {path.relative_to(root)}: {unresolved}")
        path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def file_record(path: Path, root: Path) -> dict[str, Any]:
    return {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, FIXED_TIME)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    return info


def build_zip(source: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source.rglob("*"), key=lambda item: item.relative_to(source).as_posix()):
            relative = path.relative_to(source)
            if path.is_file() and "__pycache__" not in relative.parts and path.suffix != ".pyc":
                archive.writestr(zip_info(f"{source.name}/{relative.as_posix()}"), path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def gate_inputs(destination: Path) -> dict[str, str]:
    projection = json.loads((ROOT / "projections" / "manifest.json").read_text(encoding="utf-8"))
    worker = projection["agents"]["bbk_worker"]
    manifest = worker["compiled_procedures"]["codex"]
    catalog = worker["effective_external_catalogs"]["codex"]
    target = destination / "gate-inputs"
    target.mkdir(parents=True, exist_ok=True)
    write_json(target / "bbk-worker-codex-compiled-manifest.json", manifest)
    write_json(target / "bbk-worker-codex-effective-catalog.json", catalog)
    shutil.copy2(ROOT / "tests" / "fixtures" / "alpha17-optimization" / "planning-readiness.valid.json", target / "planning-readiness.valid.json")
    shutil.copy2(ROOT / "projections" / "codex" / "agents" / "bbk_worker.toml", target / "bbk_worker.toml")
    return {path.name: sha256(path) for path in sorted(target.iterdir()) if path.is_file()}


def validate(destination: Path, archive_name: str, archive_sha: str, package_root_sha: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    def check(name: str, condition: bool, detail: Any = None) -> None:
        checks.append({"name": name, "status": "PASS" if condition else "FAIL", "detail": detail})
        if not condition:
            raise ValueError(f"Codex manual-kit validation failed: {name}: {detail}")

    check("rc-archive", (destination / archive_name).is_file() and sha256(destination / archive_name) == archive_sha)
    manifest = json.loads((destination / f"bbk-{VERSION}-package-manifest.json").read_text(encoding="utf-8"))
    check("package-version", manifest.get("version") == VERSION, manifest.get("version"))
    check("package-root", manifest.get("root_sha256") == package_root_sha, manifest.get("root_sha256"))
    prepare = (destination / "prepare-codex-fixtures.ps1").read_text(encoding="utf-8")
    check("command-emitter", "No Codex process was started" in prepare and "launch-codex-commands.ps1" in prepare)
    check("no-codex-launch", "Start-Process" not in prepare and "& $CodexPath" not in prepare)
    check("project-install", '"--scope", "project"' in prepare and '"--codex"' in prepare)
    check("no-credentials", all(value not in prepare.upper() for value in ("OPENAI_API_KEY=", "API_KEY=")))
    analyze = (destination / "analyze-codex-run.ps1").read_text(encoding="utf-8")
    check("analyzer-gate", "evaluate_alpha17_gates.py" in analyze and "alpha17-config.json" in analyze)
    primary = (destination / "prompts" / "MH-CODEX-01-PRIMARY.md").read_text(encoding="utf-8")
    check("primary-zero-read-directive", "must not read `shared/skills/bbk-work-unit-execution/SKILL.md`" in primary)
    followup = (destination / "prompts" / "MH-CODEX-02-FOLLOWUP.md").read_text(encoding="utf-8")
    check("followup-same-child", "same logical `bbk_worker` child" in followup and "Do not spawn a replacement child" in followup)
    rolling = (destination / "prompts" / "MH-CODEX-03-ROLLING-WAVE.md").read_text(encoding="utf-8")
    check("rolling-frontier", all(value in rolling for value in ("FAST_CONTINUATION", "ADOPT_AND_GAP", "ROADMAP_READY", "FRONTIER_READY", "DEFERRED_UNTIL_FRONTIER")))
    for path in sorted((destination / "gate-inputs").glob("*.json")):
        json.loads(path.read_text(encoding="utf-8-sig"))
    compiled = json.loads((destination / "gate-inputs" / "bbk-worker-codex-compiled-manifest.json").read_text(encoding="utf-8"))
    catalog = json.loads((destination / "gate-inputs" / "bbk-worker-codex-effective-catalog.json").read_text(encoding="utf-8"))
    ids = {str(item["id"]) for item in compiled.get("procedures") or []}
    available = set(catalog.get("available_external_procedures") or catalog.get("effective_external_catalog") or [])
    check("static-catalog-suppression", bool(ids) and not ids.intersection(available), {"compiled": sorted(ids), "available_overlap": sorted(ids.intersection(available))})
    prompt = (destination / "gate-inputs" / "bbk_worker.toml").read_text(encoding="utf-8")
    check("compiled-tail-present", "## Compiled procedures" in prompt and "## End compiled procedures" in prompt)
    for path in sorted(destination.rglob("*.py")):
        completed = subprocess.run([sys.executable, "-m", "py_compile", str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        check(f"python-syntax:{path.relative_to(destination).as_posix()}", completed.returncode == 0, completed.stderr)
    token_hits: list[str] = []
    for path in sorted(destination.rglob("*")):
        if not path.is_file() or path.suffix == ".zip":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if TOKEN_RE.search(text):
            token_hits.append(path.relative_to(destination).as_posix())
    check("no-template-tokens", not token_hits, token_hits)
    return {"schema": "bbk.alpha17-codex-manual-kit-validation.v1", "version": VERSION, "status": "PASS", "check_count": len(checks), "checks": checks}


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

    destination = output_dir / f"codex-qualification-kit-alpha17-{slug}"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(TEMPLATE, destination)
    shutil.copytree(ANALYZER, destination / "jsonl-analyzer", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    replacements = {
        "@BBK_VERSION@": VERSION,
        "@BBK_RC_LABEL@": label,
        "@BBK_RC_SLUG@": slug,
        "@BBK_ARCHIVE_SHA256@": archive_sha,
        "@BBK_PACKAGE_ROOT_SHA256@": package_root_sha,
    }
    replace_tokens(destination, replacements)
    shutil.copy2(archive, destination / archive_name)
    shutil.copy2(manifest_source, destination / f"bbk-{VERSION}-package-manifest.json")
    shutil.copy2(notes_source, destination / f"bbk-{VERSION}-release-notes.md")
    (destination / f"{archive_name}.sha256").write_text(f"{archive_sha}  {archive_name}\n", encoding="utf-8", newline="\n")
    inputs = gate_inputs(destination)

    record = {
        "schema": "bbk.alpha17-codex-manual-kit.v1",
        "version": VERSION,
        "created_at": "2026-08-06T00:00:00Z",
        "candidate_archive": archive_name,
        "candidate_archive_sha256": archive_sha,
        "package_root_sha256": package_root_sha,
        "principal_gates": ["MH-CODEX-01", "MH-CODEX-02", "MH-CODEX-03"],
        "supplemental_tests": ["MH-CODEX-04", "MH-CODEX-05", "MH-CODEX-06"],
        "credential_policy": "USE_EXISTING_CODEX_AUTHENTICATION_ONLY",
        "starts_codex_process": False,
        "gate_inputs": inputs,
    }
    write_json(destination / "codex-manual-kit.json", record)

    for cache in list(destination.rglob("__pycache__")):
        shutil.rmtree(cache)
    for compiled in list(destination.rglob("*.pyc")):
        compiled.unlink()
    payload = [path for path in sorted(destination.rglob("*"), key=lambda item: item.relative_to(destination).as_posix()) if path.is_file() and path.name not in {"KIT-MANIFEST.json", "SHA256SUMS.txt"}]
    kit_manifest = {"schema": "bbk.codex-manual-kit-manifest.v1", "version": VERSION, "file_count": len(payload), "files": [file_record(path, destination) for path in payload]}
    kit_manifest["root_sha256"] = hashlib.sha256(canonical({"version": VERSION, "files": kit_manifest["files"]})).hexdigest()
    write_json(destination / "KIT-MANIFEST.json", kit_manifest)
    checksum_files = [path for path in sorted(destination.rglob("*"), key=lambda item: item.relative_to(destination).as_posix()) if path.is_file() and path.name != "SHA256SUMS.txt"]
    (destination / "SHA256SUMS.txt").write_text("".join(f"{sha256(path)}  {path.relative_to(destination).as_posix()}\n" for path in checksum_files), encoding="utf-8", newline="\n")

    validation = validate(destination, archive_name, archive_sha, package_root_sha)
    for cache in list(destination.rglob("__pycache__")):
        shutil.rmtree(cache)
    for compiled in list(destination.rglob("*.pyc")):
        compiled.unlink()
    write_json(output_dir / f"bbk-{VERSION}-codex-manual-kit-validation.json", validation)
    output_zip = output_dir / f"bbk-{VERSION}-codex-manual-qualification-kit.zip"
    if output_zip.exists():
        output_zip.unlink()
    build_zip(destination, output_zip)
    digest = sha256(output_zip)
    (output_dir / f"{output_zip.name}.sha256").write_text(f"{digest}  {output_zip.name}\n", encoding="utf-8", newline="\n")
    print(f"Built: {output_zip}")
    print(f"SHA-256: {digest}")
    print(f"Kit root SHA-256: {kit_manifest['root_sha256']}")
    print(f"Validation checks: {validation['check_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
