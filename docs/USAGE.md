# Using BBK

BBK scales from a light coordination discipline to explicit project records, execution baselines, candidates, gates, and assurance evidence. Use the least structure that protects the important claims and interfaces.

## OMP entrypoint

```text
/bbk          enter persistent BBK mode
/bbk:exit     leave BBK mode
/bbk:status   inspect deterministic project status
/bbk:models   inspect or change sub-agent routing
```

While BBK mode is active, ordinary messages are interpreted as part of the continuing governed workflow. The parent session remains user-facing and routes work to the appropriate named BBK roles.

## Typical lifecycle

```text
outcome and fit
  → questions and decisions
    → architecture and interface contracts
      → implementation structure
        → execution slices and work units
          → exact candidate
            → gates, review, and evidence
              → acceptance and operational feedback
```

Not every task requires every step. Routine work can remain mostly inline.

## Project initialization

```bash
bbk init --title "Project name"
bbk status
```

Initialization is additive. Existing project records are preserved rather than silently replaced.

## Planning and execution

Use planning roles when outcome, scope, architecture, authority, interfaces, work structure, or assurance remains unresolved. Use execution roles only against an accepted and sufficiently specified baseline.

Material discoveries during implementation are not silently absorbed as scope drift. Return them to planning, record the effect on the baseline, and invalidate affected candidates or evidence where necessary.

## Candidates and gates

A candidate identifies the exact subject being validated or reviewed. Gate results and evidence apply to that identity, not to an informal idea of "the same code."

When the subject changes materially:

- affected evidence becomes stale;
- gate reuse must be re-evaluated;
- review conclusions must not be carried forward by implication.

## Recovery

Resume from durable project state rather than model memory:

- accepted decisions;
- active work and leases;
- exact candidate identity;
- blockers and deviations;
- findings and dispositions;
- gate and evidence state.

## Proportionality

Prefer the lightest responsible workflow:

- tiny, local, reversible change: inline reasoning and existing tests;
- material interface or public contract: explicit structure, candidate, and focused review;
- consequential migration, safety, security, or recovery change: explicit assertions, evidence, independence, rollback, and authority.

## Language profiles

Language and domain profiles specialize procedure and evidence collection. They do not broaden authority. Profile-aware roles should:

1. inspect the installed-profile registry;
2. select the smallest applicable profile router;
3. load only the focused profile procedures required for the current role and assertion;
4. propagate profile identity, lock/digest, assumptions, gates, and unavailable-capability dispositions to children.

See [LANGUAGE-PROFILES.md](LANGUAGE-PROFILES.md).
