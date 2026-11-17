"""Scrive latest.json per il controllo degli aggiornamenti (iudex.autonoma.aggiornamenti).

Uso: python packaging/latest_json.py VERSIONE CARTELLA_DEGLI_INSTALLER URL_BASE > latest.json
URL_BASE è l'indirizzo dei file della release (…/releases/download/vX.Y.Z).

Chiavi: ``windows`` (installer), ``linux`` (AppImage: le versioni già installate leggono questa),
``linux-deb`` (pacchetto .deb).
"""

import hashlib
import json
import sys
import time
from pathlib import Path

PIATTAFORME = (("windows", "*-setup.exe"), ("linux", "*.AppImage"), ("linux-deb", "*.deb"))


def manifesto(versione: str, cartella: Path, base: str, data: str | None = None) -> dict:
    """Il contenuto di latest.json per i file in ``cartella``."""
    base = base.rstrip("/")
    dati = {"versione": versione, "data": data or time.strftime("%Y-%m-%d"), "note": ""}
    for piattaforma, motivo in PIATTAFORME:
        for f in sorted(Path(cartella).glob(motivo)):
            dati[piattaforma] = {
                "url": f"{base}/{f.name}",
                "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                "byte": f.stat().st_size,
            }
    return dati


if __name__ == "__main__":
    print(json.dumps(manifesto(sys.argv[1], Path(sys.argv[2]), sys.argv[3]), indent=1))
