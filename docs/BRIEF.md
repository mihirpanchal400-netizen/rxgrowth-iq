# BUILD BRIEF / MASTER PROMPT
# Pharma Prescription Growth Intelligence Platform ("RxGrowth IQ")
# Target runner: Claude Code, with GitHub integration already configured

> **How to use this file:** Paste Sections 0–3 as your opening message to Claude Code, then
> feed Sections 4+ phase by phase. Or drop this file at the repo root and open with:
> `Read pharma-rx-growth-intel-PROMPT.md and execute Phase 0.`

---

## 0. ROLE & OPERATING CONTRACT

You are the lead full-stack + data engineer building a production-grade **Pharmaceutical
Prescription Growth Intelligence Platform**. You own architecture, code, tests, CI, and the
GitHub workflow end to end.

**Non-negotiables — apply to every single change:**

1. **Never invent domain math.** Every metric you implement must match the formula in the
   Metric Dictionary (Section 3.2) exactly. If a metric is ambiguous, stop and ask.
2. **Synthetic data only.** This repo must never contain real prescription, patient, or
   licensed vendor data. See Section 7 (Compliance) — a hard gate, not a preference.
3. **Test-first for all business logic.** Any function computing a metric, cohort, or model
   feature ships with unit tests including edge cases (zero denominators, missing months,
   negative adjustments, newly launched products with no history).
4. **One GitHub issue → one branch → one PR.** No direct commits to `main`. Ever.
5. **Work in vertical slices.** Each PR must leave the app runnable end to end. Never merge a
   backend change whose UI/API consumer does not exist yet — stub it in the same PR.
6. **Ask before scope changes.** If you discover the spec is wrong or underspecified in a way
   that changes the data model, raise it in the PR description and in chat before proceeding.
7. **Report honestly.** If tests fail, paste the failure. If you skipped something, say so
   explicitly in the PR body under `## Not Done`.

**Interaction style:** Terse. Show diffs and commands, not essays. When a phase is complete,
report what shipped, test results, what is stubbed, and the next 3 issues you would open.

---

## 1. PRODUCT DEFINITION

### 1.1 The problem

Pharma commercial teams sit on prescription (Rx) data, CRM call activity, and payer/formulary
data in three disconnected systems. They can answer *"what happened"* (last month's TRx) but
not *"why"* or *"what should my rep do Tuesday morning."* Analysts rebuild the same
growth-decomposition spreadsheets every cycle, and by the time an insight reaches a territory
manager it is five weeks stale.

### 1.2 What we are building

An analytics and decision-support platform that ingests prescriber-level Rx data, promotional
activity, and payer access data, then:

- **Measures** brand performance at every hierarchy level (national → region → district →
  territory → prescriber) across TRx / NRx / NBRx / share.
- **Explains** growth by mathematically decomposing it into market growth vs. share gain, and
  writer breadth vs. writer depth.
- **Predicts** which prescribers are most likely to grow and which are at decline risk.
- **Recommends** a ranked Next-Best-Action list per rep per week, with the reasoning shown.
- **Narrates** the above in plain English via an LLM layer grounded strictly in computed
  numbers — no free-form invented statistics.

### 1.3 Personas and jobs-to-be-done

| Persona | Primary job | Key screen |
|---|---|---|
| **Field Rep** | "Who do I call this week and what do I say?" | My Targets / NBA feed |
| **District Manager** | "Which territories are off-plan and why?" | Territory scorecard + variance drill |
| **Brand / Commercial Analyst** | "Decompose Q3 growth by driver" | Growth Decomposition Studio |
| **Market Access Lead** | "Where is formulary status suppressing demand?" | Payer / Access heatmap |
| **Sales Ops** | "Is targeting aligned to opportunity?" | Alignment and coverage |

### 1.4 Explicit non-goals (v1)

- No patient-level longitudinal analytics (LAAD), adherence, or persistence modeling.
- No incentive-compensation calculation — adjacent product, different compliance surface.
- No real-time streaming. Batch cadence is weekly Rx, daily CRM.
- No multi-tenant SaaS isolation in v1. Single-tenant deployment, but design the schema so
  `tenant_id` can be added later without a rewrite.

---

## 2. TECHNICAL ARCHITECTURE

### 2.1 Stack — use exactly this unless you flag a reason not to

```
Data layer      DuckDB (local dev) -> Postgres 16 (app state); dbt-core for transforms
Orchestration   Prefect 3 (flows: ingest -> transform -> score -> publish)
Backend         Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic migrations
ML              scikit-learn + LightGBM; MLflow for experiment tracking and model registry
LLM layer       Anthropic API — claude-sonnet-5 for narratives, claude-opus-5 for the
                analyst "deep explain" path. Tool-use pattern: the model may ONLY read
                numbers via typed tools, never state a figure it was not handed.
Frontend        Next.js 15 (App Router), TypeScript strict, TanStack Query, Tailwind,
                shadcn/ui, Recharts (visx only if a chart needs custom marks)
Auth            OIDC via Auth.js; RBAC roles: rep | manager | analyst | admin
Testing         pytest + pytest-cov (backend), Vitest + Testing Library (web),
                Playwright for 5 critical E2E journeys
Infra           Docker Compose for dev; Terraform stubs for AWS (ECS Fargate, RDS, S3)
Quality gates   ruff + mypy --strict (backend), eslint + tsc --noEmit (web),
                pre-commit hooks, conventional commits
```

### 2.2 Repository layout

```
rxgrowth-iq/
├── .github/
│   ├── workflows/{ci.yml,e2e.yml,dbt-ci.yml,codeql.yml,release.yml}
│   ├── ISSUE_TEMPLATE/{feature.yml,bug.yml,data-issue.yml}
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── CODEOWNERS
│   └── dependabot.yml
├── apps/
│   ├── api/                      # FastAPI service
│   │   ├── src/rxiq/
│   │   │   ├── core/             # metric engine — PURE functions, zero I/O, heavily tested
│   │   │   ├── domain/           # entities: Prescriber, Territory, Product, Payer, Period
│   │   │   ├── repositories/     # data access, one class per aggregate
│   │   │   ├── services/         # orchestration: decomposition, NBA, forecasting
│   │   │   ├── ml/               # feature store, training, inference, model cards
│   │   │   ├── llm/              # Claude client, tool defs, prompt templates, guardrails
│   │   │   ├── api/v1/           # routers
│   │   │   └── config.py
│   │   └── tests/{unit,integration,fixtures}
│   └── web/                      # Next.js
│       ├── app/(dash)/{overview,targets,decomposition,territory,access,admin}
│       ├── components/{charts,tables,filters,narrative}
│       └── lib/{api-client,formatters,rx-formatting}
├── packages/
│   ├── dbt/                      # staging -> intermediate -> marts
│   └── synth/                    # synthetic data generator (the ONLY source of data)
├── infra/{docker,terraform}
├── docs/{ADR,metric-dictionary.md,data-dictionary.md,compliance.md,models/}
└── Makefile
```

### 2.3 Architectural rules

- **`core/` is pure.** Metric functions take dataframes/primitives in and return values out.
  No DB, no HTTP, no clock reads. This is what makes the domain math testable and auditable.
- **Metric definitions live in exactly one place** (`core/metrics/`). The API, dbt models, and
  ML feature store all consume the same definitions — never reimplement a formula in SQL where
  it can drift. Where dbt must compute in-warehouse, generate the SQL from the Python spec and
  assert parity in a CI test.
- **All volume and currency values use `Decimal`, never float.** Projected Rx counts are
  fractional and rounding error compounds across hierarchy rollups.
- **Every API response carrying a metric also carries `definition_id` and `period_basis`**, so
  the UI can show "how is this calculated?" without guessing.

---

## 3. DOMAIN SPEC — THE PART THAT MATTERS MOST

### 3.1 Glossary (implement as typed enums / domain objects)

- **TRx** — Total prescriptions dispensed in a period (new + refills).
- **NRx** — New prescriptions (new starts + switches; excludes refills).
- **NBRx** — New-to-Brand: patient had no dispensed claim for this brand within the lookback
  window (default 12 months). Configurable per brand.
- **Market basket** — the set of products a brand competes against. Every share metric is
  meaningless without an explicit basket; make it a first-class configurable entity.
- **Decile** — prescribers ranked by *market* volume (not brand volume) into 10 bins;
  decile 10 = highest. Recompute quarterly.
- **Writer status** — per prescriber per brand per period:
  `NEVER | NEW | CONTINUING | GROWING | DECLINING | LAPSED`
  (LAPSED = wrote in the prior window, zero in the current window.)
- **Reach** — % of target prescribers with at least one call in period.
- **Frequency** — mean calls per reached target.
- **Share of Voice (SOV)** — brand calls / total tracked market calls to that prescriber.
- **Projection factor** — Rx panel data is projected to 100%. Carry the factor; never present
  raw panel counts as actuals.
- **Access status** — per payer plan per brand:
  `PREFERRED | COVERED | NON_PREFERRED | PRIOR_AUTH | STEP_THERAPY | NOT_COVERED`.

### 3.2 Metric Dictionary — implement exactly

**Share**
```
market_share(brand, level, period) = sum(brand_TRx) / sum(basket_TRx)   # 0 if denom = 0, and flag it
nbrx_share(...)                    = sum(brand_NBRx) / sum(basket_NBRx)
```

**Growth**
```
growth_pct(m, t) = (m[t] - m[t-1]) / m[t-1]        # None if m[t-1] == 0 — never infinity
yoy_growth(m, t) = (m[t] - m[t-52w]) / m[t-52w]
rolling(m, t, n) = sum(m[t-n+1 .. t])              # R4, R13, R26, R52 windows
```

**Growth Decomposition A — market vs. share** (the flagship feature)
```
Let B = brand TRx, M = market TRx, S = B / M.
delta_B = B1 - B0
  market_effect = S0 * (M1 - M0)
  share_effect  = M0 * (S1 - S0)
  interaction   = (M1 - M0) * (S1 - S0)
  delta_B == market_effect + share_effect + interaction     # MUST hold to 1e-9. Assert it.
```

**Growth Decomposition B — breadth vs. depth**
```
Let W = number of writers, D = TRx / writer.  B = W * D.
  breadth_effect = D0 * (W1 - W0)
  depth_effect   = W0 * (D1 - D0)
  interaction    = (W1 - W0) * (D1 - D0)
```

**Decomposition C — hierarchical contribution.** For any parent node, attribute delta_TRx to
each child, sorted by absolute contribution. Must sum to the parent delta_TRx exactly.

**Opportunity sizing (per prescriber)**
```
target_share  = 75th-percentile share among peers in the same
                (specialty, decile, access_status) cohort
potential_trx = market_trx_prescriber * target_share
opportunity   = max(0, potential_trx - actual_brand_trx)
```

**Promotional response**
```
reach(period)     = count(p in targets : calls(p) >= 1) / count(targets)
frequency(period) = sum(calls) / count(p : calls(p) >= 1)
call_yield        = delta_NBRx over 8 weeks post-call / calls     # correlational — LABEL IT
```
> `call_yield` is **not** causal. Any UI surfacing it must say so, and the uplift model
> (Phase 5) is the causal path. Do not let the LLM narrative describe it as "caused by".

### 3.3 Data model (core tables)

```
dim_prescriber    (prescriber_id PK, npi_synth, specialty, sub_specialty, decile,
                   segment, primary_affiliation_id, territory_id, active_from, active_to)
dim_territory     (territory_id PK, district_id, region_id, geography, rep_id, effective_from)
dim_product       (product_id PK, brand, molecule, market_basket_id, launch_date, is_own_brand)
dim_payer_plan    (plan_id PK, payer_id, channel {COMMERCIAL|MEDICARE|MEDICAID|CASH}, lives)
dim_period        (period_id PK, period_type {WEEK|MONTH|QUARTER}, start_date, end_date)

fact_rx           (prescriber_id, product_id, period_id, plan_id,
                   trx, nrx, nbrx, projection_factor, units, source_system)   -- grain locked
fact_call         (prescriber_id, rep_id, period_id, call_type, product_ids[],
                   duration_min, samples_dropped, is_speaker_program)
fact_access       (plan_id, product_id, period_id, access_status, copay_tier, pa_required)

bridge_target_list (prescriber_id, brand, cycle_id, target_tier, planned_frequency)
```

Design constraints:

- `fact_rx` grain is **(prescriber, product, period, plan)** — enforce with a unique index and
  a dbt uniqueness test. Aggregations that assume a coarser grain are the number-one source of
  double-counting bugs. Write a test that would catch it.
- **Slowly-changing dimensions:** territory alignment changes mid-year. Rx history must be
  restateable under both the *current* and the *as-of* alignment. Support both, default to
  current, and expose it as an explicit API parameter (`alignment_basis`).
- **Handle missing periods.** A prescriber with no Rx in a week has no row, not a zero row.
  Every rollup must densify against `dim_period` or it will silently misstate averages.

### 3.4 Synthetic data generator (`packages/synth`) — build this FIRST

Generate a defensible fake market so every downstream feature is demoable:

- 3 own brands + 6 competitors across 2 market baskets; one brand launched 9 months ago
  (exercises new-product code paths with no YoY history).
- 12,000 prescribers, realistic specialty mix, **Pareto volume distribution** (top 20% of
  writers ≈ 70% of volume). Decile assignment derived, not random.
- 250 territories → 25 districts → 5 regions, including one mid-year realignment event.
- 156 weeks of history with: seasonality (Q4 lift, summer trough), a competitor launch shock at
  week 88, a payer access loss for one brand at week 104 with a visible ~6-week demand decay,
  and injected noise.
- Call activity correlated with — but not deterministic of — Rx, so the uplift model has real
  confounding to contend with.
- A `--seed` flag; deterministic output. Test fixtures derive from a small seeded slice.

**Deliverable:** `make seed` populates the warehouse in under 90 seconds.

---

## 4. PHASED DELIVERY PLAN

Each phase = one GitHub **Milestone**. Each bullet = one **Issue**. Each issue = one **PR**.

### Phase 0 — Foundation
- Scaffold monorepo, Makefile, Docker Compose (Postgres, MLflow, api, web).
- Pre-commit: ruff, mypy, eslint, prettier, conventional-commit lint.
- `.github/workflows/ci.yml`: lint → typecheck → unit → integration; matrix py3.12 / node20;
  cached deps; fail on coverage drop.
- Issue and PR templates, CODEOWNERS, dependabot, CodeQL.
- `docs/ADR/0001-architecture.md`, `docs/compliance.md`.
- **Exit criteria:** `make dev` boots the stack; CI green on an empty PR.

### Phase 1 — Data foundation
- `packages/synth` generator per Section 3.4.
- Alembic migrations for the schema in 3.3; dbt staging + marts.
- dbt tests: uniqueness on every fact grain, not-null on keys, relationship tests, an
  accepted-range test on `projection_factor`.
- `make seed`, `make dbt`.
- **Exit criteria:** row counts and distributions match a documented expected profile; dbt
  tests pass in CI.

### Phase 2 — Metric engine
- `core/metrics/` implementing every formula in 3.2 as pure functions.
- Property-based tests (Hypothesis) for the decomposition identities — the sum-to-delta_B
  assertions must hold for randomly generated inputs.
- Period densification and rolling-window utilities with an explicit missing-data policy.
- Hierarchy rollup engine with `alignment_basis` support.
- **Exit criteria:** ≥95% coverage on `core/`; a golden-dataset test whose expected values were
  hand-computed and committed as CSV.

### Phase 3 — API + first vertical slice
- FastAPI routers: `/v1/performance`, `/v1/hierarchy`, `/v1/prescribers`, `/v1/decomposition`.
- Cursor pagination; filter DSL (brand, period range, level, node, alignment_basis).
- Response caching (Redis), request-scoped query budget, structured logging with trace IDs.
- Next.js Overview dashboard: KPI row (TRx / NRx / NBRx / share + YoY), trend chart,
  hierarchy drill table.
- **Exit criteria:** Playwright E2E — log in → drill region → territory → prescriber → numbers
  reconcile against a direct DB query.

### Phase 4 — Growth Decomposition Studio
- Waterfall chart: market effect / share effect / interaction, with the residual visibly zero.
- Breadth vs. depth quadrant view.
- Contribution table: top positive and negative contributors at any level, drillable.
- Period comparison controls (vs. prior period, prior year, custom baseline).
- XLSX export with the formulas documented on a second sheet.
- **Exit criteria:** an analyst can reproduce the waterfall in Excel from the export and match.

### Phase 5 — Predictive layer
- Feature store: 60+ features (Rx trajectory slopes, volatility, writer-status transitions,
  peer-cohort deltas, promo history, access changes, tenure, competitive share drift).
- **Model 1 — Growth propensity:** LightGBM binary classifier, P(prescriber grows ≥X% next
  quarter). Time-based split, no leakage. Report AUC, PR-AUC, calibration curve.
- **Model 2 — Decline/churn risk:** same discipline.
- **Model 3 — Call uplift:** two-model / T-learner uplift estimator with propensity weighting.
  Report the Qini curve. Be explicit in the model card about unmeasured confounding.
- SHAP explanations surfaced per prescriber in the UI.
- MLflow tracking; model cards in `docs/models/`; a drift-check job.
- **Exit criteria:** reproducible training run from a single command; every model has a
  committed model card stating intended use, limitations, and known failure modes.

### Phase 6 — Next-Best-Action engine
- Rule layer (hard business constraints: PDMA sample limits, do-not-call flags, cycle frequency
  caps, access-status gating) **and** score layer (propensity × opportunity × uplift).
- Ranked weekly action list per rep, each with action type, prescriber, why-now reasoning
  chips, expected impact band, and the data as-of date.
- Feedback capture (rep marks acted / dismissed with reason) — future training signal.
- **Exit criteria:** constraint violations are impossible by construction; add a fuzz test that
  tries to produce one.

### Phase 7 — Payer / access intelligence
- Access heatmap: plan × brand × status, weighted by covered lives and by local Rx volume.
- Access-change event detection with before/after demand-impact estimate.
- Territory-level "access-suppressed opportunity" metric.

### Phase 8 — LLM narrative layer
- Claude tool-use: typed tools `get_metric`, `get_decomposition`, `get_top_movers`,
  `get_prescriber_profile`. The model has no raw data access — only these tools.
- **Grounding guardrail:** post-process every generated narrative, extract all numerals, and
  verify each appears in the tool responses for that request. Any unverifiable number →
  regenerate once, then fail closed to a template-based narrative.
- Prompt templates per persona — the DM summary reads differently from the analyst deep-dive.
- Cache narratives by `(scope, period, data_version)` hash.
- Log every prompt and response for audit.
- **Exit criteria:** an adversarial eval set of 30 questions where invented figures are caught
  100% of the time by the verifier.

### Phase 9 — Hardening
- RBAC enforcement tests — a rep must not read another territory; test the negative case.
- Query performance: p95 < 800 ms on the largest hierarchy rollup. Add indexes and
  materializations as needed, and document them.
- Audit log for every data export.
- Terraform stubs, runbook, backup/restore doc.
- Load test with k6 at 100 concurrent users.

---

## 5. GITHUB WORKFLOW — FOLLOW LITERALLY

```bash
# Per phase
gh issue create --milestone "Phase N — <name>" --title "..." --body "..." --label "..."

# Per issue
git checkout main && git pull
git checkout -b <type>/<issue#>-<slug>        # feat|fix|chore|docs|refactor|test|perf
# ... work, committing in logical units ...
git commit -m "feat(metrics): add market/share growth decomposition

Implements delta_B = market_effect + share_effect + interaction with an
identity assertion to 1e-9. Property tests via Hypothesis.

Closes #42"
gh pr create --fill --base main
# wait for CI; fix anything red before requesting review
```

**Labels to create:** `phase-0` … `phase-9`, `area:data`, `area:api`, `area:web`, `area:ml`,
`area:llm`, `compliance`, `tech-debt`, `needs-domain-input`, `blocked`.

**PR template must include:**
```markdown
## What & Why
## Metric definitions touched (formula + doc link)
## Test evidence  (paste actual output, not "tests pass")
## Screenshots / API samples
## Data integrity impact  (grain? rollups? backfill needed?)
## Not Done  (be honest — list anything stubbed or deferred)
## Compliance check  [ ] no real/licensed data  [ ] no PHI  [ ] audit-logged if exporting
```

**Branch protection on `main`:** require PR, require CI green, require conversation resolution,
squash-merge only, linear history, no force push.

**Commit convention:** Conventional Commits. Scope = area (`metrics`, `api`, `web`, `ml`,
`llm`, `dbt`, `synth`).

---

## 6. QUALITY BAR

- `mypy --strict` clean on `apps/api/src`. No `Any` in `core/` — none.
- `tsc --noEmit` clean; no `any` in `web/lib` or `web/components`.
- Coverage gates: `core/` ≥95%, `services/` ≥85%, overall ≥80%. CI fails on regression.
- Every public function in `core/` has a docstring with its formula and a worked example.
- No magic numbers — lookback windows, thresholds, and percentile targets are config, and every
  default is justified in a comment.
- Charts: colorblind-safe palette, dark/light parity, every axis labeled with units and period
  basis, and a visible "data as of" stamp on every screen.
- Accessibility: keyboard-navigable tables, ARIA on charts with a data-table fallback.

---

## 7. COMPLIANCE & DATA GOVERNANCE — READ BEFORE WRITING CODE

This platform sits next to a heavily regulated data supply chain. Build the guardrails now,
not later.

1. **No real data in the repo, ever.** Synthetic only. Add a CI check that greps added files
   for NPI-shaped 10-digit numbers, DEA-number formats, and common vendor filename patterns,
   and fails the build. Real licensed data (IQVIA / Symphony / Komodo) lives only in a
   customer's own environment under their data-use agreement.
2. **No PHI.** The schema has no patient identifiers, DOB, or claim IDs by design. NBRx is a
   pre-aggregated count supplied by the vendor, not something derived here from patient records.
3. **Prescriber privacy.** Support an opt-out flag (AMA PDRP-style) that suppresses individual
   prescriber-level display while still counting that volume in aggregates. Test that a
   suppressed prescriber never appears in any API response, export, or LLM tool result.
4. **Aggregate-spend awareness.** Speaker programs and meals are transfer-of-value events.
   Model the fields, but v1 does **not** compute or report spend — flag it as out of scope so
   no one mistakes this for a Sunshine Act reporting system.
5. **Promotional guardrails.** The NBA engine must never recommend an action conditioned on a
   prescriber's prescribing in exchange for anything. Recommendations are
   informational-need-based. Encode do-not-contact and speaker-eligibility constraints as hard
   rules that no score can override.
6. **Audit trail.** Every export, every LLM narrative, and every access to prescriber-level
   detail is logged with user, scope, timestamp, and data version.
7. **`docs/compliance.md`** documents all of the above plus what a customer must add before
   production use: their DUA terms, legal/medical review, SSO, and retention policy. State
   plainly that this repo is not a substitute for their own compliance review.

---

## 8. START HERE

Execute now, in order:

1. Confirm you have read this brief; list anything you consider underspecified.
2. Create the GitHub milestones `Phase 0` … `Phase 9` and the label set from Section 5.
3. Open the Phase 0 issues — one per bullet in Section 4, Phase 0.
4. Create branch `chore/1-scaffold-monorepo` and execute Phase 0.
5. Open the PR, paste CI results, then stop and report. Do not auto-start Phase 1.

At every phase boundary, report in this format:

```
SHIPPED:      <bullets>
TEST RESULTS: <actual output>
STUBBED:      <what is fake and where>
RISKS:        <what worries you>
NEXT 3:       <proposed issues>
```
