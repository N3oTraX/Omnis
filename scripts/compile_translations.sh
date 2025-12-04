#!/bin/bash
# Compile Qt translation files (.ts) to binary format (.qm)

set -e

TRANSLATIONS_DIR="src/omnis/gui/translations"
LRELEASE="pyside6-lrelease"

# Check if pyside6-lrelease is available, fallback to lrelease
if ! command -v "$LRELEASE" &> /dev/null; then
    LRELEASE="lrelease"
    if ! command -v "$LRELEASE" &> /dev/null; then
        echo "Error: Neither pyside6-lrelease nor lrelease found."
        echo "Install PySide6 (pip install PySide6) or Qt6 linguist tools."
        exit 1
    fi
fi

# Find all .ts files and compile them
for ts_file in "$TRANSLATIONS_DIR"/*.ts; do
    if [ -f "$ts_file" ]; then
        qm_file="${ts_file%.ts}.qm"
        echo "Compiling: $ts_file -> $qm_file"
        "$LRELEASE" "$ts_file" -qm "$qm_file"
    fi
done

echo "✓ All translations compiled successfully"
