#!/usr/bin/env bash

set -euo pipefail

DEFAULT_REPO_URL="git+https://github.com/kaemori/motionpaper.git"
REPO_URL="${1:-$DEFAULT_REPO_URL}"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    echo "Usage: install.sh [git+https://github.com/owner/repo.git]"
    echo ""
    echo "Installs MotionPaper via pipx, then installs desktop entries."
    exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "error: python3 is required but not found"
    exit 1
fi

if ! command -v pipx >/dev/null 2>&1; then
    echo "pipx not found; attempting a user install via python3 -m pip..."
    if ! python3 -m pip install --user pipx; then
        echo "error: failed to install pipx with pip"
        echo "install pipx with your distro package manager, then re-run this script"
        exit 1
    fi
    python3 -m pipx ensurepath >/dev/null || true
    export PATH="$HOME/.local/bin:$PATH"
fi

if ! command -v pipx >/dev/null 2>&1; then
    echo "error: pipx still not on PATH; open a new shell and re-run"
    exit 1
fi

echo "Installing MotionPaper from: $REPO_URL"
pipx install --force "$REPO_URL"

echo "Installing desktop entries..."
motionpaper-install

echo "Done. Launch with: motionpaper"
