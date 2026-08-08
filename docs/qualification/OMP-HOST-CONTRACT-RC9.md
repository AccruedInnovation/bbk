# OMP 16.4.8 host-contract feasibility report

Status: **PASS**

## Qualified binary

- Version output: `omp/16.4.8`
- SHA-256: `cdf0775e05b88d63f9da606de542cc3fc0beedf0a864b4ac42f777961f86844c`
- Platform: `linux`
- Provider: localhost keyless OpenAI-compatible fixture
- External provider credentials: not supplied

## Observed contracts

- `VER-017`: parent and child session identities were distinct: `true`.
- `VER-017`: parent and child CWDs were equal: `true`; CWD is therefore context, not an isolation identity.
- `VER-017`: task name, agent, and parent tool-call binding were observed through lifecycle events: `true`.
- `VER-018`: built-in `write`, `edit`, and `bash` calls returned blocked tool results before effects; absent effects were `True`, `True`, and `True` respectively.
- `VER-018`: the custom governed write created only the scoped fixture file with expected content: `true`.
- `VER-019`: unsupported paths remain explicitly `DETECT_ONLY` or `UNQUALIFIED`; this report does not claim OS sandboxing, Windows qualification, real-provider qualification, or prevention outside OMP-mediated pre-tool hooks.
- `VER-020`: an `extensions: []` final overlay suppressed an extension stored in OMP configuration while preserving the explicit qualification extension: configured loaded `false`, explicit loaded `true`.
- `VER-021`: OMP removed the presentation-only `i` field before the pre-effect hook `true`, and the hook still replaced the canonical compact dispatch envelope with the exact full task input before OMP spawned the child: rewrite observed `true`, child started `true`, compact marker absent from child request `true`.
- `VER-022`: a malformed child `yield` was blocked before acceptance `true`; a complete prepared return was admitted unchanged `true`; the parent observed only that full validated role return `true`.

## Host quirk retained as evidence

OMP 16.4.8 suppresses explicit -e extensions when --no-extensions is also present, contrary to the CLI help text.

The qualified manual-launch strategy is: Omit --no-extensions, apply a final config overlay containing extensions: [], disable skills and rules, then load the exact BBK extension and qualification helper explicitly in order. The keyless fixture proves the overlay suppresses a configured extension while preserving the explicit extension.

## Reproduction

```text
python tools/qualification/omp_host_contract.py --omp <path-to-omp-16.4.8> --output <report.json> --markdown <report.md>
```

The runner constructs isolated HOME, OMP agent, and project roots; removes proxy and credential-bearing environment variables; starts only a `127.0.0.1` mock provider; and records normalized event evidence without retaining model prompts or secrets.
