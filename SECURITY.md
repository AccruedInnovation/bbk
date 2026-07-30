# Security policy

## Reporting a vulnerability

Do not disclose a suspected security issue in a public issue when it could expose users, credentials, installations, host integrations, or target repositories.

Use GitHub private vulnerability reporting when enabled, or contact the maintainer through the private address listed in the repository profile or release metadata.

Include, where possible:

- affected BBK and host versions;
- operating system and installation scope;
- exact reproduction steps;
- files, commands, extensions, profiles, or model-routing surfaces involved;
- expected and observed behavior;
- impact and likely preconditions;
- any safe workaround;
- whether credentials or third-party systems may be affected.

## Scope

Security-relevant areas include:

- archive extraction and path traversal;
- installer ownership, backups, divergence, and uninstall;
- host extension command/context boundaries;
- model-routing and agent-definition mutation;
- profile-package verification;
- candidate/evidence identity and stale-state handling;
- unintended authority or effect escalation;
- unsafe defaults involving filesystem, network, credentials, publication, deployment, or control systems.

## Supported versions

Until BBK reaches a stable release policy, security fixes are normally made against the latest published pre-1.0 release. Historical releases may receive migration guidance rather than patched archives.

## Boundary

A BBK package qualification does not establish the security of a target project, selected model, external provider, compiler, runtime, extension host, or language-profile toolchain. Those remain separate qualification subjects.
