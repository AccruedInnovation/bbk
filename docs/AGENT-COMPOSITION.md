# Agent composition and delegation

BBK defines one canonical logical role catalogue and projects it into OMP, Codex, Claude Code, and generic hosts. Host definitions are adapters; the canonical responsibility and direct-child topology live in `spec/roles.json`.

## Root responsibilities

`bbk_root_wayfinder` owns planning when outcome, scope, architecture, authority, work structure, or assurance remains unresolved.

`bbk_root_orchestrator` coordinates execution and recovery against an accepted operating baseline.

The baseline `bbk` skill acts as an entry controller in a primary session. It selects the appropriate root or review role rather than making every request an execution request.

## Direct-child topology

A role may delegate only to its canonical direct children. The host representation differs:

| Host | Delegation representation |
|---|---|
| OMP | native `spawns` metadata |
| Codex | explicit delegation contract in generated agent instructions |
| Claude Code | delegation contract plus `Agent(...)` allowlist |
| Generic | portable delegation contract |

Availability of additional host agents does not broaden the BBK role's delegation authority.

## Logical and physical roles

A logical role is a responsibility boundary. A physical invocation is a model/session/process that performs one or more logical roles.

Several logical roles may share one physical invocation when the work is routine and no independence claim depends on separation. Approval, validation, review, integration, or evidence-independence requirements may require separate invocations, contexts, models, people, or tools.

Never claim physical independence merely because two role names were used.

## Context contract

Each delegation should bind, proportionately:

- exact subject and objective;
- accepted decisions and baseline references;
- authority and permitted effects;
- required skills and profiles;
- interfaces and invariants;
- assurance obligations and stopping conditions;
- expected structured return;
- omitted, redacted, or unavailable context.

Ambient transcript inheritance is not an authority grant.

## Mutating and non-mutating responsibilities

Host sandbox permission and BBK role authority are separate. A role may need filesystem access to write notes, findings, plans, evidence, or handoffs without being authorized to modify the implementation subject.

Only the roles explicitly authorized by the current work contract may alter the subject. Other roles return implementation work to an authorized worker or parent.

## Return discipline

Child returns should identify:

- result or disposition;
- exact subject and revision;
- decisions, assumptions, and deviations;
- evidence and findings;
- blockers and residual uncertainty;
- requested parent action.

## Codex sandbox inheritance and role authority

Generated Codex sub-agents inherit the parent Codex sandbox rather than forcing a read-only sandbox. This lets planning, review, validation, and orchestration roles write bounded coordination artifacts such as notes, handoffs, findings, plans, evidence records, and result packets.

That inherited sandbox access does not authorize a role to modify subject or product artifacts. BBK role authority remains narrower than host filesystem capability: only a role explicitly authorized by the accepted work contract may alter the implementation subject. Other roles may write coordination artifacts but must return product changes to an authorized worker or parent.
