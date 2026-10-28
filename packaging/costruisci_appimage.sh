#!/bin/sh
# AppImage di Iudex da build/dist/Iudex (PyInstaller su Linux). Uso:
#   sh packaging/costruisci_appimage.sh VERSIONE
# Richiede appimagetool 1.9.1 (scaricato e verificato con lo sha256 qui sotto).
set -eu
VERSIONE="$1"
URL=https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage
SHA=ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0
mkdir -p build/appimage
[ -f build/appimage/appimagetool ] || curl -sSL -o build/appimage/appimagetool "$URL"
echo "$SHA  build/appimage/appimagetool" | sha256sum -c -
chmod +x build/appimage/appimagetool
APPDIR=build/appimage/Iudex.AppDir
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib/iudex"
cp -r build/dist/Iudex/. "$APPDIR/usr/lib/iudex/"
cp packaging/appimage/AppRun "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"
cp packaging/appimage/iudex.desktop "$APPDIR/iudex.desktop"
cp src/iudex/static/favicon.png "$APPDIR/iudex.png"
mkdir -p build/installer
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 build/appimage/appimagetool "$APPDIR" "build/installer/Iudex-$VERSIONE-x86_64.AppImage"
