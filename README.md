# Azure OpenAI — EU Data Zone Standard model & price overview

A single-page overview of every text/chat + embedding model you can deploy on
**Data Zone Standard** in **Sweden Central** and **West Europe**, with official Azure
**input/output token prices in DKK and USD**.

Live demo: _set after enabling GitHub Pages (see below)_

## How it works

- **`generate.py`** — fetches live prices from the [Azure Retail Prices API](https://prices.azure.com/api/retail/prices)
  (DKK + USD, Data Zone meters) and writes a fully self-contained **`index.html`** with the data baked in.
  No dependencies beyond the Python standard library.
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
changes, edit the `MODELS` list at the top of `generate.py` (meter names + `regions`), using the
[availability page](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability?pivots=standard#data-zone-standard)
as the source, then re-run. `generate.py` prints a `WARNING` if Azure ever renames a meter it expects.

## Run locally

```bash
python3 generate.py   # rewrites index.html with the latest prices
open index.html       # macOS; or just double-click it
```
