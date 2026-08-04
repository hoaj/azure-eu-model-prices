# Azure OpenAI — EU Data Zone Standard model & price overview

> ## ⚠️ Retired — moved to an internal repository
>
> This project now lives at **`nuuday/aao-llm-guidedance`**, and the site is served privately at
> <https://solid-adventure-9mq575m.pages.github.io/index.html> (sign-in required).
>
> Nothing here is maintained any more. The daily price refresh workflow has been **deleted from
> this repository** and runs in the new home instead, so `index.html` here is a signpost page,
> not a generated artifact. `generate.py` is left in place for history only — running it would
> overwrite the signpost with a stale table.

A single-page overview of every text/chat + embedding model you can deploy on
**Data Zone Standard** in **Sweden Central** and **West Europe**, with official Azure
**input/output token prices in DKK and USD**.

Live demo: _set after enabling GitHub Pages (see below)_

## How it works

- **`generate.py`** — fetches live prices from the [Azure Retail Prices API](https://prices.azure.com/api/retail/prices)
  (DKK + USD, Data Zone meters) and writes a fully self-contained **`index.html`** with the data baked in.
  No dependencies beyond the Python standard library.
- It also scrapes the [Cognigy model-support page](https://docs.cognigy.com/ai/agents/develop/gen-ai-and-llms/model-support-by-feature)
  (no API exists — it's a static HTML table) for the **Microsoft Azure OpenAI** section: chat models are judged on
  *LLM Prompt Node* support, embeddings on *Knowledge Search*. If the scrape fails, the last-known values are kept.
- It also scrapes the [Artificial Analysis τ³-Banking leaderboard](https://artificialanalysis.ai/evaluations/tau3-banking)
  (no API — the scores live in the page's Next.js RSC payload, keyed by a `tau_banking` field) for
  each model's agentic customer-support score: find the right policy in a large knowledge base, then
  execute the correct multi-step tool sequence, graded on backend state. Fallback to last-known on
  failure. The scraper takes the leaderboard URL and payload field as arguments, so swapping or
  adding a leaderboard is a two-argument change. AA publishes each **reasoning-effort variant as its
  own entry** (`gpt-5-6-sol-high`, `…-low`, …), so the build assembles a per-effort *ladder* per
  model. The page's **τ³ at effort** control re-keys the score column to one tier, making the
  ranking apples-to-apples instead of comparing `gpt-5.6` at *max* against `gpt-5` at *high*; the
  row expander shows a model's whole curve. When that ladder shrinks or the scrape fails, the build
  stays green but writes `benchdrift.txt`, which the workflow turns into an assigned issue.
- It also scrapes the [Azure region-availability page](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability?pivots=standard#data-zone-standard)
  and **diffs it against the `MODELS` registry**. It doesn't drive the table — `regions` stays hand-curated —
  but the build now warns when a model becomes deployable in Sweden Central / West Europe and isn't listed,
  or when a region changes. Without this, a new release (GPT-5.6 did exactly this) is invisible until
  someone spots it by eye.
- **`index.html`** — the artifact. Self-contained; open it directly in a browser, or serve it via GitHub Pages.
- **`.github/workflows/update.yml`** — runs `generate.py` daily and on demand, commits the refreshed `index.html`.

### Why the data is baked in (and not fetched in the browser)

The Azure prices API sends **no CORS headers**, so a browser can't call it directly, and
**region availability** (e.g. `gpt-5.1` is Sweden Central only) isn't exposed by any API.
So the fetching happens server-side in GitHub Actions, and the result is committed. This keeps
`index.html` a single static file that works offline and on plain GitHub Pages.

## The "one-press refresh"

Open the repo's **Actions** tab → **Update prices** → **Run workflow**. It re-queries Azure,
regenerates `index.html`, commits, and GitHub Pages redeploys within ~30s. A daily schedule
(`05:17 UTC`) does the same automatically, so most of the time you don't press anything.

> Note: GitHub disables scheduled workflows after 60 days of repo inactivity (it emails you to re-enable).

## Enable GitHub Pages

Settings → **Pages** → Source: **Deploy from a branch** → Branch: **`main`** / **`/ (root)`** → Save.
The site appears at `https://<user>.github.io/<repo>/`.

> GitHub Pages on a **private** repo requires a paid plan (Pro/Team). On the free plan the repo
> must be **public** for Pages to publish.

## Update the model list / availability

Prices auto-refresh for the models in the registry. When a **new** model becomes deployable in
Sweden Central / West Europe, or a region changes, the daily run opens a GitHub issue assigned to
`@hoaj` naming the model. Add it to the `MODELS` list (meter names + `regions`) and, if it's a
reasoning model, to `REASONING` — using the
[availability page](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability?pivots=standard#data-zone-standard)
and the [prices API](https://prices.azure.com/api/retail/prices) as sources. Two things to watch
when picking a meter: it must be a **Data Zone** meter (`DZ`/`Dz`/`Data Zone` — the Global `Gl`
meters sit right beside them and otherwise look identical), and for the 5.x family the
**short-context standard** tier (`ShortCo` + `Std`, not `LongCo`/`Batch`/`PP`/cached).

Re-run `python3 generate.py` afterwards: it must exit 0 and leave no `drift.txt` behind. A wrong
meter name aborts the build; an incomplete entry keeps the drift warning alive.

`generate.py` fails the build outright if Azure renames a meter it already expects.

## Run locally

```bash
python3 generate.py   # rewrites index.html with the latest prices
open index.html       # macOS; or just double-click it
```
