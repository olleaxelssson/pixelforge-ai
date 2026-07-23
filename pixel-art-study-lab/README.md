# Pixel Art Study Lab

A **local-first** tool for collecting *legally usable* pixel-art references and studying the craft:
palettes, silhouettes, colour ramps, dithering, grid discipline, tileability, sprite sheets, and
animation. Everything runs on your machine — a local SQLite library, a local vector index, and a
local analysis engine. No account, no cloud, no data leaves your computer. An optional API key can
add a stronger vision-language description, but the tool is **fully useful without one**.

It ships with two things most reference tools skip: a **rules-first collector** that refuses to
touch anything it isn't clearly allowed to, storing complete provenance for every asset; and, next
to the human-readable study notes, a compact **LLM-facing digest** for every asset so an assistant
(like the one that may be helping you study) can reason about a sprite precisely and cheaply.

---

## What it does

- **Collect, carefully.** A controlled scraper that only ever visits sources you explicitly enable
  in an allowlist, obeys `robots.txt`, honours per-domain rate limits, retries transient failures,
  and *defaults to a dry-run* (it shows you what it would collect and downloads nothing). Every
  candidate must clear three gates in order: license → robots → rate limit. It prefers official
  APIs and only accepts a fixed set of reuse-friendly licenses (CC0, public domain, CC-BY, CC-BY-SA,
  OpenGameArt-BY). It never logs in, never bypasses paywalls/CAPTCHAs, and never collects personal
  data.
- **Import your own art.** Files, whole folders, PNG sprite sheets, and animated GIFs — sheet layout
  and frame counts are detected automatically. Pixel-art validation runs on import, with a manual
  override when you know better.
- **Understand every asset.** Palette and ramps, contrast, grid scale and effective resolution,
  outline ratio, dithering, silhouette read, tileability, sheet/animation layout — plus plain-English
  *study notes* ("why this reads well at 16×16") and a *critique* of uploaded work.
- **Find things.** Search by text (titles, tags, notes, creators), by colour, by dimensions/tags/
  license, or by visual similarity ("more like this"). Near-duplicate and similarity warnings guard
  against accidentally re-collecting — or reproducing — a specific artist's work.
- **A pleasant local app + a full CLI.** A gallery with filters, an asset-detail panel with the
  analysis and attribution, an upload-and-critique area — and a scriptable command line for
  everything.

---

## Why these technologies

The guiding constraint was *quality-first, but genuinely runnable on a personal computer, offline,
with no heavyweight setup.* That ruled a lot in and a lot out.

| Choice | Why |
| --- | --- |
| **Python 3.11 + standard library** | `sqlite3` (with FTS5), `urllib.robotparser`, `hashlib`, `tomllib`, `zipfile`, `argparse` cover storage, robots, hashing, config, archives and the CLI with **zero** third-party weight. |
| **SQLite (one file)** | The whole library — provenance, tags, colours, embeddings, full-text index — is a single file you can back up, inspect, or delete. FTS5 gives real full-text search with no server. |
| **Local vector index = float32 blobs + numpy cosine** | At personal scale (thousands of assets) a linear scan is instant and needs no ANN index to build or keep in sync. Similarity search has *no* extra dependency. |
| **Hand-built 340-d visual embedding (no ML deps)** | Structure (16×16 thumbnail) + HSV colour histogram + gradient orientation + shape scalars, L2-normalised. Deterministic, CPU-instant, and good enough to rank visually similar references — so the "useful without an API key" promise holds. |
| **Three-layer dedup** | Exact (SHA-256) → perceptual (dHash/Hamming) → semantic (embedding cosine). Cheap checks first; the semantic layer is what warns you when you're about to reproduce a specific work. |
| **Pillow + numpy** | The only non-stdlib runtime deps for imaging/analysis. Ubiquitous, wheels everywhere, no native build pain. |
| **FastAPI + uvicorn, single embedded HTML page** | A tiny JSON API and a **build-step-free** frontend (no Node, no bundler). `pip install` and you have a web app. |
| **Provenance as a first-class column** | Source URL, creator, license, ready-to-display attribution, content hash and collection date live *on the asset row*. Removing a source cascades to its assets and files. |
| **The scraper's HTTP is injectable** | The network sits behind a `Fetcher` interface, so every collection rule is unit-tested offline — no test ever hits the internet. |
| **Optional VLM behind a local default** | With `STUDYLAB_VLM_PROVIDER`/`STUDYLAB_VLM_API_KEY` set, descriptions can use a hosted vision model; otherwise a deterministic local describer runs. It **always** falls back to local on any error. Keys are read from the environment only and never written to disk. |

**On the "AI" here, honestly:** the tagger is a *k-nearest-neighbours classifier* over the local
embeddings, trained only on assets you already hold with an allowed license and your own tags. It is
not a foundation model and makes no such claim. The trained index is a plain `.npz` you can inspect
or delete.

---

## Legal & safety design (read this)

This tool is deliberately conservative about collection:

- **Allowlist only.** Nothing is fetched unless a source is `enabled = true` in `sources.toml`.
- **License gate.** Only CC0 / public-domain / CC-BY / CC-BY-SA / OGA-BY are accepted by the
  collector; anything else is skipped and never stored.
- **`robots.txt` is obeyed** and cannot be disabled — the config loader *rejects* a source that sets
  `obey_robots = false`, and collection fails closed if a site's robots policy can't be read.
- **Rate limits + retries** are enforced per domain; the default is gentle (one request / 2s).
- **No bypassing** logins, paywalls, CAPTCHAs, or anti-bot systems. No scraping of private or
  personal data.
- **Full provenance** is stored for every asset, and attribution strings are pre-built for display.
- **Easy removal:** delete a single asset or an entire source (files included) from the CLI or UI.
- **Anti-reproduction guardrails:** duplicate/near-duplicate/similarity warnings exist specifically
  so you don't accidentally build a copy of a living artist's specific work. This is a *study* tool.

You are still responsible for reading each source's terms before enabling it. When in doubt, don't.

---

## Setup (macOS-first)

Requires Python 3.11+. On macOS:

```bash
# 1. From this directory, create a virtual environment and install.
cd pixel-art-study-lab
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"        # drop [dev] if you don't want the test tools

# 2. Initialise the local library (creates ~/.studylab).
studylab init
```

(Linux is identical. On Windows, use `py -m venv .venv` and `.venv\Scripts\activate`.)

Everything lives under `~/.studylab` by default — override with `STUDYLAB_DATA_DIR`. To wipe the
library completely, delete that folder.

### Optional: stronger vision-language descriptions

```bash
export STUDYLAB_VLM_PROVIDER=anthropic        # or "openai"; default "local"
export STUDYLAB_VLM_API_KEY=sk-...            # read from env only, never stored
```

Without these, a deterministic local describer is used. The app never requires them.

---

## Try it immediately (a legally-safe demo dataset)

The demo dataset is **generated procedurally on your machine**, so it is CC0 by construction — no
network, no third-party art:

```bash
studylab demo            # generates ~12 sprites/textures/a sheet/a GIF and imports them
studylab stats           # see what's in the library
studylab serve           # open http://127.0.0.1:8080
```

---

## Collect from approved sources

```bash
# 1. Create your allowlist from the example and edit it.
cp sources.example.toml sources.toml
$EDITOR sources.toml         # set `enabled = true` ONLY for sources whose terms you've read

# 2. See what's configured.
studylab scrape --list

# 3. DRY-RUN first (default): shows exactly what WOULD be collected, downloads nothing.
studylab scrape wikimedia-pixel-art

# 4. Actually collect (only after you're happy with the dry-run).
studylab scrape wikimedia-pixel-art --execute --limit 20
```

Runs are **resumable**: if interrupted, re-running skips everything already processed. Collection
obeys the license gate, `robots.txt`, and the per-domain rate limit on every candidate.

---

## Everyday use (CLI)

```bash
studylab import ~/sprites --license self --tags hero,rpg   # a file or a whole folder
studylab import walkcycle.gif                              # GIFs & sheets: layout auto-detected
studylab analyze sprite.png                                # metrics + notes + LLM digest (no import)
studylab critique my_wip.png                               # strengths + concrete suggestions

studylab search "knight"                                   # text: titles, tags, notes, creators
studylab search --color '#3b5dc9'                          # by colour
studylab search --like 42 --pixel-art                      # visually similar to asset 42
studylab search --license CC0-1.0                          # filter by license

studylab tag --train                                       # (re)train the local kNN tagger
studylab tag sprite.png                                    # suggest tags for an image

studylab export library.zip                                # portable dataset (manifest + files)
studylab import-dataset library.zip                        # merge a dataset (dedup applies)
studylab backup backup.zip                                 # full backup of the data dir
studylab restore backup.zip

studylab remove --asset 42                                 # delete one asset (+ its files)
studylab remove --source 3                                 # delete a whole source (+ its assets)

studylab serve --port 8080                                 # the local web app
```

Add `--json` to any command for machine-readable output. Every analysis carries the compact
`PALAB/1 …` digest — dense, deterministic, and easy for an LLM assistant to parse.

---

## The web app

`studylab serve` opens a local gallery (binds to `127.0.0.1` only):

- **Gallery + filters** — license, pixel-art-only, search box, colour picker.
- **Asset detail** — the image, full metrics, *why it reads*, a study critique, tags, the
  attribution line and source link, the LLM digest, "find similar", and remove.
- **Upload / Critique** — drop an image to import it (with license + tags), or critique it without
  importing. Near-duplicate warnings surface on import.

---

## Project layout

```
studylab/
  config.py          filesystem layout + env settings (keys read from env only)
  db.py              SQLite schema + typed repository (FTS5, cascade delete)
  provenance.py      license allowlist + attribution
  hashing.py         SHA-256 + perceptual dHash
  dedup.py           exact / perceptual / semantic near-duplicate detection
  importer.py        bytes/file/folder → validated, analyzed, attributed asset
  demo.py            procedural CC0 demo dataset
  search.py          text / colour / similarity / combined queries
  tagger.py          local kNN tag classifier (licensed data only)
  backup.py          dataset export/import + full backup/restore
  cli.py             the `studylab` command line
  webapp.py          FastAPI app + embedded single-page UI
  analysis/          palette, pixel-art metrics, embedding, sheets/GIF, notes,
                     critique, the LLM digest, and the optional VLM describer
  scraper/           allowlist, robots, rate-limited fetch, adapters, runner
tests/               scraper rules, provenance, import, dedup, analysis, search,
                     tagger, backup, and the web API (all offline)
sources.example.toml the allowlist template
```

---

## Testing

```bash
pip install -e ".[dev]"
pytest -q            # 52 tests, fully offline (the scraper's network is mocked)
```

Coverage spans the scraper rules (allowlist validation, license mapping, robots obedience, dry-run,
resume, rate limiting), license/provenance, import (files/folders/GIF/sheets/validation/dedup),
near-duplicate detection, the analysis pipeline and digest, search + the tagger, export/backup
round-trips, and the web API.

---

## License

MIT for this tool's code. Collected assets keep **their own** licenses — always check and honour the
attribution recorded with each asset before you reuse it.
