import sys
sys.path.insert(0, "./libs")

import argparse
import subprocess
import os
import re

# Configuration file to track if initial setup was completed
SETUP_MARKER_FILE = os.path.join(os.path.dirname(__file__) or '.', '.setup_complete')

# Import optional dependencies - will be checked during setup
try:
    import fitz  # PyMuPDF
    import spacy
    from langdetect import detect
    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False

# Available spaCy models for different languages
# Uncomment languages as needed before installing them
LANGUAGE_MODELS = {
    'en': 'en_core_web_lg',      # English
    'it': 'it_core_news_lg',     # Italian
    'es': 'es_core_news_lg',     # Spanish
    'fr': 'fr_core_news_lg',     # French
    'de': 'de_core_news_lg',     # German
    'pt': 'pt_core_news_lg',     # Portuguese
    'nl': 'nl_core_news_lg',     # Dutch
    'el': 'el_core_news_lg',     # Greek
    'pl': 'pl_core_news_lg',     # Polish
    'ro': 'ro_core_news_lg',     # Romanian
}

def check_dependencies():
    """Check if required Python packages are installed."""
    missing_packages = []
    
    # These imports are local to avoid breaking the script if packages are missing
    try:
        import fitz  # noqa: F401
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
            except:
                print(f"  [{lang_code}] {model_name:20} {status}")
        else:
            print(f"  [{lang_code}] {model_name:20} {status}")
    
    print("\n💡 To install a missing model, run:")
    print("   python geoNamesFromPdf.py --install-language <language_code>")
    print("\nExample: python geoNamesFromPdf.py --install-language it")

def install_language_model(language_code):
    """Install a language model for the specified language."""
    if language_code not in LANGUAGE_MODELS:
        print(f"❌ Error: Language code '{language_code}' is not configured.")
        print(f"\n📋 Available language codes: {', '.join(sorted(LANGUAGE_MODELS.keys()))}")
        print("\nTo add a new language, edit the LANGUAGE_MODELS dictionary in the script.")
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
        result = subprocess.run(
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

def load_nlp_model(language_code):
    """Load the appropriate spaCy model for the detected language."""
    model_name = LANGUAGE_MODELS.get(language_code, 'en_core_web_lg')
    try:
        return spacy.load(model_name)
    except OSError:
        print(f"Warning: Model '{model_name}' not found. Falling back to English model.")
        return spacy.load('en_core_web_lg')

def detect_language(text):
    """Detect the language of the text."""
    try:
        # Take a sample of the text for language detection (first 1000 chars)
        sample_text = text[:1000].strip()
        if len(sample_text) < 50:
            return 'en'  # Default to English if text is too short
        return detect(sample_text)
    except:
        return 'en'  # Default to English if detection fails

def extract_text_from_pdf(pdf_path):
    """Extract full text from PDF using PyMuPDF."""
    doc = fitz.open(pdf_path)
    text = " ".join(page.get_text() for page in doc)
    return text

def extract_toponyms(text, nlp_model):
    """Extract place names using spaCy NER."""
    doc = nlp_model(text)
    toponyms = [ent.text for ent in doc.ents if ent.label_ in ("GPE", "LOC", "FAC")]
    return sorted(set(toponyms))  # unique + sorted

def load_gazetteer(file_path):
    """Load gazetteer from a file into a set."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f if line.strip())
    except Exception as e:
        print(f"Error loading gazetteer: {e}")
        return set()

def match_gazetteer(text, gazetteer):
    """Find matches for gazetteer entries in the text."""
    matches = set()
    for place in gazetteer:
        # Use word boundaries to ensure exact matches
        if re.search(rf"\\b{re.escape(place)}\\b", text, re.IGNORECASE):
            matches.add(place)
    return matches

if __name__ == "__main__":
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description="Extract toponyms (place names) from PDF files using spaCy NER.")
    parser.add_argument("pdf_path", nargs="?", help="Path to the PDF file to process")
    parser.add_argument("-l", "--language", help="Force specific language (en, it, etc.). If not specified, language will be auto-detected.")
    parser.add_argument("--list-languages", action="store_true", help="List all available language models and exit")
    parser.add_argument("--install-language", metavar="LANG_CODE", help="Install language model for the specified language code (e.g., it, es, fr, de) and exit")
    parser.add_argument("--skip-setup", action="store_true", help="Skip first-run setup check")
    parser.add_argument("--gazetteer", help="Path to a gazetteer file for custom place name extraction")
    
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
    
    # Load gazetteer if provided
    gazetteer = set()
    if args.gazetteer:
        print(f"📖 Loading gazetteer from: {args.gazetteer}")
        gazetteer = load_gazetteer(args.gazetteer)
        print(f"✅ Loaded {len(gazetteer)} entries from gazetteer.")

    try:
        text = extract_text_from_pdf(args.pdf_path)
        
        # Detect or use specified language
        if args.language:
            language = args.language.lower()
            print(f"🌐 Using specified language: {language}")
        else:
            language = detect_language(text)
            print(f"🌐 Detected language: {language}")
        
        # Load appropriate NLP model
        nlp_model = load_nlp_model(language)
        print(f"🧠 Using model: {nlp_model.meta['name']} v{nlp_model.meta['version']}")
        
        # Extract toponyms using spaCy
        places = extract_toponyms(text, nlp_model)

        # Match gazetteer entries if provided
        if gazetteer:
            gazetteer_matches = match_gazetteer(text, gazetteer)
            places = sorted(set(places).union(gazetteer_matches))

        print(f"\n📍 Toponyms found in the PDF ({len(places)} total):\n")
        for p in places:
            print("-", p)
            
    except FileNotFoundError:
        print(f"Error: PDF file '{args.pdf_path}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error processing PDF: {e}")
        sys.exit(1)