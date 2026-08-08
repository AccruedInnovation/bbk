# Changelog

## 1.0.0 — 2026-08-05

- Initial standalone release.
- Supports JSONL files, recursive directories, and ZIP archives.
- Emits session, command, function, patch, skill-read, role, category, tool, duplicate, warning, and summary reports.
- Adds before/after comparison reports.
- Includes configurable command categories and role classes.
- Defaults to local command redaction and never exports raw message bodies or raw tool outputs.
- Includes standard-library unit tests and PowerShell/POSIX wrappers.
