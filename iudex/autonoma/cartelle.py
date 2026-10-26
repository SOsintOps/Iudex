"""Dove stanno i dati di un'app installata.

Dai sorgenti i dati restano in ``dati/`` accanto al pacchetto (com'è sempre stato); da un
eseguibile (PyInstaller) vanno nella cartella dell'utente del sistema operativo:
``%APPDATA%\\Iudex`` su Windows, ``~/Library/Application Support/Iudex`` su macOS,
``$XDG_DATA_HOME/iudex`` (``~/.local/share/iudex``) su Linux.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

SOTTOCARTELLE = ("backup", "log")


def congelata() -> bool:
    """Vero quando il programma gira da un eseguibile costruito con PyInstaller."""
    return bool(getattr(sys, "frozen", False))


def cartella_utente(app: str, piattaforma: str | None = None) -> Path:
    """La cartella dei dati dell'app ``app`` (``"iudex"``, ``"praeco"``) per il sistema."""
    piattaforma = piattaforma or sys.platform
    nome = app.capitalize()
    if piattaforma == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / nome
    if piattaforma == "darwin":
        return Path.home() / "Library" / "Application Support" / nome
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / app.lower()


def cartella_predefinita(app: str, radice_sorgenti: Path) -> Path:
    """``dati/`` dei sorgenti, o la cartella dell'utente se l'app è un eseguibile."""
    return cartella_utente(app) if congelata() else radice_sorgenti / "dati"


def prepara(cartella: Path, extra: tuple[str, ...] = ()) -> Path:
    """Crea la cartella dei dati e le sottocartelle (backup, log e quelle in ``extra``)."""
    for nome in (*SOTTOCARTELLE, *extra):
        (cartella / nome).mkdir(parents=True, exist_ok=True)
    return cartella


def applica_avvio(prefisso: str, impostazioni, cartella: str | None, porta: int | None):
    """Le impostazioni con ``--data-dir`` e ``--port`` (campi ``cartella_dati`` e ``porta``);
    gli stessi valori vanno in ``<PREFISSO>_DATI`` e ``<PREFISSO>_PORTA`` per i processi
    figli. Le impostazioni restituite vanno pubblicate prima di importare l'app."""
    from dataclasses import replace

    campi: dict = {}
    if cartella:
        campi["cartella_dati"] = Path(cartella).resolve()
        os.environ[f"{prefisso}_DATI"] = str(campi["cartella_dati"])
    if porta:
        campi["porta"] = int(porta)
        os.environ[f"{prefisso}_PORTA"] = str(campi["porta"])
    return replace(impostazioni, **campi) if campi else impostazioni
