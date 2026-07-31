#!/bin/bash
# ──────────────────────────────────────────────────────────
#  Palm Farm Management System — Startup Script
# ──────────────────────────────────────────────────────────

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   🌴  Palm Farm Management System        ║"
echo "║   Nkrankwanta · Dormaa West              ║"
echo "╚══════════════════════════════════════════╝"
echo ""

if ! command -v python3 &>/dev/null; then
    echo "❌  Python 3 not found. Please install from https://python.org"
    exit 1
fi

python3 -c "import flask" 2>/dev/null || {
    echo "📦  Installing Flask..."
    pip3 install -r requirements.txt
    echo ""
}

echo "✅  Starting server..."
echo "🌐  Opening at: http://127.0.0.1:5000"
echo "    (Press Ctrl+C to stop)"
echo ""

# Open browser using 127.0.0.1 — avoids Chrome localhost 403 error
sleep 1.5 && open "http://127.0.0.1:5000" &

python3 app.py
