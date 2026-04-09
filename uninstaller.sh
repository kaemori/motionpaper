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
ICON_FILE="$HOME/.local/share/icons/hicolor/256x256/apps/motionpaper.png"
PID_FILE="/tmp/motionpaper-daemon.pid"
LOG_FILE="/tmp/motionpaper-daemon.log"

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

if [[ -f "$PID_FILE" ]]; then
	pid="$(cat "$PID_FILE" 2>/dev/null || true)"
	if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
		echo "Stopping daemon pid $pid"
		kill "$pid" >/dev/null 2>&1 || true
	fi
	rm -f "$PID_FILE"
fi

rm -f "$LOG_FILE"

for desktop_file in "${DESKTOP_FILES[@]}"; do
	rm -f "$APPLICATIONS_DIR/$desktop_file"
	rm -f "$AUTOSTART_DIR/$desktop_file"
done

if command -v update-desktop-database >/dev/null 2>&1; then
	update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi

rm -f "$ICON_FILE"

if [[ "$PURGE_CONFIG" -eq 1 ]]; then
	echo "Removing config directory: $HOME/.config/motionpaper"
	rm -rf "$HOME/.config/motionpaper"
else
	echo "Keeping config directory: $HOME/.config/motionpaper"
fi

echo "MotionPaper uninstall complete."
