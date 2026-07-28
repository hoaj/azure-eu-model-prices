# τ³ score per reasoning effort

**Date:** 2026-07-28
**Status:** implemented

## Problem

The `Agentic τ³` column shows one score per model, taken from whatever reasoning effort Artificial
Analysis ran hardest. That means the column silently mixes tiers: `gpt-5.6-sol` is scored at `max`,
`gpt-5.5` at `xhigh`, `gpt-5` at `high`. Sorting it ranks models that were not asked to do the same
amount of thinking, and the page gives no way to ask the two questions that matter when picking a
model:

- **Within a model** — how much does the score actually improve from `low` to `max`? Is the most
  expensive tier worth the extra output tokens?
- **Across models** — which model is best *at the same effort*? A cheap model at `max` may beat an
  expensive one at `medium`, and today's column cannot show that.

The reasoning-effort data was already half-present on the page: the row expander lists which effort
levels Azure supports, but attaches no outcome to any of them.

## What the source actually provides

AA models each reasoning-effort variant as **its own leaderboard entry**. The base slug carries the
highest effort AA ran; lower efforts are suffixed:

```
gpt-5-6-sol                33.0   "GPT-5.6 Sol (max)"      <- base = highest effort
gpt-5-6-sol-xhigh          32.6   "GPT-5.6 Sol (xhigh)"
gpt-5-6-sol-high           30.6   "GPT-5.6 Sol (high)"
gpt-5-6-sol-medium         26.5   "GPT-5.6 Sol (medium)"
gpt-5-6-sol-low            24.4   "GPT-5.6 Sol (low)"
gpt-5-6-sol-non-reasoning  16.1   "GPT-5.6 Sol (Non-reasoning)"
```

Coverage across the registry, read from the τ³ RSC payload:

| Model | none | low | medium | high | xhigh | max |
|---|---|---|---|---|---|---|
| gpt-5.6-sol | 16.1 | 24.4 | 26.5 | 30.6 | 32.6 | **33.0** |
| gpt-5.6-terra | 13.4 | 16.1 | 19.4 | 22.3 | 24.3 | **31.8** |
| gpt-5.6-luna | 9.1 | 12.0 | 15.3 | 22.3 | 24.3 | **27.2** |
| gpt-5.5 | 13.8 | 21.2 | 25.8 | 29.5 | **31.3** | — |
| gpt-5.4 | — | — | — | — | **30.3** | — |
| gpt-5 / gpt-5.1 / gpt-5-mini | — | — | — | **single** | — | — |
| o3-mini | — | — | — | **5.2** | — | — |

Four models have a real ladder; the rest are single-point. That asymmetry is the design constraint:
the feature must stay useful when most rows have one data point.

`o3-mini` is a pre-existing blind spot — AA publishes it *only* as `o3-mini-high`, with no base
slug, so today's exact-slug lookup finds nothing and the cell renders `—`. Scanning suffixes fixes
it as a side effect.

## Decision

A **global effort selector** re-keys the τ³ column, and the **row expander** gains the per-effort
ladder. Both questions get answered, and neither needs a new column.

Rejected: expander-only (no way to rank models at a fixed effort without opening every row); a
column per effort level (six mostly-empty columns, and it breaks the page's one-line-per-model
layout).

## Implementation

**`generate.py`**

1. `fetch_aa_scores()` is **unchanged** — it already returns every slug on the leaderboard, variant
   entries included. Only the join changes.
2. New `aa_ladder(scraped, model_id)` returns `({effort: score}, best_effort, best_label)`. It scans
   the base slug plus each known effort suffix. AA's `non-reasoning` normalises to Azure's `none`.
   The base entry's own effort is recoverable **only from its display label** — `"GPT-5.6 Sol (max)"`
   — so an unparseable label degrades to "best, effort unknown" rather than guessing a tier.
3. Row payload gains `tau3_by_effort` (`{}` when absent) and `tau3_best_effort`, alongside the
   existing `tau3` / `tau3_variant`, which keep their current meaning so nothing regresses. The
   last-known fallback in `bench()` carries all four.
4. No new failure tier. A missing ladder is ordinary absent data, rendered `—`, not a build problem.

**Template (inside `generate.py`)**

- A fourth segmented control, `Effort`, after Family: `Best · max · xhigh · high · medium · low ·
  none`, defaulting to `Best` so the page loads exactly as it does today.
- Selecting an effort re-keys the τ³ cell, retitles the header to `Agentic τ³ · high`, and shows `—`
  where AA did not test that model at that effort.
- **Sorting reads the displayed value**, so sort-by-τ³ at a fixed effort is a true apples-to-apples
  ranking. Nulls keep sinking to the bottom.
- Expander pills stay driven by the curated `REASONING` options — Azure remains the source of truth
  for what is *supported* — with AA scores attached where they exist. A supported-but-unbenchmarked
  level shows a pill with no number, so the two sources stay visibly distinct instead of being
  silently merged. An effort AA scored that Azure does not list is rendered as a marked outlier.
- Ladder bars scale to the **global best score across all models and efforts** (~33), not per-row.
  Per-row scaling would make luna's ladder look identical to sol's; a global denominator keeps the
  pills cross-model comparable — the same reasoning behind the column's raw-scale bar.

**Docs:** `CLAUDE.md` gains the variant-slug convention and the label-parenthetical trap; README's
data-source section notes the effort selector.

## Verification

`python3 generate.py` exits 0 and writes no `drift.txt`. In the regenerated `index.html`: the
selector switches the column, `gpt-5.6-sol` at `high` reads 30.6 while `gpt-5.5` reads 29.5,
`gpt-5.4` reads `—` at every effort except `xhigh`, `o3-mini` now reads 5.2, and expanding
`gpt-5.6-sol` shows all six scores on its effort pills. Confirmed by screenshot.
