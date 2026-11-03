"""Registry of the synthetic sample packets shipped with the demo."""

from __future__ import annotations

from pathlib import Path

from .config import SAMPLES_DIR

SAMPLES: dict[str, dict[str, str]] = {
    "complete": {
        "file": "packet_complete.pdf",
        "label": "Complete packet",
        "description": "All checklist categories present",
    },
    "incomplete": {
        "file": "packet_incomplete.pdf",
        "label": "Missing documentation",
        "description": "Two categories omitted",
    },
    "ambiguous": {
        "file": "packet_ambiguous.pdf",
        "label": "Ambiguous packet",
        "description": "One conflicting order field",
    },
}


def sample_path(key: str) -> Path:
    return SAMPLES_DIR / SAMPLES[key]["file"]


def sample_url(key: str) -> str:
    return f"/api/samples/{key}/file"


def list_samples() -> list[dict[str, object]]:
    return [
        {
            "key": key,
            "file": s["file"],
            "label": s["label"],
            "description": s["description"],
            "available": sample_path(key).is_file(),
            "url": sample_url(key),
        }
        for key, s in SAMPLES.items()
    ]
