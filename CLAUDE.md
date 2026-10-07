@AGENTS.md

## Claude Code notes

- AGENTS.md above is the source of truth for rules, decisions and commands. This file only adds
  Claude Code specifics.
- Start each phase in plan mode: read the phase prompt in `docs/prompts/`, propose a plan, and wait
  for approval before editing files.
- Use the task list to track the phase's tasks and tick them off as tests pass.
- Do not run `uv run pytest -m live` or any command that spends Token Factory credits unless the
  phase prompt or the owner asks for it.
