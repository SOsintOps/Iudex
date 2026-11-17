#!/bin/sh
# Pacchetto .deb di Iudex da build/dist/Iudex (PyInstaller su Linux). Uso:
#   sh packaging/costruisci_deb.sh VERSIONE
# Richiede build/dist/dipendenze.txt, scritto da packaging/controlla_pacchetto.py.
# Il file ha un nome senza versione (iudex_amd64.deb), così il comando della guida si copia
# senza modifiche: sudo apt install ./iudex_amd64.deb
set -eu
VERSIONE="$1"
RADICE=build/deb/iudex
rm -rf build/deb
mkdir -p "$RADICE/DEBIAN" "$RADICE/usr/lib/iudex" "$RADICE/usr/bin" \
  "$RADICE/usr/share/applications" "$RADICE/usr/share/icons/hicolor/256x256/apps"
cp -r build/dist/Iudex/. "$RADICE/usr/lib/iudex/"
echo deb > "$RADICE/usr/lib/iudex/confezione"
printf '#!/bin/sh\nexec /usr/lib/iudex/iudex "$@"\n' > "$RADICE/usr/bin/iudex"
chmod 755 "$RADICE/usr/bin/iudex"
cp packaging/appimage/iudex.desktop "$RADICE/usr/share/applications/iudex.desktop"
cp src/iudex/static/favicon.png "$RADICE/usr/share/icons/hicolor/256x256/apps/iudex.png"
DIPENDENZE="$(cat build/dist/dipendenze.txt)"
sed -e "s/@VERSIONE@/$VERSIONE/" -e "s/@DIPENDENZE@/$DIPENDENZE/" packaging/deb/control.in \
  > "$RADICE/DEBIAN/control"
mkdir -p build/installer
dpkg-deb --root-owner-group --build "$RADICE" build/installer/iudex_amd64.deb
dpkg-deb --info build/installer/iudex_amd64.deb
