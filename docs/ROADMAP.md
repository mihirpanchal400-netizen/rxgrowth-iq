# Delivery Roadmap

Each phase is a GitHub **Milestone**. Each bullet is an **Issue**. Each issue is one **PR**.

Read the phase you are working on at the start of the session. Do not read ahead — building
Phase 5 concerns into Phase 2 code is how the metric engine gets polluted with ML assumptions.

**Do not auto-advance between phases.** Complete the phase, report, and wait.

---

## Phase 0 — Foundation

- Scaffold monorepo, `uv` workspace, task runner, local dev without Docker
- Pre-commit: ruff, mypy, eslint, prettier, conventional-commit lint
- `.github/workflows/ci.yml` — lint → typecheck → unit → integration; py3.12 / node20; cached deps; fail on coverage drop
- **Synthetic-data CI gate** — scan added files for NPI-shaped IDs, DEA formats, vendor filename patterns
- Issue templates, PR template, CODEOWNERS, dependabot, CodeQL
- `docs/ADR/0001-architecture.md`

**Exit:** `uv run dev` boots the stack; CI green on an empty PR.

## Phase 1 — Data foundation

- `packages/synth` generator: 3 own brands + 6 competitors, 2 baskets, one brand launched 9
  months ago; 12,000 prescribers with Pareto volume distribution; 250 territories → 25
  districts → 5 regions with one mid-year realignment; 156 weeks with seasonality, a
  competitor launch shock at week 88, and a payer access loss at week 104 with ~6-week decay
- Deterministic `--seed`; test fixtures from a small seeded slice
- Alembic migrations; dbt staging → intermediate → marts
- dbt tests: uniqueness on every fact grain, not-null on keys, relationships, accepted range on `projection_factor`

**Exit:** `uv run seed` populates the warehouse in <90s; distributions match a documented
expected profile; dbt tests green in CI.

## Phase 2 — Metric engine

- `core/metrics/` — every formula in `metric-dictionary.md` as pure functions
- **Property-based tests (Hypothesis) for the decomposition identities** — sum-to-delta must
  hold across randomly generated inputs
- Period densification + rolling windows with an explicit missing-data policy
- Hierarchy rollup engine with `alignment_basis` support
- Writer-status classifier and transition detection

**Exit:** ≥95% coverage on `core/`; golden-dataset test with hand-computed expected values
committed as CSV.

## Phase 3 — API + first vertical slice

- Routers: `/v1/performance`, `/v1/hierarchy`, `/v1/prescribers`, `/v1/decomposition`
- Cursor pagination; filter DSL (brand, period range, level, node, alignment_basis)
- Response caching, request-scoped query budget, structured logging with trace IDs
- Next.js Overview dashboard: KPI row (TRx/NRx/NBRx/share + YoY), trend chart, hierarchy drill table

**Exit:** Playwright E2E — log in → drill region → territory → prescriber → numbers reconcile
against a direct DB query.

## Phase 4 — Growth Decomposition Studio

- Waterfall: market effect / share effect / interaction, residual visibly zero
- Breadth vs. depth quadrant view
- Contribution table — top positive and negative movers at any level, drillable
- Period comparison controls (prior period, prior year, custom baseline)
- XLSX export with formulas documented on a second sheet

**Exit:** an analyst can reproduce the waterfall in Excel from the export and match to 1e-9.

## Phase 5 — Predictive layer

- Feature store: 60+ features — Rx trajectory slopes, volatility, writer-status transitions,
  peer-cohort deltas, promo history, access changes, tenure, competitive share drift
- **Model 1 — growth propensity:** LightGBM, P(grows ≥X% next quarter). Time-based split, no
  leakage. Report AUC, PR-AUC, calibration curve
- **Model 2 — decline/churn risk:** same discipline
- **Model 3 — call uplift:** T-learner with propensity weighting; report Qini curve
- SHAP explanations surfaced per prescriber
- MLflow tracking (file mode); model cards in `docs/models/`; drift-check job

**Exit:** reproducible training from a single command; every model has a committed model card
stating intended use, limitations, and known failure modes — including unmeasured confounding
for the uplift model.

## Phase 6 — Next-Best-Action engine

- Score layer (propensity × opportunity × uplift) **and** rule layer (hard constraints per
  `compliance.md` §5). Rules run after scoring and remove candidates
- Ranked weekly action list per rep: action type, prescriber, why-now reasoning chips,
  expected impact band, data as-of date
- Feedback capture — acted / dismissed with reason

**Exit:** constraint violations impossible by construction; fuzz test actively tries to
produce one and fails to.

## Phase 7 — Payer / access intelligence

- Access heatmap: plan × brand × status, weighted by covered lives and by local Rx volume
- Access-change event detection with before/after demand-impact estimate
- Territory-level access-suppressed opportunity metric

## Phase 8 — LLM narrative layer

- Typed Claude tools: `get_metric`, `get_decomposition`, `get_top_movers`, `get_prescriber_profile`.
  No raw data access
- **Grounding verifier:** extract every numeral from generated text, verify against tool
  responses, regenerate once, then fail closed to a template
- Per-persona prompt templates — the DM summary is not the analyst deep-dive
- Cache by `(scope, period, data_version)` hash; log every prompt and response

**Exit:** adversarial eval set of 30 questions; invented figures caught 100% by the verifier.

## Phase 9 — Hardening

- RBAC enforcement tests — **test the negative case**: a rep must not read another territory
- Query performance: p95 < 800ms on the largest hierarchy rollup; document added indexes
- Audit log for every export
- Docker Compose + Terraform stubs, runbook, backup/restore doc
- k6 load test at 100 concurrent users

---

## Phase report format

```
SHIPPED:      <bullets>
TEST RESULTS: <actual output, pasted>
STUBBED:      <what is fake and where>
RISKS:        <what worries you>
NEXT 3:       <proposed issues>
```
