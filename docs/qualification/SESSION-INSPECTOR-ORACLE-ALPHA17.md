# Alpha.17 Session Inspector oracle qualification

Status: **automated PASS for WU-016**

Release target: `0.1.0-alpha.17`

## Qualified fixture

The supplied Alpha.16 OMP Session Inspector HTML export is the authoritative
source. The separately supplied analyzer JSON is retained only by immutable
file digest and is classified as `INCOMPLETE_SECONDARY`; it cannot establish
complete session topology, task identity, wait semantics, prompt-integrity
coverage, or inclusive usage by itself.

The checked-in fixture consists of:

- `fixtures/session-inspector-alpha16/source-session-oracle.json`
- `fixtures/session-inspector-alpha16/derived-analysis-contradictions.json`
- `spec/schemas/bbk-session-inspector-oracle-manifest-v1.schema.json`
- `spec/schemas/bbk-session-inspector-contradictions-v1.schema.json`
- `spec/schemas/bbk-session-inspector-oracle-verification-v1.schema.json`
- `tools/session_oracle.py`

The raw 6.37 MB HTML export and 904 KB analyzer JSON are not copied into the
package. The fixture retains their exact SHA-256 identities, the decoded
payload digest, anonymized session/task aliases, structural hashes, entry and
receipt counts, relative timing, aggregate token/cost facts, and explicit
positive and negative assertions.

## Exact source facts

Independent local decoding established:

```text
Sessions:                         5
Main entries:                     690
Child entries:                    629
Inclusive entries:               1,319
Root task invocations:            4
Explicit ask waits:               1
Explicit ask duration:            5,217 ms
Provider/model responses:         281
Prompt binding receipts:          5
Prompt provider-verified receipts:281
Prompt-integrity receipts total:  286
Inclusive tokens:                 31,239,337
Inclusive reported cost:          USD 0.47572615
Main job/IRC polling calls:        30 / 14
Inclusive job/IRC polling calls:   30 / 16
```

The five normalized session aliases are `session:main`,
`session:root-wayfinder`, `session:root-orchestrator`,
`session:api-reviewer`, and `session:api-rechecker`. The four task calls are
correlated to those four child sessions using the source task name and
sub-session label; provider response IDs are never accepted as agent identity.

## Positive oracle

The raw export proves all of the following:

- inclusive session-entry conservation across Main and all four child exports;
- exact task-to-child-session correlation for all four root task calls;
- one user wait correlated by the exact `ask` tool-call ID and result;
- inclusive provider usage conservation across 281 uniquely identified model
  responses;
- prompt-integrity conservation across five binding receipts and 281 verified
  provider-request receipts.

The analyzer JSON also has three useful positive controls: it preserves all 690
Main entries, Main provider usage and cost, and all 167 Main prompt receipts.
Those controls prevent the negative fixture from treating the analyzer as
wholly corrupt.

## Negative oracle

The same comparison deterministically confirms eight blocking contradictions:

1. 629 child entries are absent from the analyzer output.
2. Four child sessions are absent.
3. 166 provider response IDs are misidentified as agents, alongside four
   synthetic role identities.
4. All four task-topology records are absent from the normalized result.
5. The exact 5,217 ms `ask` wait is absent; the analyzer reports two unrelated
   timestamp gaps instead.
6. 115 child provider responses are excluded.
7. USD 0.295132594 of child-session cost is excluded.
8. 119 child prompt-integrity receipts are excluded.

The required conclusion is therefore
`derived_analysis_can_establish_complete_truth: false`, while the analyzer
remains usable as a Main-session secondary observation.

## IF-014 binding

The fixture projects task-spawn and user-wait observations into
`bbk.host-event.v1` records with normalized aliases, exact correlation methods,
payload digests, and source timestamps. The export does not contain a
trustworthy OMP host version, so the records explicitly use
`host_version: UNOBSERVED_IN_EXPORT` and
`enforcement_boundary: DETECT_ONLY`. No host qualification is inferred from
filename, prompt text, or model prose.

## Privacy and source handling

The fixture excludes raw prompts, raw task assignments, local paths, raw
session UUIDs, provider response IDs, credentials, and API keys. Session IDs,
task-call IDs, assignments, entry structure, and source files are bound by
SHA-256 digests. The decoder reads one exact `script#session-data` payload,
base64-decodes it, and parses JSON; it does not execute HTML, JavaScript, prompt
content, or imported commands.

## Automated evidence

Exact source reproduction:

```text
python tools/session_oracle.py verify \
  --manifest fixtures/session-inspector-alpha16/source-session-oracle.json \
  --contradictions fixtures/session-inspector-alpha16/derived-analysis-contradictions.json \
  --source-html <supplied-alpha16-session-export.html> \
  --derived-json <supplied-alpha16-analysis.json>
```

Observed result on 2026-08-04:

```text
Fixture verification:       PASS
Manifest reproduced:        true
Contradictions reproduced:  true
Manifest digest:            sha256:8cc80edaee86751cd9d8c417a300e723e6c576915ab31f113851ebdee8fdad63
Contradictions digest:      sha256:fa02863df7267d51c7eeadc4f993cf54a9c6c2dc6629419867b15d6965a60333
Fast verification checks:   7/7 PASS
Fast tests:                 159
Fast skips:                 0
Failures/errors:            0/0
Python files compiled:      92
JSON files parsed:          374
Implicit text encodings:    0
Network/API keys:           not used
```

The complete standard profile also passed all 32 test modules: 524 unique tests,
zero failures, zero errors, and zero unresolved skips. Thirteen conditional
adapter/host cases initially skipped in the unqualified shell were rerun with
the supplied local `bd`, `jj`, and OMP 16.4.8 binaries; all thirteen passed.
The semantic fixture audit passed 157 checks, including both oracle fixtures
and all three oracle schemas. Machine-readable status is in
`evidence/qualification/session-inspector-oracle-alpha17.json`.

## Acceptance assertion

- `VER-035`: **PASS** — the exact supplied Alpha.16 transcript and analyzer JSON
  are bound by immutable source digests and reproducibly generate permanent
  positive and negative oracle fixtures without retaining sensitive raw
  content.

## Honest limits

- This qualifies WU-016 only, not the Alpha.17 release as a whole.
- The export does not establish its own OMP host version; IF-014 records remain
  `DETECT_ONLY` for that field.
- Cost values are the provider-reported source values, normalized to at most 12
  decimal places; they are not billing reconciliation.
- The fixture detects the analyzer contradictions represented by the supplied
  evidence. It does not claim that every possible future analyzer defect is
  enumerated.
- No provider credentials, external network, or user-global configuration were
  used. The supplied OMP 16.4.8 binary was exercised only by the keyless local
  host-contract probe.
