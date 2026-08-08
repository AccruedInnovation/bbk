---
name: bbk-context-routing
description: Compile explicit, least-privilege context edges and result envelopes between logical roles or procedures instead of relying on inherited transcript history. Use for question branches, delegated planning, workers, reviewers, validators, and cross-territory handoffs.
requires_prompt_modules: ["bbk-prompt-context-human-relay"]
standalone_prompt_modules: ["bbk-prompt-human-request", "bbk-prompt-profile-qualification"]
---


# BBK Context Routing

> Apply the already embedded `bbk-prompt-context-human-relay` module here.

## Human relay edges

<!-- BBK prompt module bbk-prompt-human-request: expanded from canonical source -->

### Controller-mediated human request protocol

Create, transport, bind, and resume one exact human decision, authority, private-context, acceptance, or protected-floor request without creating another user-facing identity.

- `HUMAN.REQUEST_TRIGGER` — Originate a human request only for a material decision, authority grant, private context, accountable acceptance, protected-floor exception, hard-to-reverse commitment, or other trigger explicitly owned by this role. Routine reversible choices inside standing authority remain with the role.
- `HUMAN.REQUEST_PACKET` — Carry a stable request ID; requesting agent and logical role; semantic parent; exact subject and revision; request kind DECISION, AUTHORITY, PRIVATE_CONTEXT, ACCEPTANCE, or PROTECTED_FLOOR_EXCEPTION; the smallest exact question; current recommendation; credible alternatives; consequences; safely inferable default if any; blocker state; work that can continue; expiry or invalidation conditions; durable packet reference when needed; and exact reply target.
- `HUMAN.REQUEST_TRANSPORT` — In OMP, resolve the peer whose kind is main and send the concise request through hub/IRC with the exact replyTo binding. Persist long-form or authority-bearing content in a verified durable carrier rather than placing it in IRC.
- `HUMAN.REQUEST_RESPONSE` — Treat only an authoritative reply bound to the stable request, exact subject, and reply target as the response. Delivery, silence, timeout, cancellation, a status message, or unrelated prose does not answer or authorize the request.
- `HUMAN.REQUEST_CONTINUE` — Continue every independent authorized branch after sending. Wait only when the request blocks all remaining valid work; resume the same logical role and request lineage after a valid response rather than restarting or silently changing the question.
- `HUMAN.REQUEST_FALLBACK` — When live relay is unavailable, return the same request packet through the invocation chain using BLOCKED_DECISION, BLOCKED_AUTHORITY, or the applicable private-context state. Never bypass the harness-root controller.
- `HUMAN.CALLBACK_SAFE_CHILDREN` — After sending a BBK_USER_REQUEST or equivalent controller callback, do not enter a cancellation-sensitive blocking child wait while an immediate response may arrive. Do not batch the request transport and such a task wait in the same callback window. Dispatch decision-dependent specialists only after the bound response is durably integrated. Continue local analysis or independent work only through a child-lifetime mechanism proven not to cascade-cancel on parent interruption; otherwise sequence safely and defer the child dispatch.

<!-- End BBK prompt module bbk-prompt-human-request -->

## Profile context edges

<!-- BBK prompt module bbk-prompt-profile-qualification: expanded from canonical source -->

### Language, domain, toolchain, and model qualification

Select only applicable installed profiles and focused procedures without allowing them to broaden authority.

- `PROFILE.EXPLICIT` — Use only a profile explicitly supplied or selected from the current installed-profile registry for the exact language, domain, framework, runtime, or toolchain responsibility.
- `PROFILE.FOCUSED` — Load the router and only the focused procedures and gates material to this role and assertion; do not fan out every profile or specialist pack.
- `PROFILE.BIND` — Carry profile identity, version or digest, toolchain assumptions, required gates, qualified operations, unavailable-capability policy, and evidence bindings into child and return contracts.
- `PROFILE.NO_AUTHORITY` — A profile, skill, tool, model route, or host capability adds method and evidence requirements only. It cannot broaden scope, effects, authority, or acceptance.
- `PROFILE.UNAVAILABLE` — When a required profile, toolchain, model, environment, or qualified operation is unavailable, return the exact technical or eligibility blocker instead of improvising qualification.

<!-- End BBK prompt module bbk-prompt-profile-qualification -->
