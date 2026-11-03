"""Small PDF helpers. Never logs document contents."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader


def looks_like_pdf(data: bytes) -> bool:
    return data[:4] == b"%PDF"


def count_pages(data: bytes) -> int | None:
    try:
        reader = PdfReader(BytesIO(data), strict=False)
        return len(reader.pages)
    except Exception:
        return None
