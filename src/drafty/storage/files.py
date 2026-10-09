"""Run file storage behind one interface.

Local disk now; the S3 backend is added in Phase 6 and selected with ``STORAGE_BACKEND``.
"""

from __future__ import annotations

from pathlib import Path


class LocalFileStore:
    """Stores run files under ``<base_dir>/runs/<run_id>/``."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)

    def _path(self, run_id: str, name: str) -> Path:
        return self.base_dir / "runs" / run_id / name

    def write(self, run_id: str, name: str, data: bytes) -> str:
        path = self._path(run_id, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def read(self, run_id: str, name: str) -> bytes:
        return self._path(run_id, name).read_bytes()

    def exists(self, run_id: str, name: str) -> bool:
        return self._path(run_id, name).is_file()

    def local_path(self, run_id: str, name: str) -> Path:
        return self._path(run_id, name)
