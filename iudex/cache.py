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
CREATE INDEX IF NOT EXISTS risposte_quando ON risposte (quando);
CREATE INDEX IF NOT EXISTS estremi_quando ON estremi (quando);
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

# Colonne aggiunte dopo la 0.1.0: vengono create se mancano (migrazione 1).
COLONNE_AGGIUNTE = {
    "salvate": (
        ("ultimo_controllo", "REAL"),
        ("trovati", "INTEGER"),
        ("ultimi_id", "TEXT"),
        ("nuovi", "INTEGER"),
    ),
}

# Versione dello schema, salvata in ``PRAGMA user_version`` (0 fino alla 0.7.0). Ogni
# migrazione porta il database dalla versione precedente alla sua ed è idempotente: un
# archivio della 0.7.0 ha già alcune colonne della migrazione 1.
VERSIONE_SCHEMA = 3

# Tabelle il cui contenuto è dell'utente: se una ha righe, prima di migrare si fa la copia.
TABELLE_UTENTE = ("ricerche", "salvate", "preferiti", "diario", "consultate")


def _migra_1(conn: sqlite3.Connection) -> None:
    for tabella, colonne in COLONNE_AGGIUNTE.items():
        presenti = {r["name"] for r in conn.execute(f"PRAGMA table_info({tabella})")}
        for nome, tipo in colonne:
            if nome not in presenti:
                conn.execute(f"ALTER TABLE {tabella} ADD COLUMN {nome} {tipo}")


def _migra_2(conn: sqlite3.Connection) -> None:
    # Impostazioni scelte dall'utente nella scheda Impostazioni: valore JSON per chiave.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS impostazioni ("
        " chiave TEXT PRIMARY KEY, valore TEXT NOT NULL, quando REAL NOT NULL)"
    )


def _migra_3(conn: sqlite3.Connection) -> None:
    # Memoria permanente delle ricerche: ogni pagina di risultati vista è un'esecuzione, con
    # le sentenze mostrate in ``risultati`` (da quale ricerca è uscita una sentenza).
    # ``ricerca`` è il permalink della pagina 1, lo stesso di ``ricerche.permalink``.
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS esecuzioni (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quando REAL NOT NULL,
            ricerca TEXT NOT NULL,
            permalink TEXT NOT NULL,
            descrizione TEXT,
            pagina INTEGER NOT NULL,
            righe INTEGER NOT NULL,
            trovati INTEGER,
            dalla_cache INTEGER NOT NULL,
            origine TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS esecuzioni_ricerca ON esecuzioni (ricerca);
        CREATE TABLE IF NOT EXISTS risultati (
            id_esecuzione INTEGER NOT NULL,
            posizione INTEGER NOT NULL,
            id_sentenza TEXT NOT NULL,
            estremi TEXT NOT NULL,
            PRIMARY KEY (id_esecuzione, posizione)
        );
        CREATE INDEX IF NOT EXISTS risultati_sentenza ON risultati (id_sentenza);
        """
    )
    presenti = {r["name"] for r in conn.execute("PRAGMA table_info(ricerche)")}
    if "prima_volta" not in presenti:
        conn.execute("ALTER TABLE ricerche ADD COLUMN prima_volta REAL")
        conn.execute("UPDATE ricerche SET prima_volta = quando")
    if "volte" not in presenti:
        conn.execute("ALTER TABLE ricerche ADD COLUMN volte INTEGER NOT NULL DEFAULT 1")


MIGRAZIONI = {1: _migra_1, 2: _migra_2, 3: _migra_3}

# Estremi di una sentenza conservati con ogni risultato: bastano a riconoscerla e a
# esportarla anche se il testo non è mai stato aperto.
CAMPI_ESTREMI = (
    "archivio",
    "kind",
    "tipo",
    "sezione",
    "numero",
    "anno",
    "data_decisione",
    "data_deposito",
    "ecli",
    "presidente",
    "relatore",
    "filename",
)


class Archivio:
    def __init__(self, percorso: Path | str):
        percorso = Path(percorso)
        self._percorso = None if str(percorso) == ":memory:" else percorso
        if self._percorso is not None:
            percorso.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(percorso), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(SCHEMA)
            self._migra()

    @property
    def versione_schema(self) -> int:
        with self._lock:
            return self._conn.execute("PRAGMA user_version").fetchone()[0]

    def _migra(self) -> None:
        """Applica le migrazioni mancanti; prima, se l'archivio ha già dati dell'utente, ne fa
        una copia di sicurezza in ``backup/`` accanto al database."""
        versione = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if versione >= VERSIONE_SCHEMA:
            return
        if self._percorso is not None and any(
            self._conn.execute(f"SELECT EXISTS(SELECT 1 FROM {t})").fetchone()[0]
            for t in TABELLE_UTENTE
        ):
            from .autonoma import backup

            backup.esegui(
                self._vacuum_into,
                self._percorso.parent / "backup",
                "iudex",
                f"prima della migrazione dello schema {versione} → {VERSIONE_SCHEMA}",
            )
        for numero in range(versione + 1, VERSIONE_SCHEMA + 1):
            with self._conn:
                MIGRAZIONI[numero](self._conn)
            # PRAGMA non accetta parametri; il numero viene da MIGRAZIONI.
            self._conn.execute(f"PRAGMA user_version = {numero}")

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

    def pulisci_scadute(self, ttl_risposte: int, ttl_estremi: int) -> int:
        """Toglie le risposte e le normalizzazioni scadute (la lettura le ignorava già).

        SQLite non ha una scadenza automatica: le righe si cancellano con un DELETE sulla
        colonna ``quando``, indicizzata. Diario, consultate e testi non sono toccati.
        """
        adesso = time.time()
        with self._lock, self._conn:
            n = self._conn.execute(
                "DELETE FROM risposte WHERE quando < ?", (adesso - ttl_risposte,)
            ).rowcount
            n += self._conn.execute(
                "DELETE FROM estremi WHERE quando < ?", (adesso - ttl_estremi,)
            ).rowcount
        if n:
            # Come requests-cache dopo la pulizia: senza VACUUM le pagine liberate restano
            # nel file e il contenuto cancellato resta recuperabile (documentazione SQLite,
            # "VACUUM"). Va eseguito fuori da una transazione.
            with self._lock:
                self._conn.execute("VACUUM")
        return n

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
        adesso = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO ricerche (quando, testo, riferimenti, filtri, ordinamento, righe,"
                " trovati, permalink, prima_volta, volte) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)"
                " ON CONFLICT(permalink) DO UPDATE SET quando = excluded.quando,"
                " trovati = excluded.trovati, volte = ricerche.volte + 1",
                (
                    adesso,
                    testo,
                    riferimenti,
                    json.dumps(filtri, ensure_ascii=False),
                    ordinamento,
                    righe,
                    trovati,
                    permalink,
                    adesso,
                ),
            )

    def registra_esecuzione(
        self,
        *,
        ricerca: str,
        permalink: str,
        descrizione: str,
        pagina: int,
        righe: int,
        trovati: int | None,
        dalla_cache: bool,
        origine: str,
        documenti: list[dict],
        inizio: int = 0,
    ) -> int:
        """Una pagina di risultati vista (``origine`` = ``ricerca`` o ``controllo`` di una
        ricerca salvata) e le sentenze mostrate, con la loro posizione nei risultati."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO esecuzioni (quando, ricerca, permalink, descrizione, pagina, righe,"
                " trovati, dalla_cache, origine) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    time.time(),
                    ricerca,
                    permalink,
                    descrizione,
                    pagina,
                    righe,
                    trovati,
                    int(dalla_cache),
                    origine,
                ),
            )
            id_esecuzione = cur.lastrowid
            self._conn.executemany(
                "INSERT OR IGNORE INTO risultati (id_esecuzione, posizione, id_sentenza, estremi)"
                " VALUES (?, ?, ?, ?)",
                [
                    (
                        id_esecuzione,
                        inizio + i + 1,
                        d["id"],
                        json.dumps(
                            {k: d.get(k) for k in CAMPI_ESTREMI if d.get(k) is not None},
                            ensure_ascii=False,
                        ),
                    )
                    for i, d in enumerate(documenti)
                    if d.get("id")
                ],
            )
        return id_esecuzione

    def provenienze(self, ids: list[str]) -> dict[str, list[dict]]:
        """Per ogni sentenza, le ricerche in cui è uscita: ``[{ricerca, descrizione,
        quando}]`` con l'ultima volta per ricerca, dalla più recente."""
        if not ids:
            return {}
        segnaposto = ",".join("?" * len(ids))
        with self._lock:
            righe = self._conn.execute(
                "SELECT r.id_sentenza, e.ricerca, MAX(e.quando) AS quando,"
                " (SELECT descrizione FROM esecuzioni WHERE ricerca = e.ricerca"
                "  ORDER BY quando DESC LIMIT 1) AS descrizione"
                " FROM risultati r JOIN esecuzioni e ON e.id = r.id_esecuzione"
                f" WHERE r.id_sentenza IN ({segnaposto})"
                " GROUP BY r.id_sentenza, e.ricerca ORDER BY quando DESC",
                list(ids),
            ).fetchall()
        esito: dict[str, list[dict]] = {}
        for r in righe:
            esito.setdefault(r["id_sentenza"], []).append(
                {"ricerca": r["ricerca"], "descrizione": r["descrizione"], "quando": r["quando"]}
            )
        return esito

    def conta_esecuzioni(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM esecuzioni").fetchone()[0]

    def _togli_esecuzioni(self, dove: str = "", valori: tuple = ()) -> None:
        self._conn.execute(
            f"DELETE FROM risultati WHERE id_esecuzione IN (SELECT id FROM esecuzioni{dove})",
            valori,
        )
        self._conn.execute(f"DELETE FROM esecuzioni{dove}", valori)

    def cronologia(self, limite: int = 200) -> list[dict]:
        with self._lock:
            righe = self._conn.execute(
                "SELECT * FROM ricerche ORDER BY quando DESC LIMIT ?", (limite,)
            ).fetchall()
        return [dict(r, filtri=json.loads(r["filtri"] or "{}")) for r in righe]

    def svuota_cronologia(self) -> None:
        """Cancella tutte le ricerche con le loro esecuzioni e i risultati (provenienze)."""
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM ricerche")
            self._togli_esecuzioni()

    def elimina_ricerca(self, id_ricerca: int) -> None:
        """Cancella la ricerca e le sue esecuzioni: le sentenze non risultano più uscite da lì."""
        with self._lock, self._conn:
            riga = self._conn.execute(
                "SELECT permalink FROM ricerche WHERE id = ?", (id_ricerca,)
            ).fetchone()
            self._conn.execute("DELETE FROM ricerche WHERE id = ?", (id_ricerca,))
            if riga:
                self._togli_esecuzioni(" WHERE ricerca = ?", (riga["permalink"],))

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

    # --- impostazioni dell'utente ----------------------------------------------------------

    def impostazioni(self) -> dict:
        """Le impostazioni salvate, ``{chiave: valore}`` (i valori sono JSON)."""
        with self._lock:
            righe = self._conn.execute("SELECT chiave, valore FROM impostazioni").fetchall()
        return {r["chiave"]: json.loads(r["valore"]) for r in righe}

    def scrivi_impostazioni(self, valori: dict) -> None:
        """Salva le chiavi indicate; ``None`` toglie la chiave (torna il predefinito)."""
        adesso = time.time()
        with self._lock, self._conn:
            for chiave, valore in valori.items():
                if valore is None:
                    self._conn.execute("DELETE FROM impostazioni WHERE chiave = ?", (chiave,))
                else:
                    self._conn.execute(
                        "INSERT INTO impostazioni (chiave, valore, quando) VALUES (?, ?, ?)"
                        " ON CONFLICT(chiave) DO UPDATE SET valore = excluded.valore,"
                        " quando = excluded.quando",
                        (chiave, json.dumps(valore, ensure_ascii=False), adesso),
                    )

    # --- copia di sicurezza --------------------------------------------------------------

    def copia_di_sicurezza(self, destinazione: Path) -> Path:
        """Copia pulita del database (``VACUUM INTO``), senza il file WAL."""
        with self._lock:
            return self._vacuum_into(destinazione)

    def _vacuum_into(self, destinazione: Path) -> Path:
        destinazione = Path(destinazione)
        destinazione.parent.mkdir(parents=True, exist_ok=True)
        self._conn.execute("VACUUM INTO ?", (str(destinazione),))
        return destinazione
