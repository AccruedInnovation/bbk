---
name: bbk-profile-routing
description: Discover installed language and domain profiles, then resolve and dispatch only applicable procedures, lenses, inventories, evidence adapters, and gates.
---

# BBK Profile Routing

## Installed-profile registry

Read `bbk-installed-profiles` before resolving profile work. Treat that generated skill—and the machine-readable `effective-language-profiles.json` beside the installation manifest—as the inventory of profiles managed by this BBK installation.

1. Match the exact changed surface and runtime/toolchain context to the smallest applicable installed profile.
2. Load the profile router skill first; let it select focused worker, reviewer, gate, and evidence modules rather than loading the entire profile corpus.
3. Preserve the profile identity, version, router skill, capability status, effective digest or lock, and unavailable-tool dispositions in downstream context edges.
4. An unlisted profile is unavailable to this installation. A stray similarly named skill or executable elsewhere on the host is not proof of managed profile availability.
5. A profile adds procedure and evidence expectations only. It cannot grant tools or effects, broaden scope, waive generic BBK rules, reduce assurance, declare a pass, or authorize release.

Repository-declared policy wins within its legitimate scope. Select procedures by role, task, assurance, changed surface, fit, structure, slice, State–Decision–Effect, and review inputs. Ordinary work must not fan out every specialist. Required unavailable capability blocks; optional unavailable capability advises.

## Discover the active profiles

1. Consult `bbk-installed-profiles` for the installation-bound catalogue, then confirm current discovery with `bbk --json profile list`. Project profile paths and `BBK_PROFILE_PATH` may change the live set or precedence.
2. Consider only packages whose verification and compatibility status are `PASS`, unless bounded investigation explicitly permits otherwise.
3. Match the repository language or domain, exact task, changed surface, and assurance need. Select one profile per applicable language/domain concern rather than loading every installed profile.
4. Load the selected profile's router skill from the `router` entry in `PROFILE.json.skills`. The router chooses the smallest focused skill set; do not infer procedure applicability from a skill name alone.
5. Resolve and lock the exact profile identity, version, source digest, selected components, and effective digest before relying on its outputs.

## Capability dispatch

Treat capability declarations and entrypoints separately. Only capabilities declaring `dispatch_protocol: bbk.profile-capability.v1` may be centrally dispatched. Capability fields reference entrypoint **names**; `entrypoints` supplies the argv arrays. Never execute a path copied from a capability field.

Use the core-owned request/result protocol. Bind exact content digests, use request-package-relative inputs, keep the subject read-only, and return a typed result. Do not reinterpret `runTools` as mutation or network authority.

Profiles may contribute ImplementationStructure and ExecutionSlice projections, State–Decision–Effect projections and inventories, logical review-lens procedures, review context, gate recipes, or EvidenceReceipt v2 adapters. Generic BBK remains authoritative for schemas, assertion ownership, context completeness, evidence eligibility, aggregation, findings, dispositions, locks, and candidate identity. Unsupported lenses remain visible and must be handled by another qualified method or explicitly dispositioned.

If a required profile or capability is missing, incompatible, unverifiable, or unavailable, return `BLOCKED`; do not silently fall back to generic guidance while claiming profile-qualified evidence. Alpha.7 declarations without the typed protocol and earlier profiles remain usable but are not automatically dispatched.
