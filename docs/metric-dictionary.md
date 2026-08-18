# Metric Dictionary

The single source of truth for every metric in RxGrowth IQ. Implementations live in
`apps/api/src/rxiq/core/metrics/` and must match these formulas exactly. Each metric has a
stable `definition_id` returned alongside its value in every API response.

## Conventions

- All volume values are `Decimal`, never `float`.
- A zero denominator returns `0` for shares and `None` for growth rates — **never infinity,
  never NaN.** Both cases set a `quality_flag` on the result.
- Every metric is evaluated against a `period_basis` (`WEEK | MONTH | QUARTER`) and, where
  hierarchy is involved, an `alignment_basis` (`CURRENT | AS_OF`).
- Periods are densified against `dim_period` before any averaging. A prescriber with no Rx in
  a week has no row in `fact_rx`; treating that as absent rather than zero misstates means.

---

## 1. Volume

| `definition_id` | Metric | Definition |
|---|---|---|
| `vol.trx` | TRx | Total prescriptions dispensed in period (new + refills) |
| `vol.nrx` | NRx | New prescriptions — new starts + switches, excludes refills |
| `vol.nbrx` | NBRx | New-to-brand: no dispensed claim for this brand within the lookback window (default 12 months, configurable per brand) |

NBRx arrives pre-aggregated from the data vendor. It is **not** derived here from patient-level
records — see `compliance.md`.

All volume is projected. `projection_factor` travels with every fact row and raw panel counts
are never presented as actuals.

## 2. Share

Share requires an explicit **market basket** — the configured competitive set. A share metric
without a named basket is meaningless and the API must reject the request.

```
share.market = sum(brand_TRx)  / sum(basket_TRx)     # 0 if denominator == 0, flagged
share.nbrx   = sum(brand_NBRx) / sum(basket_NBRx)
```

| `definition_id` | Metric |
|---|---|
| `share.market` | Market share (TRx basis) |
| `share.nbrx` | New-to-brand share — the leading indicator; moves before TRx share |

## 3. Growth

```
growth.pct  = (m[t] - m[t-1])   / m[t-1]      # None if m[t-1] == 0
growth.yoy  = (m[t] - m[t-52w]) / m[t-52w]
growth.roll = sum(m[t-n+1 .. t])              # n in {4, 13, 26, 52}
```

| `definition_id` | Metric |
|---|---|
| `growth.pct` | Period-over-period growth |
| `growth.yoy` | Year-over-year growth |
| `growth.r4` / `.r13` / `.r26` / `.r52` | Rolling sums |

Products launched inside the comparison window have no valid YoY. Return `None` with
`quality_flag = INSUFFICIENT_HISTORY` rather than comparing against a partial baseline.

---

## 4. Growth Decomposition A — market vs. share

**The flagship metric.** Answers: did we grow because the market grew, or because we won share?

Let `B` = brand TRx, `M` = market TRx, `S = B / M`. Subscript `0` = baseline, `1` = current.

```
market_effect = S0 * (M1 - M0)          # growth we'd have had at flat share
share_effect  = M0 * (S1 - S0)          # growth from share movement at baseline market size
interaction   = (M1 - M0) * (S1 - S0)   # joint effect — do NOT drop this term
```

**Identity — assert on every computation:**
```
B1 - B0 == market_effect + share_effect + interaction    (tolerance 1e-9)
```

Dropping the interaction term is the most common error in spreadsheet implementations and is
why their waterfalls never quite reconcile. Property-based tests (Hypothesis) verify the
identity across randomly generated inputs.

`definition_id`: `decomp.market_share`

## 5. Growth Decomposition B — breadth vs. depth

Answers: did we grow by adding writers, or by getting more from existing ones?

Let `W` = number of writers, `D` = TRx per writer. `B = W * D`.

```
breadth_effect = D0 * (W1 - W0)
depth_effect   = W0 * (D1 - D0)
interaction    = (W1 - W0) * (D1 - D0)
```

Same identity assertion applies. `definition_id`: `decomp.breadth_depth`

## 6. Growth Decomposition C — hierarchical contribution

For any parent node, attribute `delta_TRx` to each child, sorted by absolute contribution.
Child contributions **must sum to the parent delta exactly**. Under `alignment_basis = AS_OF`,
prescribers that moved territory mid-period are attributed to their alignment at each point in
time, not their current one.

`definition_id`: `decomp.hierarchy`

---

## 7. Writer status

Per prescriber, per brand, per period:

| Status | Definition |
|---|---|
| `NEVER` | No brand Rx in any period on record |
| `NEW` | First brand Rx in the current period |
| `CONTINUING` | Wrote in both current and prior window, change within +/- threshold |
| `GROWING` | Wrote in both, current > prior by more than threshold |
| `DECLINING` | Wrote in both, current < prior by more than threshold |
| `LAPSED` | Wrote in the prior window, zero in the current window |

Threshold is config, not a literal. Status transitions are a core ML feature — a
`CONTINUING → DECLINING` flip is the earliest churn signal available.

## 8. Opportunity sizing

Per prescriber:

```
target_share  = 75th-percentile brand share among peers in the same
                (specialty, decile, access_status) cohort
potential_trx = market_trx_prescriber * target_share
opportunity   = max(0, potential_trx - actual_brand_trx)
```

Peer-cohort benchmarking rather than an absolute target — a prescriber in a `NOT_COVERED` plan
mix cannot reach the share of one in a `PREFERRED` mix, and scoring them against the same bar
sends reps on wasted calls. Cohorts below a minimum size fall back to the next-coarser cohort
(drop `access_status`, then `decile`); record which level was used.

`definition_id`: `opp.headroom`

## 9. Promotional response

```
reach     = count(p in targets : calls(p) >= 1) / count(targets)
frequency = sum(calls) / count(p : calls(p) >= 1)
sov       = brand_calls / total_tracked_market_calls          # share of voice
call_yield = delta_NBRx over 8 weeks post-call / calls
```

> ### `call_yield` is correlational, not causal
>
> Reps are sent to prescribers who were already growing — that is what targeting *is*. The
> resulting correlation is confounded by design.
>
> **Requirements:** any UI surfacing `call_yield` must label it as an association. The LLM
> narrative layer must never render it with causal language ("drove", "caused", "resulted in").
> The Phase 5 uplift model is the causal estimate, and even that carries an unmeasured-
> confounding caveat in its model card.

| `definition_id` | Metric |
|---|---|
| `promo.reach` / `promo.frequency` / `promo.sov` | Activity metrics |
| `promo.call_yield` | Association only — carries `causal: false` in its response envelope |
