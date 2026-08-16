## BBK prompt-authoring guide

1. Use compact technical English. Prefer: Direct commands, Active voice, Short sentences, One rule per line, Exact project terms, Small decision tables for real branches, Short labels.

2. Put a rule at the narrowest layer that reaches every required consumer.

3. Keep universal rules in shared modules; keep role rules in role files; keep host rules in host projections.

4. Prove child receipt before removing local repetition.

5. State actor, condition, action, scope, and result.

6. Keep `must`, `may`, `only`, `not`, `unless`, `before`, and `after` explicit.

7. Never change role IDs, tool names, paths, keys, enums, markers, or state values for style.

8. Keep schema facts beside the schema or render every required fact into the prompt.

9. Keep failure, partial, blocked, recovery, and handoff states distinct.

10. Retain order when order changes behavior.

11. Repeat text only when contexts do not inherit it.

12. Keep one example only when it defines syntax, an edge case, or a state boundary.

13. Do not put audit hashes or generator bookkeeping in model text unless the model must use them.

14. Measure canonical source and effective runtime prompts separately.

15. Compare every role on every supported harness.

16. Reject unresolved variables, missing modules, duplicate module bodies, and duplicate procedure bodies.

17. Test role boundaries, module assignments, procedure order, host branches, return fields, and exact interface literals.

18. Regenerate from canonical sources; never hand-edit projections, manifests, or checksums.

19. When equivalence is uncertain, keep the old rule and record the missing proof.

## How BBK Prompts Are Assembled

BBK does not keep a role’s full prompt in one file. `tools/generate_agents.py` builds a harness-specific base in this order:

1. Host wrapper, role identity, and purpose.

2. Constitution groups selected by the role from `spec/roles/catalog.json`.

3. Scope and duties from `spec/roles/<role>-role.json`.

4. Shared rules named in the role’s `prompt_modules`, loaded from `spec/prompt-modules/` in catalog order.

5. Delegation, escalation, human-request triggers, prohibitions, procedure declarations, and profile rules from the role definition.

6. OMP-, Codex-, or Claude-specific instructions. Generic and PI use the common form.

7. The role’s exact `return_contract`, rendered by `tools/return_contracts.py`.

`tools/compiled_procedures.py` then selects the primary and other required procedures, closes their dependencies, and appends their full bodies. Dependencies come first; the primary procedure always comes last. On-demand procedures remain uncompiled unless a profile or invocation selects them. Procedure references to shared modules must resolve to modules already embedded in the prompt, exactly once.

The controller follows a smaller path: controller identity and limits, required shared modules, `bbk-context-routing`, then the primary `bbk` procedure.

The generator writes the resulting harness projections under `projections/`. Edit the canonical role, module, procedure, return-contract, or generator source—not a generated projection. A host may add task, tool, sandbox, and runtime data at dispatch, but it must not add new semantic instructions after the compiled primary procedure. Review the final prompt received by the agent, not any one source fragment or generated file.
