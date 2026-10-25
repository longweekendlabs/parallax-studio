#!/bin/bash
# Parallax Studio RPM packaging script
# Produces: dist/rpm/parallax-studio-<version>-1.<arch>.rpm
#
# Usage:
#   chmod +x build_rpm.sh   (first time only)
#   ./build_rpm.sh

set -euo pipefail
cd "$(dirname "$0")"

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "Error: This script must run on Linux."
    exit 1
fi

if [[ ! -x "dist/parallax-studio/parallax-studio" || "${SKIP_APP_BUILD:-0}" != "1" ]]; then
    ./build_linux.sh
fi

VENV_PY="$(find . -maxdepth 2 -path './.venv-linux-*/bin/python' | sort | head -n 1)"
PYTHON_BIN="${VENV_PY:-python3}"
VERSION="$("$PYTHON_BIN" -c 'from app.version import __version__; print(__version__)')"
RELEASE="${RELEASE:-1}"
ARCH="$(uname -m)"

RPM_ROOT="$(pwd)/build/rpm"
SOURCE_NAME="parallax-studio-$VERSION"
SOURCE_DIR="$RPM_ROOT/source/$SOURCE_NAME"
TARBALL="$RPM_ROOT/SOURCES/$SOURCE_NAME.tar.gz"
SPEC_FILE="$RPM_ROOT/SPECS/parallax-studio.spec"
RPM_OUT="$(pwd)/dist/rpm"

echo "=========================================="
echo "  Parallax Studio - RPM Build"
echo "=========================================="
echo ""

rm -rf "$RPM_ROOT"
mkdir -p "$RPM_ROOT"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS,tmp,source} "$RPM_OUT"
mkdir -p "$SOURCE_DIR"

cp -a dist/parallax-studio "$SOURCE_DIR/parallax-studio"

cat > "$SOURCE_DIR/com.longweekendlabs.parallaxstudio.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Parallax Studio
Comment=Turn layered artwork into looping parallax animations
Exec=parallax-studio
Icon=parallax-studio
Terminal=false
Categories=Graphics;Video;AudioVideo;
StartupWMClass=Parallax Studio
EOF

tar -C "$RPM_ROOT/source" -czf "$TARBALL" "$SOURCE_NAME"

cat > "$SPEC_FILE" <<EOF
%global debug_package %{nil}
%global _build_id_links none
%global __debug_install_post %{nil}
# Ship the prebuilt files exactly as PyInstaller made them. The default
# post-install step strips every shared library, and Ubuntu 22.04's strip
# (binutils 2.38) left two empty LOAD segments in numpy's OpenBLAS at file
# offsets that are not page-aligned. Newer glibc refuses to load that, so the
# v0.10.0 RPM built in CI could not import numpy and did not start, while
# Fedora's newer strip happened to produce a working file locally.
%global __os_install_post %{nil}
%global __strip /bin/true

Name:           parallax-studio
Version:        $VERSION
Release:        $RELEASE%{?dist}
Summary:        Turn layered artwork into looping parallax animations
License:        MIT
URL:            https://github.com/longweekendlabs/parallax-studio
Source0:        %{name}-%{version}.tar.gz

AutoReqProv:    no

%description
Parallax Studio is a local desktop app for importing layered artwork,
painting depth maps, previewing parallax motion, and exporting animations.

%prep
%autosetup

%build

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/opt/parallax-studio
cp -a parallax-studio/. %{buildroot}/opt/parallax-studio/

mkdir -p %{buildroot}/usr/bin
ln -s /opt/parallax-studio/parallax-studio %{buildroot}/usr/bin/parallax-studio

mkdir -p %{buildroot}/usr/share/applications
install -m 0644 com.longweekendlabs.parallaxstudio.desktop %{buildroot}/usr/share/applications/

mkdir -p %{buildroot}/usr/share/icons/hicolor/256x256/apps
install -m 0644 parallax-studio/_internal/assets/icons/parallax-studio.png %{buildroot}/usr/share/icons/hicolor/256x256/apps/parallax-studio.png

%post
# Desktop environments cache icons aggressively; without this an upgrade that
# changes the icon keeps showing the old one until the cache is rebuilt.
touch --no-create /usr/share/icons/hicolor &>/dev/null || :
gtk-update-icon-cache -q /usr/share/icons/hicolor &>/dev/null || :
update-desktop-database -q /usr/share/applications &>/dev/null || :

%postun
touch --no-create /usr/share/icons/hicolor &>/dev/null || :
gtk-update-icon-cache -q /usr/share/icons/hicolor &>/dev/null || :
update-desktop-database -q /usr/share/applications &>/dev/null || :

%files
/opt/parallax-studio
/usr/bin/parallax-studio
/usr/share/applications/com.longweekendlabs.parallaxstudio.desktop
/usr/share/icons/hicolor/256x256/apps/parallax-studio.png
EOF

rpmbuild \
    --define "_topdir $RPM_ROOT" \
    --define "_tmppath $RPM_ROOT/tmp" \
    -bb "$SPEC_FILE"

find "$RPM_ROOT/RPMS" -name "*.rpm" -exec cp -f {} "$RPM_OUT/" \;

echo ""
echo "=========================================="
echo "  RPM build complete"
echo "=========================================="
echo ""
find "$RPM_OUT" -name "*.rpm" -maxdepth 1 -printf "  RPM:  %p\n"
echo ""
