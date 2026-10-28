"""Iudex come app locale: server in un thread e finestra nativa con icona nell'area di
notifica (``iudex.autonoma``).

Su Windows usa il componente WebView2 già presente in Windows 11; su Linux WebKitGTK, su
macOS WebKit. Richiede l'extra ``[desktop]`` (``pip install -e .[desktop]``).
Avvio: ``python -m iudex.desktop`` oppure ``scripts\\avvia-finestra.cmd``; nell'installer è
l'eseguibile ``Iudex``. Se Iudex è già acceso (``/health`` risponde ``"iudex"``) la
finestra apre quello invece di avviarne un secondo.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from . import __version__, accesso, config
from .autonoma.cartelle import applica_avvio, prepara
from .autonoma.server import ServerInThread, log_su_file, scegli_porta

try:
    import webview  # noqa: F401 - controlla che l'extra sia installato
except ImportError as exc:  # pragma: no cover - dipende dall'extra installato
    raise SystemExit("Installa l'extra desktop: pip install -e .[desktop]") from exc


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="iudex-finestra", description=f"Iudex {__version__}")
    parser.add_argument("--data-dir", help="cartella dei dati (altrimenti IUDEX_DATI)")
    parser.add_argument("--port", type=int, help="porta (altrimenti IUDEX_PORTA)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    config.impostazioni = impostazioni = applica_avvio(
        "IUDEX", config.impostazioni, args.data_dir, args.port
    )
    prepara(impostazioni.cartella_dati)
    log_su_file(impostazioni.cartella_dati, "iudex")

    from .autonoma.finestra import Guscio

    porta, gia_attivo = scegli_porta(impostazioni.host, impostazioni.porta, "iudex")
    server = None
    if gia_attivo:
        base = f"http://{impostazioni.host}:{porta}/"
    else:
        config.impostazioni = impostazioni = applica_avvio("IUDEX", impostazioni, None, porta)
        from .app import app

        server = ServerInThread(app, impostazioni.host, porta)
        if not server.avvia():
            raise SystemExit("il server non è partito: vedi log/iudex.log nella cartella dei dati")
        base = server.url
    # La finestra entra con il token della cartella dei dati (lo stesso che legge il server).
    url = f"{base.rstrip('/')}/accesso?codice={accesso.leggi_o_crea(impostazioni.cartella_dati)}"
    icona = Path(__file__).resolve().parent / "static" / "favicon.png"
    Guscio(
        url,
        f"Iudex {__version__}",
        icona=icona,
        all_uscita=server.ferma if server else None,
    ).avvia()


if __name__ == "__main__":
    main()
