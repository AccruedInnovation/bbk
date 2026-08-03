"""Deterministic BBK unittest profile selection.

The complete release suite remains available, while routine verification can
skip release-author self-tests and optional external-schema cross-checks.
Selection is deliberately data-driven and operates on stable unittest IDs so
individual test modules remain readable and can still be invoked directly.
"""
from __future__ import annotations

import os
import unittest
from collections.abc import Iterable, Iterator

PROFILE_ENV = "BBK_TEST_PROFILE"
PROFILES = ("fast", "standard", "release")
DEFAULT_PROFILE = "release"

# These tests validate the test/release machinery itself or repeat an optional
# whole-package external-engine boundary. They remain part of release
# qualification but are not required for ordinary development/preinstall runs.
RELEASE_ONLY = frozenset(
    {
        "test_installation_portability.Alpha93VerificationReportingTests.test_runner_end_to_end_repeats_failure_and_error_at_the_end",
        "test_installation_portability.Alpha93VerificationReportingTests.test_runner_end_to_end_prints_clean_final_summary",
        "test_installation_portability.Alpha117GitRepositoryTests.test_pooled_runner_uses_bounded_multi_module_processes",
        "test_installation_portability.Alpha117GitRepositoryTests.test_batch_runner_uses_one_python_process_for_all_discovered_modules",
        "test_installation_portability.Alpha117GitRepositoryTests.test_test_runner_emits_suite_progress_and_quiet_heartbeat",
        "test_installation_portability.Alpha117GitRepositoryTests.test_parallel_runner_heartbeat_names_the_current_test",
        "test_installation_portability.Alpha117GitRepositoryTests.test_suite_children_cannot_read_the_developer_console",
        "test_installation_portability.Alpha117GitRepositoryTests.test_test_runner_survives_cp1252_console_and_non_utf8_child_bytes",
        "test_installation_portability.Alpha117GitRepositoryTests.test_output_stream_failure_terminates_child_before_capture_cleanup",
        "test_installation_portability.Alpha117GitRepositoryTests.test_windows_process_tree_cleanup_bounds_taskkill",
        "test_installation_portability.Alpha117GitRepositoryTests.test_capture_cleanup_retries_and_suppresses_windows_sharing_violation",
        "test_installation_portability.Alpha117GitRepositoryTests.test_ordered_verifier_survives_cp1252_console_with_unicode_child_output",
        "test_installation_portability.Alpha117GitRepositoryTests.test_install_verification_gate_survives_cp1252_console_mirroring",
        "test_contract_package_v1.ContractPackageV1Tests.test_declared_nullability_matches_role_contract_prose_and_schema",
        "test_contract_package_v1.ContractPackageV1Tests.test_representative_return_for_every_role_validates",
        "test_contract_package_v1.ContractPackageV1Tests.test_exact_role_contract_discriminators_reject_drift_for_every_role",
        "test_contract_package_v1.ContractPackageV1Tests.test_result_payload_is_closed_and_every_declared_field_is_required",
        "test_contract_package_v1.ContractPackageV1Tests.test_supplemental_enum_fields_are_exact_machine_discriminators",
        "test_contract_package_v1.ContractPackageV1Tests.test_all_supported_field_kinds_have_schema_valid_examples",
        "test_contract_package_v1.ContractPackageV1Tests.test_execution_contract_examples_validate_against_published_schemas",
        "test_prompt_module_package_v1.PromptModulePackageV1Tests.test_catalog_and_module_schemas_are_valid_draft_2020_12",
        "test_role_package_v4.SplitRolePackageV4Tests.test_published_draft_2020_12_schemas_validate_all_instances",
    }
)

# Fast verification intentionally covers canonical contracts, prompt/role
# compilation, assurance logic, and deterministic transformations. Real
# installer/Node/Git/platform boundaries remain in standard/release profiles.
FAST_MODULES = frozenset(
    {
        "test_assurance_state",
        "test_contract_package_v1",
        "test_prompt_module_package_v1",
        "test_role_package_v4",
    }
)


def normalize_test_id(test_id: str) -> str:
    """Return a stable ID independent of ``tests.`` package loading style."""
    value = str(test_id)
    return value[6:] if value.startswith("tests.") else value


def iter_tests(suite: unittest.TestSuite) -> Iterator[unittest.TestCase]:
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iter_tests(item)
        else:
            yield item


def selected(test_id: str, profile: str) -> bool:
    """Return whether *test_id* belongs to *profile*."""
    if profile not in PROFILES:
        raise ValueError(f"unknown BBK test profile: {profile}")
    normalized = normalize_test_id(test_id)
    if profile == "release":
        return True
    if normalized in RELEASE_ONLY:
        return False
    if profile == "standard":
        return True
    module = normalized.split(".", 1)[0]
    return module in FAST_MODULES


def filter_suite(
    suite: unittest.TestSuite,
    *,
    profile: str | None = None,
) -> unittest.TestSuite:
    """Flatten and deterministically filter a loaded suite."""
    active = profile or os.environ.get(PROFILE_ENV, DEFAULT_PROFILE)
    if active not in PROFILES:
        raise RuntimeError(
            f"{PROFILE_ENV} must be one of {', '.join(PROFILES)}; got {active!r}"
        )
    return unittest.TestSuite(
        test for test in iter_tests(suite) if selected(test.id(), active)
    )


def load_profiled_tests(
    loader: unittest.TestLoader,
    tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    """Standard ``load_tests`` hook shared by every public test module."""
    del loader, pattern
    return filter_suite(tests)


def profile_counts(test_ids: Iterable[str]) -> dict[str, int]:
    """Return deterministic inventory counts for diagnostics and tests."""
    values = list(test_ids)
    return {
        profile: sum(1 for test_id in values if selected(test_id, profile))
        for profile in PROFILES
    }
