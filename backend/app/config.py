"""Runtime settings. Secrets come from the environment or backend/.env (never from the frontend)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")  # does not override variables already set in the environment

# Model used for extraction. gpt-4.1 is documented for PDF file input with Structured Outputs.
MODEL_ID: str = os.environ.get("OPENAI_MODEL", "").strip() or "gpt-4.1"
MAX_UPLOAD_BYTES: int = 20 * 1024 * 1024  # 20 MB upload limit for the demo
MAX_PAGES: int = 100
SAMPLES_DIR: Path = Path(os.environ.get("SAMPLES_DIR") or BACKEND_DIR / "samples")
ALLOWED_ORIGINS: list[str] = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]


def api_key_configured() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))
