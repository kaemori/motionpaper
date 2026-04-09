#!/usr/bin/env bash

set -euo pipefail

PURGE_CONFIG=0

if [[ "${1:-}" == "--purge-config" ]]; then
	PURGE_CONFIG=1
elif [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
	echo "Usage: uninstaller.sh [--purge-config]"
	echo ""
	echo "Uninstalls MotionPaper from pipx and removes desktop integration files."
	echo "--purge-config also removes ~/.config/motionpaper."
	exit 0
fi

APPLICATIONS_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILES=(
	"motionpaper.desktop"
	"motionpaper-daemon.desktop"
	"motionpaperdaemon.desktop"
)

if command -v motionpaper-uninstall >/dev/null 2>&1; then
	echo "Running motionpaper-uninstall cleanup"
	if [[ "$PURGE_CONFIG" -eq 1 ]]; then
		motionpaper-uninstall --purge-config
	else
		motionpaper-uninstall
	fi
else
	echo "motionpaper-uninstall command not found; using shell fallback cleanup"
	for desktop_file in "${DESKTOP_FILES[@]}"; do
		rm -f "$APPLICATIONS_DIR/$desktop_file"
		rm -f "$AUTOSTART_DIR/$desktop_file"
	done
	if command -v update-desktop-database >/dev/null 2>&1; then
		update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
	fi
	if [[ "$PURGE_CONFIG" -eq 1 ]]; then
		rm -rf "$HOME/.config/motionpaper"
	fi
fi

if command -v pipx >/dev/null 2>&1; then
	if pipx list --short 2>/dev/null | grep -qx "motionpaper"; then
		echo "Uninstalling pipx package: motionpaper"
		pipx uninstall motionpaper || true
	else
		echo "pipx package 'motionpaper' is not installed"
	fi
else
	echo "pipx not found; skipping pipx uninstall"
fi

echo "MotionPaper uninstall workflow complete."
