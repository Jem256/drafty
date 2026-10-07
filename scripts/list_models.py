"""Model availability listing helper for the owner.

Calls GET {base_url}models with the OpenAI SDK and prints every model id, highlighting any id that
contains "nemotron". Reads the key from .env and never prints it.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://api.tokenfactory.nebius.com/v1/"


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    api_key = os.getenv("NEBIUS_API_KEY")
    if not api_key:
        print("NEBIUS_API_KEY is not set. Add it to .env (see .env.example).")
        return 1

    client = OpenAI(base_url=BASE_URL, api_key=api_key)
    model_ids = sorted(model.id for model in client.models.list().data)

    print(f"{len(model_ids)} models available at {BASE_URL}:")
    for model_id in model_ids:
        marker = "  <-- nemotron" if "nemotron" in model_id.lower() else ""
        print(f"  {model_id}{marker}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
