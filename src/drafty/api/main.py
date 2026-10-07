"""Drafty FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="Drafty", description="First-draft road drainage design assistant.")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
