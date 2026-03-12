#!/bin/sh
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WRAPPER="$SCRIPT_DIR/directsendit"
TARGET="/usr/local/bin/directsendit"

if [ ! -f "$WRAPPER" ]; then
    echo "ERROR: '$WRAPPER' not found. Run install.sh from the repo directory."
    exit 1
fi

chmod +x "$WRAPPER"
chmod +x "$SCRIPT_DIR/directsendit.py"

if cp "$WRAPPER" "$TARGET" 2>/dev/null; then
    echo "Installed to $TARGET"
else
    echo "Permission denied. Try: sudo ./install.sh"
    exit 1
fi
