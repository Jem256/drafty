# Drafty

Drafty turns a plain-language road brief into a **checked first-draft drainage design**: a DXF drawing
(plan, typical cross-section, long-section), a drain schedule and rough quantities. A deterministic
engine computes every number; a rule checker judges the design; NVIDIA Nemotron models on Nebius Token
Factory parse the brief, draft the layout with tool calls and revise it until the checks pass.

It is a drafting assistant for engineer review, **not** a certified design.

## Quickstart

```bash
uv sync
uv run uvicorn drafty.api.main:app --reload --port 8000
cd frontend && npm install && npm run dev
```

## Commands

```bash
uv sync                                   # install Python deps
uv run ruff check . && uv run ruff format --check .
uv run pytest                             # offline tests
uv run pytest -m live                     # live Token Factory tests (needs NEBIUS_API_KEY)
uv run uvicorn drafty.api.main:app --reload --port 8000
cd frontend && npm install && npm run dev
uv run python -m drafty.evals.run_evals --set smoke   # 5-brief smoke eval
uv run python scripts/list_models.py      # owner: find Nemotron model IDs
docker build -t drafty:dev .
```

## Licence

MIT. See [LICENSE](LICENSE).
