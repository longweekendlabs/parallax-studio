#!/bin/bash
# Parallax Studio — macOS Apple Silicon build script
# Produces: dist/Parallax Studio.app  and  dist/Parallax Studio.dmg
#
# Usage:
#   chmod +x build_macos.sh   (first time only)
#   ./build_macos.sh

set -e
cd "$(dirname "$0")"

# ── Guard: Apple Silicon only ──────────────────────────────────────────────
if [[ "$(uname -m)" != "arm64" ]]; then
    echo "Error: This script must run on Apple Silicon (M1/M2/M3/M4)."
    echo "       The resulting .app only works on Apple Silicon anyway."
    exit 1
fi

echo "╔══════════════════════════════════════════╗"
echo "║  Parallax Studio — macOS Build           ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Activate virtual environment ───────────────────────────────────────────
if [[ ! -d ".venv" ]]; then
    echo "Error: .venv not found."
    echo "       Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi
source .venv/bin/activate
echo "▶  Python: $(python --version)"

# ── Ensure PyInstaller is available ────────────────────────────────────────
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "▶  Installing PyInstaller..."
    pip install "pyinstaller>=6.0" --quiet
fi
echo "▶  PyInstaller: $(python -c 'import PyInstaller; print(PyInstaller.__version__)')"

# ── Clean previous build ───────────────────────────────────────────────────
echo "▶  Cleaning previous build..."
rm -rf dist build

# ── Run PyInstaller ────────────────────────────────────────────────────────
echo "▶  Building .app (this takes 2–5 minutes)..."
pyinstaller parallax_studio.spec --noconfirm

APP="dist/Parallax Studio.app"
if [[ ! -d "$APP" ]]; then
    echo ""
    echo "✗  Build failed — $APP not found."
    exit 1
fi

# ── Ad-hoc code sign ───────────────────────────────────────────────────────
# Prevents macOS Sonoma from showing "damaged app" instead of the normal
# "unidentified developer" prompt.  Free, no Apple Developer account needed.
echo "▶  Ad-hoc signing..."
codesign --force --deep --sign - "$APP" 2>/dev/null && echo "   Signed OK" || echo "   (codesign skipped — not critical)"

# ── Create DMG ─────────────────────────────────────────────────────────────
DMG="dist/Parallax Studio.dmg"
echo "▶  Creating DMG..."
rm -f "$DMG"
hdiutil create \
    -volname "Parallax Studio" \
    -srcfolder "$APP" \
    -ov \
    -format UDZO \
    "$DMG" \
    2>&1 | grep -v "^hdiutil:" || true   # suppress verbose hdiutil noise

if [[ ! -f "$DMG" ]]; then
    echo "   Warning: DMG creation failed — .app is still usable directly."
else
    echo "   DMG: $DMG ($(du -sh "$DMG" | cut -f1))"
fi

# ── Done ───────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Build complete                          ║"
echo "╚══════════════════════════════════════════╝"
echo ""
APP_SIZE=$(du -sh "$APP" | cut -f1)
echo "  .app  →  $APP  ($APP_SIZE)"
[[ -f "$DMG" ]] && echo "  .dmg  →  $DMG"
echo ""
echo "  Test:   open \"$APP\""
echo ""
echo "  To share the DMG:"
echo "    Recipient right-clicks the app → Open → Open"
echo "    (one time only, because the app is not notarized)"
echo ""
