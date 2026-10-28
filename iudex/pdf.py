"""PDF delle sentenze salvati in locale: la cartella, il nome del file, l'apertura.

Il file di una sentenza è ``<id_sentenza>.pdf`` nella cartella dei PDF, lo stesso nome usato
da Praeco (``dati/pdf/<id>.pdf``), così i due programmi possono un giorno condividerla. La
cartella si sceglie nell'installer (``installazione.ini`` nella cartella dei dati) o nella
scheda Impostazioni; altrimenti è ``pdf/`` nella cartella dei dati.
"""

from __future__ import annotations

import configparser
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

# Gli id di SentenzeWeb sono lettere e cifre (es. snpen2024605337S): niente separatori di
# percorso, quindi il nome del file non può uscire dalla cartella.
ID_VALIDO = re.compile(r"^[A-Za-z0-9]{1,64}$")
FILE_INSTALLAZIONE = "installazione.ini"


def id_valido(id_sentenza: str) -> bool:
    return bool(ID_VALIDO.match(id_sentenza or ""))


def cartella(scelta: str | None, cartella_dati: Path) -> Path:
    """La cartella dei PDF: quella scelta dall'utente, altrimenti ``pdf/`` nei dati."""
    return Path(scelta).expanduser() if scelta else cartella_dati / "pdf"


def da_installazione(cartella_dati: Path) -> str | None:
    """La cartella dei PDF indicata nell'installer (``[pdf] cartella = ...``), se c'è."""
    percorso = cartella_dati / FILE_INSTALLAZIONE
    if not percorso.exists():
        return None
    # L'installer lo scrive in UTF-8; un file scritto a mano può essere nella codifica di
    # Windows: un file illeggibile non deve fermare l'avvio.
    for codifica in ("utf-8-sig", "cp1252"):
        lettore = configparser.ConfigParser()
        try:
            lettore.read(percorso, encoding=codifica)
        except UnicodeDecodeError:
            continue
        except configparser.Error:
            return None
        valore = lettore.get("pdf", "cartella", fallback="").strip()
        return valore or None
    return None


def file_di(base: Path, id_sentenza: str) -> Path:
    if not id_valido(id_sentenza):
        raise ValueError(f"id di sentenza non valido: {id_sentenza!r}")
    return base / f"{id_sentenza}.pdf"


def relativo(base: Path, percorso: Path) -> str:
    """Il percorso da registrare: relativo alla cartella se ci sta dentro, così la cartella
    si può spostare; assoluto altrimenti."""
    try:
        return percorso.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return str(percorso.resolve())


def risolvi(base: Path, registrato: str) -> Path:
    p = Path(registrato)
    return p if p.is_absolute() else base / p


def salva(destinazione: Path, contenuto: bytes) -> str:
    """Scrive il file in modo atomico (provvisorio poi rinominato) e restituisce lo sha256."""
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    provvisorio = destinazione.with_name(destinazione.name + ".parziale")
    provvisorio.write_bytes(contenuto)
    os.replace(provvisorio, destinazione)
    return hashlib.sha256(contenuto).hexdigest()


def apri_con_programma(percorso: Path) -> None:
    """Apre il file con il programma PDF predefinito del sistema."""
    if sys.platform == "win32":
        os.startfile(str(percorso))  # noqa: S606 - file locale scelto da Iudex
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(percorso)])  # noqa: S603, S607
    else:
        subprocess.Popen(["xdg-open", str(percorso)])  # noqa: S603, S607
