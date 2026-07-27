# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A one-page static site listing every text/chat + embedding model deployable on **Azure OpenAI Data Zone Standard** in **Sweden Central** and **West Europe**, with official input/output token prices in DKK and USD.

Two files matter: **`generate.py`** (the whole build — registry, scrapers, and the HTML template as a string at the bottom) and **`index.html`** (the generated artifact, committed so GitHub Pages can serve it).

## Commands

```bash
python3 generate.py   # the only build; rewrites index.html in place
open index.html       # view the result
```

Python 3.12, **standard library only** — no venv, no requirements file, no package manager. Do not add dependencies.

There is no test suite and no linter. Verification is: `python3 generate.py` exits 0, leaves no `drift.txt` behind, and the resulting `index.html` looks right. The script hits four live sources on every run, so it needs network and cannot be run offline.

To find an Azure meter name (needed when adding a model):

```bash
curl -s "https://prices.azure.com/api/retail/prices?currencyCode=USD&\$filter=armRegionName%20eq%20'swedencentral'%20and%20productName%20eq%20'Azure%20OpenAI%20GPT5'"
```

## Architecture

**Never hand-edit `index.html`.** It is generated. The page's markup, CSS, and JS live in the `TEMPLATE` string at the bottom of `generate.py`; data is injected by replacing the literal `/*DATA*/null` with a JSON payload.

Data flow in `main()`:

1. `fetch_prices()` — Azure Retail Prices API, once per currency (Data Zone meters are zone-wide, so one region query covers both).
2. `fetch_cognigy_azure_support()`, `fetch_aa_scores()` (the Artificial Analysis τ³-Banking leaderboard), `fetch_availability()`, `fetch_reasoning_doc_text()` — four HTML scrapes.
3. `build_rows()` joins all of it against the hand-curated `MODELS` / `REASONING` registries.
4. Payload → `TEMPLATE` → `index.html`.

**Why the data is baked in rather than fetched in the browser:** the Azure prices API sends no CORS headers, and per-region deployability isn't exposed by *any* API. So fetching happens server-side in CI and the result is committed, keeping `index.html` a single static file that works offline and on plain GitHub Pages.

### Curated registry vs. scrapers

`MODELS` (`meterIn`/`meterOut`/`regions`/`released`) and `REASONING` are hand-maintained. The scrapers do **not** drive the table — three of them exist purely to detect that the registry has gone stale, because a new model release is otherwise invisible until someone spots it by eye (gpt-5.6 sat unnoticed for 18 days).

### Failure policy — the core design decision

Three deliberately distinct tiers:

| Tier | Trigger | Behavior |
|---|---|---|
| **Fatal** (`exit 1`) | A price meter that used to resolve is missing/renamed; Cognigy unparseable *and* no prior values to fall back on | `index.html` is left untouched, preserving last-known-good data. The failed run emails via an auto-assigned issue. |
| **Soft** (warning, build green) | Any single scrape failed | Last-known values carried over from the previous run |
| **Drift** (warning + `drift.txt`, build green) | Availability page lists a model missing from `MODELS`, or a region changed | Never fails the build — a new model must not freeze the daily price refresh for models already tracked |

`read_old_payload()` re-parses `const PAYLOAD = {...}` back out of the committed `index.html`. **That file is the state store** — there is no database and no cache.

`drift.txt` is gitignored, written only when drift exists, and deleted when it clears. It is the signal the workflow keys on.

### Adding a model to `MODELS` — the traps

- The meter must be a **Data Zone** meter (`DZ` / `Dz` / `Data Zone` in the name). `Gl` (Global Standard) meters sit right next to them and match every other filter — a `Gl` meter silently puts Global prices on a page that is entirely about Data Zone.
- For the 5.x family use the **short-context standard** tier: meters with `ShortCo` and `Std`, never `LongCo`, `Batch`, `PP` (priority processing), or `Cd`/`cchd` (cached). Add `"note": "short-context tier"`.
- `regions` is per model and comes from the Learn availability page — don't assume both regions.
- In `REASONING`, `default: None` means **"not documented for this specific model"**. Never infer a default from a sibling model or a summary; that failure mode renders as a plausible-but-wrong number that nothing downstream can catch.
- Model ids map to two external slug conventions: `cognigy_code()` (`gpt-5.` → `gpt-5-`) and `aa_slug()` (dots → dashes, used for every Artificial Analysis leaderboard).

### Scrapers are regex over HTML, by design

Stdlib-only means no HTML parser. Each scraper anchors on a structural landmark rather than position: Cognigy on the provider header row (`Microsoft Azure OpenAI`) so non-Azure sections are ignored; availability on `<h2 id="data-zone-standard">` plus the first table carrying both region columns; Artificial Analysis on the Next.js RSC payload (`self.__next_f.push`), matching each score to the nearest preceding `"slug"` — `fetch_aa_scores(url, field)` is parameterised by leaderboard (`tau_banking` on τ³-Banking), so swapping or adding one is a two-argument change. Every scraper catches broadly and returns `None` on failure — callers depend on that, so don't let exceptions escape.

### Frontend

Vanilla JS inside `TEMPLATE`, no build step: a `state` object plus a full `render()` redraw. Region/family/text filters, DKK↔USD toggle, sortable columns (rows with no price sink to the bottom), and a per-row expander showing reasoning-effort pills.

## CI (`.github/workflows/update.yml`)

Runs daily at 05:17 UTC and on demand ("Run workflow"). It regenerates, then commits `index.html` if changed — the `updated` timestamp is stamped every run, so there is a commit every day as proof the job ran.

When `drift.txt` exists, an assigned GitHub issue is opened (or commented on, if one is already open) naming the model. Filling in the registry is a hand edit — an agent-authored PR was tried and dropped: `claude-code-action` doesn't open the PR itself, and the action refuses to run unless the workflow is byte-identical to main, which made iterating on it costly.

The `fail_test` workflow input deliberately fails a run, to verify failure emails still arrive.

## Conventions

Comments in `generate.py` explain *why* (no CORS, no availability API, the drift incident that motivated the guard) rather than what. Preserve that when editing — most of the non-obvious constraints in this repo are only recorded there.
