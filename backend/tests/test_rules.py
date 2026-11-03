"""Offline checks of the deterministic rules layer and the draft builder. No API call."""

from __future__ import annotations

from app.draft import build_draft
from app.rules import RULES, ReviewerOverride, evaluate, rule_map
from tests.conftest import NOT_FOUND_DOC, NOT_FOUND_FIELD


def test_complete_packet_is_clear(full_extraction):
    ex = full_extraction()
    r = evaluate(ex)
    assert r.attention_count == 0
    assert r.status == "clear"
    assert r.headline == "No documentation gaps detected"
    assert "all expected documentation was located" in build_draft(r, ex, "x.pdf")


def test_incomplete_packet_flags_exactly_two(incomplete_extraction):
    r = evaluate(incomplete_extraction)
    flagged = sorted(i.id for i in r.items if i.status == "not_found")
    assert flagged == ["doc_recent_labs", "insurance_evidence"]
    assert "2 items" in r.headline
    assert r.subline == "2 not found in uploaded packet"
    draft = build_draft(r, incomplete_extraction, "x.pdf")
    assert "most recent labs" in draft
    assert "insurance card" in draft.lower()
    assert "supporting clinical notes" not in draft
    assert "[Draft for staff review — not sent]" in draft


def test_override_clears_item_and_changes_draft(incomplete_extraction):
    r = evaluate(incomplete_extraction, {"insurance_evidence": ReviewerOverride(kind="verified", note="Card on file")})
    assert r.attention_count == 1
    item = next(i for i in r.items if i.id == "insurance_evidence")
    assert item.status == "ok"
    assert item.detail == "Verified by staff: Card on file"
    assert item.override is not None and item.override.kind == "verified"
    assert "insurance card" not in build_draft(r, incomplete_extraction, "x.pdf").lower()


def test_insurance_any_of_details_without_cards(full_extraction):
    ex = full_extraction(documents={"insurance_card_front": NOT_FOUND_DOC, "insurance_card_back": NOT_FOUND_DOC})
    item = next(i for i in evaluate(ex).items if i.id == "insurance_evidence")
    assert item.status == "ok"
    assert "no card images detected" in item.detail


def test_insurance_partial_needs_review(full_extraction):
    ex = full_extraction(
        documents={"insurance_card_back": NOT_FOUND_DOC},
        fields={
            "primary_payer": NOT_FOUND_FIELD,
            "primary_subscriber_name": NOT_FOUND_FIELD,
            "primary_member_id": NOT_FOUND_FIELD,
        },
    )
    item = next(i for i in evaluate(ex).items if i.id == "insurance_evidence")
    assert item.status == "needs_review"
    assert "Detected: card front" in item.detail


def test_ambiguous_frequency_needs_review_and_correction_clears(full_extraction):
    ex = full_extraction(
        fields={"infusion_frequency": {"status": "uncertain", "value": "induction AND every 4 weeks", "note": "Both frequency options are marked."}}
    )
    r = evaluate(ex)
    item = next(i for i in r.items if i.id == "infusion_frequency")
    assert item.status == "needs_review"
    assert "Both frequency options" in item.detail
    assert r.attention_count == 1
    assert r.subline == "1 needs staff review"

    corrected = evaluate(ex, {"infusion_frequency": ReviewerOverride(kind="corrected", value="Weeks 0, 2, 6 then every 8 weeks", note="Confirmed with office")})
    assert corrected.attention_count == 0
    fixed = next(i for i in corrected.items if i.id == "infusion_frequency")
    assert fixed.value == "Weeks 0, 2, 6 then every 8 weeks"
    assert fixed.detail.startswith("Corrected by staff")


def test_info_level_fields_never_count(full_extraction):
    ex = full_extraction(
        fields={
            "patient_email": NOT_FOUND_FIELD,
            "premedication": {"status": "uncertain", "value": None, "note": "smudged"},
            "contact_title": NOT_FOUND_FIELD,
        }
    )
    r = evaluate(ex)
    assert r.attention_count == 0
    assert next(i for i in r.items if i.id == "premedication").status == "info"


def test_every_rule_cites_a_reference_page():
    for rule in RULES:
        assert rule.source, rule.id
        for s in rule.source:
            assert s.pdf in ("A", "B") and s.page == 1 and s.section
    assert len({r.id for r in RULES}) == len(RULES)


def test_rule_map_is_serializable():
    rows = rule_map()
    assert len(rows) == len(RULES)
    assert rows[0]["source"][0]["pdf"] in ("A", "B")


def test_review_serializes_camel_case(incomplete_extraction):
    data = evaluate(incomplete_extraction).model_dump(by_alias=True)
    assert "attentionCount" in data
    assert "fieldRecords" in data["items"][0]
    assert "documentRecords" in data["items"][0]
    # Extraction records inside keep their snake_case contract.
    insurance = next(i for i in data["items"] if i["id"] == "insurance_evidence")
    assert "evidence" in insurance["fieldRecords"][0]
