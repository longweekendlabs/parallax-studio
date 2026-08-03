#!/usr/bin/env bash
# Package an already-built dist/parallax-studio into tar.gz, deb and rpm.
# Expects VERSION in the environment. Used by .github/workflows/release.yml.
set -euo pipefail

VERSION="${VERSION:?VERSION must be set}"
NAME="parallax-studio"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP="$ROOT/dist/$NAME"
OUT="$ROOT/release"
[ -d "$APP" ] || { echo "missing $APP; build first" >&2; exit 1; }
mkdir -p "$OUT"

# Portable tarball
tar -czf "$OUT/${NAME}-v${VERSION}-linux-x86_64.tar.gz" -C "$ROOT/dist" "$NAME"

# The desktop entry and icon are shared by both packages.
write_tree() {
  local root="$1"
  install -d "$root/opt/$NAME" "$root/usr/bin" \
             "$root/usr/share/applications" \
             "$root/usr/share/icons/hicolor/512x512/apps"
  cp -a "$APP/." "$root/opt/$NAME/"
  ln -sf "/opt/$NAME/$NAME" "$root/usr/bin/$NAME"
  install -m 644 "$ROOT/assets/icons/parallax-studio.png" \
    "$root/usr/share/icons/hicolor/512x512/apps/$NAME.png"
  cat > "$root/usr/share/applications/com.longweekendlabs.parallaxstudio.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Parallax Studio
Comment=Turn a still image into a looping 2.5D parallax animation
Exec=/opt/$NAME/$NAME
Icon=$NAME
Terminal=false
Categories=Graphics;Video;
DESKTOP
}

# deb
DEB="$ROOT/build/deb"
rm -rf "$DEB"; mkdir -p "$DEB/DEBIAN"
write_tree "$DEB"
cat > "$DEB/DEBIAN/control" <<CONTROL
Package: $NAME
Version: $VERSION
Section: graphics
Priority: optional
Architecture: amd64
Maintainer: Long Weekend Labs <2272935+longweekendlabs@users.noreply.github.com>
Depends: libegl1, libgl1, libxkbcommon-x11-0
Description: Parallax Studio
 Turn a still image into a looping 2.5D parallax animation, with depth and
 pose models that run entirely on the local machine.
CONTROL
dpkg-deb --build --root-owner-group "$DEB" \
  "$OUT/${NAME}_${VERSION}_amd64.deb" >/dev/null

# rpm: produced by build_rpm.sh, which is the same script used for local
# builds, so CI and a developer machine cannot drift apart.
SKIP_APP_BUILD=1 bash "$ROOT/build_rpm.sh" >/dev/null
# Only this version: dist/rpm accumulates every local build over time, and
# sweeping the whole directory would attach all of them to the release.
find "$ROOT/dist/rpm" -name "${NAME}-${VERSION}-*.rpm" -exec cp {} "$OUT/" \;

echo "Packaged into $OUT:"
ls -lh "$OUT"
