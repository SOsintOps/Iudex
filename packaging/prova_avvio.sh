#!/bin/sh
# Prova di avvio dei pacchetti Linux in un contenitore Debian o Ubuntu (job prova-linux del
# workflow Rilascio). Uso, da root nel contenitore:
#   sh packaging/prova_avvio.sh CARTELLA_CON_DEB_E_APPIMAGE
# Installa il .deb (apt porta le dipendenze), avvia Iudex sotto uno schermo virtuale (Xvfb) e
# aspetta nel registro la riga «finestra aperta»; controlla /health e una ricerca locale
# (indice FTS5 dello SQLite di sistema). Poi lo stesso con l'AppImage, estratta al volo
# (nei contenitori FUSE non c'è).
set -eu
ART="$(cd "$1" && pwd)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q "$ART/iudex_amd64.deb" xvfb xauth curl procps

prova() {
  nome="$1"
  shift
  HOME="$(mktemp -d)"
  export HOME
  dati="$HOME/.local/share/iudex"
  xvfb-run -a "$@" > "$HOME/uscita.txt" 2>&1 &
  pid=$!
  esito=1
  for _ in $(seq 1 120); do
    if grep -q "finestra aperta" "$dati/log/iudex.log" 2>/dev/null; then
      esito=0
      break
    fi
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
  done
  if [ "$esito" -eq 0 ]; then
    porta="$(sed -n 's/.*in ascolto su http:\/\/127.0.0.1:\([0-9]*\).*/\1/p' "$dati/log/iudex.log" | tail -1)"
    curl -fsS "http://127.0.0.1:$porta/health" > /dev/null || esito=1
    curl -fsS -H "X-Iudex: 1" -H "X-Iudex-Token: $(cat "$dati/token")" \
      "http://127.0.0.1:$porta/api/locale/cerca?testo=prova" > /dev/null || esito=1
  fi
  pkill -f "lib/iudex/iudex" 2>/dev/null || true
  pkill -f "squashfs-root" 2>/dev/null || true
  kill "$pid" 2>/dev/null || true
  if [ "$esito" -eq 0 ]; then
    echo "OK   $nome: finestra aperta, /health e ricerca locale rispondono"
  else
    echo "ERRORE $nome: la finestra non si è aperta"
    echo "--- uscita"; cat "$HOME/uscita.txt" || true
    echo "--- registro"; cat "$dati/log/iudex.log" 2>/dev/null || true
  fi
  return "$esito"
}

errori=0
prova ".deb" iudex || errori=$((errori + 1))
appimage="$(ls "$ART"/*.AppImage | head -1)"
chmod +x "$appimage"
cd "$(mktemp -d)"
prova "AppImage" "$appimage" --appimage-extract-and-run || errori=$((errori + 1))
exit "$errori"
