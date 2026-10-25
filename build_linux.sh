#!/bin/bash
# Parallax Studio Linux build script
# Produces: dist/parallax-studio/parallax-studio
#
# Usage:
#   chmod +x build_linux.sh   (first time only)
#   ./build_linux.sh

set -euo pipefail
cd "$(dirname "$0")"

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "Error: This script must run on Linux."
    exit 1
fi

echo "=========================================="
echo "  Parallax Studio - Linux Build"
echo "=========================================="
echo ""

if [[ -z "${PYTHON_BIN:-}" ]]; then
    for candidate in python3.12 python3.11 python3.13 python3; do
        if command -v "$candidate" >/dev/null 2>&1; then
            PYTHON_BIN="$candidate"
            break
        fi
    done
fi

if [[ -z "${PYTHON_BIN:-}" ]]; then
    echo "Error: python3 was not found."
    exit 1
fi

PY_TAG="$("$PYTHON_BIN" -c 'import sys; print(f"py{sys.version_info.major}{sys.version_info.minor}")')"
if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(not ((3, 11) <= sys.version_info[:2] < (3, 14)))'; then
    echo "Error: Parallax Studio's pinned dependency set currently supports Python 3.11 through 3.13."
    echo "       Found: $("$PYTHON_BIN" --version)"
    echo "       Install python3.11 or python3.12, or set PYTHON_BIN to one of them."
    exit 1
fi

# A venv of its own, not the one used for development.
#
# PyInstaller bundles whatever it finds installed, so building out of the
# development venv ships every extra that has ever been pip installed into it.
# Installing onnxruntime-gpu there for CUDA during development put 1.7GB of
# CUDA runtime into the bundle -- libcublasLt alone was 715MB -- and took the
# RPM from 140MB to 1.01GB, which is exactly what requirements.txt says must
# never be bundled. This venv is built from requirements.txt and nothing else,
# so the shipped app is reproducible and the development venv is free to carry
# whatever it likes.
VENV_DIR="${VENV_DIR:-.venv-build-$PY_TAG}"

if [[ ! -d "$VENV_DIR" ]]; then
    echo "> Creating virtual environment: $VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
echo "> Python: $(python --version)"

echo "> Installing runtime/build dependencies..."
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt -r requirements-dev.txt --quiet

echo "> PyInstaller: $(python -c 'import PyInstaller; print(PyInstaller.__version__)')"

echo "> Cleaning previous Linux build..."
rm -rf build/linux dist/parallax-studio

echo "> Building Linux app..."
pyinstaller parallax_studio_linux.spec --noconfirm --clean --workpath build/linux --distpath dist

APP="dist/parallax-studio/parallax-studio"
if [[ ! -x "$APP" ]]; then
    echo ""
    echo "x  Build failed - $APP not found or not executable."
    exit 1
fi

DESKTOP_FILE="dist/parallax-studio/com.longweekendlabs.parallaxstudio.desktop"
DESKTOP_ICON="$(pwd)/dist/parallax-studio/_internal/assets/icons/parallax-studio.png"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Parallax Studio
Comment=Turn layered artwork into looping parallax animations
Exec=$(pwd)/$APP
Icon=$DESKTOP_ICON
Terminal=false
Categories=Graphics;Video;AudioVideo;
StartupWMClass=Parallax Studio
EOF

echo ""
echo "=========================================="
echo "  Build complete"
echo "=========================================="
echo ""
echo "  App:   $APP ($(du -sh "dist/parallax-studio" | cut -f1))"
echo "  Menu:  $DESKTOP_FILE"
echo ""
echo "  Test:  ./$APP"
echo ""
