# Assurance and review

BBK turns review into revision-bound, evidence-bearing, inspectable records while preserving proportional assurance.

`AssuranceContract` remains the statement of what must be proven. The review layer records how one review covers that contract, what context existed, what actually ran, what findings resulted, and what remains open.

```text
AssuranceContract
  → ReviewManifest
    → ReviewContextManifest
      → ReviewRun / ReviewAttempt
        → EvidenceReceipt and ReviewFinding
          → FindingDisposition
            → ReviewAggregate
              → optional LearningCandidate
```


## Proportional assurance modes

BBK uses three explicit modes. `INLINE` is the routine default. `FOCUSED` requires an exact material risk, candidate scope, or finding-scoped recheck. `FULL` is reserved for consequential assurance, material external effects, complex cleanup/recovery, authority ambiguity, interrupted attempts, candidate/release boundaries, or explicit parent request. FOCUSED and FULL record their risk rationale; the presence of a mechanical defect alone is not sufficient.

Independent review normally targets an integrated candidate or an exact material risk. A repair recheck contains only the finding, successor candidate, affected scope, relevant evidence, and reopening triggers unless semantics changed materially.

## Generated review packages

`bbk context review` compiles and seals a `bbk.review-package.v2` from an exact verified candidate, review request, applicable floors, prior findings, and assurance mode. The Reviewer consumes this mechanical context and does not author the manifest that admits its own subject. Legacy ReviewManifest and ReviewContextManifest commands remain available.

## Role-return boundary

Reviewer and Validator results use different exact schemas. A Validator evaluates fixed candidate-bound assertions through fixed methods and returns assertion results to Validator Orchestrator. A Reviewer performs bounded qualitative, cross-cutting, conformance, proportionality, readiness, or evidence-sufficiency judgment. Missing assertion, criteria, evidence-method, or revalidation design returns to Verification Designer. Operational `COMPLETE` means the attempt completed; it does not itself mean the candidate passed, findings are closed, or release is authorized.

## Object responsibilities

### AssuranceContract

Defines exact subject, non-averaging risk, change classes, protected floors, assertions, evidence and methods, gate obligations, independence, repair, and reuse policy.

### ReviewManifest

Plans one review decision. It binds the exact subject and assurance digests, purpose, applicability (`none`, `inline`, or `manifest`), assertions, logical lenses, primary ownership, context selection, deterministic evidence, independence, sharding, aggregation, repair, and staleness closure.

### ReviewContextManifest

Proves what was available, omitted, stale, redacted, generated, external, retrieval-only, or sharded. Full canonical content roots—not path/size summaries—protect integrity.

### ReviewRun and ReviewAttempt

Record one execution and each lens/tool activity. Attempts distinguish candidate failure from reviewer, context, environment, schema, and infrastructure failure. Reviewer independence dimensions and prior-finding visibility are recorded separately.

### EvidenceReceipt v2

Records what was run or observed. It does not state what the evidence proves. Assertion evaluation and aggregate disposition remain separate.

### ReviewFinding and FindingDisposition

A finding is immutable. Closure is a successor disposition tied to exact evidence and authority. Absence from a later review, majority vote, tone, or fingerprint mismatch never closes a finding.

### LearningCandidate

Captures a proposed reusable lesson with supporting and contrary evidence. It cannot change BBK method, roles, profiles, or policy automatically.

## Logical lenses

BBK includes a small extensible registry:

1. intent and outcome conformance;
2. specification and acceptance completeness;
3. feasibility and dependency risk;
4. architecture and deep-module boundary;
5. interface, consumer, and compatibility;
6. implementation structure and delegated freedom;
7. state, concurrency, effect, recovery, and rollback;
8. security, privacy, credentials, and supply chain;
9. test strategy and evidence adequacy;
10. operational, observability, performance, and resource behavior;
11. package, installation, migration, and release;
12. cross-shard and integrated behavior.

Profiles may provide procedures and tools for these lenses. They do not create a second generic review authority.

## Assertion ownership and overlap

Each required assertion has one primary evaluation owner. A second evaluation is valid only when its assignment states a complementary independence rationale and uses a genuinely distinct method or lens. Global permission to use complementary review is not enough by itself.

No fixed reviewer count is embedded. The planner compiles the smallest sufficient lens set from risk, subject, change classes, assertions, profile capabilities, and environment.

## Applicability

| Risk | Typical review |
|---|---|
| Routine | none or inline; deterministic checks first |
| Material | focused manifest for exact material assertions |
| Consequential | explicit context, adverse/consumer/fault lenses as applicable, independent acceptance review |
| Critical | complementary methods and accountable human authority where the contract requires it |

The `AssuranceContract` controls. File count, repository unfamiliarity, or available agents do not automatically activate full fan-out.

## Commands

```bash
bbk assurance new --output .bbk/assurance/AC-001.json
bbk assurance validate .bbk/assurance/AC-001.json

bbk review plan \
  --assurance .bbk/assurance/AC-001.json \
  --id RM-001 \
  --purpose acceptance \
  --output .bbk/reviews/manifests/RM-001.json

bbk review context \
  --manifest .bbk/reviews/manifests/RM-001.json \
  --id RCM-001 \
  --source . \
  --output .bbk/reviews/contexts/RCM-001.json

bbk review run \
  --id RR-001 \
  --manifest .bbk/reviews/manifests/RM-001.json \
  --context .bbk/reviews/contexts/RCM-001.json \
  --attempt .bbk/reviews/attempts/RA-001.json \
  --receipt .bbk/receipts/ER-001.json \
  --finding .bbk/reviews/findings/RF-001.json \
  --output .bbk/reviews/runs/RR-001.json

bbk review inspect .bbk/reviews/runs/RR-001.json
bbk review reconcile .bbk/reviews/findings/*.json
bbk review close \
  --finding .bbk/reviews/findings/RF-001.json \
  --id FD-001 --disposition FIXED \
  --successor-ref C-002 --successor-file .bbk/candidates/C-002/candidate.json \
  --evidence ER-002 --review-attempt RA-002 \
  --residual-impact "No known residual effect" \
  --output .bbk/reviews/dispositions/FD-001.json
bbk review learn --run .bbk/reviews/runs/RR-001.json --output .bbk/reviews/learning/LC-001.json
```

Command option details are available through `--help`. Planning and validation are package-qualified. Actual agent/model invocation, host session isolation, and tool execution remain subject to the explicit OMP effect grant and live-host qualification.

## Aggregate policy

Allowed review results are:

```text
PASS
PASS_ADVISORY
NEEDS_REVISION
BLOCKED_INSUFFICIENT_CONTEXT
BLOCKED_ENVIRONMENT
INCONCLUSIVE
ERROR
ESCALATED
CANCELLED
STALE
```

No averaging or majority vote can hide a failed required assertion or open protected-floor finding.

## Authority boundary

BBK review records are local method/evidence records. They do not establish official Blueprint readiness, execution authorization, verification, completion, release, or organizational authority.

## Review context integrity

A reviewer can only be interpreted against the context it actually received. `ReviewContextManifest` records the exact subject, source revision, included files/objects, retrieval-only material, exclusions, omissions, redactions, generated content, shards, context packs, compiler identity, and dependency closure.

### Completeness states

```text
COMPLETE
COMPLETE_WITH_DECLARED_EXCLUSIONS
PARTIAL_NONBLOCKING
BLOCKED_REQUIRED_CONTEXT_MISSING
STALE
INVALID
```

A required missing item blocks only the affected review scope; it does not become a defect finding against the subject. “Too large” is not a waiver: narrow, retrieve, summarize, or shard while preserving omission accounting.

### Full content roots

Integrity uses algorithm-qualified canonical content/artifact/tree digests. Path names, sizes, counts, and shortened hashes may help display or planning but cannot bind a review subject.

### Semantic sharding

Preferred grouping:

1. execution slice or work unit;
2. territory/responsibility boundary;
3. interface cluster;
4. assertion/requirement cluster;
5. package/domain;
6. path/size fallback.

Each item has one primary shard. Shared contracts may occur in several context packs but are declared shared. A cross-shard attempt is required when an assertion, interface, recovery path, or intent chain spans shards.

### Redaction and hostile content

Redactions are explicit and may make independent reproduction incomplete. Untrusted source content remains data, not instruction. Review context must not include credentials, undisclosed secrets, or implicit effect authority.

### Blind review

A new session ID does not prove independence. A blind attempt requires a separately compiled context pack with prior findings and worker self-assessment omitted by policy and digest. Targeted closure intentionally includes the exact finding and closure criteria.

## Evidence receipts

An `EvidenceReceipt` records an actual operation or observation against an exact subject. It does not by itself declare an assertion satisfied.

Required distinctions:

```text
EvidenceReceipt       what ran or was observed
AssertionEvaluation   what it establishes for one assertion
ReviewAggregate       whether the review decision may advance
```

### Trust classes

```text
DETERMINISTIC_LOCAL
QUALIFIED_TOOL
QUALIFIED_EXTERNAL_CHECK
SIMULATOR_OR_HARNESS
AGENT_INSPECTION
HUMAN_REVIEW
OPERATIONAL_OBSERVATION
UNSTRUCTURED_OBSERVATION
LEGACY_IMPORTED
```

Trust class does not imply sufficiency. The assurance contract decides what is adequate.

Freeform “tests passed” prose is `UNSTRUCTURED_OBSERVATION`; it cannot satisfy a required build, test, recovery, package, or release assertion without a qualified interpretation step.

### Identity and reuse

A receipt binds subject/candidate, assertion references, operation or sanitized argv, execution root, times, completion state, output/artifact/trace digests, tool/toolchain/environment/workspace identities, input closure, coverage, trust, redaction, and freshness dependencies.

Reuse is permitted only when every declared dependency remains unchanged. Reuse creates a new acceptance/reference record and never rewrites the original receipt.

### Redaction

Secrets must not appear in argv, environment, stdout, stderr, paths, or exported reports. A receipt records whether raw bytes or redacted bytes were hashed, where local-only raw evidence lives, and whether redaction prevents reproduction.

Commands:

```bash
bbk evidence new --output .bbk/receipts/ER-001.json
bbk evidence validate .bbk/receipts/ER-001.json
```

## Finding lifecycle

A `ReviewFinding` is immutable. A `FindingDisposition` is a successor record that states what happened later.

Projection states:

```text
OPEN
REPAIR_PROPOSED
REVALIDATION_REQUIRED
DISPOSITIONED
SUPERSEDED
```

Allowed dispositions:

```text
FIXED
REBUTTED
ACCEPTED_RISK
FALSE_POSITIVE
DUPLICATE_OF
SUPERSEDED
DEFERRED
OUT_OF_SCOPE
REMAINS_OPEN
```

Every closing disposition binds the exact finding, successor candidate or changed context, closure evidence, reviewing attempt or accountable authority, residual impact, and reopening trigger.

### What never closes a finding

- a later reviewer does not repeat it;
- a fingerprint or line number changes;
- a majority disagrees;
- the worker says it is fixed;
- another finding is more severe;
- a new model produces a friendlier answer.

Fingerprints are correlation aids only. Duplicate and shared-root-cause relationships preserve every original record and evidence.

### Repair and re-review

A repair creates a successor candidate. Two lanes are available:

- **targeted closure** receives the exact finding and closure criteria;
- **blind reassessment** receives the current subject and assertions without prior finding text.

Routine repairs may use targeted closure alone. Consequential, broad, recurring, or protected-floor repairs usually require both according to the assurance contract.

## Review independence

Independence is multidimensional. BBK records:

```text
author separation
worker/reviewer role separation
invocation or session separation
independent context assembly
prior-findings visibility
model-family diversity
provider diversity
deterministic evidence independence
human organizational independence
candidate mutation prohibition
```

A fresh model or session is an independence fact, not automatic proof of adequate independence.

Prior-finding visibility:

```text
HIDDEN          blind reassessment
TARGETED        exact finding and closure criteria
FULL            synthesis, reconciliation, or adjudication
NOT_APPLICABLE  deterministic or first-run activity
```

Reviewer context digests—not conversational claims—establish what was hidden or supplied. Candidate reviewers remain read-only, and workers cannot close their own material findings.

## Intent conformance

Local repairs can satisfy a child contract while drifting from the parent mission. The intent-conformance lens compares exact links such as:

```text
requested intervention ↔ SolutionOutcomeFit ↔ operational outcome
parent plan ↔ child plan
architecture/interface ↔ ImplementationStructureContract
ExecutionSlice ↔ WorkUnit
AssuranceContract ↔ candidate/evidence
package/release subject ↔ promised capability
```

It detects dropped obligations, unauthorized scope changes, a child that no longer contributes to the outcome, weakened failure/recovery/security behavior, changed accepted boundaries, activity evidence without outcome relevance, and repairs that “fix” a test by changing the contract.

Intent drift is routed to the responsible planning or authority boundary. A reviewer or worker may not silently edit the parent artifact to manufacture conformance.
