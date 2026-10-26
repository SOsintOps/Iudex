"""Copie di sicurezza del database con ``VACUUM INTO`` in ``backup/``, con rotazione.

Voicebox non fa backup del suo database (lacuna annotata nello studio del 26 ottobre 2026);
qui una copia pulita (senza il file WAL) si fa una volta alla settimana e prima delle
migrazioni dello schema, tenendo le ultime otto.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger("iudex.autonoma")

CONSERVA = 8


def copie(cartella: Path, nome: str) -> list[Path]:
    """Le copie di ``nome`` in ``cartella``, dalla più vecchia alla più recente."""
    return sorted(cartella.glob(f"{nome}-*.sqlite"))


def serve(cartella: Path, nome: str, giorni: float = 7, adesso: float | None = None) -> bool:
    """Vero se non c'è una copia più recente di ``giorni``."""
    esistenti = copie(cartella, nome)
    if not esistenti:
        return True
    adesso = time.time() if adesso is None else adesso
    return adesso - esistenti[-1].stat().st_mtime > giorni * 86400


def esegui(
    copia: Callable[[Path], object],
    cartella: Path,
    nome: str,
    motivo: str = "settimanale",
    conserva: int = CONSERVA,
) -> Path:
    """Crea ``backup/<nome>-AAAAMMGG-HHMMSS.sqlite`` con ``copia`` (che fa il ``VACUUM
    INTO``) e toglie le copie oltre le ultime ``conserva``."""
    cartella.mkdir(parents=True, exist_ok=True)
    destinazione = cartella / f"{nome}-{time.strftime('%Y%m%d-%H%M%S')}.sqlite"
    n = 1
    while destinazione.exists():  # due copie nello stesso secondo
        destinazione = cartella / f"{nome}-{time.strftime('%Y%m%d-%H%M%S')}-{n}.sqlite"
        n += 1
    copia(destinazione)
    for vecchia in copie(cartella, nome)[:-conserva]:
        vecchia.unlink(missing_ok=True)
    log.info("copia di sicurezza (%s): %s", motivo, destinazione)
    return destinazione


def se_serve(copia: Callable[[Path], object], cartella: Path, nome: str) -> Path | None:
    """La copia settimanale, se l'ultima ha più di sette giorni."""
    return esegui(copia, cartella, nome) if serve(cartella, nome) else None
