#!/usr/bin/env bash
set -euo pipefail

# Safety banner / metadata
# Script canonical location:
SCRIPT_URL="https://raw.githubusercontent.com/lad-sapienza/geoNamesFromPdf/GUI-PyQtPySide/scripts/setup_and_run.sh"

cat <<'BANNER'
======================================================================
geoNamesFromPdf — setup_and_run.sh
This script will clone or update the repository, create a venv and install
dependencies. If you plan to run this directly from the internet via:

  curl -sL <script-url> | bash -s -- [--run-gui]

please review the script first. You can view it here:
  $SCRIPT_URL

Running an internet-supplied script has security implications. Press Ctrl-C
now to abort if you want to inspect the file before executing.
======================================================================
BANNER

# Minimal, idempotent setup script for geoNamesFromPdf
# - clones (or updates) the repository
# - creates a virtualenv in <repo>/venv
# - installs requirements.txt
# - optionally runs the GUI (use --run-gui)
#
# Usage examples:
#  curl -sL https://raw.githubusercontent.com/lad-sapienza/geoNamesFromPdf/GUI-PyQtPySide/scripts/setup_and_run.sh | bash -s -- --run-gui
#  ./scripts/setup_and_run.sh --run-gui

REPO_URL="https://github.com/lad-sapienza/geoNamesFromPdf.git"
BRANCH="GUI-PyQtPySide"
DEST="${HOME}/geoNamesFromPdf"
PYTHON_CMD=${PYTHON:-python3}
RUN_GUI=false
INSTALL_SPACY_MODELS=false
SPACY_MODELS="en_core_web_lg,it_core_news_lg"
SKIP_PIP=false

print_help() {
  cat <<EOF
setup_and_run.sh — clone, create venv, install deps, (optionally) run GUI

Usage:
  $(basename "$0") [--run-gui] [--dest <dir>] [--branch <branch>] [--repo <repo_url>] [--python <python_cmd>]

Options:
  --run-gui        After setup, run the GUI (invokes: venv/bin/python gui.py)
  --dest DIR       Destination directory to clone/update (default: $DEST)
  --branch BRANCH  Git branch to checkout (default: $BRANCH)
  --repo URL       Repository URL (default: $REPO_URL)
  --python CMD     Python executable to create venv with (default: ${PYTHON_CMD})
  -h, --help       Show this message

Examples:
  curl -sL https://raw.githubusercontent.com/lad-sapienza/geoNamesFromPdf/GUI-PyQtPySide/scripts/setup_and_run.sh | bash -s -- --run-gui
  ./scripts/setup_and_run.sh --dest ~/projects/geoNames --python /usr/bin/python3
EOF
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-gui)
      RUN_GUI=true
      shift
      ;;
    --install-spacy-models)
      INSTALL_SPACY_MODELS=true
      shift
      ;;
    --spacy-models)
      SPACY_MODELS="$2"
      shift 2
      ;;
    --skip-pip)
      SKIP_PIP=true
      shift
      ;;
    --dest)
      DEST="$2"
      shift 2
      ;;
    --branch)
      BRANCH="$2"
      shift 2
      ;;
    --repo)
      REPO_URL="$2"
      shift 2
      ;;
    --python)
      PYTHON_CMD="$2"
      shift 2
      ;;
    -h|--help)
      print_help
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      echo "Unknown option: $1" >&2
      print_help
      exit 1
      ;;
  esac
done

echo "Repo: $REPO_URL"
echo "Branch: $BRANCH"
echo "Destination: $DEST"
echo "Python command: $PYTHON_CMD"

# Basic requirements
if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git is required but was not found in PATH" >&2
  exit 1
fi

# Clone or update
if [ -d "$DEST/.git" ]; then
  echo "Repository already exists at $DEST — fetching updates"
  git -C "$DEST" fetch --all --prune
  git -C "$DEST" checkout "$BRANCH" || git -C "$DEST" checkout -B "$BRANCH" "origin/$BRANCH" || true
  git -C "$DEST" pull --ff-only || echo "Non-fast-forward pull or no changes"
else
  echo "Cloning $REPO_URL (branch: $BRANCH) into $DEST"
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$DEST"
fi

cd "$DEST"

# Create virtualenv
if [ ! -d "venv" ]; then
  echo "Creating virtual environment using: $PYTHON_CMD"
  if ! command -v "$PYTHON_CMD" >/dev/null 2>&1; then
    echo "ERROR: Python executable '$PYTHON_CMD' not found in PATH" >&2
    echo "Please install Python 3 and rerun, or pass --python /path/to/python3" >&2
    exit 1
  fi
  "$PYTHON_CMD" -m venv venv
else
  echo "Reusing existing virtualenv at $DEST/venv"
fi

# Activate venv for the remainder of the script
# shellcheck source=/dev/null
source venv/bin/activate

# Upgrade pip and install requirements if present (can be skipped with --skip-pip)
pip install --upgrade pip setuptools wheel
if [ "$SKIP_PIP" = true ]; then
  echo "SKIP_PIP=true — skipping pip install step"
else
  if [ -f requirements.txt ]; then
    echo "Installing Python requirements from requirements.txt"
    pip install -r requirements.txt
  else
    echo "No requirements.txt found; skipping pip install"
  fi
fi

# Note about spaCy models: the script will not automatically download large spaCy models.
# If your workflow requires a model (e.g. 'it_core_news_lg'), install it manually or
# add it to requirements / package steps.

# Optionally install spaCy models (explicit flag required)
if [ "$INSTALL_SPACY_MODELS" = true ]; then
  echo "Installing spaCy models: $SPACY_MODELS"
  # Install each model
  for m in ${SPACY_MODELS//,/ } ; do
    echo " - Downloading: $m"
    python -m spacy download "$m" || echo "Failed to download $m"
  done
fi

if [ "$RUN_GUI" = true ]; then
  echo "Running GUI with: venv/bin/python gui.py"
  # Run the GUI; keep the environment active so GUI dependencies are available
  python gui.py
else
  echo "Setup complete. To run the GUI now, use:"
  echo "  $DEST/venv/bin/python $DEST/gui.py"
  echo "Or call this script with --run-gui to run the GUI after setup."
fi
