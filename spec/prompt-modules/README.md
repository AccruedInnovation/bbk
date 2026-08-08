# Canonical BBK prompt-module package

This directory owns small, reusable behavior capsules shared across canonical role prompts and standalone procedures. The package removes repeated normative text without weakening role-specific purpose, scope, responsibilities, topology, procedure, or return contracts.

## Source ownership

- `catalog.json` owns deterministic module order, source paths, package version, compilation policy, and mandatory-procedure exception records.
- Each `bbk-prompt-*.json` file owns one module and its stable clause IDs.
- `../method-content.json` owns procedure templates. A template includes a module with `{{bbk-module:<module-id>}}`; it must not copy the module body.
- Each canonical role selects an ordered `prompt_modules` set. The assembler verifies that every module required by its mandatory procedures is assigned and that behavior-specific modules are not distributed to roles that do not own that behavior.
- Generated role prompts, standalone `SKILL.md` files, and host projections are projections. Do not edit them independently.

## Compilation model

A role prompt is compiled as:

```text
role-specific contract
+ each assigned prompt module exactly once
+ compact mandatory procedure body or bodies
+ exact role-return contract
+ host-specific transport instructions
```

A standalone procedure expands each referenced module once. Later references in the same procedure remain compact. Codex receives module identity as Markdown; tagged hosts receive authenticated `<bbk-prompt-module>` blocks.

The current roles each need one primary mandatory procedure. That is a measured property of this package, not a universal maximum. `mandatory_procedure_maximum` is `null`.

A role may carry additional mandatory procedures only through a catalogued exception that:

1. names the exact ordered procedure list;
2. states the behavior uniquely supplied by every additional procedure;
3. binds the current `spec/method-content.json` SHA-256;
4. records deterministic UTF-8 byte measurements for compact procedure bodies;
5. proves that prompt-module bodies remain embedded zero additional times; and
6. provides a role-specific rationale.

The assembler recomputes that record. A stale measurement, generic rationale, missing behavior distinction, or duplicated module body is rejected. There is deliberately no special ceiling at three procedures.

## Clause design

Create a module only when the behavior is:

- materially identical across multiple role or procedure contexts;
- independently understandable at the point of use;
- governed by one semantic owner;
- small enough to audit as a cohesive rule set; and
- safer to maintain once than to repeat.

Role-specific algorithms, authority, stopping rules, readiness, and result semantics remain in the primary role procedure or role contract. Similar wording alone is not sufficient reason to extract a module.

Role-specific typed vocabularies and protocol ladders also remain explicit where their meaning depends on that role—for example source classifications, authority intersections, assurance attempt taxonomy, candidate/evidence object separation, and failure routing. Gate 4 preservation tests assert those fragments in compiled prompts so compaction cannot silently replace them with weaker prose.

## Validation

Check the module package, role assembly, and focused tests without writing changes:

```console
python tools/prompt_modules.py --check
python tools/assemble_roles.py --check
python -m unittest tests.test_prompt_module_package_v1 -v
```

After an intentional module change, regenerate the canonical module projections and assembled role surfaces before regenerating host projections:

```console
python tools/prompt_modules.py
python tools/assemble_roles.py
```

The OMP adapter, source manifests, projection generator, and release tests also verify the package. See [`docs/DEVELOPMENT.md`](../../docs/DEVELOPMENT.md) for the full generation and release sequence.
