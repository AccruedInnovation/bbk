# DeepSeek Codex lifecycle fixture

This fixture documents the keyless actor boundary used by
`tests/test_codex_ds_lifecycle.py`: actor selection is explicit (`role` plus
`deepseek-v4-pro` or `deepseek-v4-flash`) and the credential is represented only
as `{ "kind": "environment", "env_key": "DEEPSEEK_API_KEY", "value_persisted": false }`.
No credential value belongs in a fixture or lifecycle manifest.

Status fixtures may show `credential_state: ABSENT` and
`provider_state: CREDENTIAL_ABSENT`; provider diagnostics use
`provider_state: ERROR` with a bounded `provider_error`. Neither state permits
silent target fallback.
