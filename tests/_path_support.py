"""Cross-platform path assertions for BBK tests.

Host filesystem paths have two different contracts in the test suite:

* **physical identity** — long/8.3 Windows spellings, case variants, symlinks,
  and junctions may identify the same object; use :func:`assert_same_path`;
* **serialized spelling** — portable relative paths and documented output may
  deliberately require exact slash/case/text form; use ordinary string
  assertions (or :func:`assert_exact_path_text`) and make that intent explicit.

Do not compare host paths with raw ``Path``/string equality.  Windows temporary
roots are especially likely to appear through both a long name and an 8.3
alias.  The helpers prefer ``os.path.samefile`` for existing objects and fall
back to BBK's tested canonical-path algorithm for planned or missing leaves.
"""
from __future__ import annotations

import ast
import os
import sys
import unittest
from pathlib import Path
from typing import Iterable, Sequence, TypeAlias

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from path_compat import canonical_path_text, path_key, same_path

PathValue: TypeAlias = str | os.PathLike[str]

# These are path-bearing fields whose values describe native filesystem
# locations rather than portable package-relative names.
PHYSICAL_PATH_FIELDS = frozenset(
    {
        "binding_path",
        "manifest_path",
        "omp_agents",
        "package_root",
        "project_root",
        "routing_program",
        "state_path",
    }
)
PHYSICAL_PATH_LABELS = frozenset(
    {
        "Agents",
        "Binding",
        "Manifest",
        "Package",
        "Project",
        "Root",
        "Router",
        "State",
    }
)
RAW_ASSERTION_ESCAPE = "BBK_TEST_ALLOW_RAW_PATH_IDENTITY"


def _path_text(value: PathValue) -> str:
    return os.fspath(value)


def paths_identify_same(left: PathValue, right: PathValue) -> bool:
    """Return whether two native-host spellings identify one destination.

    ``samefile`` gives an implementation-independent file-identity check when
    both objects exist.  The canonical-key fallback supports installation plans
    and notification paths whose final leaf may not exist yet.
    """
    left_text = _path_text(left)
    right_text = _path_text(right)
    try:
        if os.path.exists(left_text) and os.path.exists(right_text):
            return os.path.samefile(left_text, right_text)
    except (OSError, ValueError):
        pass
    return same_path(left_text, right_text)


def path_identity_key(value: PathValue) -> str:
    """Return BBK's canonical native-host identity key for dictionaries/sets."""
    return path_key(value)


def path_is_within(candidate: PathValue, root: PathValue) -> bool:
    """Return whether *candidate* identifies *root* or one of its descendants."""
    candidate_key = path_key(candidate).rstrip("/")
    root_key = path_key(root).rstrip("/")
    return candidate_key == root_key or candidate_key.startswith(root_key + "/")


def _diagnostic(value: PathValue) -> str:
    text = _path_text(value)
    try:
        exists = os.path.exists(text)
    except (OSError, ValueError):
        exists = False
    try:
        canonical = canonical_path_text(text)
    except (OSError, ValueError) as exc:
        canonical = f"<canonicalization failed: {exc}>"
    try:
        key = path_key(text)
    except (OSError, ValueError) as exc:
        key = f"<identity key failed: {exc}>"
    return f"raw={text!r}, canonical={canonical!r}, key={key!r}, exists={exists}"


def assert_same_path(
    case: unittest.TestCase,
    actual: PathValue,
    expected: PathValue,
    msg: str | None = None,
) -> None:
    """Assert physical filesystem identity with alias-aware diagnostics."""
    if paths_identify_same(actual, expected):
        return
    detail = (
        msg + ": " if msg else ""
    ) + f"paths identify different destinations\nactual:   {_diagnostic(actual)}\nexpected: {_diagnostic(expected)}"
    case.fail(detail)


def assert_different_path(
    case: unittest.TestCase,
    left: PathValue,
    right: PathValue,
    msg: str | None = None,
) -> None:
    """Assert that two spellings do not identify the same filesystem object."""
    if not paths_identify_same(left, right):
        return
    detail = (
        msg + ": " if msg else ""
    ) + f"paths unexpectedly identify the same destination\nleft:  {_diagnostic(left)}\nright: {_diagnostic(right)}"
    case.fail(detail)


def assert_same_path_sequence(
    case: unittest.TestCase,
    actual: Sequence[PathValue],
    expected: Sequence[PathValue],
    msg: str | None = None,
) -> None:
    """Assert ordered physical identity for two path sequences."""
    case.assertEqual(
        len(actual),
        len(expected),
        (msg + ": " if msg else "")
        + f"path sequence lengths differ: {len(actual)} != {len(expected)}",
    )
    for index, (actual_item, expected_item) in enumerate(zip(actual, expected, strict=True)):
        assert_same_path(
            case,
            actual_item,
            expected_item,
            (msg + ": " if msg else "") + f"path sequence item {index}",
        )


def assert_no_path_within(
    case: unittest.TestCase,
    candidates: Iterable[PathValue],
    root: PathValue,
    msg: str | None = None,
) -> None:
    """Assert that no candidate identifies *root* or one of its descendants."""
    offending = [value for value in candidates if path_is_within(value, root)]
    if not offending:
        return
    detail = (
        msg + ": " if msg else ""
    ) + f"paths unexpectedly fall within {_diagnostic(root)}: {[os.fspath(value) for value in offending]!r}"
    case.fail(detail)


def labeled_path_values(messages: Iterable[str], field: str) -> list[str]:
    """Extract values from ``Field: <native path>`` notification lines."""
    prefix = f"{field}: "
    return [
        line[len(prefix) :]
        for message in messages
        for line in str(message).splitlines()
        if line.startswith(prefix)
    ]


def assert_labeled_path(
    case: unittest.TestCase,
    messages: Iterable[str],
    field: str,
    expected: PathValue,
    *,
    required_text: str | None = None,
) -> None:
    """Assert that one matching notification line identifies *expected*."""
    message_list = [str(message) for message in messages]
    candidates = [
        value
        for message in message_list
        if required_text is None or required_text in message
        for value in labeled_path_values([message], field)
    ]
    if any(paths_identify_same(value, expected) for value in candidates):
        return
    case.fail(
        f"{field} did not identify the expected destination\n"
        f"expected: {_diagnostic(expected)}\n"
        f"candidates: {[ _diagnostic(value) for value in candidates ]!r}\n"
        f"messages: {message_list!r}"
    )







def command_arguments_after_launcher(
    command: Sequence[PathValue],
    launcher: PathValue,
) -> list[str]:
    """Return logical arguments after *launcher* in a native command vector.

    On Windows a ``.cmd`` or ``.bat`` launcher is represented as
    ``cmd.exe /d /s /c <launcher> ...``. Tests must assert the logical launcher
    and arguments rather than assuming the launcher is always ``argv[0]``.
    """
    for index, value in enumerate(command):
        try:
            if paths_identify_same(value, launcher):
                return [os.fspath(item) for item in command[index + 1 :]]
        except (OSError, TypeError, ValueError):
            continue
    rendered = [os.fspath(item) for item in command]
    raise AssertionError(
        "command does not invoke the expected launcher\n"
        f"launcher: {_diagnostic(launcher)}\n"
        f"command: {rendered!r}"
    )


def assert_command_invokes(
    case: unittest.TestCase,
    command: Sequence[PathValue],
    launcher: PathValue,
    expected_arguments: Sequence[str],
    msg: str | None = None,
) -> None:
    try:
        actual = command_arguments_after_launcher(command, launcher)
    except AssertionError as exc:
        case.fail((msg + ": " if msg else "") + str(exc))
        return
    case.assertEqual(list(expected_arguments), actual, msg)


# Historical test refactors used this name; keep it as the public sequence helper.
assert_path_sequence_equal = assert_same_path_sequence


# OMP notifications are the first consumer, so retain the specific public name
# alongside the generic labelled-line helper.
assert_notification_path = assert_labeled_path


def assert_exact_path_text(
    case: unittest.TestCase,
    actual: PathValue,
    expected: PathValue,
    msg: str | None = None,
) -> None:
    """Assert exact path spelling when spelling itself is the public contract."""
    case.assertEqual(_path_text(actual), _path_text(expected), msg)


def create_symlink_or_skip(
    case: unittest.TestCase,
    link: Path,
    target: Path,
    *,
    target_is_directory: bool = False,
) -> None:
    """Create a real symlink for an integration test or skip it cleanly.

    ``os.symlink`` can be present while the current Windows process still lacks
    ``SeCreateSymbolicLinkPrivilege`` (WinError 1314).  Filesystems and sandbox
    policies can also reject links even on otherwise supported hosts.  Tests
    that specifically require a real filesystem link must therefore probe the
    operation rather than treating API presence as capability.

    Deterministic unit coverage of BBK's link-rejection logic should not depend
    on this helper; use it only for the additional host integration check.
    """
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (NotImplementedError, OSError) as exc:
        case.skipTest(f"symbolic links unavailable to this test process: {exc}")


def _subscript_key(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Subscript):
        return None
    value = node.slice
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


def _call_leaf(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _joined_text(node: ast.AST) -> str:
    return "".join(
        value.value
        for value in ast.walk(node)
        if isinstance(value, ast.Constant) and isinstance(value.value, str)
    )


def find_unsafe_path_assertions(path: Path) -> list[str]:
    """Find raw path-identity assertions that should use this module.

    This is intentionally a narrow guard, not a general Python linter.  It
    catches the recurring BBK failure modes: direct equality around resolved
    host paths, direct calls to path identity primitives, physical-path JSON
    fields, and interpolation of labelled native paths into notification text.
    Exact portable-relative serialization assertions remain valid.
    """
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(path))
    findings: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "path_compat":
            imported = {alias.name for alias in node.names}
            if imported & {"canonical_path_text", "path_key", "same_path"}:
                findings.append(
                    f"{path.name}:{node.lineno}: imports path identity primitives directly; "
                    "use tests._path_support"
                )
            continue
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        assertion = node.func.attr
        if assertion not in {
            "assertEqual",
            "assertNotEqual",
            "assertTrue",
            "assertFalse",
            "assertIn",
            "assertNotIn",
        }:
            continue
        line = lines[node.lineno - 1] if 0 < node.lineno <= len(lines) else ""
        previous = lines[node.lineno - 2] if node.lineno > 1 else ""
        if RAW_ASSERTION_ESCAPE in line or RAW_ASSERTION_ESCAPE in previous:
            continue

        descendants = list(ast.walk(node))
        call_names = {
            name
            for child in descendants
            if isinstance(child, ast.Call)
            for name in [_call_leaf(child)]
            if name is not None
        }
        subscript_keys = {
            key
            for child in descendants
            for key in [_subscript_key(child)]
            if key is not None
        }
        resolved_host_path = bool(call_names & {"Path", "absolute", "canonical_path_text", "path_key", "resolve", "same_path"})
        physical_field = bool(subscript_keys & PHYSICAL_PATH_FIELDS)
        two_path_fields = sum(key == "path" for key in subscript_keys) >= 1 and sum(
            1 for child in descendants if _subscript_key(child) == "path"
        ) >= 2
        labelled_path_text = any(
            f"{label}: " in _joined_text(node) for label in PHYSICAL_PATH_LABELS
        )

        if assertion in {"assertEqual", "assertNotEqual"} and (
            resolved_host_path or physical_field or two_path_fields
        ):
            findings.append(
                f"{path.name}:{node.lineno}: {assertion} performs raw physical-path comparison"
            )
        elif assertion in {"assertTrue", "assertFalse", "assertIn", "assertNotIn"} and (
            call_names & {"path_key", "same_path"} or labelled_path_text
        ):
            findings.append(
                f"{path.name}:{node.lineno}: {assertion} performs raw physical-path/text comparison"
            )
    return findings


def _caught_exception_names(handler: ast.ExceptHandler) -> set[str]:
    value = handler.type
    if value is None:
        return {"BaseException"}
    if isinstance(value, ast.Name):
        return {value.id}
    if isinstance(value, ast.Attribute):
        return {value.attr}
    if isinstance(value, ast.Tuple):
        result: set[str] = set()
        for item in value.elts:
            if isinstance(item, ast.Name):
                result.add(item.id)
            elif isinstance(item, ast.Attribute):
                result.add(item.attr)
        return result
    return set()


def _is_symlink_creation_call(node: ast.Call) -> bool:
    function = node.func
    if not isinstance(function, ast.Attribute):
        return False
    if function.attr == "symlink_to":
        return True
    return (
        function.attr == "symlink"
        and isinstance(function.value, ast.Name)
        and function.value.id == "os"
    )


def find_unguarded_symlink_creations(path: Path) -> list[str]:
    """Find test symlink creation that assumes API presence implies capability.

    Windows exposes ``os.symlink`` even when the current process lacks the
    privilege needed to call it.  Real-link integration fixtures must therefore
    be inside a capability guard that catches ``OSError`` (or a broader
    exception), or go through :func:`create_symlink_or_skip`.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings: list[str] = []
    capability_exceptions = {
        "BaseException",
        "Exception",
        "NotImplementedError",
        "OSError",
        "PermissionError",
    }

    def visit(node: ast.AST, *, guarded: bool = False) -> None:
        if isinstance(node, ast.Try):
            catches_capability_error = any(
                _caught_exception_names(handler) & capability_exceptions
                for handler in node.handlers
            )
            for child in node.body:
                visit(child, guarded=guarded or catches_capability_error)
            for handler in node.handlers:
                for child in handler.body:
                    visit(child, guarded=guarded)
            for child in node.orelse:
                visit(child, guarded=guarded)
            for child in node.finalbody:
                visit(child, guarded=guarded)
            return
        if isinstance(node, ast.Call) and _is_symlink_creation_call(node) and not guarded:
            findings.append(
                f"{path.name}:{node.lineno}: symlink fixture creation is not capability-guarded; "
                "use create_symlink_or_skip or catch OSError"
            )
        for child in ast.iter_child_nodes(node):
            visit(child, guarded=guarded)

    visit(tree)
    return findings
