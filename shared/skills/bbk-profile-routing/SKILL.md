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

- `PROFILE.REGISTRY` — Use `bbk-installed-profiles` as the installation-bound catalog; confirm live state with `bbk --json profile list` when needed. Project paths and `BBK_PROFILE_PATH` may change membership/precedence; a same-named skill or executable does not prove managed availability.
- `PROFILE.ELIGIBILITY` — Use only profile packages with verification and compatibility status PASS, unless a bounded investigation expressly allows otherwise.
- `PROFILE.MATCH` — Match the exact language/domain, task, changed surface, runtime/toolchain context, and assurance need; select the smallest applicable profile set, not every installed specialist pack.
- `PROFILE.ROUTER` — Load the selected router from `PROFILE.json.skills`. Let it choose focused Worker, Reviewer, gate, evidence, lens, inventory, or projection procedures; never infer applicability from a skill name.
- `PROFILE.LOCK` — Before reliance, bind profile ID, version, source digest, selected components, effective digest/lock, capability status, unavailable-tool policy, and known qualification limits.
- `PROFILE.DISPATCH_PROTOCOL` — Keep capability declarations separate from entrypoints. Centrally dispatch only capabilities with `dispatch_protocol` `bbk.profile-capability.v1`; capability fields name entrypoints, and entrypoints provide argv arrays. Never execute a path copied from a capability field.
- `PROFILE.REQUEST_RESULT` — Use the core typed request/result protocol, exact content digests, request-package-relative inputs, read-only subject, and typed result. `runTools` grants neither mutation nor network authority.
- `PROFILE.AUTHORITY_SPLIT` — Profiles may supply structure/slice projections, State–Decision–Effect inventories, review lenses/context, gate recipes, or EvidenceReceipt adapters. Generic BBK owns schemas, assertion ownership, context completeness, evidence eligibility, aggregation, findings, dispositions, locks, candidate identity, and authority.
- `PROFILE.UNAVAILABLE_PROTOCOL` — When a required profile/capability is missing, incompatible, unverifiable, or unavailable, return the exact typed blocker. Do not claim profile-qualified evidence from generic guidance; legacy declarations without the typed protocol may be used manually but are not centrally dispatched.

<!-- End BBK prompt module bbk-prompt-profile-dispatch -->

## Capability dispatch

> Apply the `PROFILE.DISPATCH_PROTOCOL`, `PROFILE.REQUEST_RESULT`, `PROFILE.AUTHORITY_SPLIT`, and `PROFILE.UNAVAILABLE_PROTOCOL` clauses above.
