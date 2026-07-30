# Language and Toolchain Profiles

BBK language/domain profiles are optional, independently versioned procedure packs. They compose with a stable role constitution, task-kind profile, exact subject, and AssuranceContract. They are not role families, semantic authorities, or permission bundles.

```text
role constitution
+ task-kind profile
+ exact fit/structure/slice/work context
+ language/domain profile
+ assurance and review manifests
= effective invocation
```

A profile may add repository/toolchain detection, focused procedures, deterministic gate recipes, actual-structure inventory, logical review-lens procedures, context selection, and evidence adaptation. It may not grant tools or effects, expand scope, reduce assurance, close findings, or declare generic BBK, product, acceptance, compliance, or release success.

## Discovery, verification, and locking

BBK searches explicit `--profile-dir` paths, `BBK_PROFILE_PATH`, project profile locations, the user BBK data root, and bundled profiles in precedence order. A manifested package must verify before normal use.

```bash
bbk profile list
bbk profile inspect --id rust
bbk profile resolve --id rust --role worker --task-profile implementation --assurance-tier routine
```

Resolution records selected components and a content-addressed profile lock. A changed profile can invalidate profile-dependent evidence without changing candidate bytes.

## Alpha.8 typed capability dispatch

Alpha.8 distinguishes capability declaration from executable integration. A profile participates in automatic State–Decision–Effect or Review Assurance dispatch only when the capability declares:

```json
"dispatch_protocol": "bbk.profile-capability.v1"
```

Capability fields such as `projection_entrypoint`, `context_entrypoint`, and `review_entrypoint` contain **entrypoint names**, not file paths. Those names resolve through `entrypoints`, whose values are argv arrays.

The six operations are:

```text
state-effect
state-effect-inventory
state-effect-review
review-context
review-lens
evidence-adapter
```

Every operation receives one core-owned `bbk.profile-capability-request.v1` file. Its input paths are relative to the request package; the actual source root is available through `BBK_PROFILE_SOURCE_ROOT`. The profile returns one `bbk.profile-capability-result.v1` bound to the exact request digest.

Dispatch is read-only toward the subject. `--run-tools` permits only profile-qualified read-only inspection or evidence tools; it never grants mutation or external effects. Generic BBK validation, assertion sufficiency, aggregation, finding closure, and authority remain controlling.

Use `bbk profile dispatch` for one explicit operation. `bbk profile resolve` centrally dispatches the smallest applicable set from exact supplied SDE, assurance, review-manifest, and evidence inputs. Unsupported logical lenses remain explicit for another profile or generic reviewer; they are not silently skipped.

Profiles written for alpha.7 without the typed protocol remain valid as `legacy-declared`. Alpha.2 profiles remain valid under their earlier capability state. Neither gains automatic capability by implication.

## Maturity

Profiles may describe maturity as `review-only`, `worker-capable`, `assurance-capable`, `comprehensive-alpha`, or `comprehensive`. Maturity is descriptive; the validated capability and exact dispatch protocol determine what BBK may invoke.
