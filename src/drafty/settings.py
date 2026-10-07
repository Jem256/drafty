"""Environment-driven settings and filesystem paths for Drafty."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
DEFAULT_MODELS_PATH = CONFIG_DIR / "models.yaml"
DEFAULT_STANDARDS_PATH = CONFIG_DIR / "standards.yaml"


def _int_env(name: str, default: int | None) -> int | None:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class Settings:
    """Resolved runtime configuration. Secrets are read directly from the environment."""

    data_dir: Path
    storage_backend: str
    models_path: Path
    standards_path: Path
    run_token_budget: int | None
    daily_token_cap: int | None
    max_concurrency: int
    rate_limit_per_hour: int
    s3_endpoint_url: str | None
    s3_bucket: str | None
    s3_access_key_id: str | None
    s3_secret_access_key: str | None


def load_settings(env_file: str | Path | None = None) -> Settings:
    """Load settings from the environment, optionally seeding it from a .env file."""
    load_dotenv(env_file if env_file is not None else REPO_ROOT / ".env")

    data_dir = Path(os.getenv("DATA_DIR", "./data")).expanduser()
    if not data_dir.is_absolute():
        data_dir = (REPO_ROOT / data_dir).resolve()

    return Settings(
        data_dir=data_dir,
        storage_backend=os.getenv("STORAGE_BACKEND", "local"),
        models_path=DEFAULT_MODELS_PATH,
        standards_path=DEFAULT_STANDARDS_PATH,
        run_token_budget=_int_env("RUN_TOKEN_BUDGET", None),
        daily_token_cap=_int_env("DAILY_TOKEN_CAP", None),
        max_concurrency=_int_env("MAX_CONCURRENCY", 4) or 4,
        rate_limit_per_hour=_int_env("RATE_LIMIT_PER_HOUR", 20) or 20,
        s3_endpoint_url=os.getenv("S3_ENDPOINT_URL") or None,
        s3_bucket=os.getenv("S3_BUCKET") or None,
        s3_access_key_id=os.getenv("S3_ACCESS_KEY_ID") or None,
        s3_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY") or None,
    )


settings = load_settings()
