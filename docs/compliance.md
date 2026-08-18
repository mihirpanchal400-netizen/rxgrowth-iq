# Compliance & Data Governance

RxGrowth IQ sits next to a heavily regulated data supply chain. These guardrails are built in
from Phase 0, not retrofitted.

> **This document is not legal advice and this repository is not a substitute for your own
> compliance review.** See [Before production use](#before-production-use).

---

## 1. Synthetic data only — enforced by CI

This repository contains no real prescription, patient, or licensed vendor data, and must
never contain any. All data comes from `packages/synth`.

Real prescriber-level Rx data (IQVIA, Symphony Health, Komodo, and similar) is licensed under
data-use agreements that restrict where it may be stored, who may access it, and explicitly
prohibit re-identification. It lives only inside a customer's own environment under their DUA
— never in this repo, never in a fixture, never in a screenshot in an issue.

### The CI gate

`.github/workflows/data-guard.yml` runs `scripts/check_no_real_data.py` on every pull request
and every push to `main`. It scans the **diff**, not the working tree, so it stays fast and
does not re-flag an allowlisted fixture on every subsequent PR.

It fails the build on:

| Detection | Rule |
|---|---|
| **Real-looking NPI** | 10 digits beginning with 1 or 2 that pass the CMS check digit (Luhn over `80840` + first nine digits) |
| **Real-looking DEA number** | Two letters + seven digits satisfying the DEA checksum |
| **Licensed vendor filename** | Path contains a known extract pattern — `xponent`, `plantrak`, `dddx`, `iqvia`, `komodo`, and similar |
| **Bulk data file** | Added `.csv` / `.parquet` / `.xlsx` / `.sas7bdat` (and similar) over 512 KiB |

Vendor patterns match on **file paths only, never on content** — otherwise this very document,
which names those vendors in prose, would fail the build.

Findings print a **masked** identifier (`123***93`). A scanner that echoed a real NPI into a
public CI log would itself be the leak.

### The synthetic NPI range — `9`-prefixed

`packages/synth` emits `npi_synth` values that **begin with the digit 9**.

CMS has only ever issued NPIs beginning with 1 or 2; 3 through 9 have never been allocated. A
9-prefixed identifier is therefore structurally incapable of colliding with a real registrant,
and the scanner treats the entire range as safe. A self-test iterates the range and asserts
that no generated value can ever trip the gate — so the generator cannot be broken by a future
change to the detection logic without CI noticing.

This is preferred over relying on a failed check digit alone: check digits can pass by
coincidence, whereas an unissued prefix cannot.

### Allowlisting a fixture

A reviewed synthetic fixture that trips a detection may carry the marker
`rxiq:synthetic-data-ok` in the file. The exemption must be justified in the PR description.
Reach for it rarely — a fixture that looks like real data usually is.

## 2. No PHI

The schema has no patient identifiers, dates of birth, or claim IDs **by design**.

NBRx is a pre-aggregated count supplied by the data vendor. It is not derived here from
patient-level records. This is the boundary that keeps the platform outside HIPAA's
patient-data surface, and any feature request that would cross it — adherence, persistence,
patient journey, longitudinal cohorts — is a scope change requiring explicit review, not a
sprint task.

## 3. Prescriber privacy

Prescribers may opt out of having their individual prescribing data shown to sales
representatives (in the US, via the AMA's Physician Data Restriction Program; several states
add their own rules).

**Implementation:** a `display_suppressed` flag on `dim_prescriber`. When set:

- The prescriber's volume **still counts** in every aggregate and rollup.
- The prescriber **never appears** in any API response, export, UI view, NBA
  recommendation, or LLM tool result as an identifiable row.

Suppression is enforced at the repository layer, not the UI layer, so no new endpoint can
accidentally leak it. Tests must assert the negative case: a suppressed prescriber is absent
from every surface while aggregate totals remain unchanged.

## 4. Aggregate spend — out of scope in v1

Speaker programs, meals, and consulting payments are transfer-of-value events reportable under
the US Physician Payments Sunshine Act and analogous regimes elsewhere.

`fact_call` models `is_speaker_program` because it matters as a promotional signal, but v1
**does not compute, aggregate, or report spend**. This is deliberate: a half-built spend view
invites someone to mistake this for a compliant aggregate-spend reporting system. It is not.

## 5. Promotional guardrails in the NBA engine

Next-best-action recommendations are **informational-need-based**. The engine must never
recommend an action conditioned on a prescriber's prescribing in exchange for anything of
value — that is the anti-kickback exposure this feature category carries.

Encoded as **hard rules that no score can override**:

- Do-not-contact and opt-out flags
- Sample-distribution limits and signature requirements (PDMA)
- Cycle frequency caps
- Speaker-program eligibility constraints
- Access-status gating (do not promote where the product is not obtainable)

Architecturally the rule layer runs *after* the score layer and removes candidates. A
constraint violation must be impossible by construction, and Phase 6 includes a fuzz test that
actively tries to produce one.

## 6. LLM guardrails

The narrative layer reads numbers **only** through typed tools. It has no raw data access and
no ability to query freely.

Every generated narrative is post-processed: all numerals are extracted and verified against
the tool responses for that request. An unverifiable number triggers one regeneration, then
fails closed to a deterministic template. A fabricated market-share figure in front of a brand
director is a trust-ending event, so this fails closed rather than open.

The narrative layer also inherits the causal-language restriction on `call_yield` — see
`metric-dictionary.md` §9.

## 7. Audit trail

Logged with user, scope, timestamp, and data version:

- Every data export
- Every access to prescriber-level detail
- Every LLM prompt and response

Audit records are append-only and separate from application logs.

---

## Before production use

This repo is a platform, not a compliant deployment. A customer must add, at minimum:

| Requirement | Why |
|---|---|
| Their executed **data-use agreements** and the field-level restrictions each imposes | DUA terms vary by vendor and contract; some restrict prescriber-level display outright |
| **Legal and medical/regulatory review** of every rep-facing recommendation and narrative template | Promotional content is regulated speech |
| **Their SSO/IdP** and reviewed RBAC role mapping | Territory-level data access is the core control |
| **Data retention and deletion policy** | Varies by jurisdiction and contract |
| **Privacy review** covering their prescriber opt-out feeds | Opt-out lists must be ingested and refreshed, not assumed static |
| Region-specific review (**GDPR** where prescriber data is personal data, plus local pharma marketing codes) | Prescriber-level data is personal data in the EU/UK |

Raise anything touching these areas as an issue labelled `compliance` and get a human decision
before implementing. Do not resolve a compliance ambiguity by picking the convenient reading.
