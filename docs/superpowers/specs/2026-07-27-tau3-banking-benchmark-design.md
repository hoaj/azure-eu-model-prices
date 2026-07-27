# Second agentic benchmark column: τ³-Banking

**Date:** 2026-07-27
**Status:** approved for implementation

## Problem

The table's only benchmark column is the Artificial Analysis **τ²-Bench Telecom** score. AA has not
run τ²-Telecom for `gpt-5.6-luna` — the model is on the site, but its Telco τ² cell is `—`, so the
newest small-tier GPT-5.6 model can't be compared on agentic support work at all. `gpt-4o-mini` has
the same gap. A leaderboard AA stops extending is a column that decays: every future model release
risks landing with an empty cell.

## What was surveyed

Every AA evaluation page was checked for (a) whether `gpt-5-6-luna` has a score and (b) how much of
this site's 18-model registry it covers. Scores read from the Next.js RSC payload, same technique
the existing τ² scraper uses.

| AA leaderboard | payload key | covers luna | registry coverage |
|---|---|---|---|
| τ²-Bench Telecom (current) | `tau2` | **no** | 16/18 |
| **τ³-Banking** | `tau_banking` | **yes** (27.2) | **11/18** |
| IFBench | `ifbench` | no | 16/18 |
| APEX-Agents-AA | `apex_agents` | yes | 4/18 |
| ITBench-AA (SRE) | `it_bench_sre` | yes | 4/18 |
| Terminal-Bench v2.1 | `terminalbench_v2_1` | yes | 11/18 |
| AA-Briefcase / GDPval / AutomationBench | — | partial | ≤ 0–9/18, not support-shaped |

## Decision

Add **τ³-Banking** (`https://artificialanalysis.ai/evaluations/tau3-banking`) as a **second**
benchmark column, alongside — not replacing — Telco τ².

Why it is the right telco proxy:

- **Same framework.** τ³-Banking is the third benchmark in Sierra Research's τ-Knowledge series, the
  direct extension of the τ-Bench line that τ²-Telecom belongs to. Same dual-control setup, same
  grading philosophy.
- **Same shape of work as a telco contact centre.** 97 tasks over ~700 interconnected policy
  documents (~195K tokens, 21 product categories). The agent must retrieve the right policy from a
  large unstructured knowledge base *and* execute the correct multi-step sequence of tool calls.
  Graded against backend database state (was the dispute filed, was the credit issued), not
  conversational quality. Swap "dispute / provisional credit / product change" for "SIM swap /
  bill credit / tariff change" and it is the same job — which is exactly the work this page's
  Cognigy column is about.
- **It covers the gap.** `gpt-5.6-luna` scores 27.2; all three GPT-5.6 variants are on it.

Rejected: IFBench (best coverage, but no luna — doesn't solve the problem); APEX-Agents and
ITBench-AA (luna present, but 4/18 leaves a near-empty column); Terminal-Bench (good coverage, but
it measures terminal/SWE work, not customer support).

## Implementation

**`generate.py`**

1. Generalise the scraper. `fetch_tau2_telecom()` becomes `fetch_aa_scores(url, field)` —
   identical regex-over-RSC technique, parameterised by leaderboard URL and payload key. Two module
   constants: `AA_TAU2_URL`, `AA_TAU3_URL`. `tau2_slug()` → `aa_slug()` (both leaderboards use the
   same dots-to-dashes slug convention).
2. `build_rows()` takes `tau3` alongside `tau2`; the inner `tau2_data()` becomes a generic
   `bench()` used twice. New row fields `tau3` and `tau3_variant`, mirroring `tau2`/`tau2_variant`,
   including the last-known fallback via `old_by_id` when a scrape fails.
3. `main()` fetches both leaderboards and emits an independent soft warning per benchmark. A
   benchmark scrape failure stays **soft** (build green, last-known values kept) — unchanged policy.

**Template (inside `generate.py`)**

- New sortable column `Agentic τ³` after `Telco τ²`, same `hide`-on-mobile treatment.
- Distinct bar colour (indigo) so the two benchmark columns are not confused.
- Bars stay raw-percentage for both columns. τ³ tops out near 33% where τ² reaches 94%; a
  per-column relative bar would make 27% look like a top score.
- Sort comparator handles both keys; nulls sink. Detail-row `colspan` 8 → 9.
- Header source list gains a τ³-banking link; a new legend box explains what τ³-Banking measures
  and why it sits next to the telecom score.
- The existing τ² legend box keeps its "not on the leaderboard" note — still true for luna.

**Docs:** README data-source section and `CLAUDE.md` (scraper names, slug helper) updated to match.

## Verification

`python3 generate.py` exits 0, writes no `drift.txt`, and the regenerated `index.html` shows a
τ³ score for `gpt-5.6-luna` (27.2) plus all other models on the τ³ leaderboard. Spot-check the
rendered page: both benchmark columns sort, and the row expander still lines up.
