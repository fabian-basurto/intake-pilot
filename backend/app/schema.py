"""Extraction contract between the AI layer and the rules layer.

Field ids and document category ids are derived from the two reference PDFs.
See docs/RULE_MAP.md for the page-level source of each one.
"""

from __future__ import annotations

from typing import Literal, get_args

from pydantic import BaseModel, Field

FieldId = Literal[
    # Patient demographics (PDF B p1; PDF A p1 header)
    "patient_name",
    "patient_dob",
    "patient_sex",
    "patient_phone",
    "patient_address",
    "patient_email",
    "funded_program",
    "support_program_interest",
    # Insurance (PDF B p1)
    "primary_payer",
    "primary_subscriber_name",
    "primary_member_id",
    "primary_group_number",
    "secondary_payer",
    # Order (PDF A p1)
    "diagnosis",
    "icd10_code",
    "dosage",
    "infusion_frequency",
    "patient_weight",
    "premedication",
    "order_notes",
    "provider_signature",
    "signature_date",
    "provider_name",
    "provider_phone",
    "provider_fax",
    # Referring office contact (PDF B p1)
    "contact_name",
    "practice_name",
    "contact_title",
    "contact_phone",
    "contact_email",
]

DocumentId = Literal[
    "order_form",
    "recent_labs",
    "clinical_notes",
    "insurance_card_front",
    "insurance_card_back",
    "referral_checklist",
]

ExtractionStatus = Literal["found", "not_found", "uncertain"]

FIELD_IDS: tuple[str, ...] = get_args(FieldId)
DOCUMENT_IDS: tuple[str, ...] = get_args(DocumentId)
STATUSES: frozenset[str] = frozenset(get_args(ExtractionStatus))


class Evidence(BaseModel):
    page: int | None = Field(description="1-based page number where the value was observed, or null")
    excerpt: str | None = Field(
        description="Short verbatim excerpt (under 160 characters) supporting the value, or null"
    )


class ExtractedField(BaseModel):
    field: FieldId
    status: ExtractionStatus
    value: str | None = Field(description="The completed value as written. Null when not found.")
    evidence: Evidence
    note: str | None = Field(
        description="Why the status is uncertain, or a caveat about the value. Null otherwise."
    )


class ExtractedDocument(BaseModel):
    category: DocumentId
    status: ExtractionStatus
    pages: list[int] = Field(description="1-based page numbers where this document type appears")
    excerpt: str | None = Field(description="Short excerpt such as a heading that identifies the document")
    note: str | None


class PageSummary(BaseModel):
    page: int
    description: str = Field(description="One short line describing what the page contains")


class Extraction(BaseModel):
    fields: list[ExtractedField]
    documents: list[ExtractedDocument]
    page_summary: list[PageSummary]
    packet_notes: str | None = Field(
        description="Any cross-page inconsistency or legibility problem worth telling staff. Null if none."
    )


def field_map(extraction: Extraction) -> dict[str, ExtractedField]:
    """First occurrence wins; the model is asked for exactly one record per field."""
    out: dict[str, ExtractedField] = {}
    for f in extraction.fields:
        out.setdefault(f.field, f)
    return out


def document_map(extraction: Extraction) -> dict[str, ExtractedDocument]:
    out: dict[str, ExtractedDocument] = {}
    for d in extraction.documents:
        out.setdefault(d.category, d)
    return out


def normalize_extraction(raw: Extraction) -> Extraction:
    """Fill in any field or document the model omitted so the rules always have a record."""
    fields = field_map(raw)
    docs = document_map(raw)
    return Extraction(
        fields=[
            fields.get(fid)
            or ExtractedField(
                field=fid,  # type: ignore[arg-type]
                status="not_found",
                value=None,
                evidence=Evidence(page=None, excerpt=None),
                note="Not reported by extraction",
            )
            for fid in FIELD_IDS
        ],
        documents=[
            docs.get(did)
            or ExtractedDocument(
                category=did,  # type: ignore[arg-type]
                status="not_found",
                pages=[],
                excerpt=None,
                note="Not reported by extraction",
            )
            for did in DOCUMENT_IDS
        ],
        page_summary=sorted(raw.page_summary, key=lambda p: p.page),
        packet_notes=raw.packet_notes,
    )
