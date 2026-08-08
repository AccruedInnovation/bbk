#!/usr/bin/env python3
"""Late-bound effective profile/environment admission receipts."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any, Mapping, Sequence


class RuntimeIdentityError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code; self.message = message
        super().__init__(f"{code}: {message}")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def resolve_effective_profile(
    constraints: Mapping[str, Any], effective_profile: Mapping[str, Any], environment_identity: Mapping[str, Any],
    *, registry_revision: str, selector: str | None = None, exact_digest_required: bool = False,
    exact_digest_reason: str | None = None, observed_at: str | None = None,
) -> dict[str, Any]:
    required_capabilities={str(item) for item in constraints.get('required_capabilities') or []}
    required_gates={str(item) for item in constraints.get('required_gates') or []}
    allowed_families={str(item) for item in constraints.get('allowed_families') or []}
    actual_capabilities={str(item) for item in effective_profile.get('capabilities') or []}
    actual_gates={str(item) for item in effective_profile.get('gates') or []}
    family=str(effective_profile.get('family') or '')
    missing_caps=sorted(required_capabilities-actual_capabilities)
    missing_gates=sorted(required_gates-actual_gates)
    family_ok=not allowed_families or family in allowed_families
    effective_sha=str(effective_profile.get('sha256') or _digest(effective_profile))
    predicted=str(constraints.get('predicted_sha256') or '')
    digest_deviation=bool(predicted and predicted != effective_sha)
    exact_ok=not exact_digest_required or not predicted or predicted==effective_sha
    status='PASS' if not missing_caps and not missing_gates and family_ok and exact_ok else 'FAIL'
    deviations=[]
    if digest_deviation:
        deviations.append({'kind':'EFFECTIVE_DIGEST_DIFFERENCE','predicted':predicted,'observed':effective_sha,'semantic_constraints_satisfied':status=='PASS'})
    if not family_ok: deviations.append({'kind':'FAMILY_NOT_ALLOWED','observed':family,'allowed':sorted(allowed_families)})
    if missing_caps: deviations.append({'kind':'MISSING_CAPABILITIES','values':missing_caps})
    if missing_gates: deviations.append({'kind':'MISSING_GATES','values':missing_gates})
    if exact_digest_required and not exact_ok: deviations.append({'kind':'EXACT_DIGEST_REQUIRED','reason':exact_digest_reason})
    now=observed_at or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
    return {
        'schema':'bbk.effective-profile-receipt.v1','status':status,
        'selector':selector or str(constraints.get('selector') or 'default'),
        'registry_revision':registry_revision,
        'required_capabilities':sorted(required_capabilities),'required_gates':sorted(required_gates),'allowed_families':sorted(allowed_families),
        'resolved_profile_id':str(effective_profile.get('id') or effective_profile.get('profile_id') or 'unknown'),
        'resolved_profile_version':str(effective_profile.get('version') or 'unknown'),
        'resolved_profile_sha256':effective_sha,
        'environment_identity':dict(environment_identity),
        'constraint_result':status,
        'satisfied_capabilities':sorted(required_capabilities & actual_capabilities),
        'satisfied_gates':sorted(required_gates & actual_gates),
        'deviations':deviations,
        'semantic_equivalence':'EQUIVALENT' if status=='PASS' else 'NOT_EQUIVALENT',
        'planning_reopen_required':status!='PASS',
        'exact_digest_required':exact_digest_required,
        'exact_digest_reason':exact_digest_reason,
        'invalidation_keys':[f'registry:{registry_revision}',f'constraints:{_digest(constraints)}',f'profile:{effective_sha}',f'environment:{_digest(environment_identity)}'],
        'observed_at':now,
    }
