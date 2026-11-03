from __future__ import annotations

from typing import Any, Callable

import pytest

from app.schema import DOCUMENT_IDS, FIELD_IDS, Extraction

FieldOverrides = dict[str, dict[str, Any]]


def _full_extraction(fields: FieldOverrides | None = None, documents: FieldOverrides | None = None) -> Extraction:
    """Every field and document found, with per-id overrides, mirroring the handoff's complete packet."""
    fields = fields or {}
    documents = documents or {}
    return Extraction.model_validate(
        {
            "fields": [
                {
                    "field": fid,
                    "status": "found",
                    "value": f"sample {fid}",
                    "evidence": {"page": 1, "excerpt": f"excerpt {fid}"},
                    "note": None,
                    **fields.get(fid, {}),
                }
                for fid in FIELD_IDS
            ],
            "documents": [
                {
                    "category": did,
                    "status": "found",
                    "pages": [2],
                    "excerpt": f"heading {did}",
                    "note": None,
                    **documents.get(did, {}),
                }
                for did in DOCUMENT_IDS
            ],
            "page_summary": [{"page": 1, "description": "cover"}],
            "packet_notes": None,
        }
    )


NOT_FOUND_FIELD = {"status": "not_found", "value": None, "evidence": {"page": None, "excerpt": None}}
NOT_FOUND_DOC = {"status": "not_found", "pages": [], "excerpt": None}


def _incomplete_extraction() -> Extraction:
    """No labs and no insurance evidence of either kind: the handoff's two-gap packet."""
    return _full_extraction(
        fields={
            "primary_payer": NOT_FOUND_FIELD,
            "primary_subscriber_name": NOT_FOUND_FIELD,
            "primary_member_id": NOT_FOUND_FIELD,
            "primary_group_number": NOT_FOUND_FIELD,
        },
        documents={
            "recent_labs": NOT_FOUND_DOC,
            "insurance_card_front": NOT_FOUND_DOC,
            "insurance_card_back": NOT_FOUND_DOC,
        },
    )


@pytest.fixture
def full_extraction() -> Callable[..., Extraction]:
    return _full_extraction


@pytest.fixture
def incomplete_extraction() -> Extraction:
    return _incomplete_extraction()
