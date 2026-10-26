"""Punto di ingresso: ``python -m iudex`` avvia il server locale.

Con ``--apri`` apre il browser quando il server risponde davvero (non prima), sulla porta
configurata. Se la porta è già occupata da un'altra istanza di Iudex non ne avvia una
seconda: con ``--apri`` apre quella; altrimenti spiega l'errore senza traccia Python.

Come backend di un'app (modello Voicebox): ``--data-dir`` sceglie la cartella dei dati,
``--port`` la porta, ``--parent-pid`` il processo da sorvegliare (quando termina, il server
si chiude).
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

from . import config
from .autonoma.cartelle import applica_avvio, prepara
from .autonoma.server import ServerInThread, log_su_file, sorveglia_genitore
from .config import impostazioni


def _ricarica_impostazioni(cartella: str | None, porta: int | None) -> None:
    """``--data-dir`` e ``--port`` valgono come IUDEX_DATI e IUDEX_PORTA: le impostazioni si
    ricreano prima di importare l'app, che le legge all'import."""
    global impostazioni
    config.impostazioni = impostazioni = applica_avvio(
        "IUDEX", config.impostazioni, cartella, porta
    )


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
    parser.add_argument("--data-dir", help="cartella dei dati (altrimenti IUDEX_DATI)")
    parser.add_argument("--port", type=int, help="porta (altrimenti IUDEX_PORTA)")
    parser.add_argument("--parent-pid", type=int, help="chiude il server quando termina")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if args.data_dir or args.port:
        _ricarica_impostazioni(args.data_dir, args.port)
    prepara(impostazioni.cartella_dati)
    log_su_file(impostazioni.cartella_dati, "iudex")

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
    if args.parent_pid:
        from .app import app

        server = ServerInThread(app, impostazioni.host, impostazioni.porta)
        sorveglia_genitore(args.parent_pid, server.ferma)
        server.thread.start()
        server.thread.join()
        return 0
    uvicorn.run(
        "iudex.app:app",
        host=impostazioni.host,
        port=impostazioni.porta,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
