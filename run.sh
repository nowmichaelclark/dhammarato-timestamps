#!/usr/bin/env bash
# run.sh — One-click launcher for the timestamp finder.
# Usage: ./run.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── 1. Check for Python ────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 not found. Please install Python 3.9+."
    exit 1
fi

# ── 2. Create / activate a local venv ─────────────────────────────────────
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment …"
    python3 -m venv .venv
fi

source .venv/bin/activate

# ── 3. Install / upgrade dependencies ─────────────────────────────────────
echo "Checking dependencies …"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# ── 4. Run ─────────────────────────────────────────────────────────────────
python main.py
