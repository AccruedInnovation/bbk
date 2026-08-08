# Alpha.17 governed vertical-slice fixture

This deliberately small project is the permanent, keyless release fixture for
`VER-036`. Two isolated worker attempts own disjoint `backend/` and
`frontend/` paths. The content-neutral integration adapter combines their
changes, after which a real declared mise task verifies the exact integrated
candidate. Review and validation remain read-only.

The fixture contains no provider calls, credentials, telemetry, dependency
installation, or external network step.
