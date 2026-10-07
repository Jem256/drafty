# Drafty handoff pack

How to use this pack with Claude Code and DeepSeek-based coding agents.

1. Create an empty public GitHub repo `drafty` and copy everything in this folder into it.
   Delete this file afterwards if you like.
2. Do the "Before Phase 0" items in `docs/human-tasks.md`.
3. Open the repo in your agent. Claude Code reads `CLAUDE.md` (which imports `AGENTS.md`); most
   other agents read `AGENTS.md` directly. If your DeepSeek tool reads neither, paste `AGENTS.md`
   as the first message of each session.
4. Paste `docs/prompts/phase-0-scaffold.md` and let the agent work. Review its report.
5. Continue phase by phase using the table in `docs/prompts/README.md`, doing your own tasks from
   `docs/human-tasks.md` when a phase needs them.

What's here:

| Path | Purpose |
| --- | --- |
| `AGENTS.md` | Rules, decisions, commands for every agent |
| `CLAUDE.md` | Claude Code entry point (imports AGENTS.md) |
| `docs/architecture.md` | What to build: the design reference |
| `docs/plan.md` | When: phases, testing method, brief set, rule compliance |
| `docs/human-tasks.md` | Your checklist; agents must not do these |
| `docs/prompts/` | One paste-ready prompt per phase |
| `config/models.yaml` | Role → Nemotron model mapping; you fill the IDs |
| `config/standards.yaml` | Engineering thresholds; you fill from the design manual |
| `tests/fixtures/test_standards.yaml` | Test-only numbers so the engine can be tested now |

Defaults chosen (change in AGENTS.md if you disagree): MIT licence, React + Vite + TypeScript,
GitHub Container Registry, open demo URL with rate limits and token caps, revision cap 5.
