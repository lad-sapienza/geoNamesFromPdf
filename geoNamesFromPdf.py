import sys
import os

# Optional: allow a local ``libs/`` directory (e.g. bundled wheels) on the path.
_LIBS_DIR = os.path.join(os.path.dirname(__file__) or '.', 'libs')
if os.path.isdir(_LIBS_DIR):
    sys.path.insert(0, _LIBS_DIR)

import argparse
import subprocess

import core
from core import (  # noqa: F401  (re-exported for backward compatibility)
    LANGUAGE_MODELS,
    parse_page_ranges,
    detect_language,
)

# Configuration file to track if initial setup was completed
SETUP_MARKER_FILE = os.path.join(os.path.dirname(__file__) or '.', '.setup_complete')

# Import optional dependencies - will be checked during setup
try:
    import pymupdf  # noqa: F401
    import spacy
    from langdetect import detect  # noqa: F401
    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False


def check_dependencies():
    """Check if required Python packages are installed."""
    missing_packages = []

    # These imports are local to avoid breaking the script if packages are missing
    try:
        import pymupdf  # noqa: F401
    except ImportError:
        missing_packages.append('PyMuPDF')

    try:
        import spacy  # noqa: F401
    except ImportError:
        missing_packages.append('spacy')

    try:
        from langdetect import detect  # noqa: F401
    except ImportError:
        missing_packages.append('langdetect')

    return missing_packages


def check_language_models():
    """Check which essential language models are missing."""
    try:
        import spacy  # noqa: F401
        installed_models = spacy.util.get_installed_models()
    except ImportError:
        # If spacy isn't installed, all models are missing
        return [('en', LANGUAGE_MODELS['en']), ('it', LANGUAGE_MODELS['it'])]

    essential_models = ['en', 'it']  # Default essential languages
    missing_models = []

    for lang_code in essential_models:
        model_name = LANGUAGE_MODELS.get(lang_code)
        if model_name and model_name not in installed_models:
            missing_models.append((lang_code, model_name))

    return missing_models


def first_run_setup():
    """Perform first-run setup: check and install dependencies."""
    # Skip if setup was already completed
    if os.path.exists(SETUP_MARKER_FILE):
        return True

    print("=" * 70)
    print("🚀 FIRST RUN SETUP - geoNamesFromPdf")
    print("=" * 70)
    print("\nChecking dependencies...\n")

    # Check Python packages
    missing_packages = check_dependencies()
    missing_models = check_language_models()

    if not missing_packages and not missing_models:
        print("✅ All dependencies are already installed!")
        # Create marker file
        with open(SETUP_MARKER_FILE, 'w') as f:
            f.write("Setup completed\n")
        return True

    # Show what's missing
    if missing_packages:
        print("📦 Missing Python packages:")
        for package in missing_packages:
            print(f"   ❌ {package}")
        print()

    if missing_models:
        print("🌍 Missing essential language models:")
        for lang_code, model_name in missing_models:
            lang_name = lang_code.upper()
            print(f"   ❌ {lang_name} - {model_name}")
        print()

    # Ask for confirmation
    print("=" * 70)
    print("This script needs to install the missing dependencies to work properly.")
    print("The installation may take several minutes and download ~500MB per language.")
    print("=" * 70)

    response = input("\n❓ Do you want to install missing dependencies now? (yes/no): ").strip().lower()

    if response not in ['yes', 'y']:
        print("\n⚠️  Setup cancelled. Please install dependencies manually:")
        if missing_packages:
            print(f"\n   pip install {' '.join(missing_packages)}")
        if missing_models:
            for lang_code, model_name in missing_models:
                print(f"   python -m spacy download {model_name}")
        print("\nOr run this script again to retry automatic installation.\n")
        return False

    print("\n" + "=" * 70)
    print("📥 INSTALLING DEPENDENCIES")
    print("=" * 70 + "\n")

    success = True

    # Install Python packages
    if missing_packages:
        print(f"Installing Python packages: {', '.join(missing_packages)}...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install"] + missing_packages,
                check=True
            )
            print("✅ Python packages installed successfully!\n")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error installing packages: {e}\n")
            success = False

    # Install language models
    if missing_models and success:
        for lang_code, model_name in missing_models:
            lang_name = lang_code.upper()
            print(f"Installing {lang_name} language model ({model_name})...")
            print("   This may take a few minutes...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "spacy", "download", model_name],
                    check=True,
                    capture_output=True
                )
                print(f"   ✅ {lang_name} model installed successfully!\n")
            except subprocess.CalledProcessError as e:
                print(f"   ❌ Error installing {lang_name} model\n")
                success = False

    if success:
        print("=" * 70)
        print("🎉 SETUP COMPLETE!")
        print("=" * 70)
        print("\n✅ All dependencies have been installed successfully.")
        print("   You can now use geoNamesFromPdf to extract toponyms from PDFs.")
        print("\n💡 Please run your command again to use the newly installed dependencies.\n")

        # Create marker file
        with open(SETUP_MARKER_FILE, 'w') as f:
            f.write("Setup completed\n")

        # Exit so user runs the command again with fresh imports
        sys.exit(0)
    else:
        print("\n⚠️  Some dependencies failed to install.")
        print("   Please check the errors above and try manual installation.\n")
        return False


def list_available_languages():
    """List all configured and installed language models."""
    if not IMPORTS_AVAILABLE:
        print("❌ Error: Required dependencies not installed.")
        print("   Run the first-time setup or install manually:")
        print("   pip install PyMuPDF spacy langdetect")
        return

    print("🌍 Configured Languages:")
    print("=" * 60)

    installed_models = spacy.util.get_installed_models()

    for lang_code, model_name in sorted(LANGUAGE_MODELS.items()):
        is_installed = model_name in installed_models
        status = "✅ Installed" if is_installed else "❌ Not installed"

        if is_installed:
            try:
                nlp = spacy.load(model_name)
                version = nlp.meta.get('version', 'unknown')
                lang_name = nlp.meta.get('lang', lang_code).upper()
                print(f"  [{lang_code}] {lang_name:12} - {model_name:20} {status} (v{version})")
            except Exception:
                print(f"  [{lang_code}] {model_name:20} {status}")
        else:
            print(f"  [{lang_code}] {model_name:20} {status}")

    print("\n💡 To install a missing model, run:")
    print("   python geoNamesFromPdf.py --install-language <language_code>")
    print("\nExample: python geoNamesFromPdf.py --install-language it")


def install_language_model(language_code):
    """Install a language model for the specified language."""
    if not IMPORTS_AVAILABLE:
        print("❌ Error: spaCy is not installed yet, so models cannot be downloaded.")
        print("   Install the core dependencies first:")
        print("   pip install -r requirements.txt")
        return False

    if language_code not in LANGUAGE_MODELS:
        print(f"❌ Error: Language code '{language_code}' is not configured.")
        print(f"\n📋 Available language codes: {', '.join(sorted(LANGUAGE_MODELS.keys()))}")
        print("\nTo add a new language, edit the LANGUAGE_MODELS dictionary in core.py.")
        return False

    model_name = LANGUAGE_MODELS[language_code]

    # Check if already installed
    installed_models = spacy.util.get_installed_models()
    if model_name in installed_models:
        print(f"✅ Model '{model_name}' for language '{language_code}' is already installed.")
        return True

    print(f"📦 Installing language model: {model_name}")
    print(f"   Language: {language_code.upper()}")
    print(f"   This may take a few minutes...\n")

    try:
        # Run spacy download command
        subprocess.run(
            [sys.executable, "-m", "spacy", "download", model_name],
            check=True,
            capture_output=True,
            text=True
        )

        print(f"\n✅ Successfully installed {model_name}!")
        print(f"   You can now process {language_code.upper()} documents.")
        return True

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error installing model '{model_name}':")
        print(f"   {e.stderr}")
        print(f"\nYou can try installing manually with:")
        print(f"   python -m spacy download {model_name}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False


# --------------------------------------------------------------------------- #
# Backward-compatible thin wrappers around ``core`` (kept for external callers
# and the examples in CONTRIBUTING.md). New code should call ``core`` directly.
# --------------------------------------------------------------------------- #

def load_nlp_model(language_code):
    """Load the (NER-only) spaCy model for the given language, English on fallback."""
    try:
        return core.load_nlp(language_code)
    except core.ModelNotAvailable as exc:
        print(f"Warning: {exc}")
        raise


def extract_text_from_pdf(pdf_path, page_ranges=None):
    """Extract text from a PDF as a single string (optionally limited to pages)."""
    pages, _ = core.extract_pages(pdf_path, page_ranges)
    return " ".join(page.text for page in pages)


def extract_toponyms(text, nlp_model, exclude_list=None):
    """Extract place names using spaCy NER, excluding items in the exclude list.

    Args:
        text (str): The text to analyze
        nlp_model: Loaded spaCy language model
        exclude_list: iterable of names to drop (case-insensitive)

    Returns:
        list: Sorted list of unique toponyms
    """
    page = [core.PdfPage(number=1, text=text)]
    found = core.extract_ner(page, nlp_model)
    exclude_keys = {x.strip().casefold() for x in exclude_list} if exclude_list else set()
    return sorted(t.name for k, t in found.items() if k not in exclude_keys)


def load_gazetteer(file_path):
    """Load gazetteer from a file into a set of names."""
    try:
        return {entry.name for entry in core.load_gazetteer(file_path)}
    except Exception as e:
        print(f"Error loading gazetteer: {e}")
        return set()


def match_gazetteer(text, gazetteer):
    """Find gazetteer entries occurring in the text (word-boundary, case-insensitive)."""
    entries = [core.GazEntry(name=name) for name in gazetteer]
    matcher = core.GazetteerMatcher(entries)
    hits = matcher.find([core.PdfPage(number=1, text=text)])
    return {topo.name for topo in hits.values()}


def _print_status(result, args):
    """Print the human-readable status header for a completed analysis."""
    if args.pages:
        print(f"📄 Processing pages: {args.pages}")
    if result.pages_skipped:
        print(f"⚠️  Ignored non-existent pages: {', '.join(map(str, result.pages_skipped))}")
    if args.no_ner:
        print("🧭 Gazetteer-only mode (NER disabled)")
    elif args.language:
        print(f"🌐 Using specified language: {result.language}")
    else:
        print(f"🌐 Detected language: {result.language}")
    if result.model and not args.no_ner:
        print(f"🧠 Using engine '{result.engine}' / model: {result.model}")
    for warning in result.warnings:
        if "page" not in warning:  # page warning already shown above
            print(f"⚠️  {warning}")


if __name__ == "__main__":
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description="Extract toponyms (place names) from PDF files using spaCy NER.")
    parser.add_argument("pdf_path", nargs="?", help="Path to the PDF file to process")
    parser.add_argument("-l", "--language", help="Force specific language (en, it, etc.). If not specified, language will be auto-detected.")
    parser.add_argument("-p", "--pages", help="Page range(s) to process (e.g., '5', '5-10', '5-10, 12-14'). If not specified, all pages are processed.")
    parser.add_argument("--engine", choices=["spacy", "spacy-trf", "gliner"], default="spacy",
                        help="Extraction engine (all offline). 'spacy' (default) = CNN models; "
                             "'spacy-trf' = transformer models; 'gliner' = local GLiNER model.")
    parser.add_argument("--no-ner", action="store_true",
                        help="Disable NER; extract using the gazetteer only (needs --gazetteer).")
    parser.add_argument("-f", "--format", choices=["txt", "csv", "json", "geojson"], default="txt",
                        help="Output format (default: txt). 'geojson' only emits entries that carry coordinates.")
    parser.add_argument("-o", "--output", metavar="FILE", help="Write results to FILE instead of stdout")
    parser.add_argument("--details", action="store_true", help="With --format txt, also show label/count/pages")
    parser.add_argument("--list-languages", action="store_true", help="List all available language models and exit")
    parser.add_argument("--install-language", metavar="LANG_CODE", help="Install language model for the specified language code (e.g., it, es, fr, de) and exit")
    parser.add_argument("--skip-setup", action="store_true", help="Skip first-run setup check")
    parser.add_argument("--gazetteer", help="Path to a gazetteer file (.txt, or .csv/.tsv with name/id/lat/lon columns)")
    parser.add_argument("--exclude", help="Comma-separated list of toponyms to exclude from extraction")

    # Parse command-line arguments
    args = parser.parse_args()

    # Perform first-run setup check (unless explicitly skipped or running setup commands)
    if not args.skip_setup and not args.list_languages and not args.install_language:
        if not first_run_setup():
            print("Exiting due to incomplete setup.")
            sys.exit(1)

    # Handle list languages option
    if args.list_languages:
        list_available_languages()
        sys.exit(0)

    # Handle install language option
    if args.install_language:
        success = install_language_model(args.install_language.lower())
        sys.exit(0 if success else 1)

    # Validate that pdf_path is provided when not listing or installing languages
    if not args.pdf_path:
        parser.error("pdf_path is required unless --list-languages or --install-language is specified")

    if args.no_ner and not args.gazetteer:
        parser.error("--no-ner requires --gazetteer (there would be nothing to match)")

    # Prepare exclude list
    exclude_list = set()
    if args.exclude:
        exclude_list = {item.strip() for item in args.exclude.split(",") if item.strip()}
        print(f"🚫 Excluding toponyms: {', '.join(sorted(exclude_list))}")

    if args.gazetteer:
        print(f"📖 Loading gazetteer from: {args.gazetteer}")

    try:
        result = core.analyze(
            args.pdf_path,
            language=args.language,
            pages=args.pages,
            gazetteer=args.gazetteer,
            exclude=exclude_list,
            engine=args.engine,
            use_ner=not args.no_ner,
        )
    except FileNotFoundError:
        print(f"Error: PDF file '{args.pdf_path}' not found.")
        sys.exit(1)
    except core.GeoNamesError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error processing PDF: {e}")
        sys.exit(1)

    _print_status(result, args)

    if args.format == "txt":
        rendered = core.to_txt(result, details=args.details)
    else:
        rendered = core.serialize(result, args.format)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(rendered + ("\n" if not rendered.endswith("\n") else ""))
        print(f"\n📍 {len(result.toponyms)} toponym(s) written to {args.output}")
    elif args.format == "txt":
        print(f"\n📍 Toponyms found in the PDF ({len(result.toponyms)} total):\n")
        print(rendered)
    else:
        print(rendered)
