"""Importazione dello storico di un altro Iudex: pacchetto ZIP, JSONL o copia del database.

I tre formati si leggono nella stessa forma di ``Archivio.dati_ricerche`` più le sentenze
consultate (risposta intera) e i PDF; l'unione senza duplicati la fa ``Archivio.unisci``.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .export import FORMATO_PACCHETTO
from .pdf import id_valido

INTESTAZIONE_SQLITE = b"SQLite format 3\x00"


class ImportazioneNonValida(ValueError):
    pass


@dataclass
class Pacchetto:
    dati: dict
    consultate: list[tuple[str, dict | None, dict]] = field(default_factory=list)
    # PDF presenti nel pacchetto: {id: contenuto}; i metadati (sha256) sono in dati["pdf"].
    pdf: dict[str, bytes] = field(default_factory=dict)
    formato: str = ""


def _vuoto() -> dict:
    return {
        "macchine": {},
        "ricerche": [],
        "esecuzioni": [],
        "risultati": [],
        "diario": [],
        "consultate": [],
        "pdf": [],
    }


CHIAVI = {
    "ricerca": "ricerche",
    "esecuzione": "esecuzioni",
    "risultato": "risultati",
    "diario": "diario",
    "consultata": "consultate",
    "pdf": "pdf",
}


def da_jsonl(testo: str) -> dict:
    righe = [r for r in testo.splitlines() if r.strip()]
    if not righe:
        raise ImportazioneNonValida("il file è vuoto")
    try:
        record = [json.loads(r) for r in righe]
    except json.JSONDecodeError as exc:
        raise ImportazioneNonValida(f"JSONL non valido alla riga {exc.lineno}") from None
    testa = record[0]
    if testa.get("record") != "pacchetto" or testa.get("app") != "iudex":
        raise ImportazioneNonValida("non è un export dello storico di Iudex")
    if int(testa.get("formato") or 0) > FORMATO_PACCHETTO:
        raise ImportazioneNonValida(
            "il pacchetto viene da una versione più recente di Iudex: aggiorna prima"
        )
    dati = _vuoto()
    for r in record[1:]:
        tipo = r.pop("record", None)
        r.pop("quando_locale", None)
        if tipo == "macchina":
            dati["macchine"][r["id"]] = {"nome": r.get("nome")}
        elif tipo in CHIAVI:
            dati[CHIAVI[tipo]].append(r)
    return dati


def da_zip(contenuto: bytes) -> Pacchetto:
    try:
        zf = zipfile.ZipFile(io.BytesIO(contenuto))
    except zipfile.BadZipFile:
        raise ImportazioneNonValida("archivio ZIP non valido") from None
    with zf:
        if "ricerche.jsonl" not in zf.namelist():
            raise ImportazioneNonValida("il pacchetto non contiene ricerche.jsonl")
        dati = da_jsonl(zf.read("ricerche.jsonl").decode("utf-8"))
        pacchetto = Pacchetto(dati, formato="zip")
        for nome in zf.namelist():
            cartella, _, file_ = nome.partition("/")
            id_sentenza = file_.rsplit(".", 1)[0]
            if not id_valido(id_sentenza):
                continue
            if cartella == "consultate" and file_.endswith(".json"):
                voce = json.loads(zf.read(nome).decode("utf-8"))
                pacchetto.consultate.append((id_sentenza, voce.get("documento"), voce["grezzo"]))
            elif cartella == "pdf" and file_.endswith(".pdf"):
                pacchetto.pdf[id_sentenza] = zf.read(nome)
    return pacchetto


def da_sqlite(contenuto: bytes) -> Pacchetto:
    """Una copia del database di Iudex (anche di una versione vecchia): si migra in una
    cartella provvisoria, il file caricato non viene toccato. I PDF non viaggiano con il
    database (i percorsi sono di un altro computer)."""
    from .cache import Archivio

    cartella = Path(tempfile.mkdtemp(prefix="iudex-importa-"))
    try:
        percorso = cartella / "importato.sqlite"
        percorso.write_bytes(contenuto)
        try:
            altro = Archivio(percorso)
        except sqlite3.DatabaseError as exc:
            raise ImportazioneNonValida(f"database non leggibile: {exc}") from None
        try:
            dati = altro.dati_ricerche()
            documenti = {c["id_sentenza"]: c["documento"] for c in altro.consultate()}
            consultate = [
                (id_s, documenti.get(id_s), grezzo) for id_s, grezzo in altro.grezzi_consultate()
            ]
        finally:
            altro.chiudi()
        dati["pdf"] = []
        return Pacchetto(dati, consultate, formato="sqlite")
    finally:
        shutil.rmtree(cartella, ignore_errors=True)


def leggi(nome: str, contenuto: bytes) -> Pacchetto:
    """Riconosce il formato dal contenuto (ZIP, database SQLite) o, per il JSONL, dal testo."""
    if contenuto.startswith(b"PK"):
        return da_zip(contenuto)
    if contenuto.startswith(INTESTAZIONE_SQLITE):
        return da_sqlite(contenuto)
    try:
        testo = contenuto.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ImportazioneNonValida(
            f"{nome}: formato non riconosciuto (attesi ZIP, JSONL o .sqlite di Iudex)"
        ) from None
    return Pacchetto(da_jsonl(testo), formato="jsonl")


def sha256(contenuto: bytes) -> str:
    return hashlib.sha256(contenuto).hexdigest()
