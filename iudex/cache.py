"""Archivio locale SQLite: cronologia, ricerche salvate, preferiti, sentenze lette, cache,
diario delle consultazioni e sentenze consultate (archivio personale permanente)."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import zlib
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
    permalink TEXT NOT NULL UNIQUE,
    ultimo_controllo REAL,
    trovati INTEGER,
    ultimi_id TEXT,
    nuovi INTEGER
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
CREATE TABLE IF NOT EXISTS diario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quando REAL NOT NULL,
    tipo TEXT NOT NULL,
    testo TEXT,
    riferimenti TEXT,
    filtri TEXT,
    ordinamento TEXT,
    pagina INTEGER,
    permalink TEXT,
    id_sentenza TEXT,
    trovati INTEGER
);
CREATE INDEX IF NOT EXISTS diario_sentenza ON diario (id_sentenza);
CREATE TABLE IF NOT EXISTS consultate (
    id_sentenza TEXT PRIMARY KEY,
    prima_volta REAL NOT NULL,
    ultima_volta REAL NOT NULL,
    volte INTEGER NOT NULL,
    documento TEXT NOT NULL,
    grezzo BLOB NOT NULL
);
"""

# Il diario e le sentenze consultate sono l'archivio personale: una riga del diario per ogni
# ricerca e per ogni apertura di una sentenza (anche la stessa, in giorni diversi, da ricerche
# diverse); in ``consultate`` ogni sentenza aperta sta una volta sola, con la risposta intera
# del server compressa. Nessuna delle due tabelle viene svuotata dai pulsanti della cache.

GIORNO_SQL = "strftime('%Y-%m-%d', quando, 'unixepoch', 'localtime')"

# Colonne aggiunte dopo la 0.1.0: vengono create se mancano (migrazione leggera).
COLONNE_AGGIUNTE = {
    "salvate": (
        ("ultimo_controllo", "REAL"),
        ("trovati", "INTEGER"),
        ("ultimi_id", "TEXT"),
        ("nuovi", "INTEGER"),
    ),
}


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
            self._migra()

    def _migra(self) -> None:
        for tabella, colonne in COLONNE_AGGIUNTE.items():
            presenti = {r["name"] for r in self._conn.execute(f"PRAGMA table_info({tabella})")}
            for nome, tipo in colonne:
                if nome not in presenti:
                    self._conn.execute(f"ALTER TABLE {tabella} ADD COLUMN {nome} {tipo}")
        self._conn.commit()

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

    def conta_risposte(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM risposte").fetchone()[0]

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

    def svuota_sentenze(self) -> int:
        with self._lock, self._conn:
            return self._conn.execute("DELETE FROM sentenze").rowcount

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

    def cronologia(self, limite: int = 200) -> list[dict]:
        with self._lock:
            righe = self._conn.execute(
                "SELECT * FROM ricerche ORDER BY quando DESC LIMIT ?", (limite,)
            ).fetchall()
        return [dict(r, filtri=json.loads(r["filtri"] or "{}")) for r in righe]

    def svuota_cronologia(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM ricerche")

    def elimina_ricerca(self, id_ricerca: int) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM ricerche WHERE id = ?", (id_ricerca,))

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
        return [self._salvata(r) for r in righe]

    def ricerca_salvata(self, id_salvata: int) -> dict | None:
        with self._lock:
            riga = self._conn.execute(
                "SELECT * FROM salvate WHERE id = ?", (id_salvata,)
            ).fetchone()
        return self._salvata(riga) if riga else None

    @staticmethod
    def _salvata(riga: sqlite3.Row) -> dict:
        d = dict(riga)
        d["ultimi_id"] = json.loads(d["ultimi_id"]) if d.get("ultimi_id") else None
        return d

    def aggiorna_controllo(self, id_salvata: int, trovati: int, ids: list[str], nuovi: int) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE salvate SET ultimo_controllo = ?, trovati = ?, ultimi_id = ?, nuovi = ?"
                " WHERE id = ?",
                (time.time(), trovati, json.dumps(ids), nuovi, id_salvata),
            )

    def elimina_ricerca_salvata(self, id_salvata: int) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM salvate WHERE id = ?", (id_salvata,))

    # --- preferiti -----------------------------------------------------------------------

    def aggiungi_preferito(self, id_sentenza: str, estremi: dict, nota: str | None) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO preferiti (id_sentenza, quando, estremi, nota) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(id_sentenza) DO UPDATE SET estremi = excluded.estremi,"
                " nota = COALESCE(excluded.nota, preferiti.nota)",
                (id_sentenza, time.time(), json.dumps(estremi, ensure_ascii=False), nota),
            )

    def aggiorna_nota(self, id_sentenza: str, nota: str | None) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE preferiti SET nota = ? WHERE id_sentenza = ?", (nota, id_sentenza)
            )
            return cur.rowcount > 0

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

    # --- diario delle consultazioni (permanente) -----------------------------------------

    def annota_ricerca(
        self,
        *,
        testo: str | None,
        riferimenti: str | None,
        filtri: dict,
        ordinamento: str,
        pagina: int,
        permalink: str,
        trovati: int,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO diario (quando, tipo, testo, riferimenti, filtri, ordinamento,"
                " pagina, permalink, trovati) VALUES (?, 'ricerca', ?, ?, ?, ?, ?, ?, ?)",
                (
                    time.time(),
                    testo,
                    riferimenti,
                    json.dumps(filtri, ensure_ascii=False),
                    ordinamento,
                    pagina,
                    permalink,
                    trovati,
                ),
            )

    def annota_sentenza(self, id_sentenza: str, permalink: str | None) -> None:
        """Un'apertura della sentenza; ``permalink`` è la ricerca da cui è stata aperta."""
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO diario (quando, tipo, permalink, id_sentenza)"
                " VALUES (?, 'sentenza', ?, ?)",
                (time.time(), permalink or None, id_sentenza),
            )

    def diario(
        self, giorno: str | None = None, id_sentenza: str | None = None, limite: int = 500
    ) -> list[dict]:
        """Voci in ordine cronologico inverso, per giorno (``AAAA-MM-GG``) o per sentenza."""
        condizioni, valori = [], []
        if giorno:
            condizioni.append(f"{GIORNO_SQL} = ?")
            valori.append(giorno)
        if id_sentenza:
            condizioni.append("diario.id_sentenza = ?")
            valori.append(id_sentenza)
        dove = (" WHERE " + " AND ".join(condizioni)) if condizioni else ""
        with self._lock:
            righe = self._conn.execute(
                f"SELECT diario.*, {GIORNO_SQL} AS giorno, consultate.documento AS documento"
                " FROM diario LEFT JOIN consultate USING (id_sentenza)"
                f"{dove} ORDER BY quando DESC, id DESC LIMIT ?",
                (*valori, limite),
            ).fetchall()
        return [self._voce_diario(r) for r in righe]

    @staticmethod
    def _voce_diario(riga: sqlite3.Row) -> dict:
        d = dict(riga)
        d["filtri"] = json.loads(d["filtri"]) if d.get("filtri") else {}
        d["documento"] = json.loads(d["documento"]) if d.get("documento") else None
        return d

    def giorni_diario(self) -> list[dict]:
        """``[{giorno, ricerche, sentenze}]`` dal più recente."""
        with self._lock:
            righe = self._conn.execute(
                f"SELECT {GIORNO_SQL} AS giorno,"
                " SUM(tipo = 'ricerca') AS ricerche, SUM(tipo = 'sentenza') AS sentenze"
                " FROM diario GROUP BY giorno ORDER BY giorno DESC"
            ).fetchall()
        return [dict(r) for r in righe]

    def conta_diario(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM diario").fetchone()[0]

    # --- sentenze consultate (permanenti, risposta intera del server) --------------------

    def tocca_consultata(self, id_sentenza: str) -> bool:
        """Segna un'altra apertura; False se la sentenza non è ancora fra le consultate."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE consultate SET ultima_volta = ?, volte = volte + 1 WHERE id_sentenza = ?",
                (time.time(), id_sentenza),
            )
            return cur.rowcount > 0

    def scrivi_consultata(self, id_sentenza: str, documento: dict, grezzo: dict) -> None:
        """Prima apertura: documento normalizzato e risposta del server compressa."""
        adesso = time.time()
        blob = zlib.compress(json.dumps(grezzo, ensure_ascii=False).encode("utf-8"), 6)
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO consultate (id_sentenza, prima_volta, ultima_volta, volte,"
                " documento, grezzo) VALUES (?, ?, ?, 1, ?, ?)"
                " ON CONFLICT(id_sentenza) DO UPDATE SET ultima_volta = excluded.ultima_volta,"
                " volte = volte + 1, documento = excluded.documento, grezzo = excluded.grezzo",
                (id_sentenza, adesso, adesso, json.dumps(documento, ensure_ascii=False), blob),
            )

    def consultata(self, id_sentenza: str) -> dict | None:
        with self._lock:
            riga = self._conn.execute(
                "SELECT id_sentenza, prima_volta, ultima_volta, volte, documento"
                " FROM consultate WHERE id_sentenza = ?",
                (id_sentenza,),
            ).fetchone()
        return dict(riga, documento=json.loads(riga["documento"])) if riga else None

    def consultate(self) -> list[dict]:
        with self._lock:
            righe = self._conn.execute(
                "SELECT id_sentenza, prima_volta, ultima_volta, volte, documento"
                " FROM consultate ORDER BY ultima_volta DESC"
            ).fetchall()
        return [dict(r, documento=json.loads(r["documento"])) for r in righe]

    def grezzo_consultata(self, id_sentenza: str) -> dict | None:
        with self._lock:
            riga = self._conn.execute(
                "SELECT grezzo FROM consultate WHERE id_sentenza = ?", (id_sentenza,)
            ).fetchone()
        if not riga:
            return None
        return json.loads(zlib.decompress(riga["grezzo"]).decode("utf-8"))

    def grezzi_consultate(self):
        """Coppie ``(id_sentenza, grezzo)`` di tutte le consultate, una alla volta."""
        with self._lock:
            ids = [
                r["id_sentenza"]
                for r in self._conn.execute(
                    "SELECT id_sentenza FROM consultate ORDER BY prima_volta"
                ).fetchall()
            ]
        for id_sentenza in ids:
            grezzo = self.grezzo_consultata(id_sentenza)
            if grezzo is not None:
                yield id_sentenza, grezzo

    def conta_consultate(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM consultate").fetchone()[0]

    # --- copia di sicurezza --------------------------------------------------------------

    def copia_di_sicurezza(self, destinazione: Path) -> Path:
        """Copia pulita del database (``VACUUM INTO``), senza il file WAL."""
        destinazione = Path(destinazione)
        destinazione.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._conn.execute("VACUUM INTO ?", (str(destinazione),))
        return destinazione
