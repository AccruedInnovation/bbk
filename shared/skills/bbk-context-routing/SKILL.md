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

- `HUMAN.REQUEST_TRIGGER` — Originate a human request only for a material decision, authority grant, private context, accountable acceptance, protected-floor exception, hard-to-reverse commitment, or other trigger this role explicitly owns. Keep routine reversible choices within standing authority.
- `HUMAN.REQUEST_PACKET` — Packet fields: stable request ID; requesting agent/role; semantic parent; exact subject/revision; kind DECISION, AUTHORITY, PRIVATE_CONTEXT, ACCEPTANCE, or PROTECTED_FLOOR_EXCEPTION; smallest exact question; current recommendation; credible alternatives/consequences; safe default if any; blocker; continuing work; expiry/invalidation; durable ref when needed; exact reply target.
- `HUMAN.REQUEST_TRANSPORT` — In OMP, resolve the peer whose kind is main; send the concise packet by hub/IRC with exact replyTo. Put long or authority-bearing content in a verified durable carrier, not IRC.
- `HUMAN.REQUEST_RESPONSE` — Only an authoritative reply bound to the stable request, exact subject, and reply target answers it. Delivery, silence, timeout, cancellation, status, or unrelated prose neither answers nor authorizes.
- `HUMAN.REQUEST_CONTINUE` — After sending, continue every independent authorized branch. Wait only if the request blocks all valid work; after a valid reply, resume the same logical role/request lineage rather than restart or change the question.
- `HUMAN.REQUEST_FALLBACK` — Without live relay, return the same packet through the invocation chain as BLOCKED_DECISION, BLOCKED_AUTHORITY, or the applicable private-context state. Never bypass the harness-root controller.
- `HUMAN.CALLBACK_SAFE_CHILDREN` — After a `BBK_USER_REQUEST` or equivalent callback, do not enter a cancellation-sensitive blocking child wait while an immediate reply may arrive, or batch both in one callback window. Integrate the bound reply before decision-dependent dispatch. Continue local analysis or independent work only through a proven non-cascading child lifetime; otherwise sequence safely and defer child dispatch.

<!-- End BBK prompt module bbk-prompt-human-request -->

## Profile context edges

<!-- BBK prompt module bbk-prompt-profile-qualification: expanded from canonical source -->

### Language, domain, toolchain, and model qualification

Select only applicable installed profiles and focused procedures without allowing them to broaden authority.

- `PROFILE.EXPLICIT` — Use only a profile explicitly supplied or selected from the current installed-profile registry for the exact language, domain, framework, runtime, or toolchain work.
- `PROFILE.FOCUSED` — Load the router and only focused procedures/gates material to this role and assertion; do not load every profile or specialist pack.
- `PROFILE.BIND` — Carry profile ID, version/digest, toolchain assumptions, required gates, qualified operations, unavailable-capability policy, and evidence bindings into child/return contracts.
- `PROFILE.NO_AUTHORITY` — Profiles, skills, tools, model routes, and host capabilities add method/evidence only; they cannot broaden scope, effects, authority, or acceptance.
- `PROFILE.UNAVAILABLE` — If a required profile, toolchain, model, environment, or qualified operation is unavailable, return the exact technical/eligibility blocker; do not invent qualification.

<!-- End BBK prompt module bbk-prompt-profile-qualification -->
