# geoNamesFromPdf

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![spaCy](https://img.shields.io/badge/built%20with-spaCy-09a3d5.svg)](https://spacy.io)

Extract toponyms (place names) from PDF documents. `geoNamesFromPdf` runs spaCy
Named Entity Recognition with automatic language detection, and can combine it
with a custom gazetteer that carries coordinates. Three front-ends sit on one
shared core: a command-line tool, a single-PDF GUI, and an assistant that tags a
whole Zotero library. Everything runs **offline** — no external API, no LLM
service.

It was built at the LAD – Laboratorio di Archeologia Digitale (Sapienza
Università di Roma) for spatial analysis of scholarly bibliography, so it pays
attention to the hard cases: long books, ancient or undocumented languages, and
place-name lists with coordinates (Pleiades, GeoNames).

## 📋 What you get

Three entry points, one engine:

| Command | Purpose |
|---|---|
| `python geoNamesFromPdf.py …` | CLI: one PDF (or a folder via a shell loop) → list / CSV / JSON / GeoJSON |
| `python gui.py` | Desktop GUI for a single PDF, with interactive include/exclude lists |
| `python zotero_assistant.py` | Review a Zotero library record by record and write geographic tags back |

Core capabilities:

- automatic language detection; 10 pre-configured spaCy languages, easily extended;
- page-range filtering, to skip front matter and bibliographies;
- custom gazetteer matching — word-boundary, case- and diacritic-insensitive,
  multi-word — optionally carrying identifiers and coordinates;
- structured output with per-toponym mention counts, pages and provenance;
- pluggable offline extraction engines: spaCy CNN (default), spaCy transformer, GLiNER;
- a gazetteer-only mode for languages spaCy has no model for.

## 🛠️ Installation

**Prerequisites:** Python 3.11 or newer (3.12 recommended; `.python-version`
pins 3.12.8) and `git`.

```bash
git clone https://github.com/lad-sapienza/geoNamesFromPdf.git
cd geoNamesFromPdf
python3.12 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
```

### First run installs what's missing

```bash
python geoNamesFromPdf.py your_document.pdf
```

On the first run the tool checks for the required Python packages and the two
essential language models (English, Italian) and offers to install them (≈500 MB
per model):

```
📦 Missing Python packages:  PyMuPDF, spacy, langdetect
🌍 Missing essential language models:  EN - en_core_web_lg, IT - it_core_news_lg

❓ Do you want to install missing dependencies now? (yes/no):
```

Answering `yes` installs everything; the tool records completion in
`.setup_complete` and won't ask again. Delete that file to run the check again,
or pass `--skip-setup` to bypass it.

### Manual install

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_lg
python -m spacy download it_core_news_lg
# or, equivalently:  python geoNamesFromPdf.py --install-language en
```

### One-step helper script

`scripts/setup_and_run.sh` clones or updates the repo, builds a venv, installs
`requirements.txt` and can launch the GUI. Run `scripts/setup_and_run.sh --help`
for its options (`--dest`, `--branch`, `--python`, `--install-spacy-models`, …).
Review any `curl … | bash` invocation before running it.

## 🚀 Command-line usage

```bash
python geoNamesFromPdf.py document.pdf                        # auto-detect language
python geoNamesFromPdf.py -l it document.pdf                  # force a language
python geoNamesFromPdf.py document.pdf -p "10-50, 60-62"      # only these pages
python geoNamesFromPdf.py document.pdf --details              # + label / count / pages
python geoNamesFromPdf.py document.pdf -f csv -o places.csv   # structured output
python geoNamesFromPdf.py document.pdf --gazetteer pleiades.tsv -f geojson -o places.geojson
python geoNamesFromPdf.py document.pdf --no-ner --gazetteer ancient_places.txt
python geoNamesFromPdf.py --exclude "Italia, Europa" document.pdf
python geoNamesFromPdf.py --list-languages
python geoNamesFromPdf.py --install-language es
```

Typical output:

```
🌐 Detected language: it
🧠 Using engine 'spacy' / model: core_news_lg v3.8.0

📍 Toponyms found in the PDF (8 total):

- Bologna
- Firenze
- Italia
- Milano
- Napoli
- Roma
- Torino
- Venezia
```

Process a whole folder:

```bash
for pdf in library/*.pdf; do
  python geoNamesFromPdf.py "$pdf" -f csv -o "toponyms/$(basename "$pdf" .pdf).csv"
done
```

### All options

```
usage: geoNamesFromPdf.py [-h] [-l LANGUAGE] [-p PAGES]
                          [--engine {spacy,spacy-trf,gliner}] [--no-ner]
                          [-f {txt,csv,json,geojson}] [-o FILE] [--details]
                          [--list-languages] [--install-language LANG_CODE]
                          [--skip-setup] [--gazetteer GAZETTEER]
                          [--exclude EXCLUDE]
                          [pdf_path]

  -l, --language LANGUAGE     Force a language code (en, it, …); default: auto-detect
  -p, --pages PAGES           Page range(s): '5', '5-10', '5-10, 12-14'; default: all
  --engine {spacy,spacy-trf,gliner}
                             Extraction engine, all offline (default: spacy)
  --no-ner                   Disable NER; use the gazetteer only (needs --gazetteer)
  -f, --format {txt,csv,json,geojson}   Output format (default: txt)
  -o, --output FILE          Write results to FILE instead of stdout
  --details                  With --format txt, also show label / count / pages
  --gazetteer GAZETTEER      Gazetteer file (.txt, or .csv/.tsv with name/id/lat/lon)
  --exclude EXCLUDE          Comma-separated toponyms to drop from the results
  --list-languages           List configured / installed language models and exit
  --install-language CODE    Download the spaCy model for CODE and exit
  --skip-setup               Skip the first-run dependency check
```

## 🌍 Languages and models

`geoNamesFromPdf` is pre-configured for ten languages; install only the ones you
need.

| Code | Language | | Code | Language |
|---|---|---|---|---|
| `en` | English | | `pt` | Portuguese |
| `it` | Italian | | `nl` | Dutch |
| `es` | Spanish | | `el` | Greek (modern) |
| `fr` | French | | `pl` | Polish |
| `de` | German | | `ro` | Romanian |

```bash
python geoNamesFromPdf.py --list-languages        # what is installed
python geoNamesFromPdf.py --install-language de    # add one
```

The code→model mapping is the `LANGUAGE_MODELS` dictionary in `core.py`; add an
entry there for any other language that has a spaCy model with an NER component
(see <https://spacy.io/models>).

`langdetect` has no model for Latin, Ancient Greek, Albanian and many others —
for those, pass `-l` explicitly or use the gazetteer-only mode below.

## 🧠 Extraction engines

`--engine` chooses how recognition is done. **Every engine runs locally; none
call an external service.**

| Engine | Flag | Extra install | Notes |
|---|---|---|---|
| spaCy CNN | `--engine spacy` *(default)* | — | fast on CPU, ~500 MB/language, NER-only pipeline |
| spaCy transformer | `--engine spacy-trf` | `pip install spacy-transformers` + a `_trf` model | more accurate on modern prose; heavier |
| GLiNER | `--engine gliner` | `pip install gliner gliner-spacy` | label-driven: extract exactly the categories you ask for; downloads a local model on first use |
| gazetteer only | `--no-ner --gazetteer FILE` | — | no model, no language detection; deterministic. Best for ancient / undocumented languages |

## 🗺️ Gazetteer

A gazetteer is your own list of place names, matched against the text and merged
with the NER results. Matching is a single pass, case- and diacritic-insensitive,
respects word boundaries (`Como` is not found inside `Comodo`) and handles
multi-word names (the longest match wins).

Plain list, one name per line:

```
Babylon
Nineveh
Uruk
```

```bash
python geoNamesFromPdf.py document.pdf --gazetteer places.txt
```

### With identifiers and coordinates (CSV / TSV)

A `.csv`/`.tsv` gazetteer can carry an id and coordinates, which are attached to
matched toponyms and exported by `-f csv` / `-f geojson`. Recognised column
headers (case-insensitive): `name`/`toponym`/`title`, `label`/`type`, `id`/`uri`,
`lat`/`latitude`, `lon`/`longitude`.

```
name	id	lat	lon
Butrint	pleiades:530798	39.7456	20.0206
Epirus	pleiades:991380	39.5000	20.5000
```

This pairs well with a local extract of [Pleiades](https://pleiades.stoa.org/)
(ancient world) or [GeoNames](https://www.geonames.org/) (modern geography): the
PDF goes in as text and comes out as a map layer.

## 📤 Output formats

The default output is a plain list. `-f/--format` (with optional
`-o/--output FILE`) produces structured results:

| Format | Contents |
|---|---|
| `txt` *(default)* | one name per line; `--details` adds label / count / pages |
| `csv` | `name,label,count,pages,sources,gazetteer_id,lat,lon` |
| `json` | the full result, including run metadata (language, model, pages processed) |
| `geojson` | a Point `FeatureCollection` — **only** toponyms that carry coordinates |

Every toponym records how many times it occurred, on which pages, and where it
came from (`ner:GPE`, `ner:LOC`, `gazetteer`, or a combination).

## 🖥️ Graphical interface (`gui.py`)

A PyQt5 desktop app for one PDF at a time.

```bash
pip install -r requirements.txt      # includes PyQt5
python gui.py
```

- Select or drag-and-drop a PDF; optional page range. The last PDF is remembered.
- Left column — the **gazetteer** (include list): load a `.txt`/`.csv`/`.tsv`, or
  add/remove entries by hand; export with *Save Included to File*.
- Right column — the **exclude list**, editable and exportable the same way.
- **Process PDF** shows the toponyms; each row has **Add** (→ gazetteer) and
  **Remove** (→ exclude list).
- Extraction runs in a background thread, so the window stays responsive on large
  documents.

## 🗂️ Zotero assistant (`zotero_assistant.py`)

A second graphical tool that helps you tag the items of a **Zotero library** with
the places mentioned in their attached PDF(s), reusing the geographic tags you
already keep.

It assumes a tagging convention: geographic tags are prefixed with `@`
(`@Butrint`, `@Çuka e Ajtoit`, …). Those existing `@` tags are fed to the
extractor as a gazetteer.

Pick a library and its records not yet tagged `geodone` appear in a filterable
list on the left. Select one and you get two check-lists:

- **existing `@` tags found in the text** — pre-checked, with occurrence count and
  page numbers;
- **new place candidates** found by NER (`GPE` / `LOC`) that are not yet in your
  vocabulary — unchecked. Each has an **editable target field** (default `@Name`)
  so you can normalise it, and when it looks close to an existing tag a one-click
  **↳ @ExistingTag** button adopts that tag instead.

*Save selected + Next* writes the approved tags, sorts the item's tag list
alphabetically, adds `geodone` (so the record leaves the list) and moves on.
*Skip and don't ask again* just writes `geodone`. *Skip (pending)* leaves the
record for a later session. Every action is appended to a
`zotero-assistant-log-*.csv` file in the working directory.

### Per-record language

The middle column has a **Language** selector and a **Re-analyze** button.
Language is auto-detected by default, but spaCy only has NER models for the
languages in `LANGUAGE_MODELS`; for anything else (Albanian, Latin, Ancient
Greek, …) it silently falls back to English, which produces many false positives
— a warning says so. Pick the right language and Re-analyze, or choose
**"— no NER (gazetteer only) —"** to match only against your `@` tags. The choice
carries over to the next record.

### Scanned PDFs / OCR

A PDF with no text layer can't be analysed. If
[`ocrmypdf`](https://ocrmypdf.readthedocs.io/) is on your `PATH`, a **Run OCR
(ocrmypdf)** button appears: it OCRs the file in memory (using the selected
language), then re-analyses — the attachment in Zotero is left unchanged. After a
successful OCR, **Save searchable PDF…** writes the OCR'd file to disk. Otherwise,
OCR the file with your own tool, reopen the record and Re-analyze.

### Requirements

- **Zotero 10.0 or newer** (the local write API landed in 10.0).
- In Zotero: *Settings → Advanced →* enable **"Allow other applications on this
  computer to communicate with Zotero"**.
- `httpx` (already in `requirements.txt`).
- *Optional:* `ocrmypdf` on `PATH` for the OCR button.

```bash
python zotero_assistant.py
```

Everything runs against Zotero's **local API** (`http://localhost:23119`): no
network, no `zotero.org` account needed. On the first save Zotero shows a
one-time dialog asking you to grant write access — choose *Always Allow* to avoid
repeating it. The library dropdown lists your personal library and any group
libraries. Files are read from Zotero's local storage: for a group whose files
sync on demand, enable *Settings → Sync → "Download files"* (or pre-download the
PDFs) — records whose PDF is not on disk are shown with a notice and can only be
skipped.

## 📊 How it works

All extraction logic lives in `core.py`, shared by the CLI
(`geoNamesFromPdf.py`), the GUI (`gui.py`) and the Zotero assistant
(`zotero_assistant.py`, with `zotero.py` for the local-API access).

1. **Text extraction** — PyMuPDF, page by page, optionally limited to `--pages`.
2. **Language detection** — `langdetect` with a fixed seed (reproducible), unless `-l` is given.
3. **Model loading** — a NER-only spaCy pipeline (tagger / parser / lemmatizer dropped for speed), cached between calls.
4. **Recognition** — geographic entities collected per page, with mention counts and page numbers.
5. **Gazetteer matching** — optional single pass; identifiers and coordinates attached when present.
6. **Post-processing** — `--exclude` names dropped (case-insensitive), de-duplicated, sorted, serialised.

Entity labels: **GPE** (countries, cities, states), **LOC** (regions, mountain
ranges, water bodies), **FAC** (buildings, roads, bridges). The CLI and GUI keep
all three; the Zotero assistant keeps GPE/LOC for its "new place" suggestions.

## 💡 Tips and troubleshooting

- **Set the language explicitly** with `-l` when you know it — auto-detection is only a guess.
- **Text-layer PDFs only.** Scanned pages yield nothing; OCR them first (`ocrmypdf`, Tesseract, …). The Zotero assistant can run `ocrmypdf` for you.
- **Ancient / undocumented languages** — use `--no-ner --gazetteer` for deterministic, noise-free matching.
- **Large books** — no problem; text is processed page by page, so length is not a limit.
- **"Model not found"** — `python -m spacy download <model>`, or `--install-language <code>`.
- **`python: command not found` (pyenv)** — call `venv/bin/python …`, or `pyenv global 3.12.8`.
- **Reset the first-run prompt** — delete `.setup_complete`.

## 🧪 Development

```bash
pip install pytest
python -m pytest        # offline unit tests — no model downloads, no Zotero
```

## 📦 Dependencies

**Core** (`requirements.txt`): PyMuPDF (`import pymupdf`), spaCy, langdetect,
PyQt5 (both GUIs), httpx (Zotero assistant); plus the `en_core_web_lg` and
`it_core_news_lg` spaCy models.

**Optional:**

| For | Install |
|---|---|
| `--engine spacy-trf` | `pip install spacy-transformers` + a `_trf` model |
| `--engine gliner` | `pip install gliner gliner-spacy` |
| Zotero assistant OCR button | `ocrmypdf` on `PATH` (`brew install ocrmypdf`, `apt install ocrmypdf`, …) |
| Running the tests | `pip install pytest` |

## 🤝 Contributing

Issues and pull requests are welcome.

- **A new language:** add `'<code>': '<spacy_model>'` to `LANGUAGE_MODELS` in
  `core.py`, download the model, test on a sample document, add a row to the
  Languages table above.
- **Bug reports:** include the Python version, OS, the exact command, and the
  full traceback.
- **Pull requests:** branch from `main`, keep `python -m pytest` green, update
  the README where behaviour changes.

## 📝 License

MIT — see [LICENSE](LICENSE).

Third-party components: spaCy (MIT), PyMuPDF (GNU AGPL v3 / commercial), langdetect
(Apache 2.0), PyQt5 (GPL v3 / commercial), httpx (BSD-3-Clause), GLiNER
(Apache 2.0), ocrmypdf (MPL 2.0).

## 🔗 Resources

- **spaCy** — [docs](https://spacy.io/) · [models](https://spacy.io/models) · [spacy-transformers](https://github.com/explosion/spacy-transformers)
- **GLiNER** — [model](https://github.com/urchade/GLiNER) · [gliner-spacy](https://github.com/theirstory/gliner-spacy)
- **PyMuPDF** — [docs](https://pymupdf.readthedocs.io/) · **langdetect** — [PyPI](https://pypi.org/project/langdetect/) · **PyQt5** — [Riverbank](https://www.riverbankcomputing.com/software/pyqt/)
- **OCR** — [ocrmypdf](https://ocrmypdf.readthedocs.io/)
- **Gazetteers** — [Pleiades](https://pleiades.stoa.org/) (ancient world) · [GeoNames](https://www.geonames.org/) (modern)
- **Zotero** — [local API](https://www.zotero.org/support/dev/web_api/v3/local_api) · [Web API v3](https://www.zotero.org/support/dev/web_api/v3/start)

---

**Version 1.2** · updated 2026-08-30
