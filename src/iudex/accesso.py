"""Accesso alle pagine e alle API locali: solo con il token della cartella dei dati.

Come il backend di Voicebox, il server di Iudex serve la propria finestra e nessun altro. Il
token sta nel file ``token`` della cartella dei dati: la finestra lo usa per aprire
``/accesso?codice=...``, che lascia un cookie di sessione; il server MCP (e un domani Praeco)
lo legge dal file e lo manda nell'header ``X-Iudex-Token``. Un browser qualsiasi che apre
http://127.0.0.1:8765/ senza il token vede solo l'invito ad aprire Iudex dalla sua finestra.
"""

from __future__ import annotations

import hmac
import os
import secrets
from pathlib import Path

FILE_TOKEN = "token"
COOKIE = "iudex_sessione"
HEADER = "x-iudex-token"


def percorso(cartella_dati: Path) -> Path:
    return Path(cartella_dati) / FILE_TOKEN


def _scrivi(file_: Path, valore: str) -> None:
    file_.parent.mkdir(parents=True, exist_ok=True)
    provvisorio = file_.with_name(file_.name + ".nuovo")
    provvisorio.write_text(valore + "\n", encoding="ascii")
    try:
        os.chmod(provvisorio, 0o600)  # su Windows vale solo la sola lettura: innocuo
    except OSError:
        pass
    os.replace(provvisorio, file_)


def leggi(cartella_dati: Path) -> str | None:
    try:
        valore = percorso(cartella_dati).read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return valore or None


def leggi_o_crea(cartella_dati: Path) -> str:
    valore = leggi(cartella_dati)
    if valore is None:
        valore = secrets.token_urlsafe(32)
        _scrivi(percorso(cartella_dati), valore)
    return valore


def rigenera(cartella_dati: Path) -> str:
    """Un token nuovo: quello vecchio smette di valere (finestre e client MCP si ricollegano)."""
    valore = secrets.token_urlsafe(32)
    _scrivi(percorso(cartella_dati), valore)
    return valore


def valido(atteso: str | None, ricevuto: str | None) -> bool:
    return bool(atteso and ricevuto) and hmac.compare_digest(atteso, ricevuto)
