#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SOURCE_DESKTOP="$PROJECT_DIR/desktop/motionpaper.desktop"
SOURCE_DAEMON_DESKTOP="$PROJECT_DIR/desktop/motionpaper-daemon.desktop"
DEST_DIR="$HOME/.local/share/applications"
DEST_DESKTOP="$DEST_DIR/motionpaper.desktop"
DEST_DAEMON_DESKTOP="$DEST_DIR/motionpaper-daemon.desktop"

if [[ ! -f "$SOURCE_DESKTOP" ]]; then
    echo "error: template not found at $SOURCE_DESKTOP"
    exit 1
fi

if [[ ! -f "$SOURCE_DAEMON_DESKTOP" ]]; then
    echo "error: template not found at $SOURCE_DAEMON_DESKTOP"
    exit 1
fi

mkdir -p "$DEST_DIR"

EXEC_PATH="$PROJECT_DIR/launch.sh"
DAEMON_EXEC_PATH="$PROJECT_DIR/daemon.sh"
ICON_PATH="$PROJECT_DIR/assets/icon.png"

printf -v ESCAPED_EXEC_PATH "%q" "$EXEC_PATH"
printf -v ESCAPED_DAEMON_EXEC_PATH "%q" "$DAEMON_EXEC_PATH"
SED_ESCAPED_EXEC_PATH="${ESCAPED_EXEC_PATH//\\/\\\\}"
SED_ESCAPED_DAEMON_EXEC_PATH="${ESCAPED_DAEMON_EXEC_PATH//\\/\\\\}"

sed -e "s|__MOTIONPAPER_EXEC__|$SED_ESCAPED_EXEC_PATH|g" \
    -e "s|__MOTIONPAPER_ICON__|$ICON_PATH|g" \
    "$SOURCE_DESKTOP" > "$DEST_DESKTOP"

sed -e "s|__MOTIONPAPER_DAEMON_EXEC__|$SED_ESCAPED_DAEMON_EXEC_PATH|g" \
    -e "s|__MOTIONPAPER_ICON__|$ICON_PATH|g" \
    "$SOURCE_DAEMON_DESKTOP" > "$DEST_DAEMON_DESKTOP"

chmod +x "$PROJECT_DIR/launch.sh" "$PROJECT_DIR/daemon.sh"
chmod +x "$SCRIPT_DIR/launch_gui.sh" "$SCRIPT_DIR/launch_daemon.sh"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DEST_DIR" >/dev/null 2>&1 || true
fi

echo "installed desktop entry: $DEST_DESKTOP"
echo "installed desktop entry: $DEST_DAEMON_DESKTOP"
