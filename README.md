# geoNamesFromPdf

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![spaCy](https://img.shields.io/badge/built%20with-spaCy-09a3d5.svg)](https://spacy.io)

Extract toponyms (place names) from PDF files using spaCy's Named Entity Recognition (NER) with automatic language detection.

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/lad-sapienza/geoNamesFromPdf.git
cd geoNamesFromPdf

# Create virtual environment (Python 3.12 recommended)
python3.12 -m venv venv
source venv/bin/activate  # On macOS/Linux
# or: venv\Scripts\activate  # On Windows

# Run the script - it will install dependencies automatically
python geoNamesFromPdf.py your_document.pdf
```

Tip: if you'd like a one-step setup (clone, create a venv, install deps and optionally run the GUI), see `scripts/setup_and_run.sh` below — it's helpful for non-technical users.

That's it! On first run, the tool will guide you through automatic dependency installation.

## 📋 Overview

This tool analyzes PDF documents and automatically identifies geographic entities such as cities, countries, regions, and landmarks. It supports multiple languages and automatically detects the language of your document for optimal accuracy.

## ✨ Features

- 🌍 **Multi-language support** - Automatically detects document language (10+ languages pre-configured)
- 🔍 **High accuracy** - Uses spaCy's large language models for NER
- 🎯 **Smart detection** - Extracts cities, countries, regions, and landmarks
- 📄 **PDF processing** - Works directly with PDF files
- 📑 **Page range filtering** - Process only specific pages or ranges to exclude introductions, bibliographies, etc.
- 🚀 **Easy to use** - Simple command-line interface
- ⚡ **Zero-friction setup** - Automatic dependency installation on first run
- 🔧 **Flexible** - Manual or automatic language model installation

## 🛠️ Installation

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

### Quick Setup (Recommended)

1. **Clone or download this repository**

2. **Run the script - it will guide you through setup on first run**:
   ```bash
   cd /path/to/geoNamesFromPdf
   python geoNamesFromPdf.py
   ```
   
   On first run, the tool will:
   - Check for missing Python packages
   - Check for missing language models (English and Italian by default)
   - Prompt you to install missing dependencies automatically
   - Remember setup is complete for future runs

### Manual Setup (Alternative)

If you prefer to set up dependencies manually:

1. **Clone or download this repository**

2. **Create and activate a virtual environment** (recommended):
   ```bash
   cd /path/to/geoNamesFromPdf
   python -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # Or: venv\Scripts\activate  # On Windows
   ```

3. **Install required packages**:
   ```bash
   pip install -r requirements.txt
   # Or manually:
   # pip install PyMuPDF spacy langdetect
   ```

4. **Download spaCy language models**:
   
   **Using the built-in installer**:
   ```bash
   python geoNamesFromPdf.py --install-language en  # English
   python geoNamesFromPdf.py --install-language it  # Italian
   # See Supported Languages section for more options
   ```
   
   **Or manually with spaCy**:
   ```bash
   python -m spacy download en_core_web_lg  # English
   python -m spacy download it_core_news_lg  # Italian
   ```

## 🚀 Usage

### Basic Usage

Extract toponyms from a PDF with automatic language detection:

```bash
python geoNamesFromPdf.py document.pdf
```

### Process Specific Pages

Limit extraction to specific page ranges (useful to exclude title pages, bibliographies, etc.):

```bash
# Single page
python geoNamesFromPdf.py document.pdf -p 5

# Page range
python geoNamesFromPdf.py document.pdf -p 5-10

# Multiple ranges
python geoNamesFromPdf.py document.pdf -p "5-10, 12-14, 20-25"
```

### Specify Language

Force a specific language (recommended for better accuracy):

```bash
python geoNamesFromPdf.py -l it italian_document.pdf
python geoNamesFromPdf.py -l en english_document.pdf
```

### List Available Languages

Check which language models are installed:

```bash
python geoNamesFromPdf.py --list-languages
```

### Install a New Language

Install a language model using the language code:

```bash
python geoNamesFromPdf.py --install-language it
python geoNamesFromPdf.py --install-language es
python geoNamesFromPdf.py --install-language fr
```

### Get Help

```bash
python geoNamesFromPdf.py --help
```

### Output Formats

By default results are printed as a plain list. Use `-f/--format` (and optionally
`-o/--output FILE`) to get structured, GIS-ready output:

```bash
# Plain list (default), with label / mention count / pages
python geoNamesFromPdf.py document.pdf --details

# CSV: name,label,count,pages,sources,gazetteer_id,lat,lon
python geoNamesFromPdf.py document.pdf -f csv -o places.csv

# JSON (full result, including per-page provenance)
python geoNamesFromPdf.py document.pdf -f json -o places.json

# GeoJSON — emits only toponyms that carry coordinates (see Gazetteer below)
python geoNamesFromPdf.py document.pdf --gazetteer pleiades.tsv -f geojson -o places.geojson
```

Every toponym now carries how many times it occurred, on which pages, and where
it came from (`ner:GPE`, `ner:LOC`, `gazetteer`, …).

### Extraction Engines (all offline, no external services)

`--engine` selects how place names are recognised. All engines run locally.

| Engine | Flag | Notes |
|--------|------|-------|
| spaCy CNN (default) | `--engine spacy` | Fast, ~500 MB per language. NER-only pipeline. |
| spaCy transformer | `--engine spacy-trf` | Better accuracy on modern text. Needs `pip install spacy-transformers` and a `_trf` model. |
| GLiNER | `--engine gliner` | Label-driven local model — extract exactly the categories you ask for. Needs `pip install gliner gliner-spacy`. |
| Gazetteer only | `--no-ner --gazetteer FILE` | No model, no language detection — deterministic matching against your list. Ideal for ancient/dead languages. |

## 🆕 Gazetteer Support

You can supply a custom gazetteer (a list of place names, optionally with
identifiers and coordinates) to complement — or entirely replace — spaCy's NER.
This is especially useful for documents in dead languages, or where NER performs
poorly.

### Using a Gazetteer

Plain list — one place name per line:

```bash
python geoNamesFromPdf.py document.pdf --gazetteer path/to/gazetteer.txt
```

- Matching is single-pass, case-insensitive, respects word boundaries (so `Como` does **not** match inside `Comodo`) and understands multi-word names (the longest match wins).
- Results are merged with the NER output; each toponym records whether it came from `ner`, the `gazetteer`, or both.
- If no gazetteer is provided, the script relies solely on the selected NER engine.

### Gazetteer With Coordinates (CSV / TSV)

A `.csv` or `.tsv` gazetteer can carry identifiers and coordinates, which are
then attached to the results and exported by `-f geojson` / `-f csv`. Recognised
column headers (case-insensitive): `name`/`toponym`/`title`, `label`/`type`,
`id`/`uri`, `lat`/`latitude`, `lon`/`longitude`.

```text
name	id	lat	lon
Butrint	pleiades:530798	39.7456	20.0206
Epirus	pleiades:991380	39.5000	20.5000
```

This pairs well with a local extract of a historical gazetteer such as
[Pleiades](https://pleiades.stoa.org/) or GeoNames.

### Example Gazetteer File (plain)

```text
Babylon
Nineveh
Uruk
Thebes
Memphis
```

### Gazetteer-Only Mode

For Latin, Ancient Greek and other languages spaCy has no model for, skip NER
entirely:

```bash
python geoNamesFromPdf.py document.pdf --no-ner --gazetteer ancient_places.txt
```

## 🖥️ GUI (PyQt) — Usage

A simple graphical interface is provided in `gui.py` for users who prefer not to use the command line. The GUI exposes the same functionality and adds interactive list management.

How to run the GUI

1. Activate your virtual environment (if you created one):
```bash
source venv/bin/activate
```
2. Install dependencies if you haven't already (from project root):
```bash
pip install -r requirements.txt
pip install PyQt5
```
3. Launch the GUI:
```bash
python gui.py
```

Main features and layout

- "Select PDF": choose a PDF to process (or drag & drop a PDF onto the window). The last selected PDF is remembered so you can re-run without reselecting.
- **Page range**: optional field to specify which pages to process (e.g., "5", "5-10", or "5-10, 12-14"). Leave blank to process all pages.
- Gazetteer (left column): load a gazetteer (.txt) or add/remove included place names manually. Use "Save Included to File" to export the list.
- Exclude list (right column): load or edit a list of toponyms to exclude from results. Use "Save Excluded to File" to export.
- "Process PDF" button runs extraction and shows a scrollable list of extracted toponyms below.
- Results are interactive: each extracted toponym has Add and Remove buttons. "Add" appends the item to the included gazetteer; "Remove" appends it to the exclude list.

Notes and tips

- Gazetteeer files should be plain UTF-8 text with one place name per line.
- The GUI supports both spaCy-based extraction and gazetteer matching; if no gazetteer is loaded the tool still runs spaCy NER.
- For a lightweight distribution, consider using the GUI in "gazetteer-only" mode by avoiding installation of spaCy models — this reduces package size (see the Packaging section below).

## 🗂️ Zotero assistant

`zotero_assistant.py` is a second graphical tool that helps you tag the items of
a **Zotero library** with the places mentioned in their attached PDF(s), reusing
the geographic tags you already use.

It assumes a tagging convention: geographic tags are prefixed with `@`
(`@Butrint`, `@Çuka e Ajtoit`, …). Those existing `@` tags are fed to the
extractor as a gazetteer.

Pick a library and its records that are not yet tagged `geodone` appear in a
list on the left (with a title filter). Select one and you get:

- **existing `@` tags that occur in the text** — pre-checked, with occurrence
  count and page numbers;
- **new place candidates** found by NER (labels `GPE` / `LOC`) that are not yet
  in your vocabulary — unchecked. Each has an **editable target field** (default
  `@Name`) so you can normalise it, and when it looks close to an existing tag a
  one-click **↳ @ExistingTag** button adopts that tag instead.

*Save selected + Next* writes the approved tags, sorts the item's tag list
alphabetically, adds `geodone` (so the record leaves the list) and moves to the
next row. *Skip and don't ask again* just writes `geodone`. *Skip (pending)*
leaves the record in the list for a later session. Every action is appended to a
`zotero-assistant-log-*.csv` file in the working directory.

### Per-record language

The middle column has a **Language** selector and a **Re-analyze** button. The
language is auto-detected by default, but spaCy only has NER models for the
languages in `LANGUAGE_MODELS`; for anything else (Albanian, Latin, Ancient
Greek, …) it silently falls back to English, which produces many false
positives — a warning says so. Pick the right language and Re-analyze, or choose
**"— no NER (gazetteer only) —"** to match only against your `@` tags, with no
NER noise. The choice carries over to the next record (handy for a run of
same-language articles).

### Scanned PDFs / OCR

A PDF with no text layer can't be analysed. If [`ocrmypdf`](https://ocrmypdf.readthedocs.io/)
is on your `PATH`, a **Run OCR (ocrmypdf)** button appears: it OCRs the file
in-memory (using the selected language), then re-analyses — the attachment in
Zotero is left unchanged. After a successful OCR a **Save searchable PDF…**
button lets you write the OCR'd file to disk (re-import it into Zotero yourself
if you want it there). Otherwise, OCR the file with your own tool, reopen the
record and Re-analyze.

### Requirements

- **Zotero 10.0 or newer** (the local write API landed in 10.0).
- In Zotero: *Settings → Advanced →* enable **"Allow other applications on this
  computer to communicate with Zotero"**.
- `pip install httpx` (already in `requirements.txt`).
- *Optional:* `ocrmypdf` on `PATH` for the OCR button (`brew install ocrmypdf`,
  `apt install ocrmypdf`, …).

Everything runs against Zotero's **local API** (`http://localhost:23119`): no
network, no `zotero.org` account needed. On the first save Zotero shows a
one-time dialog asking you to grant write access — choose *Always Allow* to
avoid repeating it.

```bash
python zotero_assistant.py
```

The library dropdown lists your personal library and any group libraries. Files
are read from Zotero's local storage: for a group whose files are synced on
demand, enable *Settings → Sync → "Download files"* (or pre-download the PDFs of
the items you will process) — records whose PDF is not on disk are shown with a
notice and can only be skipped.

## ⚙️ Quick setup script

A small helper script is provided at `scripts/setup_and_run.sh` to make it easy for non-technical users to get started. The script will clone (or update) the repository, create a virtual environment, install Python dependencies from `requirements.txt`, and — optionally — run the GUI.

Basic usage (from your shell):

```bash
# Run setup locally and then open the GUI
./scripts/setup_and_run.sh --run-gui

# Make the script executable if needed
chmod +x scripts/setup_and_run.sh
./scripts/setup_and_run.sh --run-gui
```

Download-and-run (one-liner, pipes the raw script to bash):

```bash
curl -sL https://raw.githubusercontent.com/lad-sapienza/geoNamesFromPdf/GUI-PyQtPySide/scripts/setup_and_run.sh \
   | bash -s -- --run-gui
```

Script flags

- `--run-gui` — run the GUI after setup (invokes `venv/bin/python gui.py`).
- `--dest <dir>` — destination directory to clone/update (default: `~/geoNamesFromPdf`).
- `--branch <branch>` — git branch to checkout (default: `GUI-PyQtPySide`).
- `--repo <url>` — repository URL (default: the GitHub repo).
- `--python <python_cmd>` — which Python executable to use for creating the venv (default: `python3`).

- `--run-gui` — run the GUI after setup (invokes `venv/bin/python gui.py`).
- `--dest <dir>` — destination directory to clone/update (default: `~/geoNamesFromPdf`).
- `--branch <branch>` — git branch to checkout (default: `GUI-PyQtPySide`).
- `--repo <url>` — repository URL (default: the GitHub repo).
- `--python <python_cmd>` — which Python executable to use for creating the venv (default: `python3`).

Additional flags:

- `--install-spacy-models` — after installing Python packages, download a set of spaCy models (explicit opt-in). Default models: `en_core_web_lg,it_core_news_lg`.
- `--spacy-models <comma_separated_models>` — specify a comma-separated list of spaCy model names to download (e.g. `en_core_web_lg,es_core_news_lg`).
- `--skip-pip` — skip the `pip install -r requirements.txt` step (useful for fast smoke-tests or when installing packages manually).

Notes & caveats:

- The script requires `git` and a working Python 3 executable in PATH. If you use pyenv, prefer passing `--python /full/path/to/python` or run the script after activating the desired Python environment.
- The script does not automatically download large spaCy language models. If you need spaCy models, install them manually or add the `--install-spacy-models` step when prompted.
- Running shell scripts from the internet with `curl | bash` is convenient but has security implications; review the script before executing if unsure.



## 🎬 First Run Experience

On your first run, if dependencies are missing, you'll see:

```
======================================================================
🚀 FIRST RUN SETUP - geoNamesFromPdf
======================================================================

Checking dependencies...

📦 Missing Python packages:
   ❌ PyMuPDF
   ❌ spacy
   ❌ langdetect

🌍 Missing essential language models:
   ❌ EN - en_core_web_lg
   ❌ IT - it_core_news_lg

======================================================================
This script needs to install the missing dependencies to work properly.
The installation may take several minutes and download ~500MB per language.
======================================================================

❓ Do you want to install missing dependencies now? (yes/no):
```

**Answer 'yes'** to automatically install everything, or **'no'** to install manually.

After successful installation, the tool remembers setup is complete and won't prompt again.

## 📖 Examples

### Example 1: Italian Document (Auto-detect)

```bash
python geoNamesFromPdf.py storia_italiana.pdf
```

**Output:**
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

### Example 2: English Document (Explicit Language)

```bash
python geoNamesFromPdf.py -l en travel_guide.pdf
```

**Output:**
```
🌐 Using specified language: en
🧠 Using engine 'spacy' / model: core_web_lg v3.8.0

📍 Toponyms found in the PDF (12 total):

- Africa
- Asia
- Europe
- France
- London
- New York
- Paris
- Rome
- Spain
- Tokyo
- United Kingdom
- United States
```

### Example 3: List Available Languages

Check which language models are configured and installed:

```bash
python geoNamesFromPdf.py --list-languages
```

**Output:**
```
🌍 Configured Languages:
============================================================
  [en] EN           - en_core_web_lg       ✅ Installed (v3.8.0)
  [it] IT           - it_core_news_lg      ✅ Installed (v3.8.0)

💡 To install a missing model, run:
   python geoNamesFromPdf.py --install-language <language_code>

Example: python geoNamesFromPdf.py --install-language it
```

### Example 4: Install a New Language

Install Spanish language support:

```bash
python geoNamesFromPdf.py --install-language es
```

**Output:**
```
📦 Installing language model: es_core_news_lg
   Language: ES
   This may take a few minutes...

✅ Successfully installed es_core_news_lg!
   You can now process ES documents.
```

All languages in the table below are pre-configured in the `LANGUAGE_MODELS` dictionary in `core.py`; you only need to download the model.

### Example 5: Processing Specific Pages

Extract toponyms only from specific pages or page ranges:

```bash
# Process only pages 10-50 (excluding front matter and bibliography)
python geoNamesFromPdf.py document.pdf -p "10-50"
```

**Output:**
```
📄 Processing pages: 10-50
🌐 Detected language: en
🧠 Using engine 'spacy' / model: core_web_lg v3.8.0

📍 Toponyms found in the PDF (15 total):

- Athens
- Egypt
- Greece
- Mediterranean
- Rome
...
```

### Example 6: Using with pyenv

If you use pyenv and encounter "python: command not found", use the full path:

```bash
/Users/jbogdani/Desktop/apps/geoNamesFromPdf/venv/bin/python \
  geoNamesFromPdf.py document.pdf
```

Or set a global Python version:

```bash
pyenv global 3.12.8
python geoNamesFromPdf.py document.pdf
```

## 🎯 Supported Languages

The tool comes pre-configured with support for multiple languages. Simply install the ones you need:

| Language | Code | Installation Command |
|----------|------|---------------------|
| English | `en` | `python geoNamesFromPdf.py --install-language en` |
| Italian | `it` | `python geoNamesFromPdf.py --install-language it` |
| Spanish | `es` | `python geoNamesFromPdf.py --install-language es` |
| French | `fr` | `python geoNamesFromPdf.py --install-language fr` |
| German | `de` | `python geoNamesFromPdf.py --install-language de` |
| Portuguese | `pt` | `python geoNamesFromPdf.py --install-language pt` |
| Dutch | `nl` | `python geoNamesFromPdf.py --install-language nl` |
| Greek | `el` | `python geoNamesFromPdf.py --install-language el` |
| Polish | `pl` | `python geoNamesFromPdf.py --install-language pl` |
| Romanian | `ro` | `python geoNamesFromPdf.py --install-language ro` |

### Quick Start with Languages

1. **Check available languages**:
   ```bash
   python geoNamesFromPdf.py --list-languages
   ```

2. **Install the language you need**:
   ```bash
   python geoNamesFromPdf.py --install-language es  # For Spanish
   ```

3. **Process your document**:
   ```bash
   python geoNamesFromPdf.py -l es spanish_document.pdf  # Explicit
   python geoNamesFromPdf.py spanish_document.pdf        # Auto-detect
   ```

### Adding More Languages

To add languages not listed above, edit the `LANGUAGE_MODELS` dictionary in `core.py` and add the appropriate spaCy model. Available models can be found at: https://spacy.io/models

## 🔧 Command-Line Options

```
usage: geoNamesFromPdf.py [-h] [-l LANGUAGE] [-p PAGES]
                          [--engine {spacy,spacy-trf,gliner}] [--no-ner]
                          [-f {txt,csv,json,geojson}] [-o FILE] [--details]
                          [--list-languages] [--install-language LANG_CODE]
                          [--skip-setup] [--gazetteer GAZETTEER]
                          [--exclude EXCLUDE]
                          [pdf_path]

positional arguments:
  pdf_path              Path to the PDF file to process

options:
  -h, --help            Show this help message and exit
  -l LANGUAGE, --language LANGUAGE
                        Force specific language (en, it, etc.).
                        If not specified, language will be auto-detected.
  -p PAGES, --pages PAGES
                        Page range(s) to process (e.g., '5', '5-10', '5-10, 12-14').
                        If not specified, all pages are processed.
  --engine {spacy,spacy-trf,gliner}
                        Extraction engine, all offline (default: spacy).
  --no-ner             Disable NER; use the gazetteer only (requires --gazetteer).
  -f, --format {txt,csv,json,geojson}
                        Output format (default: txt).
  -o FILE, --output FILE
                        Write results to FILE instead of stdout.
  --details            With --format txt, also show label / count / pages.
  --gazetteer GAZETTEER
                        Path to a gazetteer file (.txt, or .csv/.tsv with
                        name/id/lat/lon columns).
  --exclude EXCLUDE     Comma-separated list of toponyms to exclude from extraction
  --list-languages      List all available language models and exit
  --install-language LANG_CODE
                        Install language model for the specified language code
                        (e.g., it, es, fr, de) and exit
  --skip-setup          Skip first-run setup check
```

## 📊 How It Works

All extraction logic lives in `core.py` and is shared by the CLI
(`geoNamesFromPdf.py`), the GUI (`gui.py`) and the Zotero assistant
(`zotero_assistant.py`, with `zotero.py` for the local-API access).

1. **PDF Text Extraction**: PyMuPDF extracts text page by page (optionally limited to `--pages`)
2. **Language Detection**: `langdetect` (fixed seed) detects the language, unless `-l` is given
3. **Model Loading**: a NER-only spaCy pipeline is loaded and cached (parser/tagger/lemmatizer are dropped for speed)
4. **Named Entity Recognition**: geographic entities (`GPE`, `LOC`, `FAC`) are collected per page, with mention counts and page numbers
5. **Gazetteer Matching**: optional single-pass, word-boundary, case-insensitive matching; coordinates/identifiers are attached when present
6. **Post-processing**: `--exclude` names are dropped (case-insensitive), results are de-duplicated and sorted, then serialised (`txt`/`csv`/`json`/`geojson`)

### Entity Types Detected

- **GPE** (Geo-Political Entity): Countries, cities, states
- **LOC** (Location): Non-GPE locations, mountain ranges, bodies of water
- **FAC** (Facility): Buildings, airports, highways, bridges

## 💡 Tips for Best Results

1. **Use language-specific models**: Explicitly specify the language with `-l` for better accuracy
2. **Quality of PDF**: Clear, well-formatted PDFs yield better results
3. **Text-based PDFs**: Scanned images require OCR preprocessing (not included)
4. **Multiple languages**: If your document contains multiple languages, the tool will detect the primary language
5. **Ancient / dead languages**: `langdetect` has no model for Latin, Ancient Greek, etc. and will guess wrongly. Pass `-l` explicitly, or use `--no-ner --gazetteer` for deterministic matching.
6. **Large books**: text is processed page by page, so documents of any length are fine.

## 🧪 Development

```bash
pip install pytest
python -m pytest        # offline unit tests, no model downloads needed
```

## 🐛 Troubleshooting

### "python: command not found" with pyenv

**Solution**: Use the full path to the Python executable or set a global Python version:
```bash
pyenv global 3.12.8
```

### "Model not found" error

**Solution**: Install the required spaCy model:
```bash
python -m spacy download en_core_web_lg
python -m spacy download it_core_news_lg
```

### Poor results with non-English documents

**Solution**: Ensure you have the appropriate language model installed and either:
- Let the tool auto-detect the language, or
- Explicitly specify the language with `-l it` (for Italian, etc.)

### False positives or missed locations

**Solution**: 
- Make sure you're using the correct language model
- Try using the large (`lg`) model variants for better accuracy
- Some ambiguous terms may be incorrectly classified

### Want to skip the first-run setup prompt?

**Solution**: Use the `--skip-setup` flag:
```bash
python geoNamesFromPdf.py --skip-setup document.pdf
```

Or if you want to reset and see the setup prompt again:
```bash
rm .setup_complete
python geoNamesFromPdf.py document.pdf
```

## 📦 Dependencies

- **PyMuPDF** (`import pymupdf`) - PDF text extraction
- **spaCy** - Natural language processing and NER
- **langdetect** - Automatic language detection
- **PyQt5** - GUI (`gui.py`, `zotero_assistant.py`)
- **httpx** - Zotero local-API client (`zotero_assistant.py`)
- **en_core_web_lg** - English language model (large)
- **it_core_news_lg** - Italian language model (large)

Optional: `spacy-transformers` (`--engine spacy-trf`), `gliner` + `gliner-spacy`
(`--engine gliner`), `pytest` (tests).

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### Third-Party Licenses

This project uses the following open-source libraries:
- **spaCy** - [MIT License](https://github.com/explosion/spaCy/blob/master/LICENSE)
- **PyMuPDF** - [GNU AGPL v3](https://github.com/pymupdf/PyMuPDF/blob/master/COPYING)
- **langdetect** - [Apache License 2.0](https://github.com/Mimino666/langdetect/blob/master/LICENSE)

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

### Adding Language Support
1. Install additional spaCy language models
2. Update the `LANGUAGE_MODELS` dictionary in `geoNamesFromPdf.py`
3. Test with sample documents
4. Submit a pull request

### Reporting Issues
- Use the GitHub Issues tab
- Provide clear description and steps to reproduce
- Include Python version and OS information

### Pull Requests
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📧 Support

For issues or questions:
- Check the troubleshooting section above
- Verify all dependencies are installed correctly
- Ensure you're using the correct language model

## 🔗 Resources

- [spaCy Documentation](https://spacy.io/)
- [spaCy Models](https://spacy.io/models)
- [PyMuPDF Documentation](https://pymupdf.readthedocs.io/)
- [langdetect on PyPI](https://pypi.org/project/langdetect/)

---

**Version**: 1.1  
**Last Updated**: August 2026
