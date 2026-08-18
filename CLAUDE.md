# RxGrowth IQ — Standing Rules

Pharmaceutical Prescription Growth Intelligence Platform.
Full spec: `docs/BRIEF.md`. Phase plan: `docs/ROADMAP.md`. Workflow: `CONTRIBUTING.md`.

## Non-negotiables

1. **Never invent domain math.** Every metric must match `docs/metric-dictionary.md` exactly.
   If a metric is ambiguous, stop and ask — do not guess a formula.
2. **Synthetic data only.** No real prescription, patient, or licensed vendor data in this
   repo, ever. See `docs/compliance.md`. CI enforces this.
3. **Test-first for business logic.** Any function computing a metric, cohort, or feature
   ships with unit tests covering: zero denominators, missing periods, negative adjustments,
   and newly launched products with no prior-year history.
4. **One issue → one branch → one PR.** No direct commits to `main`.
5. **Vertical slices.** Every PR leaves the app runnable end to end. Never merge a backend
   change whose consumer does not exist — stub it in the same PR.
6. **Report honestly.** Failing tests get pasted, not paraphrased. Anything skipped goes in
   the PR body under `## Not Done`.

## Architecture rules

- **`apps/api/src/rxiq/core/` is pure.** Metric functions take primitives/dataframes in,
  return values out. No DB, no HTTP, no clock reads. This is what makes the math auditable.
- **Metric definitions live in exactly one place** (`core/metrics/`). API, dbt, and the ML
  feature store all consume them. Never reimplement a formula in SQL where it can drift —
  if dbt must compute in-warehouse, generate the SQL from the Python spec and assert parity
  in a CI test.
- **Use `Decimal`, never `float`,** for all volume and currency values. Projected Rx counts
  are fractional and rounding error compounds across hierarchy rollups.
- **Every API response carrying a metric also carries `definition_id` and `period_basis`.**

## Local stack (adapted — no Docker)

DuckDB file = warehouse. SQLite = app state (via SQLAlchemy, so Postgres is a connection-string
swap later). In-process cache instead of Redis. MLflow in file mode (`file:./mlruns`).
Task runner is `uv run`, not `make`. Docker/Compose returns at Phase 9.

## Domain glossary

- **TRx** — total prescriptions dispensed (new + refills).
- **NRx** — new prescriptions (new starts + switches; excludes refills).
- **NBRx** — new-to-brand: no dispensed claim for this brand in the lookback window
  (default 12 months, configurable per brand).
- **Market basket** — the competitive set. Share metrics are meaningless without one; it is a
  first-class configurable entity.
- **Decile** — prescribers ranked by *market* volume (not brand volume) into 10 bins;
  10 = highest. Recomputed quarterly.
- **Writer status** — `NEVER | NEW | CONTINUING | GROWING | DECLINING | LAPSED`
  (LAPSED = wrote in the prior window, zero in the current one).
- **Projection factor** — panel data projected to 100%. Carry it; never show raw panel counts
  as actuals.
- **Access status** — `PREFERRED | COVERED | NON_PREFERRED | PRIOR_AUTH | STEP_THERAPY |
  NOT_COVERED`.

## Metric formulas — implement exactly

```
market_share = sum(brand_TRx) / sum(basket_TRx)      # 0 if denom == 0, and flag it
growth_pct   = (m[t] - m[t-1]) / m[t-1]              # None if m[t-1] == 0 — never infinity
yoy_growth   = (m[t] - m[t-52w]) / m[t-52w]
```

**Decomposition A — market vs. share.** `B` = brand TRx, `M` = market TRx, `S = B/M`:
```
market_effect = S0 * (M1 - M0)
share_effect  = M0 * (S1 - S0)
interaction   = (M1 - M0) * (S1 - S0)
assert B1 - B0 == market_effect + share_effect + interaction   # to 1e-9. Always assert.
```

**Decomposition B — breadth vs. depth.** `W` = writers, `D` = TRx/writer, `B = W * D`:
```
breadth_effect = D0 * (W1 - W0)
depth_effect   = W0 * (D1 - D0)
interaction    = (W1 - W0) * (D1 - D0)
```

**Decomposition C — hierarchical contribution.** Child contributions must sum to the parent
delta exactly.

**Opportunity sizing.** `target_share` = 75th-percentile share among peers in the same
(specialty, decile, access_status) cohort; `opportunity = max(0, market_trx * target_share -
actual_brand_trx)`.

> `call_yield` (delta NBRx over 8 weeks post-call / calls) is **correlational, not causal**.
> Any UI surfacing it must say so. The uplift model (Phase 5) is the causal path. Never let
> the LLM narrative describe it as "caused by".

## Data integrity

- `fact_rx` grain is **(prescriber, product, period, plan)** — unique index + dbt uniqueness
  test. Aggregating as if the grain were coarser is the #1 source of double-counting bugs.
- **Territory alignment is slowly-changing.** History must be restateable under both current
  and as-of alignment. Expose `alignment_basis` as an explicit API parameter; default current.
- **A prescriber with no Rx in a week has no row, not a zero row.** Every rollup must densify
  against `dim_period` or it will silently misstate averages.

## Quality bar

- `mypy --strict` clean on `apps/api/src`. **No `Any` in `core/`.**
- `tsc --noEmit` clean; no `any` in `web/lib` or `web/components`.
- Coverage gates: `core/` >= 95%, `services/` >= 85%, overall >= 80%. CI fails on regression.
- Every public function in `core/` has a docstring with its formula and a worked example.
- No magic numbers — lookback windows, thresholds, percentile targets are config, and every
  default is justified in a comment.
- Charts: colorblind-safe palette, dark/light parity, axes labeled with units and period basis,
  visible "data as of" stamp on every screen.
- Accessibility: keyboard-navigable tables, ARIA on charts with a data-table fallback.

## Commits

Conventional Commits. Scope = area: `metrics`, `api`, `web`, `ml`, `llm`, `dbt`, `synth`.
