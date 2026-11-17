"""Ambiente del processo per il pacchetto Linux (PyInstaller) e tipo di confezione.

All'avvio dell'eseguibile PyInstaller punta alcune variabili di GTK e GIO alla cartella del
pacchetto e la mette in testa a ``LD_LIBRARY_PATH``. Nel pacchetto Linux di Iudex però GTK, GIO,
i loro moduli e i loro dati vengono dal sistema (``packaging/librerie_linux.py``): quelle
variabili punterebbero a cartelle vuote. ``ripristina_ambiente()`` le toglie prima che GTK
parta. ``GI_TYPELIB_PATH`` resta, perché i typelib sono nel pacchetto.

``LD_LIBRARY_PATH`` torna al valore di prima dell'avvio: il processo di Iudex continua a trovare
le sue librerie (il caricatore legge la variabile solo all'avvio), mentre i programmi avviati
da Iudex (lettore PDF, browser, processi di WebKitGTK) usano solo quelle del sistema.
"""

from __future__ import annotations

import os
import sys
from collections.abc import MutableMapping
from pathlib import Path

from .cartelle import congelata

# Variabili impostate dagli hook di PyInstaller (gio, gtk, gdkpixbuf, pango) sulla cartella del
# pacchetto.
VARIABILI_GTK = (
    "GIO_MODULE_DIR",
    "GDK_PIXBUF_MODULE_FILE",
    "GTK_DATA_PREFIX",
    "GTK_EXE_PREFIX",
    "GTK_PATH",
    "PANGO_LIBDIR",
    "PANGO_SYSCONFDIR",
)


def ripristina_ambiente(
    ambiente: MutableMapping[str, str] | None = None,
    *,
    eseguibile: bool | None = None,
    piattaforma: str | None = None,
    cartella_pacchetto: str | None = None,
) -> None:
    """Toglie le variabili di GTK del pacchetto (solo eseguibile su Linux; altrove non fa nulla)."""
    ambiente = os.environ if ambiente is None else ambiente
    eseguibile = congelata() if eseguibile is None else eseguibile
    piattaforma = piattaforma or sys.platform
    if not eseguibile or not piattaforma.startswith("linux"):
        return
    pacchetto = cartella_pacchetto or getattr(sys, "_MEIPASS", "")
    for nome in VARIABILI_GTK:
        ambiente.pop(nome, None)
    if "XDG_DATA_DIRS" in ambiente and pacchetto:
        voci = [
            v for v in ambiente["XDG_DATA_DIRS"].split(":") if v and not v.startswith(pacchetto)
        ]
        if voci:
            ambiente["XDG_DATA_DIRS"] = ":".join(voci)
        else:
            ambiente.pop("XDG_DATA_DIRS")
    if "LD_LIBRARY_PATH_ORIG" in ambiente:
        ambiente["LD_LIBRARY_PATH"] = ambiente["LD_LIBRARY_PATH_ORIG"]
    else:
        ambiente.pop("LD_LIBRARY_PATH", None)


def confezione(cartella: Path | None = None) -> str | None:
    """Come è installato Iudex su Linux: ``"deb"``, ``"appimage"`` o ``None`` (sorgenti, altro).

    Lo dice il file ``confezione`` accanto all'eseguibile, scritto da ``costruisci_deb.sh`` e
    ``costruisci_appimage.sh``.
    """
    if cartella is None:
        if not congelata():
            return None
        cartella = Path(sys.executable).resolve().parent
    try:
        valore = (cartella / "confezione").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return valore if valore in ("deb", "appimage") else None
