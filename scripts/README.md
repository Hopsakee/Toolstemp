# Groundwater map — data pipeline

`fetch_groundwater_dino.py` downloads Dutch groundwater-level data from the
**BRO public REST services** (the modern home of the DINOloket groundwater
data) and builds the dataset for [`../groundwater-nl.html`](../groundwater-nl.html).

## What it does

1. Lays a ~22 km grid over the Netherlands and, at each node, searches a small
   box for groundwater monitoring tubes (GMW) and their level dossiers (GLD).
2. Keeps only tubes with a **(near-)complete 25-year record** (2001–2025,
   ≥22 of 25 years in both the summer and winter half-year, and data that truly
   spans the full period).
3. Computes, per year, the **median summer level** (apr–sep) and **median
   winter level** (oct–mar), then fits a linear trend (cm/year, with R² and a
   two-sided p-value).
4. Picks the most complete tube per grid node → ~100 well-spread stations.
5. Writes `groundwater_data.json` and injects the data straight into
   `groundwater-nl.html` (replacing the `GROUNDWATER_DATA` placeholder), so the
   map becomes a self-contained file with real measurements.

Levels are in metres relative to NAP; a **positive** trend = rising water table.

## Run it

```bash
pip install -r scripts/requirements.txt
python scripts/fetch_groundwater_dino.py          # full ~100-station run
python scripts/fetch_groundwater_dino.py --quick  # fast smoke test (~12 stations)
```

Useful flags: `--cell-km` (station spacing), `--box-km` (search box per node),
`--target` (station count), `--max-per-cell`.

## Network requirement

The script must reach `publiek.broservices.nl`. In a sandboxed environment
(e.g. Claude Code on the web with a restricted egress policy) add that host to
the network allowlist first — otherwise the requests are blocked and no
stations are found. Until the script has run, `groundwater-nl.html` shows a
clearly-labelled **demo** dataset.

Source & licence: BRO / DINOloket open data — https://www.broloket.nl ·
https://www.dinoloket.nl
