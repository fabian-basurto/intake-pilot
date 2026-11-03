"""Editable follow-up request for the referring office.

Deterministic: asks only for items that are not found or need clarification.
Nothing here sends anything.
"""

from __future__ import annotations

from .rules import ReviewResult
from .schema import Extraction, field_map


def _capitalize(s: str) -> str:
    return s[:1].upper() + s[1:]


def _trim(s: str, limit: int = 140) -> str:
    t = s.strip()
    return t if len(t) <= limit else t[: limit - 3].rstrip() + "..."


def build_draft(review: ReviewResult, extraction: Extraction, file_name: str) -> str:
    fields = field_map(extraction)
    practice = (fields.get("practice_name") or None) and fields["practice_name"].value
    contact = (fields.get("contact_name") or None) and fields["contact_name"].value
    patient = (fields.get("patient_name") or None) and fields["patient_name"].value
    dob = (fields.get("patient_dob") or None) and fields["patient_dob"].value

    greeting = f"Hello {contact}," if contact else (f"Hello {practice} team," if practice else "Hello,")
    patient_line = (
        f"Re: referral for {patient}{f' (DOB {dob})' if dob else ''} — ENTYVIO infusion"
        if patient
        else f"Re: ENTYVIO infusion referral (packet: {file_name})"
    )

    missing = [i for i in review.items if i.status == "not_found"]
    clarify = [i for i in review.items if i.status == "needs_review"]

    if not missing and not clarify:
        return "\n".join(
            [
                greeting,
                "",
                patient_line,
                "",
                "Thank you for the referral packet. On first review all expected documentation was located. "
                "Our intake team is completing verification and will contact your office if anything further is needed.",
                "",
                "Kind regards,",
                "Infusion Intake Team",
                "",
                "[Draft for staff review — not sent]",
            ]
        )

    lines = [greeting, "", patient_line, ""]
    lines.append("Thank you for sending the referral packet. To complete intake we need the following:")
    lines.append("")
    if missing:
        lines.append("Not found in the packet we received:")
        lines.extend(f"  • {_capitalize(m.request)}" for m in missing)
        lines.append("")
    if clarify:
        lines.append("Please confirm or clarify:")
        lines.extend(f"  • {_capitalize(c.request)} — {_trim(c.detail)}" for c in clarify)
        lines.append("")
    lines.append("Please fax or securely send the items above and we will continue processing right away.")
    lines.append("")
    lines.append("Kind regards,")
    lines.append("Infusion Intake Team")
    lines.append("")
    lines.append("[Draft for staff review — not sent]")
    return "\n".join(lines)
