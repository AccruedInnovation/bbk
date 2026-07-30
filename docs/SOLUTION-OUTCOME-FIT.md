# Solution–Outcome Fit

## Purpose

`SolutionOutcomeFit` prevents a requested artifact, technology, or implementation approach from silently becoming the problem definition. It preserves three distinct things:

1. what the user asked to build or change;
2. what actor-visible or operational result is actually needed;
3. why the proposed intervention is expected to cause that result.

The record is not an accusation that the user has an “XY problem.” It is a respectful, testable bridge between intent and intervention.

## Core chain

```text
requested intervention
  -> desired outcomes
  -> current/no-intervention baseline
  -> causal hypothesis and assumptions
  -> constraints and preferences
  -> alternatives and no-change comparison where material
  -> delivered-but-outcome-remains counterfactual
  -> fit disposition and authority
  -> structure, slices and work
  -> outcome-level evidence and observation
```

Artifact completion may be legitimate evidence for an artifact objective, but it does not by itself establish an operational outcome.

## Applicability

| Level | Use |
|---|---|
| `implicit` | Routine, reversible work where the outcome and mechanism are obvious; retain the distinction in the handoff without a separate artifact. |
| `inline` | One visible causal assumption or boundary needs a compact recorded fit statement. |
| `record` | Solution-first, material, consequential, uncertain, interface-heavy, expensive, difficult-to-reverse, preference-driven, or externally mandated work. |

Useful indicators include a technology-specific request without an outcome, artifact existence used as success, an unstated root cause, a preference presented as a hard constraint, a plausible simpler alternative, or a solution that could be delivered while the pain remains.

## Dispositions

| Disposition | Meaning |
|---|---|
| `CONFIRMED_FIT` | The requested intervention is adequately supported against the outcome. |
| `REFRAMED` | The outcome is accepted, but a different or broader intervention is selected. |
| `INVESTIGATE` | A bounded research task or prototype is required before solution commitment. |
| `PREFERENCE_DRIVEN` | The requested form is itself a legitimate preference or learning outcome. |
| `CONSTRAINT_REQUIRED` | An external authority or hard constraint mandates the intervention. |
| `NO_CHANGE_PREFERRED` | The current system, configuration, or process is presently the better intervention. |
| `UNRESOLVED` | Material fit or authority remains blocked. |

`INVESTIGATE` and `UNRESOLVED` are valid records but block downstream solution commitment. A required review without an accepted review reference produces a conditional disposition.

## Risk and authority

Fit uses the same non-averaging axes as BBK assurance:

- consequence;
- irreversibility;
- uncertainty;
- interface exposure.

A severe axis cannot be averaged away. Consequential or critical solution commitments may not use delegated authority. User- or external-authority commitments require explicit approval references. Consequential or critical fit requires review.

## Downstream traceability

The exact fit identity is `fitId@revision`. Carry it, and the supported outcome IDs, into applicable:

- `ImplementationStructureContract.subject`;
- `ExecutionSlice` records;
- work units;
- profile-resolution locks;
- verification and outcome observation.

A material implementation discovery that challenges the causal mechanism, selected direction, constraint basis, or success measure returns to Wayfinding. Workers and validators do not silently reinterpret the fit record.

## Commands

```bash
bbk fit new --output .bbk/fit/SOF-001.json
bbk fit validate .bbk/fit/SOF-001.json
bbk fit render .bbk/fit/SOF-001.json --output .bbk/reviews/SOF-001.md

bbk fit check-chain \
  --fit .bbk/fit/SOF-001.json \
  --structure .bbk/structures/ISC-001.json \
  --slice .bbk/slices/ES-001.json \
  --work-unit .bbk/WU-001.json
```

`fit validate` checks structure, non-averaging risk, authority, review, alternatives, counterfactuals, outcome evidence, and artifact-only success criteria. `fit check-chain` also checks exact downstream references and prevents a blocked fit from being treated as an accepted implementation direction.

## Included fixtures

- routine confirmed fit;
- dashboard request reframed to active alerting plus diagnosis;
- unresolved microservice request requiring investigation;
- Rust as an explicit learning preference;
- externally mandated regulatory format;
- no-change/configure-existing-capability decision;
- invalid intervention-as-outcome record.

## Authority boundary

A valid BBK fit record remains a bootstrap method artifact. It does not create an official Blueprint operational frame, ADR, readiness attestation, execution authorization, verification result, outcome assessment, or release decision.
