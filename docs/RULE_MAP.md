# Rule map: which requirement came from which reference PDF

Both references are blank, single-page templates. They are used only as the
source of expected fields and document categories. No additional insurer,
clinical, or medication requirements were added.

- **PDF A** = `pdf A.pdf`, "ENTYVIO (vedolizumab) infusion orders", page 1
- **PDF B** = `pdf B.pdf`, "Referral Checklist", page 1

Rule ids match `backend/app/rules.py` (also served at `GET /api/rules`). "Required" means the demo flags the item
as *Not found in uploaded packet* when absent. "Info" means it is shown but
never flagged, because the form presents it as optional or as a pre-printed
default.

## Supporting documents (PDF B p1, header "REFERRING OFFICE, ALSO FAX")

| Rule id | Requirement | Source | Level |
|---|---|---|---|
| `doc_order_form` | Therapy-specific order form present (the ENTYVIO order form, PDF A) | PDF B p1 bullet "Order"; PDF B p1 "Order, Diagnosis and Clinical Information attached ... download a therapy-specific order form" | Required |
| `doc_recent_labs` | Most recent labs present | PDF B p1 bullet "Most recent labs" | Required |
| `doc_clinical_notes` | Supporting clinical notes present | PDF B p1 bullet "Supporting clinical notes" | Required |

PDF B p1 NOTE: "the Referral Checklist is not required. The information
specified must be included, either on this form or on attached documentation."
Therefore the checklist cover sheet itself is **never** flagged as missing;
only the information it enumerates is checked.

## Patient demographics (PDF B p1 "Patient Demographics"; PDF A p1 header)

| Rule id | Requirement | Source | Level |
|---|---|---|---|
| `patient_name` | Patient name | PDF B p1 "Patient Name"; PDF A p1 "Patient Name" | Required |
| `patient_dob` | Date of birth | PDF B p1 "DOB"; PDF A p1 "DOB" | Required |
| `patient_sex` | Gender / sex | PDF B p1 "Gender"; PDF A p1 "M / F" | Required |
| `patient_phone` | At least one patient phone (home or mobile) | PDF B p1 "Home Phone", "Mobile Phone"; PDF A p1 "Phone" | Required |
| `patient_address` | Street address and City/State/Zip | PDF B p1 "Address", "City, State, Zip Code" | Required |
| `patient_email` | Patient email | PDF B p1 "Email" | Info |
| `funded_program` | Enrolled in funded program? Yes / No / N/A | PDF B p1 "Enrolled in Funded Program?" | Info |
| `support_program_interest` | Interested in patient support programs | PDF B p1 checkbox | Info |

PDF B allows "Patient demographics attached (If YES, you may skip the Patient
Demographics section)", so these values may come from any page of the packet,
not only the checklist cover.

## Insurance (PDF B p1 "Patient Insurance")

| Rule id | Requirement | Source | Level |
|---|---|---|---|
| `insurance_evidence` | EITHER front and back of insurance card attached, OR primary payer + subscriber name + ID # (group # when present) | PDF B p1 "Front and back of insurance card attached (If YES, you may skip the Patient Insurance section)"; "Primary Payer", "Subscriber Name", "Group #", "ID #" | Required (any-of) |
| `secondary_insurance` | Secondary payer details | PDF B p1 "Secondary Payer" | Info |

## Order, diagnosis, and clinical information (PDF A p1; PDF B p1 section 3)

| Rule id | Requirement | Source | Level |
|---|---|---|---|
| `diagnosis` | Diagnosis selected: Ulcerative Colitis, Crohn's Disease, or other | PDF A p1 "DIAGNOSIS" | Required |
| `icd10_code` | ICD-10 code written | PDF A p1 "Please provide ICD-10 code" | Required |
| `dosage` | 300 mg IV | PDF A p1 "DOSAGE 300mg IV" (pre-printed, pre-selected on the blank form) | Info |
| `infusion_frequency` | Exactly one frequency selected: induction (weeks 0, 2, 6 then every 8 weeks) OR "Dose every __ weeks" with a number | PDF A p1 "FREQUENCY" | Required; both or neither selected -> Needs staff review |
| `patient_weight` | Weight in lbs or kg | PDF A p1 "PATIENT WEIGHT" | Required |
| `premedication` | Pre-medication selections | PDF A p1 "PRE-MEDICATION" | Info (no selection is a valid order) |
| `order_notes` | Free-text notes | PDF A p1 "NOTES" | Info |
| `provider_signature` | Ordering provider signature present | PDF A p1 "Signature X" | Required |
| `signature_date` | Signature date | PDF A p1 "Date" | Required |
| `provider_name` | Ordering provider name | PDF A p1 "Provider" | Required |
| `provider_phone` | Ordering provider phone | PDF A p1 "Phone" (provider block) | Required |
| `provider_fax` | Ordering provider fax | PDF A p1 "Fax" | Required |

## Referring office contact (PDF B p1 "Contact Information*")

| Rule id | Requirement | Source | Level |
|---|---|---|---|
| `contact_name` | Office contact name | PDF B p1 "Contact Name" | Required |
| `practice_name` | Practice name | PDF B p1 "Practice Name" | Required |
| `contact_phone` | Office contact phone | PDF B p1 "Phone" (contact block) | Required |
| `contact_title` | Contact title | PDF B p1 "Title" | Info |
| `contact_email` | Contact email | PDF B p1 "Email" (contact block) | Info |

PDF B allows "Contact Information attached", so the referring office details
may appear on a fax cover or letterhead instead of the checklist.

## Status language

| Extraction status | Rule outcome | On-screen label |
|---|---|---|
| `found` | `ok` | Found · Evidence: page N |
| `not_found` on a required rule | `not_found` | Not found in uploaded packet |
| `uncertain` (conflict, illegible, printed-but-not-selected) | `needs_review` | Needs staff review |
| any status on an Info rule | `info` | Shown, never counted as an attention item |
| reviewer override | `ok` | Verified by staff / Corrected by staff |

A `not_found` result means the item was not detected in *this upload*. It is
never presented as proof that the referring office failed to produce it.
