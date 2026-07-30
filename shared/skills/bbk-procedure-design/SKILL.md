---
name: bbk-procedure-design
description: Separate reusable organizational procedure from agent identity and one authorized execution baseline. Use when a multi-step, recurring, interactive, adaptive, or assurance-sensitive process must be explicit and inspectable.
---

# BBK Procedure Design

A performer definition says who or what may act. A procedure says how bounded work progresses. An execution baseline binds exact procedure revisions, roles, objects, interfaces, environments, gates, and authority for one scope.

1. Decide whether the work is routine inline behavior or needs an explicit procedure record.
2. Classify the procedure as deterministic, bounded-adaptive, plan-proposing, exploratory, or interactive-decision. Mixed procedures must expose their deterministic and adaptive boundaries.
3. Bind purpose, subject, entry conditions, inputs, outputs, steps or transitions, logical roles, context edges, authority checks, allowed effects, gates, evidence, stopping, recovery, escalation, and completion semantics.
4. Define each step's result envelope and the exact conditions that permit the next step. Tool availability, model output, queue state, or transport success never implies semantic completion.
5. Record logical-role-to-physical-invocation mapping separately. Preserve mandatory separation for approval, validation, integration, or other independence properties.
6. Keep findings, repair proposals, repair execution, approval, and commit as distinct operations unless one authority explicitly owns a permitted combination.
7. For exploratory or alternative branches, declare what may vary, how results are surfaced, selection/synthesis rules, disagreement handling, stopping, and whether fresh confirmation is later required.
8. Make interruption, duplicate return, stale result, timeout, cancellation, partial completion, ambiguous acknowledgement, and resume behavior explicit where material.
9. Version procedures immutably. A ProcedureSpec or equivalent BBK record cannot authorize itself, activate its own successor, or broaden the execution baseline.
10. Use `ImplementationStructureContract`, `StateDecisionEffectDesign`, `ExecutionSlice`, `WorkUnit`, `AssuranceContract`, and review records where they carry the needed detail; do not duplicate their authority or semantics.

## Profile-bound procedures

When a reusable procedure depends on language- or toolchain-specific behavior, bind the applicable `bbk-installed-profiles` entry, router skill, profile version/digest, capability requirements, and fallback/blocking behavior in the execution baseline rather than the logical role identity.
