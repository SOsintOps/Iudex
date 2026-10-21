"""Archivio locale SQLite: cronologia, preferiti, sentenze lette, risposte in cache."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS ricerche (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quando REAL NOT NULL,
    testo TEXT,
    riferimenti TEXT,
    filtri TEXT,
    ordinamento TEXT,
    righe INTEGER,
    trovati INTEGER,
    permalink TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS salvate (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quando REAL NOT NULL,
    nome TEXT NOT NULL,
    permalink TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS preferiti (
    id_sentenza TEXT PRIMARY KEY,
    quando REAL NOT NULL,
    estremi TEXT NOT NULL,
    nota TEXT
);
CREATE TABLE IF NOT EXISTS sentenze (
    id_sentenza TEXT PRIMARY KEY,
    quando REAL NOT NULL,
    documento TEXT NOT NULL,
    testo TEXT
);
CREATE TABLE IF NOT EXISTS risposte (
    chiave TEXT PRIMARY KEY,
    quando REAL NOT NULL,
    contenuto TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS estremi (
    chiave TEXT PRIMARY KEY,
    quando REAL NOT NULL,
    contenuto TEXT NOT NULL
);
"""


class Archivio:
    def __init__(self, percorso: Path | str):
        percorso = Path(percorso)
        if str(percorso) != ":memory:":
            percorso.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(percorso), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(SCHEMA)

    def chiudi(self) -> None:
        self._conn.close()

    # --- risposte di ricerca (TTL) -------------------------------------------------------

    def leggi_risposta(self, chiave: str, ttl: int) -> dict | None:
        with self._lock:
            riga = self._conn.execute(
                "SELECT quando, contenuto FROM risposte WHERE chiave = ?", (chiave,)
            ).fetchone()
        if riga and time.time() - riga["quando"] <= ttl:
            return json.loads(riga["contenuto"])
        return None

    def scrivi_risposta(self, chiave: str, contenuto: dict) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO risposte (chiave, quando, contenuto) VALUES (?, ?, ?)",
                (chiave, time.time(), json.dumps(contenuto, ensure_ascii=False)),
            )

    def svuota_risposte(self) -> int:
        with self._lock, self._conn:
            return self._conn.execute("DELETE FROM risposte").rowcount

    # --- estremi (lista sigle e riferimenti normalizzati) --------------------------------

    def leggi_estremi(self, chiave: str, ttl: int) -> str | None:
        with self._lock:
            riga = self._conn.execute(
                "SELECT quando, contenuto FROM estremi WHERE chiave = ?", (chiave,)
            ).fetchone()
        if riga and time.time() - riga["quando"] <= ttl:
            return riga["contenuto"]
        return None

    def scrivi_estremi(self, chiave: str, contenuto: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO estremi (chiave, quando, contenuto) VALUES (?, ?, ?)",
                (chiave, time.time(), contenuto),
            )

    # --- sentenze lette (permanenti) -----------------------------------------------------

    def leggi_sentenza(self, id_sentenza: str) -> dict | None:
        with self._lock:
            riga = self._conn.execute(
                "SELECT quando, documento, testo FROM sentenze WHERE id_sentenza = ?",
                (id_sentenza,),
            ).fetchone()
        if not riga:
            return None
        return {
            "quando": riga["quando"],
            "documento": json.loads(riga["documento"]),
            "testo": riga["testo"],
        }

    def scrivi_sentenza(self, id_sentenza: str, documento: dict, testo: str | None) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO sentenze (id_sentenza, quando, documento, testo)"
                " VALUES (?, ?, ?, ?)",
                (id_sentenza, time.time(), json.dumps(documento, ensure_ascii=False), testo),
            )

    def conta_sentenze(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM sentenze").fetchone()[0]

    # --- cronologia ----------------------------------------------------------------------

    def registra_ricerca(
        self,
        *,
        testo: str | None,
        riferimenti: str | None,
        filtri: dict,
        ordinamento: str,
        righe: int,
        trovati: int,
        permalink: str,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO ricerche (quando, testo, riferimenti, filtri, ordinamento, righe,"
                " trovati, permalink) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(permalink) DO UPDATE SET quando = excluded.quando,"
                " trovati = excluded.trovati",
                (
                    time.time(),
                    testo,
                    riferimenti,
                    json.dumps(filtri, ensure_ascii=False),
                    ordinamento,
                    righe,
                    trovati,
                    permalink,
                ),
            )

    def cronologia(self, limite: int = 100) -> list[dict]:
        with self._lock:
            righe = self._conn.execute(
                "SELECT * FROM ricerche ORDER BY quando DESC LIMIT ?", (limite,)
            ).fetchall()
        return [dict(r, filtri=json.loads(r["filtri"] or "{}")) for r in righe]

    def svuota_cronologia(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM ricerche")

    # --- ricerche salvate ----------------------------------------------------------------

    def salva_ricerca(self, nome: str, permalink: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO salvate (quando, nome, permalink) VALUES (?, ?, ?)"
                " ON CONFLICT(permalink) DO UPDATE SET nome = excluded.nome,"
                " quando = excluded.quando",
                (time.time(), nome, permalink),
            )

    def ricerche_salvate(self) -> list[dict]:
        with self._lock:
            righe = self._conn.execute("SELECT * FROM salvate ORDER BY quando DESC").fetchall()
        return [dict(r) for r in righe]

    def elimina_ricerca_salvata(self, id_salvata: int) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM salvate WHERE id = ?", (id_salvata,))

    # --- preferiti -----------------------------------------------------------------------

    def aggiungi_preferito(self, id_sentenza: str, estremi: dict, nota: str | None) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO preferiti (id_sentenza, quando, estremi, nota)"
                " VALUES (?, ?, ?, ?)",
                (id_sentenza, time.time(), json.dumps(estremi, ensure_ascii=False), nota),
            )

    def rimuovi_preferito(self, id_sentenza: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM preferiti WHERE id_sentenza = ?", (id_sentenza,))

    def preferiti(self) -> list[dict]:
        with self._lock:
            righe = self._conn.execute("SELECT * FROM preferiti ORDER BY quando DESC").fetchall()
        return [dict(r, estremi=json.loads(r["estremi"])) for r in righe]

    def id_preferiti(self) -> set[str]:
        with self._lock:
            righe = self._conn.execute("SELECT id_sentenza FROM preferiti").fetchall()
        return {r["id_sentenza"] for r in righe}
