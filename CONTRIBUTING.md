# Contributing

## Workflow — follow literally

One issue → one branch → one PR. No direct commits to `main`.

```bash
git checkout main && git pull
git checkout -b <type>/<issue#>-<slug>     # feat|fix|chore|docs|refactor|test|perf
# ... work, committing in logical units ...
gh pr create --fill --base main
# wait for CI; fix anything red before requesting review
```

## Commits

[Conventional Commits](https://www.conventionalcommits.org/). Scope is the area: `metrics`,
`api`, `web`, `ml`, `llm`, `dbt`, `synth`, `ci`.

```
feat(metrics): add market/share growth decomposition

Implements delta_B = market_effect + share_effect + interaction with an
identity assertion to 1e-9. Property tests via Hypothesis cover randomly
generated inputs including zero-market and zero-share edge cases.

Closes #42
```

## PR template

```markdown
## What & Why

## Metric definitions touched
<!-- formula + link to docs/metric-dictionary.md -->

## Test evidence
<!-- paste actual output. "tests pass" is not evidence. -->

## Screenshots / API samples

## Data integrity impact
<!-- Does this change a grain? A rollup? Does it need a backfill? -->

## Not Done
<!-- Be honest. List anything stubbed, deferred, or knowingly incomplete. -->

## Compliance check
- [ ] No real or licensed data added
- [ ] No PHI
- [ ] Prescriber suppression respected on any new read path
- [ ] Audit-logged if this exports data
```

## Labels

`phase-0` … `phase-9` · `area:data` · `area:api` · `area:web` · `area:ml` · `area:llm` ·
`compliance` · `tech-debt` · `needs-domain-input` · `blocked`

## Branch protection on `main`

Require PR · require CI green · require conversation resolution · squash-merge only ·
linear history · no force push.

## Review checklist

- [ ] Does any metric here match `docs/metric-dictionary.md` **exactly**?
- [ ] Do decomposition identities assert to 1e-9?
- [ ] Are zero denominators and missing periods handled — and tested?
- [ ] Is `fact_rx` still aggregated at its true grain (prescriber, product, period, plan)?
- [ ] Is `Decimal` used for volumes, not `float`?
- [ ] Does `core/` remain pure — no DB, HTTP, or clock reads?
- [ ] Is a correlational metric labelled as such wherever it surfaces?
- [ ] Does the app still run end to end?
