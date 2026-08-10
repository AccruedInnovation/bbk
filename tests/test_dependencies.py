from __future__ import annotations

import ast
import io
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from contextlib import redirect_stdout
from pathlib import Path, PureWindowsPath
from unittest import mock

from tests._path_support import assert_same_path, source_ast

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import dependencies
import install
import install_dependencies
import runtime_requirements
import setup
import verify_all


class DependencyContractTests(unittest.TestCase):
    def test_python_floor_is_311(self) -> None:
        self.assertEqual(runtime_requirements.MINIMUM_PYTHON, (3, 11))
        self.assertFalse(runtime_requirements.supported((3, 10, 99)))
        self.assertTrue(runtime_requirements.supported((3, 11, 0)))


    def test_python_floor_and_public_docs_are_consistent(self) -> None:
        self.assertEqual(runtime_requirements.MINIMUM_PYTHON_TEXT, "3.11")
        current_docs = [
            "README.md",
            "docs/INSTALL.md",
            "docs/USAGE.md",
            "docs/DEVELOPMENT.md",
            "tools/jsonl_analyzer/README.md",
        ]
        combined = "\n".join((ROOT / name).read_text(encoding="utf-8") for name in current_docs)
        self.assertIn("Python 3.11", combined)
        self.assertNotIn("Python 3.10", combined)
        workflow = (ROOT / ".github" / "workflows" / "windows-verification.yml").read_text(encoding="utf-8")
        self.assertIn('"3.11"', workflow)
        self.assertNotIn('"3.10"', workflow)
        self.assertIn("jdx/mise-action@v4", workflow)
        self.assertIn("--install-dependencies --codex --omp --yes", workflow)
        self.assertIn("--check-dependencies --codex --omp", workflow)

    def test_install_with_empty_path_blocks_before_writing_or_third_party_imports(self) -> None:
        environment = os.environ.copy()
        environment["PATH"] = ""
        environment.pop("BBK_TEST_ALLOW_MISSING_DEPENDENCIES", None)
        with tempfile.TemporaryDirectory() as raw_project:
            project = Path(raw_project)
            result = subprocess.run(
                [
                    sys.executable,
                    "-S",
                    str(ROOT / "tools" / "setup.py"),
                    "--install",
                    "--scope",
                    "project",
                    "--root",
                    str(project),
                    "--codex",
                    "--dry-run",
                    "--json",
                ],
                cwd=ROOT,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="backslashreplace",
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, 2, result.stderr or result.stdout)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "ERROR")
            self.assertIn("Dependency preflight failed", report["error"])
            self.assertNotIn("ModuleNotFoundError", result.stderr + result.stdout)
            self.assertFalse(any(project.iterdir()))

    def test_mise_package_verification_task_uses_the_supported_strict_flag(self) -> None:
        config = tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))
        command = config["tasks"]["bbk:verify:package"]["run"]
        self.assertIn("tools/verify_package.py --strict-mode", command)
        self.assertNotEqual(command, "python tools/verify_package.py --strict")

    def test_root_mise_config_has_no_node_cross_dependency(self) -> None:
        config = tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))
        tools = config["tools"]
        self.assertEqual(
            tools,
            {
                "github:gastownhall/beads": "1.1.0",
                "jj": "0.43.0",
            },
        )
        rendered_tasks = json.dumps(config.get("tasks", {}), sort_keys=True).lower()
        self.assertNotIn("node", rendered_tasks)

    def test_omp_node_pin_is_isolated_from_default_mise_discovery(self) -> None:
        relative = dependencies.OMP_RUNTIME_MISE_CONFIG
        self.assertNotIn(relative.name, {"mise.toml", ".mise.toml", "mise.local.toml"})
        config = tomllib.loads((ROOT / relative).read_text(encoding="utf-8"))
        self.assertEqual(config, {"tools": {"node": "22.23.2"}})
        node = dependencies.managed_tool_contract(include_node=True)[-1]
        self.assertEqual(node["source_config"], relative.as_posix())

    def test_dependency_check_runs_before_python_packages_are_installed(self) -> None:
        environment = os.environ.copy()
        environment["PATH"] = ""
        result = subprocess.run(
            [
                sys.executable,
                "-S",
                str(ROOT / "tools" / "setup.py"),
                "--check-dependencies",
                "--codex",
                "--json",
            ],
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="backslashreplace",
            check=False,
            timeout=30,
        )
        self.assertEqual(result.returncode, 2, result.stderr or result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "BLOCK")
        blocked = {item["id"] for item in report["checks"] if item["status"] != "PASS"}
        self.assertIn("python-package:jsonschema", blocked)
        self.assertIn("python-package:referencing", blocked)
        self.assertNotIn("ModuleNotFoundError", result.stderr + result.stdout)

    def test_dependency_contract_declares_all_runtime_python_packages(self) -> None:
        contract = dependencies.dependency_contract(("codex",))
        self.assertEqual(contract["system_tools"], ["git", "mise"])
        self.assertEqual(
            set(contract["runtime_python_requirements"]),
            {"jsonschema", "referencing"},
        )
        self.assertFalse(contract["host_commands_block_install"])

    def test_single_component_version_bounds_are_enforced(self) -> None:
        self.assertTrue(dependencies._version_in_range("v22.23.2", "22"))
        self.assertFalse(dependencies._version_in_range("v21.99.0", "22"))
        self.assertTrue(dependencies._version_in_range("4.26.0", "4.25.1", "5"))
        self.assertFalse(dependencies._version_in_range("5.0.0", "4.25.1", "5"))

    def test_managed_version_match_is_exact_not_a_substring(self) -> None:
        record = dependencies.managed_tool_contract()[0]
        with (
            mock.patch.object(
                dependencies,
                "_resolve_mise_executable",
                return_value=(Path(sys.executable), None),
            ),
            mock.patch.object(
                dependencies,
                "_run_version",
                return_value=(True, f"jj 10.{record['version']}"),
            ),
        ):
            result = dependencies._check_managed(
                record,
                mise=Path(sys.executable),
                environment=os.environ,
            )
        self.assertEqual(result["status"], "BLOCK")

    def test_newer_compatible_runtime_python_packages_are_accepted(self) -> None:
        for distribution, version in (("jsonschema", "4.26.0"), ("referencing", "0.37.0")):
            requirement = dependencies.RUNTIME_PYTHON_REQUIREMENTS[distribution]
            with mock.patch.object(dependencies.importlib.metadata, "version", return_value=version):
                result = dependencies._check_python_requirement(
                    distribution,
                    requirement,
                    kind="python-runtime",
                    purpose="BBK runtime schema validation",
                )
            self.assertEqual(result["status"], "PASS", result)

    def test_tools_have_no_undeclared_third_party_python_imports(self) -> None:
        stdlib = set(sys.stdlib_module_names)
        python_files = [
            path for path in (ROOT / "tools").rglob("*.py")
            if "tests" not in path.parts and "__pycache__" not in path.parts
        ]
        local_modules = {path.stem for path in python_files}
        local_modules.update(path.name for path in (ROOT / "tools").iterdir() if path.is_dir())
        external: dict[str, set[str]] = {}
        for path in python_files:
            tree = source_ast(path)
            imports: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name.split(".", 1)[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imports.add(node.module.split(".", 1)[0])
            unknown = imports - stdlib - local_modules - {"__future__"}
            if unknown:
                external[path.relative_to(ROOT).as_posix()] = unknown
        allowed = set(dependencies.RUNTIME_PYTHON_REQUIREMENTS) | set(dependencies.TEST_REQUIREMENTS)
        undeclared = {
            path: sorted(names - allowed)
            for path, names in external.items()
            if names - allowed
        }
        self.assertEqual(undeclared, {})
        observed = set().union(*external.values()) if external else set()
        self.assertTrue(observed <= allowed, observed)

    def test_codex_contract_has_no_node_dependency(self) -> None:
        contract = dependencies.dependency_contract(("codex",))
        self.assertFalse(contract["omp_node_required"])
        self.assertEqual(
            [item["tool_spec"] for item in contract["managed_tools"]],
            ["jj@0.43.0", "github:gastownhall/beads@1.1.0"],
        )
        self.assertNotIn("node", {item["id"] for item in contract["managed_tools"]})
        self.assertTrue(
            all(item["source_config"] == "mise.toml" for item in contract["managed_tools"])
        )

    def test_omp_contract_adds_only_the_pinned_node_runtime(self) -> None:
        contract = dependencies.dependency_contract(("omp",))
        self.assertTrue(contract["omp_node_required"])
        records = {item["id"]: item for item in contract["managed_tools"]}
        self.assertEqual(set(records), {"jj", "bd", "node"})
        self.assertEqual(records["node"]["tool_spec"], f"node@{records['node']['version']}")
        self.assertEqual(records["node"]["kind"], "omp-runtime")

    def test_read_only_mise_checks_disable_downloads_and_auto_install(self) -> None:
        environment = dependencies.readonly_mise_environment({"PATH": "sentinel"})
        self.assertEqual(environment["PATH"], "sentinel")
        for name in (
            "MISE_AUTO_INSTALL",
            "MISE_EXEC_AUTO_INSTALL",
            "MISE_NOT_FOUND_AUTO_INSTALL",
        ):
            self.assertEqual(environment[name], "0")
        self.assertEqual(environment["MISE_OFFLINE"], "1")

    def test_managed_resolution_uses_mise_which_not_mise_exec(self) -> None:
        record = dependencies.managed_tool_contract()[0]
        resolved = Path(sys.executable).resolve()
        observed: dict[str, object] = {}

        def fake_run(command, *, environment, cwd, timeout=20.0):
            observed["command"] = list(command)
            observed["environment"] = dict(environment)
            observed["cwd"] = cwd
            return True, str(resolved)

        with (
            mock.patch.object(dependencies, "_run_capture", side_effect=fake_run),
            mock.patch.object(dependencies, "_usable_executable", return_value=True),
        ):
            path, error = dependencies._resolve_mise_executable(
                Path("/fake/mise"),
                record,
                environment={"PATH": "sentinel"},
            )
        self.assertEqual(path, resolved)
        self.assertIsNone(error)
        command = observed["command"]
        self.assertIn("which", command)
        self.assertNotIn("exec", command)
        self.assertEqual(observed["environment"]["MISE_OFFLINE"], "1")
        self.assertEqual(observed["environment"]["MISE_AUTO_INSTALL"], "0")

    def test_codex_preflight_does_not_resolve_node(self) -> None:
        passing = {
            "id": "tool",
            "kind": "system",
            "required": True,
            "status": "PASS",
            "path": sys.executable,
            "version": "test 1.0",
            "reason": None,
        }
        with (
            mock.patch.object(dependencies, "_check_direct", return_value=passing),
            mock.patch.object(dependencies, "_check_managed", return_value=passing),
            mock.patch.object(dependencies, "_resolve_node_runtime") as resolve_node,
        ):
            report = dependencies.check_dependencies(("codex",), check_hosts=False)
        self.assertEqual(report["status"], "PASS")
        resolve_node.assert_not_called()
        self.assertFalse(report["network_accessed"])
        self.assertFalse(report["mutation_performed"])

    def test_omp_preflight_resolves_node(self) -> None:
        passing = {
            "id": "tool",
            "kind": "system",
            "required": True,
            "status": "PASS",
            "path": sys.executable,
            "version": "test 1.0",
            "reason": None,
        }
        with (
            mock.patch.object(dependencies, "_check_direct", return_value=passing),
            mock.patch.object(dependencies, "_check_managed", return_value=passing),
            mock.patch.object(
                dependencies,
                "_resolve_node_runtime",
                return_value=(Path(sys.executable), "v22.23.2", "direct"),
            ) as resolve_node,
        ):
            report = dependencies.check_dependencies(("omp",), check_hosts=False)
        self.assertEqual(report["status"], "PASS")
        resolve_node.assert_called_once()
        node = next(item for item in report["checks"] if item["id"] == "node")
        self.assertEqual(node["source"], "direct")

    def test_windows_batch_launcher_uses_comspec(self) -> None:
        with mock.patch.object(dependencies.os, "name", "nt"):
            command = dependencies.command_argv(
                Path("C:/Program Files/BBK/fake.cmd"),
                ["--version"],
                environment={"COMSPEC": "C:/Windows/System32/cmd.exe"},
            )
        self.assertEqual(command[:4], ["C:/Windows/System32/cmd.exe", "/d", "/s", "/c"])
        self.assertEqual(command[-1], "--version")

    def test_verification_environment_exports_off_path_system_tools(self) -> None:
        git = Path(sys.executable).resolve()
        mise = Path(sys.executable).resolve()
        managed = iter((Path(sys.executable).resolve(), Path(sys.executable).resolve()))

        def discover(name: str, *, environment):
            return {"git": git, "mise": mise}.get(name)

        with (
            mock.patch.object(dependencies, "discover_executable", side_effect=discover),
            mock.patch.object(
                dependencies,
                "_resolve_mise_executable",
                side_effect=lambda *_args, **_kwargs: (next(managed), None),
            ),
        ):
            environment = dependencies.verification_environment(
                {"PATH": ""},
                strict=True,
            )
        self.assertEqual(environment["BBK_GIT"], str(git))
        self.assertEqual(environment["BBK_TEST_GIT"], str(git))
        self.assertEqual(environment["BBK_MISE"], str(mise))
        self.assertEqual(environment["BBK_TEST_MISE"], str(mise))
        assert_same_path(self, environment["BBK_JJ"], Path(sys.executable).resolve())
        assert_same_path(self, environment["BBK_BD"], Path(sys.executable).resolve())
        self.assertIn(str(git.parent), environment["PATH"].split(os.pathsep))

    def test_tool_subprocesses_do_not_bypass_dependency_resolution(self) -> None:
        external = {"git", "node", "mise", "jj", "bd"}
        bypasses: list[str] = []
        for path in sorted((ROOT / "tools").rglob("*.py")):
            tree = source_ast(path)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not node.args:
                    continue
                function = node.func
                if not (
                    isinstance(function, ast.Attribute)
                    and isinstance(function.value, ast.Name)
                    and function.value.id == "subprocess"
                    and function.attr in {"run", "Popen", "call", "check_call", "check_output"}
                ):
                    continue
                command = node.args[0]
                if not isinstance(command, (ast.List, ast.Tuple)) or not command.elts:
                    continue
                first = command.elts[0]
                if isinstance(first, ast.Constant) and first.value in external:
                    bypasses.append(
                        f"{path.relative_to(ROOT).as_posix()}:{node.lineno}:{first.value}"
                    )
        self.assertEqual(bypasses, [])

    def test_windows_mise_discovery_covers_supported_package_managers(self) -> None:
        environment = {
            "HOME": "C:/Users/example",
            "LOCALAPPDATA": "C:/Users/example/AppData/Local",
            "SCOOP": "C:/Users/example/scoop",
            "ChocolateyInstall": "C:/ProgramData/chocolatey",
        }
        with (
            mock.patch.object(dependencies.os, "name", "nt"),
            mock.patch.object(dependencies, "Path", PureWindowsPath),
        ):
            rendered = {str(path).replace("\\", "/") for path in dependencies._candidate_paths("mise", environment)}
        self.assertTrue(any(value.endswith("Microsoft/WinGet/Links/mise.exe") for value in rendered))
        self.assertTrue(any(value.endswith("scoop/shims/mise.exe") for value in rendered))
        self.assertTrue(any(value.endswith("chocolatey/bin/mise.exe") for value in rendered))

    def test_bootstrap_dry_run_installs_node_through_mise_not_system_packages(self) -> None:
        before = {
            "schema": "bbk.install-dependency-report.v1",
            "status": "BLOCK",
            "checks": [
                {"id": name, "status": "BLOCK"}
                for name in ("mise", "jj", "bd", "node")
            ],
            "host_checks": [],
        }
        args = install_dependencies.build_parser().parse_args(["--omp", "--dry-run", "--json"])
        with (
            mock.patch.object(install_dependencies.dependencies, "check_dependencies", return_value=before),
            mock.patch.object(install_dependencies, "detect_package_manager", return_value="apt-get"),
        ):
            result = install_dependencies.install_dependencies(args)
        node_spec = next(
            item["tool_spec"]
            for item in dependencies.managed_tool_contract(include_node=True)
            if item["id"] == "node"
        )
        self.assertIn(f"mise install {node_spec}", result["commands"])
        self.assertFalse(any("nodejs" in command for command in result["commands"]))

    def test_supported_system_managers_install_mise_without_cross_dependencies(self) -> None:
        for manager in ("port", "pacman", "apk"):
            commands = install_dependencies.system_install_commands(
                manager,
                need_git=False,
                need_mise=True,
            )
            rendered = "\n".join(" ".join(command) for command in commands)
            self.assertIn("mise", rendered, manager)
            self.assertNotIn("node", rendered.lower(), manager)
            self.assertNotIn("beads", rendered.lower(), manager)

    def test_system_package_plan_never_installs_node_jj_or_beads(self) -> None:
        commands = install_dependencies.system_install_commands(
            "winget", need_git=True, need_mise=True
        )
        rendered = "\n".join(" ".join(command) for command in commands)
        self.assertIn("Git.Git", rendered)
        self.assertIn("jdx.mise", rendered)
        self.assertNotIn("Node", rendered)
        self.assertNotIn("beads", rendered.lower())
        self.assertNotIn(" jj", rendered.lower())

    def test_runtime_python_packages_are_installed_without_test_flag(self) -> None:
        planned = set(install_dependencies.planned_python_requirements())
        expected = {
            f"{name}{requirement['specifier']}"
            for name, requirement in dependencies.RUNTIME_PYTHON_REQUIREMENTS.items()
        }
        self.assertEqual(planned, expected)


class DependencyRoutingTests(unittest.TestCase):
    def test_setup_maps_host_focused_tests_without_cross_dependency(self) -> None:
        parser = setup.build_parser()
        codex = parser.parse_args(["--test", "--codex"])
        omp = parser.parse_args(["--test", "--omp"])
        standard = parser.parse_args(["--test"])
        self.assertEqual(setup.install_verification_profile(
            parser.parse_args(["--test-and-install", "--codex"])
        ), "codex")
        self.assertEqual(setup.install_verification_profile(
            parser.parse_args(["--test-and-install", "--omp"])
        ), "omp")
        self.assertEqual(tuple(name for name in dependencies.HARNESS_ORDER if getattr(codex, name)), ("codex",))
        self.assertEqual(tuple(name for name in dependencies.HARNESS_ORDER if getattr(omp, name)), ("omp",))
        self.assertFalse(any(getattr(standard, name) for name in dependencies.HARNESS_ORDER))

    def test_codex_verification_plan_contains_no_node_step(self) -> None:
        steps = verify_all.verification_steps(profile="codex")
        self.assertFalse(any(step.include_node for step in steps))
        self.assertFalse(
            any("node" in str(part).lower() for step in steps for part in step.command)
        )

    def test_omp_verification_plan_marks_node_steps(self) -> None:
        with mock.patch.object(
            dependencies,
            "command_with_node_runtime",
            side_effect=dependencies.DependencyError("not installed"),
        ), mock.patch.object(verify_all.shutil, "which", return_value=None):
            steps = verify_all.verification_steps(profile="omp", require_node=True)
        self.assertTrue(any(step.include_node for step in steps))
        self.assertIn("OMP extension JavaScript syntax", [step.name for step in steps])

    def test_install_blocks_before_reading_or_writing_when_preflight_fails(self) -> None:
        args = install.build_parser().parse_args(
            ["install", "--scope", "project", "--root", str(ROOT), "--codex", "--dry-run"]
        )
        with (
            mock.patch.object(
                install,
                "run_dependency_preflight",
                side_effect=install.InstallError("dependency preflight failed"),
            ),
            mock.patch.object(install, "load_existing_install") as load_existing,
        ):
            with self.assertRaisesRegex(install.InstallError, "dependency preflight failed"):
                install.install(args)
        load_existing.assert_not_called()

    def test_setup_dependency_action_forwards_host_and_test_scope(self) -> None:
        captured: list[list[str]] = []

        def fake_main(values: list[str]) -> int:
            captured.append(list(values))
            return 0

        with mock.patch.object(setup.dependency_installer, "main", side_effect=fake_main):
            with redirect_stdout(io.StringIO()):
                code = setup.main(
                    [
                        "--install-dependencies",
                        "--codex",
                        "--include-test-dependencies",
                        "--dry-run",
                        "--yes",
                    ]
                )
        self.assertEqual(code, 0)
        self.assertEqual(
            captured,
            [["--codex", "--include-test-dependencies", "--yes", "--dry-run"]],
        )


    def test_automatic_install_verification_profiles_are_host_scoped(self) -> None:
        def args(**selected: bool):
            values = {name: False for name in dependencies.HARNESS_ORDER}
            values.update(selected)
            return type("Args", (), values)()

        self.assertEqual(install.automatic_verification_profile(args(codex=True)), "codex")
        self.assertEqual(install.automatic_verification_profile(args(omp=True)), "omp")
        self.assertEqual(install.automatic_verification_profile(args(claude=True)), "fast")
        self.assertEqual(
            install.automatic_verification_profile(args(codex=True, omp=True)),
            "standard",
        )

    def test_readme_and_install_guide_document_opt_in_bootstrap(self) -> None:
        combined = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in ("README.md", "docs/INSTALL.md")
        )
        for command in (
            "tools/setup.py --check-dependencies --codex",
            "tools/setup.py --install-dependencies --codex",
            "tools/setup.py --install-dependencies --omp",
        ):
            self.assertIn(command, combined)
        self.assertIn("does not require Node", combined)
        self.assertIn("Python 3.11", combined)

    def test_omp_runtime_inventory_contains_new_local_imports(self) -> None:
        inventory = set(install.OMP_EXTENSION_RUNTIME_FILES)
        self.assertIn("dependencies.py", inventory)
        self.assertIn("runtime_requirements.py", inventory)

    def test_omp_runtime_inventory_closes_imports_for_every_copied_python_file(self) -> None:
        inventory = set(install.OMP_EXTENSION_RUNTIME_FILES)
        tools = ROOT / "tools"
        missing: dict[str, list[str]] = {}
        for relative in sorted(inventory):
            if not relative.endswith(".py"):
                continue
            path = tools / relative
            tree = source_ast(path)
            required: set[str] = set()
            for node in __import__("ast").walk(tree):
                if isinstance(node, __import__("ast").Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, __import__("ast").ImportFrom) and node.level == 0 and node.module:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    parts = name.split(".")
                    top_level = tools / f"{parts[0]}.py"
                    nested = tools.joinpath(*parts).with_suffix(".py")
                    if nested.is_file():
                        required.add(nested.relative_to(tools).as_posix())
                    elif top_level.is_file():
                        required.add(top_level.relative_to(tools).as_posix())
            absent = sorted(required - inventory)
            if absent:
                missing[relative] = absent
        self.assertEqual(missing, {})


if __name__ == "__main__":
    unittest.main()


from tests._test_profiles import load_profiled_tests as load_tests
