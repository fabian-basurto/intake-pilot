"""Deterministic review rules derived from the two reference PDFs.

    PDF A = "pdf A.pdf"  ENTYVIO (vedolizumab) infusion orders, page 1
    PDF B = "pdf B.pdf"  Referral Checklist, page 1

The AI layer only extracts. This module decides what needs attention.
Every rule cites its source so the on-screen result can be traced.
Full table: docs/RULE_MAP.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from .schema import ExtractedDocument, ExtractedField, Extraction, document_map, field_map

RuleGroup = Literal["documents", "patient", "insurance", "order", "contact"]
RuleLevel = Literal["required", "info"]
RuleStatus = Literal["ok", "not_found", "needs_review", "info"]


class CamelModel(BaseModel):
    """Serializes with camelCase keys so the frontend types stay unchanged."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, serialize_by_alias=True)


class RuleSource(CamelModel):
    pdf: Literal["A", "B"]
    page: int
    section: str


class ReviewerOverride(CamelModel):
    kind: Literal["verified", "corrected"]
    value: str | None = None
    note: str | None = None


class RuleEvidence(CamelModel):
    page: int | None
    excerpt: str | None


class RuleOutcome(CamelModel):
    status: RuleStatus
    detail: str
    value: str | None
    evidence: RuleEvidence | None


class RuleResult(RuleOutcome):
    id: str
    label: str
    group: RuleGroup
    level: RuleLevel
    source: list[RuleSource]
    request: str
    override: ReviewerOverride | None
    field_records: list[ExtractedField]
    document_records: list[ExtractedDocument]


class ReviewResult(CamelModel):
    status: Literal["clear", "attention"]
    headline: str
    subline: str
    attention_count: int
    counts: dict[str, int]
    items: list[RuleResult]


@dataclass(frozen=True)
class RuleContext:
    fields: dict[str, ExtractedField]
    documents: dict[str, ExtractedDocument]


@dataclass(frozen=True)
class Rule:
    id: str
    label: str
    group: RuleGroup
    level: RuleLevel
    source: tuple[RuleSource, ...]
    request: str
    fields: tuple[str, ...] = ()
    documents: tuple[str, ...] = ()
    evaluate: Callable[[RuleContext], RuleOutcome] | None = None


GROUP_LABELS: dict[str, str] = {
    "documents": "Supporting documents",
    "patient": "Patient demographics",
    "insurance": "Insurance",
    "order": "ENTYVIO order",
    "contact": "Referring office contact",
}

SOURCE_LABELS: dict[str, str] = {
    "A": "Reference A — ENTYVIO infusion order form",
    "B": "Reference B — Referral Checklist",
}


def _a(section: str) -> RuleSource:
    return RuleSource(pdf="A", page=1, section=section)


def _b(section: str) -> RuleSource:
    return RuleSource(pdf="B", page=1, section=section)


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------


def _first_evidence(records: list[ExtractedField | ExtractedDocument]) -> RuleEvidence | None:
    for r in records:
        if isinstance(r, ExtractedField):
            if r.evidence.page is not None or r.evidence.excerpt:
                return RuleEvidence(page=r.evidence.page, excerpt=r.evidence.excerpt)
        elif r.pages:
            return RuleEvidence(page=r.pages[0], excerpt=r.excerpt)
    return None


def _evaluate_default(rule: Rule, ctx: RuleContext) -> RuleOutcome:
    field_recs = [ctx.fields[i] for i in rule.fields if i in ctx.fields]
    doc_recs = [ctx.documents[i] for i in rule.documents if i in ctx.documents]
    all_recs: list[ExtractedField | ExtractedDocument] = [*field_recs, *doc_recs]

    uncertain = [r for r in all_recs if r.status == "uncertain"]
    missing = [r for r in all_recs if r.status == "not_found"]
    found = [r for r in all_recs if r.status == "found"]

    value = "; ".join(f.value for f in field_recs if f.value) or None
    evidence = _first_evidence(found or all_recs)
    is_info = rule.level == "info"

    if uncertain:
        note = " ".join(u.note for u in uncertain if u.note) or "Extraction could not confirm this value."
        return RuleOutcome(
            status="info" if is_info else "needs_review",
            detail=note,
            value=value,
            evidence=_first_evidence(uncertain) or evidence,
        )
    if missing:
        return RuleOutcome(
            status="info" if is_info else "not_found",
            detail="Not found in uploaded packet.",
            value=None,
            evidence=None,
        )
    pages: list[int] = []
    for d in doc_recs:
        for p in d.pages:
            if p not in pages:
                pages.append(p)
    detail = (
        f"Found on page{'s' if len(pages) > 1 else ''} {', '.join(str(p) for p in pages)}."
        if pages
        else "Found in packet."
    )
    return RuleOutcome(status="info" if is_info else "ok", detail=detail, value=value, evidence=evidence)


def _evaluate_insurance(ctx: RuleContext) -> RuleOutcome:
    front = ctx.documents.get("insurance_card_front")
    back = ctx.documents.get("insurance_card_back")
    payer = ctx.fields.get("primary_payer")
    subscriber = ctx.fields.get("primary_subscriber_name")
    member_id = ctx.fields.get("primary_member_id")
    group = ctx.fields.get("primary_group_number")

    card_recs: list[ExtractedDocument] = [d for d in (front, back) if d is not None]
    detail_recs: list[ExtractedField] = [f for f in (payer, subscriber, member_id) if f is not None]

    cards_found = len(card_recs) == 2 and all(d.status == "found" for d in card_recs)
    details_found = len(detail_recs) == 3 and all(f.status == "found" for f in detail_recs)

    detail_value: str | None = None
    if details_found:
        parts = [
            payer.value if payer else None,
            f"subscriber {subscriber.value}" if subscriber and subscriber.value else None,
            f"ID {member_id.value}" if member_id and member_id.value else None,
            f"group {group.value}" if group and group.value else None,
        ]
        detail_value = ", ".join(p for p in parts if p) or None

    if cards_found:
        pages: list[int] = []
        for d in card_recs:
            for p in d.pages:
                if p not in pages:
                    pages.append(p)
        extra = f" Payer details also listed: {detail_value}." if detail_value else ""
        return RuleOutcome(
            status="ok",
            detail=f"Insurance card front and back found on page{'s' if len(pages) > 1 else ''} {', '.join(str(p) for p in pages)}.{extra}",
            value=detail_value or "Card images attached",
            evidence=_first_evidence(list(card_recs)),
        )
    if details_found:
        one_side = any(d.status == "found" for d in card_recs)
        return RuleOutcome(
            status="ok",
            detail=(
                "Primary payer details found"
                + ("; only one side of the card was detected" if one_side else "; no card images detected")
                + ". Reference allows either."
            ),
            value=detail_value,
            evidence=_first_evidence(list(detail_recs)),
        )

    everything: list[ExtractedField | ExtractedDocument] = [*card_recs, *detail_recs]
    any_uncertain = any(r.status == "uncertain" for r in everything)
    any_partial = any(r.status == "found" for r in everything)
    if any_uncertain or any_partial:
        notes = " ".join(r.note for r in everything if r.note)
        have_parts = [
            label
            for rec, label in (
                (front, "card front"),
                (back, "card back"),
                (payer, "payer"),
                (subscriber, "subscriber"),
                (member_id, "member ID"),
            )
            if rec is not None and rec.status == "found"
        ]
        detected = ", ".join(have_parts) if have_parts else "nothing conclusive"
        return RuleOutcome(
            status="needs_review",
            detail=(
                f"Incomplete insurance evidence. Detected: {detected}. "
                f"Need both card sides, or payer + subscriber + member ID.{(' ' + notes) if notes else ''}"
            ),
            value=detail_value,
            evidence=_first_evidence([r for r in everything if r.status != "not_found"]),
        )
    return RuleOutcome(
        status="not_found",
        detail="No insurance card images and no primary payer details found in uploaded packet.",
        value=None,
        evidence=None,
    )


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

RULES: tuple[Rule, ...] = (
    # --- Supporting documents (PDF B p1 "REFERRING OFFICE, ALSO FAX") ---------
    Rule(
        id="doc_order_form",
        label="Therapy order form",
        group="documents",
        level="required",
        source=(
            _b('"Order" under REFERRING OFFICE, ALSO FAX'),
            _b("Order, Diagnosis and Clinical Information attached"),
            _a("ENTYVIO infusion orders"),
        ),
        documents=("order_form",),
        request="the completed ENTYVIO infusion order form",
    ),
    Rule(
        id="doc_recent_labs",
        label="Most recent labs",
        group="documents",
        level="required",
        source=(_b('"Most recent labs" under REFERRING OFFICE, ALSO FAX'),),
        documents=("recent_labs",),
        request="the patient's most recent labs",
    ),
    Rule(
        id="doc_clinical_notes",
        label="Supporting clinical notes",
        group="documents",
        level="required",
        source=(_b('"Supporting clinical notes" under REFERRING OFFICE, ALSO FAX'),),
        documents=("clinical_notes",),
        request="supporting clinical notes",
    ),
    # --- Patient demographics (PDF B p1; PDF A p1 header) ---------------------
    Rule(
        id="patient_name",
        label="Patient name",
        group="patient",
        level="required",
        source=(_b("Patient Demographics: Patient Name"), _a("Patient Name")),
        fields=("patient_name",),
        request="the patient's full name",
    ),
    Rule(
        id="patient_dob",
        label="Date of birth",
        group="patient",
        level="required",
        source=(_b("Patient Demographics: DOB"), _a("DOB")),
        fields=("patient_dob",),
        request="the patient's date of birth",
    ),
    Rule(
        id="patient_sex",
        label="Sex / gender",
        group="patient",
        level="required",
        source=(_b("Patient Demographics: Gender"), _a("M / F")),
        fields=("patient_sex",),
        request="the patient's sex or gender",
    ),
    Rule(
        id="patient_phone",
        label="Patient phone",
        group="patient",
        level="required",
        source=(_b("Patient Demographics: Home Phone / Mobile Phone"), _a("Phone")),
        fields=("patient_phone",),
        request="a home or mobile phone number for the patient",
    ),
    Rule(
        id="patient_address",
        label="Patient address",
        group="patient",
        level="required",
        source=(_b("Patient Demographics: Address; City, State, Zip Code"),),
        fields=("patient_address",),
        request="the patient's mailing address",
    ),
    Rule(
        id="patient_email",
        label="Patient email",
        group="patient",
        level="info",
        source=(_b("Patient Demographics: Email"),),
        fields=("patient_email",),
        request="the patient's email address",
    ),
    Rule(
        id="funded_program",
        label="Enrolled in funded program",
        group="patient",
        level="info",
        source=(_b("Enrolled in Funded Program? Yes / No / N/A"),),
        fields=("funded_program",),
        request="whether the patient is enrolled in a funded program",
    ),
    Rule(
        id="support_program_interest",
        label="Interest in patient support programs",
        group="patient",
        level="info",
        source=(_b("Patient is interested in patient support programs"),),
        fields=("support_program_interest",),
        request="whether the patient is interested in support programs",
    ),
    # --- Insurance (PDF B p1 "Patient Insurance") -----------------------------
    Rule(
        id="insurance_evidence",
        label="Insurance evidence",
        group="insurance",
        level="required",
        source=(
            _b("Front and back of insurance card attached (If YES, you may skip the Patient Insurance section)"),
            _b("Patient Insurance: Primary Payer, Subscriber Name, Group #, ID #"),
        ),
        documents=("insurance_card_front", "insurance_card_back"),
        fields=("primary_payer", "primary_subscriber_name", "primary_member_id", "primary_group_number"),
        request="a copy of the front and back of the patient's insurance card, or the primary payer, subscriber name, and member ID",
        evaluate=_evaluate_insurance,
    ),
    Rule(
        id="secondary_insurance",
        label="Secondary insurance",
        group="insurance",
        level="info",
        source=(_b("Patient Insurance: Secondary Payer"),),
        fields=("secondary_payer",),
        request="secondary insurance details",
    ),
    # --- Order (PDF A p1) -----------------------------------------------------
    Rule(
        id="diagnosis",
        label="Diagnosis",
        group="order",
        level="required",
        source=(_a("DIAGNOSIS: Ulcerative Colitis / Crohn's Disease / other"),),
        fields=("diagnosis",),
        request="the diagnosis selected on the order form",
    ),
    Rule(
        id="icd10_code",
        label="ICD-10 code",
        group="order",
        level="required",
        source=(_a('DIAGNOSIS: "Please provide ICD-10 code"'),),
        fields=("icd10_code",),
        request="the ICD-10 code for the diagnosis",
    ),
    Rule(
        id="dosage",
        label="Dosage",
        group="order",
        level="info",
        source=(_a("ENTYVIO ORDERS: DOSAGE 300mg IV (pre-printed)"),),
        fields=("dosage",),
        request="the ordered dosage",
    ),
    Rule(
        id="infusion_frequency",
        label="Infusion frequency",
        group="order",
        level="required",
        source=(_a('FREQUENCY: "Dose at weeks 0, 2, and 6, then every 8 weeks" OR "Dose every __ weeks"'),),
        fields=("infusion_frequency",),
        request="a single selected infusion frequency on the order form",
    ),
    Rule(
        id="patient_weight",
        label="Patient weight",
        group="order",
        level="required",
        source=(_a("PATIENT WEIGHT: lbs / kg"),),
        fields=("patient_weight",),
        request="the patient's current weight",
    ),
    Rule(
        id="premedication",
        label="Pre-medication",
        group="order",
        level="info",
        source=(_a("PRE-MEDICATION checkboxes"),),
        fields=("premedication",),
        request="pre-medication selections",
    ),
    Rule(
        id="order_notes",
        label="Order notes",
        group="order",
        level="info",
        source=(_a("NOTES"),),
        fields=("order_notes",),
        request="order notes",
    ),
    Rule(
        id="provider_signature",
        label="Provider signature",
        group="order",
        level="required",
        source=(_a("ORDERING PROVIDER: Signature X"),),
        fields=("provider_signature",),
        request="a signed order form",
    ),
    Rule(
        id="signature_date",
        label="Signature date",
        group="order",
        level="required",
        source=(_a("ORDERING PROVIDER: Date"),),
        fields=("signature_date",),
        request="the date the order was signed",
    ),
    Rule(
        id="provider_name",
        label="Ordering provider",
        group="order",
        level="required",
        source=(_a("ORDERING PROVIDER: Provider"),),
        fields=("provider_name",),
        request="the ordering provider's name",
    ),
    Rule(
        id="provider_phone",
        label="Provider phone",
        group="order",
        level="required",
        source=(_a("ORDERING PROVIDER: Phone"),),
        fields=("provider_phone",),
        request="the ordering provider's phone number",
    ),
    Rule(
        id="provider_fax",
        label="Provider fax",
        group="order",
        level="required",
        source=(_a("ORDERING PROVIDER: Fax"),),
        fields=("provider_fax",),
        request="the ordering provider's fax number",
    ),
    # --- Referring office contact (PDF B p1 "Contact Information*") -----------
    Rule(
        id="contact_name",
        label="Office contact name",
        group="contact",
        level="required",
        source=(_b("Contact Information: Contact Name"),),
        fields=("contact_name",),
        request="a contact name at the referring office",
    ),
    Rule(
        id="practice_name",
        label="Practice name",
        group="contact",
        level="required",
        source=(_b("Contact Information: Practice Name"),),
        fields=("practice_name",),
        request="the referring practice name",
    ),
    Rule(
        id="contact_phone",
        label="Office contact phone",
        group="contact",
        level="required",
        source=(_b("Contact Information: Phone"),),
        fields=("contact_phone",),
        request="a phone number for the referring office contact",
    ),
    Rule(
        id="contact_title",
        label="Contact title",
        group="contact",
        level="info",
        source=(_b("Contact Information: Title"),),
        fields=("contact_title",),
        request="the contact's title",
    ),
    Rule(
        id="contact_email",
        label="Contact email",
        group="contact",
        level="info",
        source=(_b("Contact Information: Email"),),
        fields=("contact_email",),
        request="the contact's email address",
    ),
)

RULES_BY_ID: dict[str, Rule] = {r.id: r for r in RULES}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _apply_override(outcome: RuleOutcome, override: ReviewerOverride | None) -> RuleOutcome:
    if override is None:
        return outcome
    if override.kind == "corrected":
        return RuleOutcome(
            status="ok",
            detail=f"Corrected by staff{(': ' + override.note) if override.note else '.'}",
            value=override.value if override.value is not None else outcome.value,
            evidence=outcome.evidence,
        )
    return RuleOutcome(
        status="ok",
        detail=f"Verified by staff{(': ' + override.note) if override.note else '.'}",
        value=outcome.value,
        evidence=outcome.evidence,
    )


def evaluate(extraction: Extraction, overrides: dict[str, ReviewerOverride] | None = None) -> ReviewResult:
    overrides = overrides or {}
    ctx = RuleContext(fields=field_map(extraction), documents=document_map(extraction))

    items: list[RuleResult] = []
    for rule in RULES:
        base = rule.evaluate(ctx) if rule.evaluate else _evaluate_default(rule, ctx)
        override = overrides.get(rule.id)
        outcome = _apply_override(base, override)
        items.append(
            RuleResult(
                **outcome.model_dump(),
                id=rule.id,
                label=rule.label,
                group=rule.group,
                level=rule.level,
                source=list(rule.source),
                request=rule.request,
                override=override,
                field_records=[ctx.fields[i] for i in rule.fields if i in ctx.fields],
                document_records=[ctx.documents[i] for i in rule.documents if i in ctx.documents],
            )
        )

    counts = {"ok": 0, "not_found": 0, "needs_review": 0, "info": 0}
    for it in items:
        counts[it.status] += 1
    attention = counts["not_found"] + counts["needs_review"]

    if attention == 0:
        headline = "No documentation gaps detected"
        subline = (
            "All checklist items were located in the uploaded packet. "
            "Pending staff verification before intake proceeds."
        )
    else:
        headline = f"Review required — {attention} item{'' if attention == 1 else 's'}"
        parts = []
        if counts["not_found"]:
            parts.append(f"{counts['not_found']} not found in uploaded packet")
        if counts["needs_review"]:
            parts.append(f"{counts['needs_review']} need{'s' if counts['needs_review'] == 1 else ''} staff review")
        subline = " · ".join(parts)

    return ReviewResult(
        status="clear" if attention == 0 else "attention",
        headline=headline,
        subline=subline,
        attention_count=attention,
        counts=counts,
        items=items,
    )


def rule_map() -> list[dict]:
    """Developer-facing rule provenance, for GET /api/rules."""
    return [
        {
            "id": r.id,
            "label": r.label,
            "group": r.group,
            "level": r.level,
            "fields": list(r.fields),
            "documents": list(r.documents),
            "request": r.request,
            "source": [s.model_dump() for s in r.source],
        }
        for r in RULES
    ]
