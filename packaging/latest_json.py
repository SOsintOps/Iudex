"""Scrive latest.json per il controllo degli aggiornamenti (iudex.autonoma.aggiornamenti).

Uso: python packaging/latest_json.py VERSIONE CARTELLA_DEGLI_INSTALLER URL_BASE > latest.json
URL_BASE è l'indirizzo dei file della release (…/releases/download/vX.Y.Z).
"""

import hashlib
import json
import sys
import time
from pathlib import Path

versione, cartella, base = sys.argv[1], Path(sys.argv[2]), sys.argv[3].rstrip("/")
dati = {"versione": versione, "data": time.strftime("%Y-%m-%d"), "note": ""}
for piattaforma, motivo in (("windows", "*-setup.exe"), ("linux", "*.AppImage")):
    for f in sorted(cartella.glob(motivo)):
        dati[piattaforma] = {
            "url": f"{base}/{f.name}",
            "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
            "byte": f.stat().st_size,
        }
print(json.dumps(dati, indent=1))
