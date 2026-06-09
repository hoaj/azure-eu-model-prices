#!/usr/bin/env python3
"""
generate.py — Build a self-contained index.html overview of Azure OpenAI models
available under **Data Zone Standard** deployment in the EU regions
**Sweden Central** and **West Europe**, with official **DKK** input/output token prices.

Run by a daily agent:  python3 generate.py

Data sources
------------
1. Prices  : Azure Retail Prices API (https://prices.azure.com/api/retail/prices),
             queried in DKK. Data Zone meters are *zone-wide* (identical for every
             EU region), so one query supplies the price for both regions.
2. Availability (which specific region you can actually deploy in) is NOT exposed by
             any API and is NOT the same as price availability. It lives only on the
             Microsoft Learn region-availability page:
             https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability?pivots=standard#data-zone-standard
             It changes rarely and is curated below in MODELS[*]["regions"].
             >>> When a NEW model appears (auto-discovered via prices), or availability
                 shifts, update the MODELS registry below from that page. <<<

Scope: text/chat LLMs + text embeddings. Audio/realtime/image/router excluded.
"""

import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

CURRENCIES = ["DKK", "USD"]  # fetched from the API; UI toggles between them
PRICE_REGION = "swedencentral"  # Data Zone prices are zone-wide; one region is enough.
PRODUCTS = [
    "Azure OpenAI",
    "Azure OpenAI GPT5",
    "Azure OpenAI Reasoning",
    "Azure OpenAI Embedding",
]

SC, WE = "swedencentral", "westeurope"

# --- Model registry -----------------------------------------------------------
# meterIn / meterOut are the EXACT Data Zone *standard* (non-batch, non-cached,
# non-provisioned) token meter names. "regions" is curated from the Learn page.
# "released" is the deployed model *version* date shown on the Learn availability
# page (embeddings use their OpenAI release date). Used for the Released column/sort.
MODELS = [
    # GPT family
    {"id": "gpt-4.1",      "family": "GPT", "released": "2025-04-14", "meterIn": "gpt 4.1 Inp Data Zone Tokens",       "meterOut": "gpt 4.1 Outp Data Zone Tokens",       "regions": [SC, WE]},
    {"id": "gpt-4.1-mini", "family": "GPT", "released": "2025-04-14", "meterIn": "gpt 4.1 mini Inp Data Zone Tokens",  "meterOut": "gpt 4.1 mini Outp Data Zone Tokens",  "regions": [SC, WE]},
    {"id": "gpt-4.1-nano", "family": "GPT", "released": "2025-04-14", "meterIn": "gpt 4.1 nano Inp Data Zone Tokens",  "meterOut": "gpt 4.1 nano Outp Data Zone Tokens",  "regions": [SC, WE]},
    {"id": "gpt-4o",       "family": "GPT", "released": "2024-11-20", "meterIn": "gpt 4o 1120 Inp Data Zone Tokens",   "meterOut": "gpt 4o 1120 Outp Data Zone Tokens",   "regions": [SC, WE], "note": "v2024-11-20"},
    {"id": "gpt-4o-mini",  "family": "GPT", "released": "2024-07-18", "meterIn": "gpt 4o mini 0718 Inp Data Zone Tokens", "meterOut": "gpt 4o mini 0718 Outp Data Zone Tokens", "regions": [SC, WE]},
    {"id": "gpt-5",        "family": "GPT", "released": "2025-08-07", "meterIn": "GPT 5 Inpt DZone 1M Tokens",         "meterOut": "GPT 5 outpt DZone 1M Tokens",         "regions": [SC, WE]},
    {"id": "gpt-5-mini",   "family": "GPT", "released": "2025-08-07", "meterIn": "GPT 5 Mini Inpt DZone 1M Tokens",    "meterOut": "GPT 5 Mini outpt DZone 1M Tokens",    "regions": [SC, WE]},
    {"id": "gpt-5-nano",   "family": "GPT", "released": "2025-08-07", "meterIn": "GPT 5 Nano Inpt DZone 1M Tokens",    "meterOut": "GPT 5 Nano outpt DZone 1M Tokens",    "regions": [SC, WE]},
    {"id": "gpt-5.1",      "family": "GPT", "released": "2025-11-13", "meterIn": "GPT 5.1 inp Dz 1M Tokens",           "meterOut": "GPT 5.1 opt Dz 1M Tokens",            "regions": [SC]},
    {"id": "gpt-5.4",      "family": "GPT", "released": "2026-03-05", "meterIn": "5.4 inp Dz 1M Tokens",               "meterOut": "5.4 opt Dz 1M Tokens",                "regions": [SC, WE], "note": "short-context tier"},
    {"id": "gpt-5.5",      "family": "GPT", "released": "2026-04-24", "meterIn": "5.5 ShortCo inp Dz 1M Tokens",       "meterOut": "5.5 ShortCo opt Dz 1M Tokens",        "regions": [SC, WE], "note": "short-context tier"},
    # o-series (reasoning-capable, shown under GPT)
    {"id": "o1",      "family": "GPT", "released": "2024-12-17", "meterIn": "o1 1217 Inp Data Zone Tokens",      "meterOut": "o1 1217 Outp Data Zone Tokens",       "regions": [SC, WE]},
    {"id": "o3",      "family": "GPT", "released": "2025-04-16", "meterIn": "o3 0416 Inp Data Zone Tokens",      "meterOut": "o3 0416 Outp Data Zone Tokens",       "regions": [SC, WE]},
    {"id": "o3-mini", "family": "GPT", "released": "2025-01-31", "meterIn": "o3 mini 0131 input Data Zone Tokens", "meterOut": "o3 mini 0131 output Data Zone Tokens", "regions": [SC, WE]},
    {"id": "o4-mini", "family": "GPT", "released": "2025-04-16", "meterIn": "o4-mini 0416 Inp Data Zone Tokens", "meterOut": "o4-mini 0416 Outp Data Zone Tokens",  "regions": [SC, WE]},
    # Embeddings (input only)
    {"id": "text-embedding-3-large", "family": "Embedding", "released": "2024-01-25", "meterIn": "text embedding 3 large DZ Tokens", "meterOut": None, "regions": [SC, WE]},
    {"id": "text-embedding-3-small", "family": "Embedding", "released": "2024-01-25", "meterIn": "text embedding 3 small DZ Tokens", "meterOut": None, "regions": [SC, WE]},
    {"id": "text-embedding-ada-002", "family": "Embedding", "released": "2022-12-15", "meterIn": None, "meterOut": None, "regions": [SC, WE], "note": "no Data Zone meter"},
]


# Cognigy model-support is published only as a static HTML table (no API):
#   https://docs.cognigy.com/ai/agents/develop/gen-ai-and-llms/model-support-by-feature
# We scrape it, locking onto the "Microsoft Azure OpenAI" provider section only.
# Chat models are judged on the "LLM Prompt Node" column; embeddings on "Knowledge Search".
COGNIGY_URL = "https://docs.cognigy.com/ai/agents/develop/gen-ai-and-llms/model-support-by-feature"
COGNIGY_PROVIDER = "Microsoft Azure OpenAI"


def cognigy_code(model_id):
    """Map our model id to the code Cognigy uses (only the 5.x family differs: dot -> dash)."""
    return model_id.replace("gpt-5.", "gpt-5-")


def fetch_cognigy_azure_support():
    """Scrape the support matrix. Returns {cognigy_code: {"llm_prompt": bool|None,
    "knowledge_search": bool|None}} for the Microsoft Azure OpenAI section, or None on failure.

    The table groups models per provider: a header row carries the provider name (e.g.
    "Microsoft Azure OpenAI"), and the model rows beneath it list <code>…</code> models with a
    check-circle / x-mark icon per feature column. We only keep rows under the Azure header.
    """
    try:
        req = urllib.request.Request(COGNIGY_URL, headers={"User-Agent": "Mozilla/5.0 (price-bot)"})
        with urllib.request.urlopen(req, timeout=60) as r:
            doc = r.read().decode("utf-8", "replace")
        tm = re.search(r"<table.*?</table>", doc, re.S)
        if not tm:
            return None
        table = tm.group(0)
        headers = [re.sub("<[^>]+>", "", x).strip() for x in re.findall(r"<th[^>]*>(.*?)</th>", table, re.S)]

        def col(name):
            for i, hh in enumerate(headers):
                if name in hh:
                    return i
            return None

        li, ki = col("LLM Prompt Node"), col("Knowledge Search")
        if li is None or ki is None:
            return None

        out, current = {}, None
        for row in re.findall(r"<tr>(.*?)</tr>", table, re.S):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            if not tds:
                continue
            first, codes = tds[0], re.findall(r"<code>(.*?)</code>", tds[0])
            if not codes:                                   # provider section header
                text = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", first)).strip()
                if text:
                    current = text
                continue
            if current != COGNIGY_PROVIDER:                 # ignore every non-Azure section
                continue
            cells = tds[1:]                                 # feature columns align to headers[1:]

            def mark(header_idx):
                td = cells[header_idx - 1] if 0 <= header_idx - 1 < len(cells) else ""
                if "icons/check-circle" in td:
                    return True
                if "icons/x-mark" in td:
                    return False
                return None

            lp, ks = mark(li), mark(ki)
            for c in codes:
                out[c] = {"llm_prompt": lp, "knowledge_search": ks}
        return out or None
    except Exception as e:  # network/parse failure -> caller falls back to last-known values
        print(f"WARNING: Cognigy scrape failed: {e}", file=sys.stderr)
        return None


def fetch_prices(region, currency):
    """Return {meterName: price_per_million} for all OpenAI products in `region`."""
    out = {}
    base = "https://prices.azure.com/api/retail/prices"
    for product in PRODUCTS:
        flt = f"armRegionName eq '{region}' and productName eq '{product}'"
        url = f"{base}?currencyCode={currency}&$filter=" + urllib.parse.quote(flt)
        while url:
            with urllib.request.urlopen(url, timeout=60) as r:
                d = json.load(r)
            for it in d["Items"]:
                price = it["retailPrice"]
                unit = it["unitOfMeasure"]
                per_m = price * 1000 if unit.strip() == "1K" else price  # normalise to 1M
                out[it["meterName"]] = round(per_m, 4)
            url = d.get("NextPageLink")
    return out


def build_rows(prices_by_cur, cognigy, old_cog):
    """prices_by_cur: {currency: {meterName: price_per_million}}.
    cognigy: scraped Azure support map (or None). old_cog: {id: cognigy dict} from last run."""
    def lookup(meter):
        if not meter:
            return None
        return {cur: prices_by_cur[cur].get(meter) for cur in CURRENCIES}

    def cog_status(m):
        # embeddings are judged on Knowledge Search; everything else on the LLM Prompt Node
        feat = "knowledge_search" if m["family"] == "Embedding" else "llm_prompt"
        label = "Knowledge Search" if feat == "knowledge_search" else "Prompt Node"
        if cognigy is None:                                  # scrape failed -> keep last-known
            prev = old_cog.get(m["id"])
            return prev if isinstance(prev, dict) else {"status": "unknown", "feature": None}
        entry = cognigy.get(cognigy_code(m["id"]))
        if not entry:                                        # not listed for Azure (the o-series)
            return {"status": "unknown", "feature": None}
        v = entry[feat]
        status = "yes" if v else ("no" if v is False else "unknown")
        return {"status": status, "feature": label if status != "unknown" else None}

    rows = []
    for m in MODELS:
        rows.append({
            "id": m["id"],
            "family": m["family"],
            "released": m["released"],
            "cognigy": cog_status(m),
            "inp": lookup(m["meterIn"]),
            "out": lookup(m["meterOut"]),
            "sc": SC in m["regions"],
            "we": WE in m["regions"],
            "note": m.get("note", ""),
        })
    return rows


def main():
    print(f"Fetching Data Zone prices ({', '.join(CURRENCIES)}) from Azure Retail Prices API ...", file=sys.stderr)
    prices_by_cur = {cur: fetch_prices(PRICE_REGION, cur) for cur in CURRENCIES}

    print("Fetching Cognigy model-support table (Microsoft Azure OpenAI) ...", file=sys.stderr)
    cognigy = fetch_cognigy_azure_support()
    if cognigy:
        print(f"  parsed {len(cognigy)} Azure model entries from Cognigy.", file=sys.stderr)
    else:
        print("  Cognigy unavailable — keeping last-known values.", file=sys.stderr)

    old = read_old_payload()
    old_cog = {r["id"]: r.get("cognigy") for r in old["rows"]} if old and old.get("rows") else {}
    rows = build_rows(prices_by_cur, cognigy, old_cog)

    # --- detect real problems; these fail the build so GitHub emails on the failure ---
    def gha(level, msg):
        print(f"::{level}::{msg}")                    # GitHub Actions annotation (run summary)
        print(f"{level.upper()}: {msg}", file=sys.stderr)

    problems = []
    missing = [r["id"] for r in rows if r["inp"] is None and r["id"] != "text-embedding-ada-002"]
    if missing:
        problems.append(f"Azure price meter(s) missing or renamed: {missing}")

    # o-series are legitimately absent from Cognigy's Azure table; everything else should resolve.
    expected_ids = [m["id"] for m in MODELS if not m["id"].startswith("o")]
    resolved = sum(1 for r in rows if r["id"] in expected_ids and r["cognigy"]["status"] != "unknown")
    if cognigy is None and not old_cog:
        problems.append("Cognigy model-support unreachable/unparseable and no prior values to fall back on.")
    elif cognigy is not None and resolved == 0:
        problems.append("Cognigy parsed but matched 0 Microsoft Azure OpenAI models (page structure likely changed).")

    if problems:
        for p in problems:
            gha("error", p)
        gha("error", "Aborting without overwriting index.html (keeping last-known-good data).")
        sys.exit(1)

    # soft issues — keep the build green, just surface a warning
    if cognigy is None:
        gha("warning", "Cognigy unreachable — kept last-known support values.")
    elif resolved < len(expected_ids):
        gha("warning", f"Cognigy resolved {resolved}/{len(expected_ids)} expected Azure models — some may have been renamed.")

    # Only move the timestamp when the data actually changed, so an unchanged daily
    # run produces a byte-identical file -> no git diff -> no noise commit.
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if old and old.get("rows") == rows and old.get("currencies") == CURRENCIES:
        updated = old.get("updated", now)
        print("No data change since last run; preserving timestamp.", file=sys.stderr)
    else:
        updated = now

    payload = {"updated": updated, "currencies": CURRENCIES, "rows": rows}
    html = TEMPLATE.replace("/*DATA*/null", json.dumps(payload, ensure_ascii=False))
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote index.html — {len(rows)} models, updated {updated}", file=sys.stderr)


def read_old_payload():
    """Parse the PAYLOAD object out of an existing index.html, if any."""
    try:
        with open("index.html", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        return None
    m = re.search(r"const PAYLOAD = (\{.*?\});", html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


# --- HTML template (single self-contained file) -------------------------------
TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Azure OpenAI · EU Data Zone Standard — Model & DKK Price Overview</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,900&family=Archivo:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#f1ede3; --paper:#faf7f0; --ink:#16212c; --muted:#62707a;
  --line:#ddd6c7; --line-strong:#c6bda9;
  --blue:#27509e;   /* West Europe / input */
  --gold:#c0892a;   /* Sweden Central */
  --rust:#b3502f;   /* output */
  --ok:#2f7d5b; --no:#b6ad9c;
  --shadow:0 1px 0 rgba(22,33,44,.04), 0 18px 40px -28px rgba(22,33,44,.5);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font-family:"Archivo",system-ui,sans-serif; font-size:15px; line-height:1.5;
  -webkit-font-smoothing:antialiased;
  background-image:
    radial-gradient(circle at 12% -8%, rgba(192,137,42,.10), transparent 42%),
    radial-gradient(circle at 96% 0%, rgba(39,80,158,.10), transparent 38%);
  background-attachment:fixed;
}
/* subtle paper grain */
body::before{
  content:""; position:fixed; inset:0; pointer-events:none; z-index:0; opacity:.5;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.035'/%3E%3C/svg%3E");
}
.wrap{position:relative; z-index:1; max-width:1080px; margin:0 auto; padding:46px 28px 90px}

/* ---------- header ---------- */
header{animation:rise .7s cubic-bezier(.2,.7,.2,1) both}
.eyebrow{
  display:inline-flex; align-items:center; gap:9px; font-size:11.5px; letter-spacing:.22em;
  text-transform:uppercase; color:var(--muted); font-weight:600;
}
.eyebrow .pulse{width:7px;height:7px;border-radius:50%;background:var(--ok);box-shadow:0 0 0 0 rgba(47,125,91,.5);animation:pulse 2.4s infinite}
h1{
  font-family:"Fraunces",serif; font-weight:900; font-optical-sizing:auto;
  font-size:clamp(38px,6.5vw,68px); line-height:.98; letter-spacing:-.02em;
  margin:.32em 0 .18em; max-width:14ch;
}
h1 em{font-style:italic; font-weight:500; color:var(--blue)}
.lede{max-width:60ch; color:#33414c; font-size:16.5px}
.meta-row{
  display:flex; flex-wrap:wrap; gap:10px 22px; align-items:center; margin-top:22px;
  padding-top:18px; border-top:1px solid var(--line); font-size:13px; color:var(--muted);
}
.meta-row b{color:var(--ink); font-weight:600}
.stamp{font-family:"JetBrains Mono",monospace; font-size:12.5px}
.srcs a{color:var(--blue); text-decoration:none; border-bottom:1px solid rgba(39,80,158,.3)}
.srcs a:hover{border-color:var(--blue)}

/* ---------- controls ---------- */
.controls{
  margin:34px 0 14px; display:flex; flex-wrap:wrap; gap:16px 26px; align-items:flex-end;
  animation:rise .7s .08s cubic-bezier(.2,.7,.2,1) both;
}
.ctl-label{display:block; font-size:11px; letter-spacing:.16em; text-transform:uppercase; color:var(--muted); font-weight:600; margin-bottom:8px}
.seg{display:inline-flex; background:var(--paper); border:1px solid var(--line-strong); border-radius:11px; padding:4px; box-shadow:var(--shadow)}
.seg button{
  border:0; background:transparent; font-family:inherit; font-size:13.5px; font-weight:600; color:var(--muted);
  padding:8px 15px; border-radius:8px; cursor:pointer; transition:.18s; display:inline-flex; align-items:center; gap:7px; white-space:nowrap;
}
.seg button .dot{width:8px;height:8px;border-radius:50%}
.seg button[data-region=swedencentral] .dot{background:var(--gold)}
.seg button[data-region=westeurope] .dot{background:var(--blue)}
.seg button.on{background:var(--ink); color:#fff; box-shadow:0 6px 16px -8px rgba(22,33,44,.7)}
.seg.fam button.on{background:var(--ink); color:#fff}
.search{position:relative}
.search input{
  font-family:inherit; font-size:14px; padding:10px 14px 10px 36px; width:230px; color:var(--ink);
  background:var(--paper); border:1px solid var(--line-strong); border-radius:11px; box-shadow:var(--shadow);
}
.search input:focus{outline:2px solid var(--blue); outline-offset:1px}
.search svg{position:absolute; left:12px; bottom:13px; color:var(--muted)}
.spacer{flex:1 1 auto}
.count{font-size:12.5px; color:var(--muted); font-family:"JetBrains Mono",monospace; padding-bottom:10px}

/* ---------- table ---------- */
.card{
  background:var(--paper); border:1px solid var(--line-strong); border-radius:16px; overflow:hidden;
  box-shadow:var(--shadow); animation:rise .7s .16s cubic-bezier(.2,.7,.2,1) both;
}
table{width:100%; border-collapse:collapse}
thead th{
  text-align:left; font-size:11px; letter-spacing:.13em; text-transform:uppercase; color:var(--muted);
  font-weight:700; padding:16px 18px; border-bottom:1.5px solid var(--line-strong); background:#f5f1e7;
  position:sticky; top:0; backdrop-filter:blur(6px); user-select:none;
}
thead th.sortable{cursor:pointer; white-space:nowrap}
thead th.num{text-align:right}
thead th .arr{opacity:.35; font-size:10px}
thead th.act .arr{opacity:1; color:var(--ink)}
tbody td{padding:15px 18px; border-bottom:1px solid var(--line); vertical-align:middle}
tbody tr{transition:background .15s}
tbody tr:hover{background:#f3eee2}
tbody tr:last-child td{border-bottom:0}
tbody tr.dim{opacity:.4}
tbody tr.dim:hover{opacity:.7}

.model{font-family:"JetBrains Mono",monospace; font-weight:500; font-size:14.5px; letter-spacing:-.01em; color:var(--ink)}
.note{display:block; font-family:"Archivo"; font-size:11px; color:var(--muted); margin-top:2px; letter-spacing:0}
.rel{font-family:"JetBrains Mono",monospace; font-size:13px; color:var(--muted); letter-spacing:-.02em}
.fam{
  display:inline-block; font-size:10.5px; font-weight:700; letter-spacing:.08em; text-transform:uppercase;
  padding:3px 9px; border-radius:999px; border:1px solid;
}
.fam.GPT{color:#1f3d77; background:rgba(39,80,158,.09); border-color:rgba(39,80,158,.25)}
.fam.Reasoning{color:#7a3c12; background:rgba(179,80,47,.10); border-color:rgba(179,80,47,.28)}
.fam.Embedding{color:#2f5b46; background:rgba(47,125,91,.10); border-color:rgba(47,125,91,.28)}

.avail{display:inline-flex; gap:7px}
.chip{display:inline-flex; align-items:center; gap:6px; font-size:11.5px; font-weight:600; color:var(--muted)}
.chip .led{width:9px;height:9px;border-radius:50%; background:var(--no); box-shadow:inset 0 0 0 1px rgba(0,0,0,.06)}
.chip.sc.yes .led{background:var(--gold); box-shadow:0 0 0 3px rgba(192,137,42,.16)}
.chip.we.yes .led{background:var(--blue); box-shadow:0 0 0 3px rgba(39,80,158,.16)}
.chip.no{opacity:.5; text-decoration:line-through}
.cog{display:inline-flex; align-items:center; gap:6px; font-size:11.5px; font-weight:600; white-space:nowrap; padding:3px 10px; border-radius:999px; border:1px solid}
.cog.yes{color:#2f5b46; background:rgba(47,125,91,.10); border-color:rgba(47,125,91,.30)}
.cog.no{color:#7a3c12; background:rgba(179,80,47,.08); border-color:rgba(179,80,47,.24); opacity:.85}
.cog.unk{color:var(--muted); background:rgba(22,33,44,.04); border-color:var(--line-strong)}

td.num{text-align:right; position:relative}
.price{font-family:"JetBrains Mono",monospace; font-weight:500; font-size:14.5px}
.price .cur{font-size:10.5px; color:var(--muted); font-weight:400; margin-left:3px}
.price.na{color:var(--no); font-weight:400}
.bar{position:absolute; left:18px; right:18px; bottom:8px; height:3px; border-radius:2px; background:rgba(22,33,44,.06); overflow:hidden}
.bar i{position:absolute; left:0; top:0; bottom:0; border-radius:2px}
td.inp .bar i{background:linear-gradient(90deg,var(--blue),#5a82d8)}
td.out .bar i{background:linear-gradient(90deg,var(--rust),#d98a6e)}

/* ---------- footer ---------- */
.legend{
  margin-top:30px; display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:14px;
  animation:rise .7s .24s cubic-bezier(.2,.7,.2,1) both;
}
.legend .box{background:var(--paper); border:1px solid var(--line); border-radius:13px; padding:16px 18px}
.legend h4{margin:0 0 7px; font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted)}
.legend p{margin:0; font-size:13px; color:#3b4751; line-height:1.55}
.legend code{font-family:"JetBrains Mono",monospace; font-size:12px; background:rgba(22,33,44,.05); padding:1px 5px; border-radius:5px}
.legend a{color:var(--blue); text-decoration:none; border-bottom:1px solid rgba(39,80,158,.3)}
.legend a:hover{border-color:var(--blue)}
footer{margin-top:34px; padding-top:20px; border-top:1px solid var(--line); font-size:12px; color:var(--muted); display:flex; flex-wrap:wrap; gap:6px 18px; justify-content:space-between}
.empty{padding:50px; text-align:center; color:var(--muted); font-size:15px}

@keyframes rise{from{opacity:0; transform:translateY(14px)} to{opacity:1; transform:none}}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(47,125,91,.5)} 70%{box-shadow:0 0 0 7px rgba(47,125,91,0)} 100%{box-shadow:0 0 0 0 rgba(47,125,91,0)}}
@media (max-width:720px){
  .wrap{padding:32px 16px 70px}
  thead th.hide,tbody td.hide{display:none}
  .search input{width:160px}
}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <span class="eyebrow"><span class="pulse"></span>Azure OpenAI · Data Zone Standard · EU</span>
    <h1>Compliant&nbsp;models, <em>priced for the EU&nbsp;zone</em>.</h1>
    <p class="lede">Every text &amp; embedding model you can deploy on <b>Data Zone Standard</b> in
      <b>Sweden Central</b> and <b>West Europe</b> — with official Azure input &amp; output token prices in Danish kroner or US dollars (per&nbsp;1M&nbsp;tokens).</p>
    <div class="meta-row">
      <span>Updated <b class="stamp" id="updated">—</b></span>
      <span>Prices in <b id="cur">DKK</b> / 1M tokens</span>
      <span class="srcs">Sources:
        <a href="https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability?pivots=standard#data-zone-standard" target="_blank" rel="noopener">availability</a> ·
        <a href="https://prices.azure.com/api/retail/prices" target="_blank" rel="noopener">retail prices API</a> ·
        <a href="https://docs.cognigy.com/ai/agents/develop/gen-ai-and-llms/model-support-by-feature" target="_blank" rel="noopener">Cognigy support</a>
      </span>
    </div>
  </header>

  <div class="controls">
    <div>
      <span class="ctl-label">Region view</span>
      <div class="seg" id="regionSeg">
        <button data-region="both" class="on">Compare both</button>
        <button data-region="swedencentral"><span class="dot"></span>Sweden Central</button>
        <button data-region="westeurope"><span class="dot"></span>West Europe</button>
      </div>
    </div>
    <div>
      <span class="ctl-label">Family</span>
      <div class="seg fam" id="famSeg">
        <button data-fam="all" class="on">All</button>
        <button data-fam="GPT">GPT</button>
        <button data-fam="Embedding">Embedding</button>
      </div>
    </div>
    <div>
      <span class="ctl-label">Currency</span>
      <div class="seg" id="curSeg">
        <button data-cur="DKK" class="on">DKK kr</button>
        <button data-cur="USD">USD $</button>
      </div>
    </div>
    <div class="search">
      <span class="ctl-label">Search</span>
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>
      <input id="q" type="search" placeholder="filter models…" autocomplete="off">
    </div>
    <span class="spacer"></span>
    <span class="count" id="count"></span>
  </div>

  <div class="card">
    <table>
      <thead><tr>
        <th class="sortable" data-sort="id">Model <span class="arr">↕</span></th>
        <th class="hide">Family</th>
        <th class="sortable hide act" data-sort="released">Released <span class="arr">↓</span></th>
        <th>Availability</th>
        <th class="sortable" data-sort="cognigy">Cognigy <span class="arr">↕</span></th>
        <th class="num sortable" data-sort="inp">Input <span class="arr">↕</span></th>
        <th class="num sortable" data-sort="out">Output <span class="arr">↕</span></th>
      </tr></thead>
      <tbody id="tbody"></tbody>
    </table>
    <div class="empty" id="empty" style="display:none">No models match those filters.</div>
  </div>

  <div class="legend">
    <div class="box"><h4>Prices are zone-wide</h4><p>Data Zone Standard token prices are billed at the EU-zone level — identical for Sweden Central and West Europe. The region toggle changes <em>availability</em>, not price.</p></div>
    <div class="box"><h4>Context tiers</h4><p><code>gpt-5.4</code> / <code>gpt-5.5</code> show the <em>short-context</em> rate. Long-context and <code>pro</code> tiers are billed higher — see the pricing page.</p></div>
    <div class="box"><h4>What's excluded</h4><p>Cached-input, Batch and Provisioned rates are not shown. <code>ada-002</code> has no Data Zone meter (price n/a). Audio / realtime / image / router models are out of scope.</p></div>
    <div class="box"><h4>Cognigy support</h4><p>Scraped from Cognigy's <a href="https://docs.cognigy.com/ai/agents/develop/gen-ai-and-llms/model-support-by-feature" target="_blank" rel="noopener">model-support</a> page — <b>Microsoft Azure OpenAI</b> section only. Chat models show <b>LLM&nbsp;Prompt&nbsp;Node</b> support; embeddings show <b>Knowledge&nbsp;Search</b> support. <code>—</code> = not listed (the reasoning o-series).</p></div>
    <div class="box"><h4>Kept fresh</h4><p>Regenerated daily by a GitHub Action that re-queries the Azure Retail Prices API (DKK&nbsp;+&nbsp;USD), re-checks region availability, and re-scrapes Cognigy support.</p></div>
  </div>

  <footer>
    <span>Azure OpenAI — EU Data Zone Standard overview</span>
    <span class="stamp" id="footcur">per 1,000,000 tokens</span>
  </footer>
</div>

<script>
const PAYLOAD = /*DATA*/null;

const $ = s => document.querySelector(s);
const state = { region:"both", fam:"all", q:"", sort:"released", dir:-1, cur:"DKK" };
let ROWS = [];

const SYM = { DKK:{sym:"kr", pre:false, loc:"da-DK"}, USD:{sym:"$", pre:true, loc:"en-US"} };

function val(cell){ return cell ? cell[state.cur] : null; }   // price for current currency

function fmt(v){
  const loc = SYM[state.cur].loc;
  if(v===null||v===undefined) return null;
  if(v >= 100) return v.toLocaleString(loc,{maximumFractionDigits:0});
  if(v >= 10)  return v.toLocaleString(loc,{minimumFractionDigits:1,maximumFractionDigits:1});
  return v.toLocaleString(loc,{minimumFractionDigits:2,maximumFractionDigits:2});
}
function priceHTML(v){
  const s = SYM[state.cur];
  const n = fmt(v);
  return s.pre ? `<span class="cur">${s.sym}</span>${n}` : `${n}<span class="cur">${s.sym}</span>`;
}

function init(){
  if(!PAYLOAD){ document.body.innerHTML="<p style='padding:40px;font-family:monospace'>No data baked in. Run: python3 generate.py</p>"; return; }
  $("#updated").textContent = PAYLOAD.updated;
  ROWS = PAYLOAD.rows;
  wire();
  render();
}

function wire(){
  $("#regionSeg").addEventListener("click",e=>{const b=e.target.closest("button"); if(!b)return;
    state.region=b.dataset.region; setOn("#regionSeg",b); render();});
  $("#famSeg").addEventListener("click",e=>{const b=e.target.closest("button"); if(!b)return;
    state.fam=b.dataset.fam; setOn("#famSeg",b); render();});
  $("#curSeg").addEventListener("click",e=>{const b=e.target.closest("button"); if(!b)return;
    state.cur=b.dataset.cur; setOn("#curSeg",b); render();});
  $("#q").addEventListener("input",e=>{state.q=e.target.value.trim().toLowerCase(); render();});
  document.querySelectorAll("th.sortable").forEach(th=>th.addEventListener("click",()=>{
    const k=th.dataset.sort;
    if(state.sort===k) state.dir*=-1; else {state.sort=k; state.dir = k==="id"?1:1;}
    document.querySelectorAll("th .arr").forEach(a=>{a.textContent="↕"; a.parentElement.classList.remove("act");});
    th.classList.add("act"); th.querySelector(".arr").textContent = state.dir>0?"↑":"↓";
    render();
  }));
}
function setOn(sel,btn){document.querySelectorAll(sel+" button").forEach(b=>b.classList.remove("on")); btn.classList.add("on");}

function visibleRows(){
  let rows = ROWS.filter(r=>{
    if(state.fam!=="all" && r.family!==state.fam) return false;
    if(state.q && !r.id.toLowerCase().includes(state.q)) return false;
    return true;
  });
  const k=state.sort, d=state.dir;
  rows.sort((a,b)=>{
    if(k==="id") return a.id.localeCompare(b.id)*d;
    if(k==="released") return a.released.localeCompare(b.released)*d;
    if(k==="cognigy"){const rk={yes:0,no:1,unknown:2}; return (rk[a.cognigy.status]-rk[b.cognigy.status])*d;}
    const av=val(a[k]), bv=val(b[k]);
    if(av===null||av===undefined) return 1; if(bv===null||bv===undefined) return -1;   // n/a sinks
    return (av-bv)*d;
  });
  return rows;
}

function availChip(on, region, label){
  return `<span class="chip ${region} ${on?'yes':'no'}"><span class="led"></span>${label}</span>`;
}
function cognigyChip(c){
  const st = (c && c.status) || "unknown";
  if(st === "unknown")
    return `<span class="cog unk" title="Not listed for Microsoft Azure OpenAI on Cognigy">—</span>`;
  const feat = c.feature || "Prompt Node";
  const cls = st === "yes" ? "yes" : "no";
  const icon = st === "yes" ? "✓" : "✗";
  const tip = `${feat} ${st === "yes" ? "supported" : "not supported"} for Microsoft Azure OpenAI (Cognigy)`;
  return `<span class="cog ${cls}" title="${tip}">${icon} ${feat}</span>`;
}

function render(){
  $("#cur").textContent = state.cur;
  $("#footcur").textContent = `${state.cur} · per 1,000,000 tokens`;
  const rows = visibleRows();
  const tb = $("#tbody"); tb.innerHTML="";
  const showSC = state.region!=="westeurope";
  const showWE = state.region!=="swedencentral";
  // magnitude bars (log-scaled) relative to the priciest model in the active currency
  const maxIn = Math.max(...ROWS.map(r=>val(r.inp)||0), 1e-9);
  const maxOut = Math.max(...ROWS.map(r=>val(r.out)||0), 1e-9);
  const bar = (v,max)=> v ? Math.max(.04, Math.log10(1+v)/Math.log10(1+max)) : 0;
  let shown=0;

  rows.forEach(r=>{
    const vin = val(r.inp), vout = val(r.out);
    // in single-region view, dim models unavailable there
    const inRegion = state.region==="both" || (state.region==="swedencentral"&&r.sc) || (state.region==="westeurope"&&r.we);
    const tr=document.createElement("tr");
    if(!inRegion) tr.className="dim";

    let avail="<span class='avail'>";
    if(showSC) avail+=availChip(r.sc,"sc","SC");
    if(showWE) avail+=availChip(r.we,"we","WE");
    avail+="</span>";

    const inCell = vin!==null && vin!==undefined
      ? `<span class="price">${priceHTML(vin)}</span><span class="bar"><i style="width:${(bar(vin,maxIn)*100).toFixed(1)}%"></i></span>`
      : `<span class="price na">n/a</span>`;
    const outCell = vout!==null && vout!==undefined
      ? `<span class="price">${priceHTML(vout)}</span><span class="bar"><i style="width:${(bar(vout,maxOut)*100).toFixed(1)}%"></i></span>`
      : `<span class="price na">${r.family==='Embedding'?'—':'n/a'}</span>`;

    tr.innerHTML = `
      <td><span class="model">${r.id}</span>${r.note?`<span class="note">${r.note}</span>`:""}</td>
      <td class="hide"><span class="fam ${r.family}">${r.family}</span></td>
      <td class="hide"><span class="rel">${r.released}</span></td>
      <td>${avail}</td>
      <td>${cognigyChip(r.cognigy)}</td>
      <td class="num inp">${inCell}</td>
      <td class="num out">${outCell}</td>`;
    tb.appendChild(tr); shown++;
  });

  $("#empty").style.display = shown?"none":"block";
  $("#count").textContent = `${shown} model${shown===1?"":"s"}`;
}

init();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
