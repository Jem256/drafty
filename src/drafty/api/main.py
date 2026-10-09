"""Drafty FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from drafty import settings as settings_module
from drafty.agent.llm import LLM
from drafty.api.ratelimit import RateLimiter, RateLimitExceeded
from drafty.api.routes import router
from drafty.api.services import RunService
from drafty.engine.standards import Standards
from drafty.settings import REPO_ROOT
from drafty.storage.db import Database
from drafty.storage.files import LocalFileStore

FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"


def build_service() -> RunService:
    """Build the production service from settings. The model is created lazily per run."""
    settings = settings_module.settings
    limits = {
        "revision_cap": 5,
        "parse_retries": 2,
        "invalid_drafts_before_cascade": 2,
        "run_token_budget": settings.run_token_budget,
        "daily_token_cap": settings.daily_token_cap,
    }
    return RunService(
        db=Database(settings.data_dir / "drafty.db"),
        standards=Standards.load(settings.standards_path),
        llm_factory=lambda: LLM(setup="routed"),
        file_store=LocalFileStore(settings.data_dir),
        data_dir=settings.data_dir,
        limits=limits,
        render=True,
        rate_limiter=RateLimiter(settings.rate_limit_per_hour, settings.daily_token_cap),
        daily_token_cap=settings.daily_token_cap,
    )


def create_app(service: RunService | None = None) -> FastAPI:
    app = FastAPI(title="Drafty", description="First-draft road drainage design assistant.")
    app.state.service = service or build_service()
    app.include_router(router)

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    if FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    return app


app = create_app()
