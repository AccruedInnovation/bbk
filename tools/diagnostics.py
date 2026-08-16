"""Small, deterministic M3 diagnostic helpers.

Diagnostics keep the semantic result (what the operation established) separate
from its mechanical envelope (whether the operation was admitted and cleaned
up).  They are deliberately data-only; no operation or effect is performed.
"""
from __future__ import annotations

from typing import Any, Mapping

IMMEDIATE_STOP_CLASSES = frozenset({
    "WRONG_SUBJECT",
    "CONTRADICTORY_EVIDENCE",
    "INTEGRITY_FAILURE",
    "UNOWNED_WRITE",
    "AMBIGUOUS_IRREVERSIBLE_EFFECT",
    "CROSS_BOUNDARY_EFFECT",
})


def typed_diagnostic(
    *,
    code: str,
    subject: str,
    semantic_status: str = "NOT_RUN",
    semantic_value: Any = None,
    mechanical_status: str = "PASS",
    effects_observed: str = "NONE",
    cleanup: str = "COMPLETE",
    message: str = "",
    claims: tuple[str, ...] = (),
    not_established: tuple[str, ...] = (),
    diagnostic_class: str = "MECHANICAL",
    immediate_stop: bool = False,
) -> dict[str, Any]:
    """Return a schema-shaped diagnostic without claiming validation."""
    return {
        "schema": "bbk.diagnostic.v1",
        "code": code,
        "class": diagnostic_class,
        "subject": subject,
        "message": message,
        "semantic_result": {
            "status": semantic_status,
            "value": semantic_value,
            "code": None,
            "message": None,
        },
        "mechanical_envelope": {
            "status": mechanical_status,
            "effects_observed": effects_observed,
            "cleanup": cleanup,
            "code": None,
            "message": None,
        },
        "claims": {"established": list(claims), "not_established": list(not_established)},
        "immediate_stop": immediate_stop,
        "prohibited_claims": ["independent validation", "candidate acceptance", "release"],
    }


def classify_failure(code: str, *, subject: str, message: str = "") -> dict[str, Any]:
    """Classify a failure and make immediate-stop behavior explicit."""
    normalized = str(code).upper()
    stop = normalized in IMMEDIATE_STOP_CLASSES
    return typed_diagnostic(
        code=normalized,
        subject=subject,
        message=message,
        diagnostic_class="IMMEDIATE_STOP" if stop else "MECHANICAL",
        mechanical_status="BLOCKED" if stop else "FAIL",
        immediate_stop=stop,
        not_established=("operation result",) if stop else (),
    )


def static_dynamic_claim(*, static_inventory: str, dynamic_execution: str) -> dict[str, Any]:
    """Return explicit static/dynamic limits; inventory never implies execution."""
    static_status = str(static_inventory).upper()
    dynamic_status = str(dynamic_execution).upper()
    dynamic_established = dynamic_status == "PASS"
    return typed_diagnostic(
        code="STATIC_DYNAMIC_CLAIM",
        subject="repository",
        semantic_status="PASS" if static_status == "PASS" else "FAIL",
        semantic_value={"static_inventory": static_status, "dynamic_execution": dynamic_status},
        mechanical_status="PASS",
        diagnostic_class="SEMANTIC",
        claims=("static inventory passed",) if static_status == "PASS" else (),
        not_established=() if dynamic_established else ("dynamic execution",),
    )

