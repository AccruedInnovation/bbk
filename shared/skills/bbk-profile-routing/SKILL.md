---
name: bbk-profile-routing
description: Discover installed language and domain profiles, then resolve and dispatch only applicable procedures, lenses, inventories, evidence adapters, and gates.
requires_prompt_modules: ["bbk-prompt-profile-qualification"]
standalone_prompt_modules: ["bbk-prompt-profile-dispatch"]
---


# BBK Profile Routing

## Installed-profile registry

> Apply the already embedded `bbk-prompt-profile-qualification` module here.

## Discover the active profiles

<!-- BBK prompt module bbk-prompt-profile-dispatch: expanded from canonical source -->

### Installed-profile discovery and capability dispatch

Resolve the exact managed language or domain profile, focused router procedures, and typed capability entrypoints without treating ambient files or tool access as qualification.

- `PROFILE.REGISTRY` — Read bbk-installed-profiles as the installation-bound catalogue and confirm live discovery with bbk --json profile list when required. Project profile paths and BBK_PROFILE_PATH may alter the live set or precedence; a stray similarly named skill or executable is not proof of managed availability.
- `PROFILE.ELIGIBILITY` — Use only profile packages whose verification and compatibility status are PASS unless a bounded investigation explicitly permits otherwise.
- `PROFILE.MATCH` — Match the exact language or domain, task, changed surface, runtime or toolchain context, and assurance need. Select the smallest applicable profile set rather than loading every installed specialist pack.
- `PROFILE.ROUTER` — Load the selected profile router from the router entry in PROFILE.json.skills. Let that router select focused Worker, Reviewer, gate, evidence, lens, inventory, or projection procedures; do not infer applicability from a skill name alone.
- `PROFILE.LOCK` — Resolve and bind profile identity, version, source digest, selected components, effective digest or lock, capability status, unavailable-tool policy, and known qualification limits before relying on profile outputs.
- `PROFILE.DISPATCH_PROTOCOL` — Treat capability declarations and executable entrypoints separately. Only capabilities declaring dispatch_protocol bbk.profile-capability.v1 may be centrally dispatched; capability fields name entrypoints, and entrypoints supply argv arrays. Never execute a path copied from a capability field.
- `PROFILE.REQUEST_RESULT` — Use the core-owned typed request/result protocol, bind exact content digests, use request-package-relative inputs, keep the subject read-only, and return a typed result. Do not reinterpret runTools as mutation or network authority.
- `PROFILE.AUTHORITY_SPLIT` — Profiles may contribute structure or slice projections, State–Decision–Effect inventories, review lenses and context, gate recipes, or EvidenceReceipt adapters. Generic BBK remains authoritative for schemas, assertion ownership, context completeness, evidence eligibility, aggregation, findings, dispositions, locks, candidate identity, and authority.
- `PROFILE.UNAVAILABLE_PROTOCOL` — When a required profile or capability is missing, incompatible, unverifiable, or unavailable, return the exact typed capability blocker. Do not silently substitute generic guidance while claiming profile-qualified evidence; legacy declarations without the typed protocol remain manually usable but are not centrally dispatched.

<!-- End BBK prompt module bbk-prompt-profile-dispatch -->

## Capability dispatch

> Apply the `PROFILE.DISPATCH_PROTOCOL`, `PROFILE.REQUEST_RESULT`, `PROFILE.AUTHORITY_SPLIT`, and `PROFILE.UNAVAILABLE_PROTOCOL` clauses above.
