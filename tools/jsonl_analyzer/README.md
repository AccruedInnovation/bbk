# BBK Codex JSONL Analyzer

`bbk-jsonl-analyzer` is a dependency-free Python CLI for inspecting Codex rollout logs. It accepts raw `.jsonl` files, directories, and ZIP archives and produces the same classes of evidence used for the BBK execution-efficiency reviews: session inventory, role distribution, shell/tool use, skill-file rereads, handoff and schema operations, patch paths, polling, token totals, command repetition, and before/after comparisons.

The analyzer does not send data anywhere. It reads local files and writes local CSV, JSON, and Markdown reports.

## Requirements

- Python 3.11 or newer.
- No third-party Python packages.

Windows installations normally expose Python through `py -3`; Linux and macOS normally use `python3`.

## Analyze a ZIP archive

Windows PowerShell:

```powershell
py -3 .\bbk_jsonl_analyzer.py analyze `
  "D:\Logs\codex_run.zip" `
  --output "D:\Logs\codex_run_analysis" `
  --label "alpha17-rc3"
```

The included wrapper is equivalent:

```powershell
.\analyze.ps1 `
  -InputPath "D:\Logs\codex_run.zip" `
  -OutputPath "D:\Logs\codex_run_analysis" `
  -Label "alpha17-rc3"
```

Linux/macOS:

```bash
python3 ./bbk_jsonl_analyzer.py analyze \
  ./codex_run.zip \
  --output ./codex_run_analysis \
  --label alpha17-rc3
```

You may supply several inputs. Directories are searched recursively for `.jsonl` and `.zip` files:

```powershell
py -3 .\bbk_jsonl_analyzer.py analyze `
  "D:\Logs\campaign-part-1" `
  "D:\Logs\campaign-part-2.zip" `
  --output "D:\Logs\combined-analysis"
```

## Compare two runs

First analyze each corpus independently, then compare their report directories:

```powershell
py -3 .\bbk_jsonl_analyzer.py compare `
  "D:\Logs\before-analysis" `
  "D:\Logs\after-analysis" `
  --output "D:\Logs\comparison" `
  --before-label "before" `
  --after-label "after"
```

This writes `comparison.json`, `comparison.csv`, and `comparison.md`.

## Output files

Each analysis directory contains:

| File | Purpose |
|---|---|
| `summary.md` | Human-readable campaign summary and diagnostic indicators. |
| `summary.json` | Stable machine-readable summary for comparison or ingestion. |
| `sessions.csv` | One row per rollout/session, including role, model, effort, duration, tokens, tools, functions, and command categories. |
| `commands.csv` | One row per `tools.shell_command` invocation, with hashes, category flags, skill references, exit code, and output size. |
| `function_calls.csv` | Collaboration calls such as `spawn_agent`, `followup_task`, `wait_agent`, `list_agents`, and `send_message`. |
| `patches.csv` | Paths reported by `patch_apply_end`, including add/update/delete and success state. |
| `skill_reads.csv` | Per-skill read/search events, including repeated reads in the same session. |
| `role_summary.csv` | Aggregated sessions, time, commands, tokens, and coordination calls by role. |
| `category_summary.csv` | Command-category totals and affected session/role counts. |
| `tool_summary.csv` | Internal tool and collaboration-function totals. |
| `structured_event_summary.csv` | Alpha.17 structured observability event totals when a matching configuration is supplied. |
| `duplicate_commands.csv` | Whitespace-normalized commands appearing more than once. |
| `warnings.csv` | Malformed JSON lines or shell invocations whose command text was dynamic/unparseable. |

## Command-text privacy modes

The parser always classifies the full command in memory. `--command-text` controls what is written to CSV:

- `redacted` — default. Redacts obvious secret assignments, bearer values, and large opaque literals.
- `full` — writes full command text. Use only with trusted local storage.
- `hash-only` — writes command hashes and classifications but no command text.
- `none` — currently equivalent to `hash-only`; retained for explicit policy configuration.

Raw user/developer/assistant message bodies and raw tool outputs are never exported. Tool-output character counts and exit codes are retained.

## Custom patterns and role classes

Write the default configuration:

```powershell
py -3 .\bbk_jsonl_analyzer.py init-config .\my-config.json
```

Edit the JSON and pass it with `--config`. Overrides are deep-merged with the defaults, so a file may replace one pattern without copying the full configuration.

The distribution includes `alpha17-config.json`, which classifies compiled-procedure selection/suppression/reuse, rolling-wave readiness, specialist triggers, atomic finalization, replay admission, workspace receipts, and project coverage.

Example:

```json
{
  "command_categories": {
    "project_validator": {
      "pattern": "(?i)python(?:\\.exe)?\\s+tools/project_validate\\.py",
      "description": "Project-specific validator"
    }
  },
  "role_classes": {
    "execution": [
      "^bbk_root_orchestrator$",
      "^bbk_territory_orchestrator$",
      "^bbk_worker_orchestrator$",
      "^bbk_worker$",
      "^custom_executor$"
    ]
  }
}
```

## Counting methodology

- A **custom tool execution block** is one `response_item/custom_tool_call` record.
- A **direct shell call** is one syntactic `tools.shell_command(...)` occurrence in the custom tool input. A JavaScript loop that invokes one syntactic call several times is counted once and reported as a dynamic-command warning; this matches the observable static call unit in the logs.
- Token values use the maximum cumulative `total_token_usage` seen in each session, then sum those per-session totals.
- Skill reads include content reads and content searches (`Get-Content`, `cat`, `rg`, `Select-String`, and similar) against a `SKILL.md` path.
- Skill-output characters are divided evenly among unique skill references in one custom call. `output_chars_call_total` preserves the underlying call total.
- Exact duplicate counts exclude the first occurrence. Normalized duplicates collapse whitespace before hashing.
- Session durations overlap. `summed_session_duration_seconds` is useful as an activity/load measure; `campaign_span_seconds` is the actual earliest-to-latest wall span.
- Built-in diagnostic indicators are heuristics, not pass/fail or correctness determinations.

## Run the tests

```powershell
py -3 -m unittest discover -s .\tests -v
```

or:

```bash
python3 -m unittest discover -s ./tests -v
```

## Optional installation

The single file can be run directly. To install a `bbk-jsonl-analyzer` command into an isolated virtual environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
bbk-jsonl-analyzer --help
```

On Windows, activate with `.venv\Scripts\Activate.ps1`.

## Known limitations

- Codex JSONL is not a declared stable public schema. The analyzer is tolerant of unknown record types but may need pattern or parser updates after host changes.
- Commands generated dynamically inside JavaScript loops cannot always be recovered exactly from the static custom-tool input. They remain counted at the syntactic call site and appear in `warnings.csv`.
- Command regex categories indicate that text matched; they do not establish that the command succeeded. Use `output_exit_code` and the underlying evidence when success matters.
- Token counters are reported as present in the logs and may include large cached-input totals.
