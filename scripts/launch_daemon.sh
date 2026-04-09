#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"
if [[ -x "$PROJECT_DIR/.venv/bin/python3" ]]; then
	exec "$PROJECT_DIR/.venv/bin/python3" main.py
fi

if command -v python3 >/dev/null 2>&1; then
	exec python3 main.py
fi

echo "error: python3 not found and no project virtualenv available at $PROJECT_DIR/.venv/bin/python3"
exit 1
