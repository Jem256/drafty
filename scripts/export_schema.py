"""Export the DesignSpec JSON schema for the parse call.

Writes ``src/drafty/spec/schema.json`` from ``DesignSpec.model_json_schema()``. Run after any change
to the spec models so the schema handed to the model stays in step.
"""

from __future__ import annotations

import json
from pathlib import Path

from drafty.spec.models import DesignSpec

OUTPUT = Path(__file__).resolve().parents[1] / "src" / "drafty" / "spec" / "schema.json"


def main() -> None:
    OUTPUT.write_text(json.dumps(DesignSpec.model_json_schema(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
