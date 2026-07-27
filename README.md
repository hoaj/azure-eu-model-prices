# Azure OpenAI — EU Data Zone Standard model & price overview

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
- It also scrapes two [Artificial Analysis](https://artificialanalysis.ai/evaluations) agentic-support
  leaderboards (no API — the scores live in each page's Next.js RSC payload):
  [τ²-Bench Telecom](https://artificialanalysis.ai/evaluations/tau2-bench) (`tau2` field) and
  [τ³-Banking](https://artificialanalysis.ai/evaluations/tau3-banking) (`tau_banking` field).
  τ²-Telecom is the telco benchmark, but AA never ran it for every model — `gpt-5.6-luna` and
  `gpt-4o-mini` are absent from it. τ³-Banking is the next benchmark in the same Sierra τ-series and
  tests the same job (find the right policy in a large knowledge base, then execute the correct
  multi-step tool sequence, graded on backend state), in the banking domain instead — and it *does*
  cover the whole GPT-5.6 line. Each falls back to last-known on failure, independently.
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

Prices auto-refresh for the models in the registry. When a **new** model appears or a region
changes, the daily run detects it and does two things:

1. **Opens an issue** assigned to `@hoaj` naming the model — the durable notification.
2. **Drafts the registry entry as a pull request**, using
   [`anthropics/claude-code-action`](https://github.com/anthropics/claude-code-action).
   It runs only on drift (roughly once a quarter), never on the daily no-op.

The PR is gated on the generator agreeing: the agent must leave `python3 generate.py` exiting 0
with no `drift.txt` remaining. That catches a wrong meter name (the build aborts with *price meter
missing or renamed*) and an incomplete entry (drift persists) — the two failure modes that would
otherwise render as plausible-but-wrong numbers. It does **not** catch a wrong `reasoning` default,
which is why this opens a PR for review instead of committing to `main`. **Review before merging.**

Requires the `COMPLIANTMODELS` repo secret (an Anthropic API key). Without it that step fails and is skipped
(`continue-on-error`) — the issue still gets opened and prices still refresh, so you can also just
edit the `MODELS` / `REASONING` registry by hand from the
[availability page](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability?pivots=standard#data-zone-standard).

`generate.py` fails the build outright if Azure renames a meter it already expects.

## Run locally

```bash
python3 generate.py   # rewrites index.html with the latest prices
open index.html       # macOS; or just double-click it
```
