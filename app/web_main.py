"""Entrypoint for web frontend service."""

from __future__ import annotations

import sys
from pathlib import Path

import uvicorn


def main() -> None:
    # Allow launching from either project root or app/ directory.
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    uvicorn.run("app.web_app:app", host="0.0.0.0", port=8080, reload=False)


if __name__ == "__main__":
    main()
