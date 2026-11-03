"""Generates the synthetic demo packets in backend/samples/.

Every page is labelled SYNTHETIC DEMO DATA. Names, identifiers, phone numbers
(555 exchange), addresses, and payer names are fictional. Page structure
mirrors the two reference forms (A: ENTYVIO infusion orders, B: Referral
Checklist) without reproducing them.

Run from backend/:  python scripts/generate_samples.py
"""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

OUT_DIR = Path(__file__).resolve().parent.parent / "samples"
W, H = letter  # 612 x 792 points
MARGIN = 54

INK = (0.10, 0.12, 0.16)
MUTED = (0.40, 0.44, 0.50)
LINE = (0.75, 0.78, 0.82)
HAND = (0.10, 0.20, 0.50)  # "handwritten" entries in blue
BANNER_BG = (0.96, 0.95, 0.90)
BANNER_INK = (0.45, 0.35, 0.10)
CARD_BG = (0.97, 0.98, 1.00)

# ---------------------------------------------------------------------------
# Synthetic facts (fictional)
# ---------------------------------------------------------------------------
P = {
    "name": "Jordan Q. Testpatient",
    "dob": "04/12/1979",
    "sex": "F",
    "address": "1200 Example Lane, Apt 4B",
    "city_state_zip": "Springfield, IL 62701",
    "home_phone": "(555) 010-2231",
    "mobile_phone": "(555) 010-2232",
    "email": "jordan.testpatient@example.invalid",
    "weight_lbs": "162",
    "weight_kg": "73.5",
    "diagnosis": "Ulcerative Colitis",
    "icd10": "K51.90",
}
PRACTICE = {
    "name": "Riverbend Gastroenterology Associates (DEMO)",
    "contact": "Morgan Sampleworth",
    "title": "Referral Coordinator",
    "phone": "(555) 010-4410",
    "fax": "(555) 010-4411",
    "email": "referrals@riverbend-gi.example.invalid",
    "provider": "Avery Sampleton, MD",
}
INS = {
    "payer": "DemoCare Health Plan PPO",
    "subscriber": "Jordan Q. Testpatient",
    "member_id": "DMC-884-120-556",
    "group": "DEMO-4471",
    "claims_phone": "(555) 010-9900",
    "claims_address": "PO Box 00000, Demo City, IL 60000",
}
DATES = {"referral": "10/28/2026", "labs": "10/21/2026", "visit": "10/22/2026", "signed": "10/28/2026"}

VARIANTS = {
    "complete": "packet_complete.pdf",
    "incomplete": "packet_incomplete.pdf",
    "ambiguous": "packet_ambiguous.pdf",
}


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------
class Doc:
    def __init__(self, target: BytesIO) -> None:
        self.c = canvas.Canvas(target, pagesize=letter)
        self.c.setTitle("Synthetic referral packet (demo)")
        self.c.setAuthor("referral-intake-copilot sample generator")
        self.y = H - MARGIN
        self.page_no = 0

    # low level -----------------------------------------------------------
    def draw(self, x: float, y: float, s: str, size: float = 10, bold: bool = False, color=INK) -> None:
        self.c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        self.c.setFillColorRGB(*color)
        self.c.drawString(x, y, s)

    def width(self, s: str, size: float = 10, bold: bool = False) -> float:
        return self.c.stringWidth(s, "Helvetica-Bold" if bold else "Helvetica", size)

    def rule(self, x1: float, y1: float, x2: float, y2: float, w: float = 0.5, color=LINE) -> None:
        self.c.setStrokeColorRGB(*color)
        self.c.setLineWidth(w)
        self.c.line(x1, y1, x2, y2)

    # layout ----------------------------------------------------------------
    def add_page(self, title: str) -> None:
        if self.page_no > 0:
            self.c.showPage()
        self.page_no += 1
        self.y = H - MARGIN
        self.c.setFillColorRGB(*BANNER_BG)
        self.c.rect(0, H - 22, W, 22, stroke=0, fill=1)
        self.draw(MARGIN, H - 15, "SYNTHETIC DEMO DATA - fictional patient and practice - not a real record", 8.5, True, BANNER_INK)
        self.draw(MARGIN, 28, f"Synthetic packet  |  Page {self.page_no}", 8, False, MUTED)
        self.heading(title, 16)

    def heading(self, text: str, size: float = 12) -> None:
        self.y -= size + 6
        self.draw(MARGIN, self.y, text, size, True)
        self.y -= 6

    def section(self, text: str) -> None:
        self.y -= 22
        self.draw(MARGIN, self.y, text.upper(), 9.5, True)
        self.y -= 4
        self.rule(MARGIN, self.y, W - MARGIN, self.y, 0.6)
        self.y -= 6

    def text(self, s: str, size: float = 10, color=INK, bold: bool = False, x: float = MARGIN) -> None:
        self.y -= size + 4
        self.draw(x, self.y, s, size, bold, color)

    def field(self, label: str, value: str | None, x: float = MARGIN, width: float | None = None, newline: bool = True) -> None:
        width = width if width is not None else W - 2 * MARGIN
        if newline:
            self.y -= 18
        label_w = self.width(label + " ", 9.5)
        self.draw(x, self.y, label, 9.5)
        self.rule(x + label_w, self.y - 2, x + width, self.y - 2)
        if value:
            self.draw(x + label_w + 4, self.y + 1, value, 10, False, HAND)

    def two_fields(self, left: tuple[str, str | None], right: tuple[str, str | None]) -> None:
        half = (W - 2 * MARGIN) / 2
        self.field(left[0], left[1], width=half - 12)
        self.field(right[0], right[1], x=MARGIN + half, width=half, newline=False)

    def checkbox(self, label: str, checked: bool, x: float = MARGIN, newline: bool = True, suffix: str | None = None) -> None:
        if newline:
            self.y -= 16
        self.c.setStrokeColorRGB(*INK)
        self.c.setLineWidth(0.7)
        self.c.rect(x, self.y - 1, 9, 9, stroke=1, fill=0)
        if checked:
            self.draw(x + 1.3, self.y + 0.3, "X", 9, True, HAND)
        self.draw(x + 14, self.y, label, 9.5)
        if suffix:
            self.draw(x + 14 + self.width(label, 9.5) + 6, self.y, suffix, 10, False, HAND)

    def radio(self, label: str, selected: bool, x: float = MARGIN, newline: bool = True, suffix: str | None = None) -> None:
        if newline:
            self.y -= 16
        self.c.setStrokeColorRGB(*INK)
        self.c.setLineWidth(0.7)
        self.c.circle(x + 4.5, self.y + 3.5, 4.5, stroke=1, fill=0)
        if selected:
            self.c.setFillColorRGB(*HAND)
            self.c.circle(x + 4.5, self.y + 3.5, 2.4, stroke=0, fill=1)
        self.draw(x + 14, self.y, label, 9.5)
        if suffix:
            self.draw(x + 14 + self.width(label, 9.5) + 6, self.y, suffix, 10, False, HAND)

    def paragraph(self, s: str, size: float = 9.5, max_width: float = W - 2 * MARGIN) -> None:
        line = ""
        for word in s.split(" "):
            test = f"{line} {word}" if line else word
            if self.width(test, size) > max_width:
                self.text(line, size)
                line = word
            else:
                line = test
        if line:
            self.text(line, size)

    def table(self, headers: list[str], rows: list[list[str]], col_x: list[float]) -> None:
        self.y -= 16
        for h, x in zip(headers, col_x):
            self.draw(x, self.y, h, 9, True)
        self.y -= 4
        self.rule(MARGIN, self.y, W - MARGIN, self.y)
        for r in rows:
            self.y -= 14
            for cell, x in zip(r, col_x):
                self.draw(x, self.y, cell, 9)

    def save(self) -> None:
        self.c.save()


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
def page_checklist(d: Doc, v: str) -> None:
    d.add_page("Referral Checklist - Fax Cover")
    d.text(f"Date: {DATES['referral']}     To: Infusion Center Intake     From: {PRACTICE['name']}", 9.5, MUTED)
    d.text(f"Pages in this transmission: {3 if v == 'incomplete' else 5}", 9.5, MUTED)

    d.section("Referring office, also fax")
    d.checkbox("Order", True)
    d.checkbox("Most recent labs", v != "incomplete")
    d.checkbox("Supporting clinical notes", True)
    d.y -= 4
    d.paragraph(
        "Note: the referral checklist itself is not required. The information below must be included "
        "either on this form or on attached documentation.",
        8.5,
    )

    d.section("Patient demographics")
    d.checkbox("Patient demographics attached (skip section if yes)", False)
    d.two_fields(("Patient Name", P["name"]), ("DOB", P["dob"]))
    d.two_fields(("Gender", "Female" if P["sex"] == "F" else "Male"), ("Email", P["email"]))
    d.field("Address", P["address"])
    d.two_fields(("City, State, Zip Code", P["city_state_zip"]), ("Home Phone", P["home_phone"]))
    d.two_fields(("Mobile Phone", P["mobile_phone"]), ("Enrolled in Funded Program?", "No"))
    d.checkbox("Patient is interested in patient support programs", True)

    d.section("Patient insurance")
    ins = v != "incomplete"
    d.checkbox("Front and back of insurance card attached (skip section if yes)", ins)
    d.two_fields(("Primary Payer", INS["payer"] if ins else None), ("Group #", INS["group"] if ins else None))
    d.two_fields(("Subscriber Name", INS["subscriber"] if ins else None), ("ID #", INS["member_id"] if ins else None))
    d.two_fields(("Secondary Payer", None), ("Group #", None))
    d.two_fields(("Subscriber Name", None), ("ID #", None))

    d.section("Order, diagnosis, and clinical information")
    d.checkbox("Order, diagnosis and clinical information attached (therapy-specific order form)", True)

    d.section("Contact information")
    d.checkbox("Contact information attached (skip section if yes)", False)
    d.two_fields(("Contact Name", PRACTICE["contact"]), ("Practice Name", PRACTICE["name"]))
    d.two_fields(("Title", PRACTICE["title"]), ("Phone", PRACTICE["phone"]))
    d.field("Email", PRACTICE["email"])


def page_order_form(d: Doc, v: str) -> None:
    d.add_page("ENTYVIO (vedolizumab) Infusion Orders")
    d.two_fields(("Patient Name", P["name"]), ("DOB", P["dob"]))
    d.field("Phone", P["mobile_phone"], width=260)
    d.radio("M", P["sex"] == "M", x=380, newline=False)
    d.radio("F", P["sex"] == "F", x=430, newline=False)

    d.section("Diagnosis  (please provide ICD-10 code)")
    uc = P["diagnosis"] == "Ulcerative Colitis"
    d.checkbox("Ulcerative Colitis", uc, suffix=f"ICD-10: {P['icd10']}" if uc else None)
    d.checkbox("Crohn's Disease", False)
    d.checkbox("Other: ______________________", False)

    d.section("Pre-medication")
    d.checkbox("Tylenol 1000 mg PO", True)
    d.checkbox("Solu-Medrol 125 mg IVP", False, x=330, newline=False)
    d.checkbox("Diphenhydramine 25 mg PO", True)
    d.checkbox("Solu-Cortef 100 mg IVP", False, x=330, newline=False)
    d.checkbox("Cetirizine 10 mg PO", False)
    d.checkbox("Diphenhydramine 25 mg IVP", False, x=330, newline=False)

    d.section("ENTYVIO orders")
    orders_top = d.y
    d.text("DOSAGE", 9.5, bold=True)
    d.radio("300 mg IV", True)
    d.text("FREQUENCY", 9.5, bold=True)
    maintenance = v == "ambiguous"  # conflict: both frequency options selected
    d.radio("Dose at weeks 0, 2, and 6, then every 8 weeks", True)
    d.radio("Dose every ____ weeks", maintenance, suffix="4" if maintenance else None)
    orders_bottom = d.y
    d.y = orders_top
    d.text("PATIENT WEIGHT", 9.5, bold=True, x=380)
    d.field("lbs", P["weight_lbs"], x=380, width=120)
    d.field("kg", P["weight_kg"], x=380, width=120)
    d.y = min(d.y, orders_bottom) - 6

    d.section("Notes")
    d.paragraph(
        "Patient tolerated prior biologic infusions without reaction. Please schedule induction dose 1 "
        "within two weeks. (Synthetic note.)"
    )

    d.section("Ordering provider")
    d.y -= 22
    d.draw(MARGIN, d.y, "Signature  X", 9.5)
    d.rule(MARGIN + 62, d.y - 2, 360, d.y - 2)
    d.draw(MARGIN + 70, d.y + 1, f"/s/ {PRACTICE['provider']}", 11, False, HAND)
    d.field("Date", DATES["signed"], x=390, width=160, newline=False)
    d.two_fields(("Provider", PRACTICE["provider"]), ("Phone", PRACTICE["phone"]))
    d.field("Fax", PRACTICE["fax"], width=240)


def page_insurance_card(d: Doc) -> None:
    d.add_page("Insurance Card (copy)")

    def card(title: str, lines: list[str], y_top: float) -> None:
        x, w, h = MARGIN + 40, 340, 170
        d.draw(x, y_top + 8, title, 9.5, True, MUTED)
        d.c.setFillColorRGB(*CARD_BG)
        d.c.setStrokeColorRGB(*INK)
        d.c.setLineWidth(0.8)
        d.c.rect(x, y_top - h, w, h, stroke=1, fill=1)
        y = y_top - 24
        for i, line in enumerate(lines):
            d.draw(x + 16, y, line, 13 if i == 0 else 10, i == 0)
            y -= 24 if i == 0 else 17

    card(
        "FRONT",
        [INS["payer"], f"Member: {INS['subscriber']}", f"Member ID: {INS['member_id']}", f"Group #: {INS['group']}", "Plan: PPO Standard (demo)", "RxBIN 000000   RxPCN DEMO"],
        d.y - 20,
    )
    card(
        "BACK",
        ["Claims and customer service (demo)", f"Member services: {INS['claims_phone']}", f"Provider services: {INS['claims_phone']}", f"Send claims to: {INS['claims_address']}", "This card does not guarantee coverage.", "Synthetic card - not valid for use."],
        d.y - 250,
    )


def page_labs(d: Doc) -> None:
    d.add_page("Laboratory Results")
    d.text(f"Patient: {P['name']}    DOB: {P['dob']}    Collected: {DATES['labs']}    Reported: {DATES['labs']}", 9.5, MUTED)
    d.text(f"Ordering provider: {PRACTICE['provider']}    Lab: Demo Regional Laboratory", 9.5, MUTED)
    cols = [MARGIN, 260, 360, 440]
    d.section("Complete blood count")
    d.table(["Test", "Result", "Units", "Reference"], [["WBC", "6.8", "10^3/uL", "4.0 - 11.0"], ["Hemoglobin", "12.1", "g/dL", "12.0 - 16.0"], ["Hematocrit", "37.4", "%", "36.0 - 46.0"], ["Platelets", "288", "10^3/uL", "150 - 400"]], cols)
    d.section("Comprehensive metabolic panel")
    d.table(["Test", "Result", "Units", "Reference"], [["Sodium", "139", "mmol/L", "135 - 145"], ["Potassium", "4.1", "mmol/L", "3.5 - 5.1"], ["Creatinine", "0.8", "mg/dL", "0.6 - 1.1"], ["ALT", "22", "U/L", "7 - 45"], ["AST", "19", "U/L", "8 - 40"], ["Albumin", "3.9", "g/dL", "3.5 - 5.0"]], cols)
    d.section("Inflammatory markers")
    d.table(["Test", "Result", "Units", "Reference"], [["CRP", "9.2", "mg/L", "< 8.0"], ["Fecal calprotectin", "310", "ug/g", "< 50"]], cols)
    d.y -= 10
    d.paragraph("All values are fabricated for demonstration and carry no clinical meaning.", 8.5)


def page_clinical_note(d: Doc) -> None:
    d.add_page("Office Visit Note")
    d.text(f"{PRACTICE['name']}    Visit date: {DATES['visit']}    Provider: {PRACTICE['provider']}", 9.5, MUTED)
    d.text(f"Patient: {P['name']}    DOB: {P['dob']}", 9.5, MUTED)
    d.section("Reason for visit")
    d.paragraph("Follow-up of moderate ulcerative colitis with persistent symptoms despite current therapy. Discussion of advancing to vedolizumab infusion.")
    d.section("History")
    d.paragraph("Diagnosed with ulcerative colitis in 2021. Prior mesalamine with partial response. Reports 4-5 loose stools daily with intermittent blood over the last six weeks. No fevers. Weight stable at 162 lb. No known drug allergies. (Synthetic history.)")
    d.section("Assessment")
    d.paragraph(f"Ulcerative colitis, moderate activity ({P['icd10']}). Candidate for vedolizumab induction per standard dosing. Labs reviewed; CRP and fecal calprotectin elevated.")
    d.section("Plan")
    d.paragraph("1. Refer to infusion center for ENTYVIO 300 mg IV at weeks 0, 2, 6 then every 8 weeks. 2. Pre-medicate with acetaminophen and diphenhydramine. 3. Continue mesalamine. 4. Return visit in 10 weeks or sooner if symptoms worsen.")
    d.y -= 10
    d.text(f"Electronically signed: {PRACTICE['provider']}  {DATES['visit']}", 9.5, HAND)
    d.y -= 20
    d.paragraph("This note is entirely fictional and generated for a software demonstration.", 8.5)


def build_packet(variant: str) -> bytes:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}")
    buf = BytesIO()
    d = Doc(buf)
    page_checklist(d, variant)
    page_order_form(d, variant)
    if variant != "incomplete":
        page_insurance_card(d)
        page_labs(d)
    page_clinical_note(d)
    d.save()
    return buf.getvalue()


def main(out_dir: Path = OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for variant, file in VARIANTS.items():
        data = build_packet(variant)
        (out_dir / file).write_bytes(data)
        print(f"wrote {file} ({len(data)} bytes)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover
        print(exc, file=sys.stderr)
        sys.exit(1)
