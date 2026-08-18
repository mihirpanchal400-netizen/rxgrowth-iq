# ADR 0001 — Core architecture

**Status:** Accepted · **Date:** 2026-08-19

## Context

We are building a prescription growth intelligence platform whose primary value is the
*correctness and explicability* of its domain math. Rx analytics fails in characteristic ways:
double-counting from misunderstood fact grain, share figures computed against an undeclared
competitive set, growth decompositions that silently drop the interaction term, and averages
distorted by treating absent periods as absent rather than zero.

Every architectural decision below is chosen to make one of those failures either impossible
or loudly detectable.

## Decisions

### 1. `core/` is a pure functional layer

Metric functions take primitives and dataframes, return values. No database, no HTTP, no clock
reads, no configuration lookups at call time.

**Why:** pure functions are exhaustively testable, including with property-based testing. The
decomposition identity `delta_B == market_effect + share_effect + interaction` can be asserted
across thousands of generated inputs only because the function has no environment.

**Cost:** callers must assemble inputs. Accepted — that assembly belongs in `services/` anyway.

### 2. Metric definitions have exactly one implementation

`core/metrics/` is the only place a formula is written. dbt and the ML feature store consume
it. Where dbt must compute in-warehouse for performance, the SQL is *generated* from the Python
spec and a CI test asserts parity between the two paths.

**Why:** the alternative — a formula in Python for the API and a hand-written one in SQL for
the warehouse — drifts within a quarter, and the drift surfaces as two dashboards disagreeing
in front of a customer.

### 3. `Decimal` for all volumes, never `float`

**Why:** projected Rx counts are fractional by nature. Float error compounds across a
five-level hierarchy rollup, and our decomposition identity asserts to 1e-9 — float noise alone
can break it on large national aggregates.

**Cost:** slower arithmetic, more conversion at boundaries. Accepted.

### 4. `fact_rx` grain is locked and enforced

Grain: **(prescriber, product, period, plan)**. A unique index in Postgres/DuckDB and a dbt
uniqueness test both enforce it.

**Why:** the single most common bug in this domain is aggregating as if the grain were coarser
— joining plan-level rows to a prescriber-level query and double-counting every prescription.
Enforcing at two layers means the mistake fails at write time or at build time, not silently at
read time.

### 5. Alignment is a first-class query parameter

Territory alignment changes mid-year. `alignment_basis` (`CURRENT | AS_OF`) is an explicit API
parameter, defaulting to `CURRENT`.

**Why:** both readings are legitimate and used for different questions — "how is this territory
doing now" versus "what did this rep actually deliver". Picking one silently means half the
users get an answer to a question they did not ask.

### 6. Periods are densified before averaging

A prescriber with no Rx in a week has **no row** in `fact_rx`. Every rollup densifies against
`dim_period` first.

**Why:** `mean()` over a sparse series silently answers "average of weeks they wrote", not
"average weekly volume". The gap is largest exactly for low-decile prescribers, which is where
targeting decisions are most marginal.

### 7. Synthetic data is the only data, enforced in CI

**Why:** licensed Rx data (IQVIA, Symphony, Komodo) carries data-use agreements that prohibit
storage outside the licensee's environment. A CI scanner failing the build on NPI-shaped
identifiers makes the accident impossible rather than merely discouraged. See
`docs/compliance.md`.

### 8. The LLM reads numbers only through typed tools, and output is verified

The narrative layer has no raw data access. Generated text is post-processed: every numeral is
extracted and checked against the tool responses for that request, with one regeneration
attempt, then a fail-closed fallback to a deterministic template.

**Why:** a fabricated market-share figure presented to a brand director ends trust in the whole
platform. Fail closed, never open.

### 9. No Docker in local development (revisited at Phase 9)

DuckDB file for the warehouse, SQLite via SQLAlchemy for app state, in-process cache instead of
Redis, MLflow in file mode.

**Why:** three daemons is friction disproportionate to the value at this stage, and the target
dev machine has no Docker installed. SQLAlchemy keeps Postgres a connection-string change.

**Revisit:** Phase 9, where Compose and Terraform arrive together for deployment.

## Consequences

- The domain math is auditable and property-testable. This is the point of the whole structure.
- Adding a metric means touching `core/`, its tests, and the metric dictionary — deliberately
  more friction than adding a SQL column, because a wrong metric is worse than a missing one.
- Local dev is fast and dependency-light; the production path is deferred, and that deferral is
  tracked rather than forgotten.
