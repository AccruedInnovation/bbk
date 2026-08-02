# Claude Code Adapter Notes

Claude Code agents are generated as Markdown files in `.claude/agents/` or `~/.claude/agents/`. BBK converts underscore role IDs to lowercase hyphenated names, injects each role's mandatory BBK procedure core directly into its agent prompt, and assigns `isolation: worktree` to mutating worker/prototyper roles. Roles with children include only their allowed `Agent` types; nested delegation additionally requires the host setting `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`.

The visible Claude Code main session is the harness root controller. Canonical BBK agents are non-user-facing children and never receive `AskUserQuestion`. They return or message structured human-decision packets to the main session instead of fabricating consent. Host tool availability and worktree isolation do not broaden semantic authority.
