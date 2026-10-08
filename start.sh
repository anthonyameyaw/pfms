#!/bin/bash
set -euo pipefail
APP_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
PYTHON="/Applications/anaconda3/bin/python3.12"
if [[ ! -x "$PYTHON" ]]; then
  echo "PFMS cannot find its configured Python: $PYTHON" >&2
  exit 1
fi
cd -- "$APP_DIR"
exec "$PYTHON" -B "$APP_DIR/launcher.py"
