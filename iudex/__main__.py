"""Punto di ingresso: ``python -m iudex`` avvia il server locale.

Con ``--apri`` apre il browser quando il server risponde davvero (non prima), sulla porta
configurata. Se la porta è già occupata da un'altra istanza di Iudex non ne avvia una
seconda: con ``--apri`` apre quella; altrimenti spiega l'errore senza traccia Python.
"""

from __future__ import annotations

import argparse
import json
import logging
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from .config import impostazioni


def _indirizzo() -> str:
    return f"http://{impostazioni.host}:{impostazioni.porta}/"


def _porta_occupata() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((impostazioni.host, impostazioni.porta)) == 0


def _versione_in_ascolto() -> str | None:
    """La versione dell'Iudex già in ascolto sulla porta, o None se lì c'è altro."""
    richiesta = urllib.request.Request(_indirizzo() + "api/stato", headers={"X-Iudex": "1"})
    try:
        with urllib.request.urlopen(richiesta, timeout=2) as r:  # noqa: S310 - solo locale
            return json.load(r).get("versione")
    except (OSError, ValueError):
        return None


def _apri_quando_pronto(limite_s: float = 20.0) -> None:
    fine = time.monotonic() + limite_s
    while time.monotonic() < fine:
        if _porta_occupata():
            webbrowser.open(_indirizzo(), new=2)
            return
        time.sleep(0.25)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="iudex", description="Interfaccia locale per SentenzeWeb")
    parser.add_argument("--apri", action="store_true", help="apre il browser quando è pronto")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    if _porta_occupata():
        versione = _versione_in_ascolto()
        if versione:
            print(f"Iudex {versione} è già in ascolto su {_indirizzo()}")  # noqa: T201
            if args.apri:
                webbrowser.open(_indirizzo(), new=2)
            return 0
        print(  # noqa: T201
            f"La porta {impostazioni.porta} è occupata da un altro programma: "
            "scegline un'altra con la variabile IUDEX_PORTA.",
            file=sys.stderr,
        )
        return 1

    if args.apri:
        threading.Thread(target=_apri_quando_pronto, daemon=True).start()
    uvicorn.run(
        "iudex.app:app",
        host=impostazioni.host,
        port=impostazioni.porta,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
