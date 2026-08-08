---
name: fixture_worker
description: BBK OMP host-contract child identity fixture
model: "bbk-mock/mock-model"
thinkingLevel: "off"
blocking: true
---

FIXTURE_CHILD_MARKER

Call `bbk_fixture_identity` exactly once with `value` set to `child`, then submit a successful terminal `yield` result.
