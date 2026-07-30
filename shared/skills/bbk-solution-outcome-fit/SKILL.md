---
name: bbk-solution-outcome-fit
description: Separate a requested intervention from the outcome the user needs, assess the causal fit, compare proportionate alternatives, and retain an explicit disposition before downstream design or execution.
---

# BBK Solution–Outcome Fit

Treat the user’s requested solution as a candidate intervention unless it is itself a legitimate preference, learning objective, or external constraint.

## Procedure

1. Record the requested intervention verbatim enough to preserve intent.
2. State the actor-visible or operational outcomes independently of that intervention.
3. Describe the current or no-intervention baseline, including strengths, workarounds, cost, burden, and no-change consequences.
4. State the causal hypothesis: why and through what mechanism the intervention should change the outcome.
5. Separate hard constraints, preferences, assumptions, and unknowns.
6. Ask the counterfactual: **If the requested intervention were delivered exactly, under what conditions would the underlying problem remain?**
7. Compare credible alternatives proportionately. Include no change when material. Do not manufacture alternatives for a routine, clearly constrained request.
8. Define success evidence that measures the outcome rather than merely the artifact’s existence.
9. Record one disposition:
   - `CONFIRMED_FIT`
   - `REFRAMED`
   - `INVESTIGATE`
   - `PREFERENCE_DRIVEN`
   - `CONSTRAINT_REQUIRED`
   - `NO_CHANGE_PREFERRED`
   - `UNRESOLVED`
10. Obtain the authority required by consequence, irreversibility, uncertainty, interface exposure, and posture.
11. Carry the exact fit reference into structure contracts, execution slices, work units, verification, and outcome observation.

## Proportionality

- **Implicit:** a routine reversible request whose outcome and mechanism are obvious may be recorded in the handoff without a separate file.
- **Inline:** a compact fit statement is enough when one material assumption or boundary needs visibility.
- **Record:** use a `SolutionOutcomeFit` artifact for solution-first, consequential, uncertain, interface-heavy, expensive, or hard-to-reverse interventions.

Do not label the user as having an “XY problem.” Expose a possible mismatch respectfully, provide a recommendation, and preserve legitimate preference-driven outcomes.

## Deterministic support

Use:

```text
bbk fit validate <path>
bbk fit render <path>
bbk fit check-chain --fit <path> [--structure ...] [--slice ...] [--work-unit ...]
```

A valid BBK fit record is still a method artifact. It grants no product decision, readiness, execution, acceptance, compliance, or release authority.

## Profile interaction

Consult `bbk-installed-profiles` and `bbk-profile-routing` when language, runtime, or toolchain feasibility materially affects alternatives or constraints. Profile availability may inform fit, but it does not make the profiled intervention preferable by itself.
