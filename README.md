# geoNamesFromPdf

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![spaCy](https://img.shields.io/badge/built%20with-spaCy-09a3d5.svg)](https://spacy.io)

Extract toponyms (place names) from PDF files using spaCy's Named Entity Recognition (NER) with automatic language detection.

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/geoNamesFromPdf.git
cd geoNamesFromPdf

# Create virtual environment (Python 3.12 recommended)
python3.12 -m venv venv
source venv/bin/activate  # On macOS/Linux
# or: venv\Scripts\activate  # On Windows

# Run the script - it will install dependencies automatically
python geoNamesFromPdf.py your_document.pdf
```

That's it! On first run, the tool will guide you through automatic dependency installation.

## 📋 Overview

This tool analyzes PDF documents and automatically identifies geographic entities such as cities, countries, regions, and landmarks. It supports multiple languages and automatically detects the language of your document for optimal accuracy.

## ✨ Features

- 🌍 **Multi-language support** - Automatically detects document language (10+ languages pre-configured)
- 🔍 **High accuracy** - Uses spaCy's large language models for NER
- 🎯 **Smart detection** - Extracts cities, countries, regions, and landmarks
- 📄 **PDF processing** - Works directly with PDF files
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
🧠 Using model: core_news_lg v3.8.0

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
🧠 Using model: core_web_lg v3.8.0

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

Note: Before installing, make sure to uncomment the Spanish entry in the `LANGUAGE_MODELS` dictionary in `geoNamesFromPdf.py`.

### Example 5: Using with pyenv

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

To add languages not listed above, edit the `LANGUAGE_MODELS` dictionary in `geoNamesFromPdf.py` and add the appropriate spaCy model. Available models can be found at: https://spacy.io/models

## 🔧 Command-Line Options

```
usage: geoNamesFromPdf.py [-h] [-l LANGUAGE] [--list-languages]
                          [--install-language LANG_CODE] [--skip-setup]
                          [pdf_path]

positional arguments:
  pdf_path              Path to the PDF file to process

options:
  -h, --help            Show this help message and exit
  -l LANGUAGE, --language LANGUAGE
                        Force specific language (en, it, etc.).
                        If not specified, language will be auto-detected.
  --list-languages      List all available language models and exit
  --install-language LANG_CODE
                        Install language model for the specified language code
                        (e.g., it, es, fr, de) and exit
  --skip-setup          Skip first-run setup check
```

## 📊 How It Works

1. **PDF Text Extraction**: Uses PyMuPDF to extract text from PDF documents
2. **Language Detection**: Analyzes text to detect the language (using langdetect)
3. **NLP Model Loading**: Loads the appropriate spaCy language model
4. **Named Entity Recognition**: Identifies geographic entities (GPE, LOC, FAC)
5. **Post-processing**: Removes duplicates and sorts results alphabetically

### Entity Types Detected

- **GPE** (Geo-Political Entity): Countries, cities, states
- **LOC** (Location): Non-GPE locations, mountain ranges, bodies of water
- **FAC** (Facility): Buildings, airports, highways, bridges

## 💡 Tips for Best Results

1. **Use language-specific models**: Explicitly specify the language with `-l` for better accuracy
2. **Quality of PDF**: Clear, well-formatted PDFs yield better results
3. **Text-based PDFs**: Scanned images require OCR preprocessing (not included)
4. **Multiple languages**: If your document contains multiple languages, the tool will detect the primary language

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

- **PyMuPDF** (fitz) - PDF text extraction
- **spaCy** - Natural language processing and NER
- **langdetect** - Automatic language detection
- **en_core_web_lg** - English language model (large)
- **it_core_news_lg** - Italian language model (large)

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

**Version**: 1.0  
**Last Updated**: October 2025
