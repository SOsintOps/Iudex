"""Iudex come app locale: server in un thread e finestra nativa (pywebview).

Su Windows usa il componente WebView2 già presente in Windows 11; su Linux WebKitGTK, su
macOS WebKit. Richiede l'extra ``[desktop]`` (``pip install -e .[desktop]``).
Avvio: ``python -m iudex.desktop`` oppure ``avvia-finestra.cmd``.
"""

from __future__ import annotations

import logging
import threading
import time
import urllib.request

import uvicorn

from . import __version__
from .config import impostazioni

try:
    import webview
except ImportError as exc:  # pragma: no cover - dipende dall'extra installato
    raise SystemExit("Installa l'extra desktop: pip install -e .[desktop]") from exc


def _attendi_server(url: str, secondi: float = 15.0) -> bool:
    scadenza = time.monotonic() + secondi
    while time.monotonic() < scadenza:
        try:
            with urllib.request.urlopen(url, timeout=1):  # noqa: S310 - indirizzo locale
                return True
        except OSError:
            time.sleep(0.2)
    return False


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    configurazione = uvicorn.Config(
        "iudex.app:app", host=impostazioni.host, port=impostazioni.porta, log_level="info"
    )
    server = uvicorn.Server(configurazione)
    thread = threading.Thread(target=server.run, name="iudex-server", daemon=True)
    thread.start()
    url = f"http://{impostazioni.host}:{impostazioni.porta}/"
    if not _attendi_server(url):
        raise SystemExit("il server non è partito: la porta è occupata?")
    webview.create_window(
        f"Iudex {__version__}", url, width=1480, height=940, min_size=(900, 600), text_select=True
    )
    webview.start()
    # La finestra è stata chiusa: si ferma il server.
    server.should_exit = True
    thread.join(timeout=10)


if __name__ == "__main__":
    main()
