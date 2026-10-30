import sqlite3
import time
import zlib

from iudex.cache import MIGRAZIONI, SCHEMA, TABELLE_UTENTE, VERSIONE_SCHEMA, Archivio
from iudex.norme import Articolo, Atto

COLONNE_070_ASSENTI = (
    "    ultimo_controllo REAL,\n    trovati INTEGER,\n    ultimi_id TEXT,\n    nuovi INTEGER\n"
)


def test_risposte_con_ttl():
    a = Archivio(":memory:")
    a.scrivi_risposta("k", {"n": 1})
    assert a.leggi_risposta("k", 60) == {"n": 1}
    assert a.leggi_risposta("k", -1) is None
    a.chiudi()


def test_pulizia_compatta_il_file(tmp_path):
    a = Archivio(tmp_path / "c.sqlite")
    for i in range(300):
        a.scrivi_risposta(f"k{i}", {"testo": "x" * 4000})
    a._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    prima = (tmp_path / "c.sqlite").stat().st_size
    assert a.pulisci_scadute(-1, -1) == 300
    a._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    assert (tmp_path / "c.sqlite").stat().st_size < prima / 4
    a.chiudi()


def test_pulizia_delle_voci_scadute():
    a = Archivio(":memory:")
    a.scrivi_risposta("vecchia", {"n": 1})
    a.scrivi_estremi("rif:x", "x")
    a.annota_sentenza("id1", None)
    assert a.pulisci_scadute(3600, 86400) == 0
    assert a.pulisci_scadute(-1, -1) == 2
    assert a.conta_risposte() == 0 and a.leggi_estremi("rif:x", 10**9) is None
    assert a.conta_diario() == 1
    a.chiudi()


def test_sentenze_cronologia_preferiti(tmp_path):
    a = Archivio(tmp_path / "x.sqlite")
    a.scrivi_sentenza("id1", {"id": "id1"}, "testo")
    assert a.leggi_sentenza("id1")["testo"] == "testo" and a.conta_sentenze() == 1
    for trovati in (5, 6):
        a.registra_ricerca(
            testo="a",
            riferimenti=None,
            filtri={"kind": ["snciv"]},
            ordinamento="pubblicazione",
            righe=10,
            trovati=trovati,
            permalink="testo=a&kind=snciv",
        )
    cron = a.cronologia()
    assert len(cron) == 1 and cron[0]["trovati"] == 6
    assert cron[0]["filtri"] == {"kind": ["snciv"]}
    a.aggiungi_preferito("id1", {"numero": "1"}, "nota")
    assert a.id_preferiti() == {"id1"} and a.preferiti()[0]["estremi"] == {"numero": "1"}
    a.rimuovi_preferito("id1")
    assert a.id_preferiti() == set()
    a.salva_ricerca("mia", "testo=a")
    assert a.ricerche_salvate()[0]["nome"] == "mia"
    a.chiudi()


def test_diario_e_consultate_sopravvivono_alla_cache(tmp_path):
    a = Archivio(tmp_path / "x.sqlite")
    for pagina in (1, 2):
        a.annota_ricerca(
            testo="mobbing",
            riferimenti=None,
            filtri={"kind": ["snciv"]},
            ordinamento="pubblicazione",
            pagina=pagina,
            permalink="testo=mobbing&kind=snciv",
            trovati=12,
        )
    # Due aperture della stessa sentenza da due ricerche: due voci, una consultata.
    assert a.tocca_consultata("id1") is False
    a.annota_sentenza("id1", "testo=mobbing&kind=snciv")
    grezzo = {"id": "id1", "ocr": ["Testo integrale. P.Q.M. Rigetta."], "ved-numdec": ["5"]}
    a.scrivi_consultata("id1", {"id": "id1", "numero": "1", "anno": "2026"}, grezzo)
    assert a.tocca_consultata("id1") is True
    a.annota_sentenza("id1", "testo=licenziamento")
    voci = a.diario()
    assert [v["tipo"] for v in voci] == ["sentenza", "sentenza", "ricerca", "ricerca"]
    assert voci[0]["permalink"] == "testo=licenziamento" and voci[0]["documento"]["numero"] == "1"
    assert voci[2]["filtri"] == {"kind": ["snciv"]} and voci[2]["pagina"] == 2
    assert len(a.diario(id_sentenza="id1")) == 2
    giorni = a.giorni_diario()
    assert len(giorni) == 1 and giorni[0]["ricerche"] == 2 and giorni[0]["sentenze"] == 2
    assert a.diario(giorno=giorni[0]["giorno"]) == voci
    assert a.diario(giorno="1999-01-01") == []
    c = a.consultata("id1")
    assert c["volte"] == 2 and c["prima_volta"] <= c["ultima_volta"]
    assert a.grezzo_consultata("id1") == grezzo and a.grezzo_consultata("zzz") is None
    assert [i for i, _ in a.grezzi_consultate()] == ["id1"]
    # Lo svuotamento della cache non tocca l'archivio personale.
    a.scrivi_sentenza("id1", {"id": "id1"}, "testo")
    a.scrivi_risposta("k", {"n": 1})
    a.svuota_sentenze()
    a.svuota_risposte()
    assert a.conta_diario() == 4 and a.conta_consultate() == 1
    copia = a.copia_di_sicurezza(tmp_path / "copie" / "c.sqlite")
    assert copia.exists() and copia.stat().st_size > 0
    b = Archivio(copia)
    assert b.conta_diario() == 4 and b.grezzo_consultata("id1") == grezzo
    b.chiudi()
    a.chiudi()


def _archivio_070(percorso):
    """Un database come lo lasciava la 0.7.0: user_version 0, ``salvate`` senza le colonne
    aggiunte, niente tabella ``impostazioni``, una ricerca e una consultata."""
    conn = sqlite3.connect(percorso)
    schema = SCHEMA.replace(COLONNE_070_ASSENTI, "").replace(
        "    permalink TEXT NOT NULL UNIQUE,\n);", "    permalink TEXT NOT NULL UNIQUE\n);"
    )
    conn.executescript(schema)
    conn.execute(
        "INSERT INTO ricerche (quando, testo, filtri, ordinamento, righe, trovati, permalink)"
        " VALUES (1, 'usura', '{}', 'pubblicazione', 10, 3, 'testo=usura')"
    )
    conn.execute(
        "INSERT INTO consultate VALUES ('id1', 1, 2, 2, '{\"id\": \"id1\"}', ?)",
        (zlib.compress(b'{"id": "id1"}'),),
    )
    conn.commit()
    conn.close()


def test_migrazione_da_070_con_copia_di_sicurezza(tmp_path):
    db = tmp_path / "iudex.sqlite"
    _archivio_070(db)
    a = Archivio(db)
    assert a.versione_schema == VERSIONE_SCHEMA
    colonne = {r["name"] for r in a._conn.execute("PRAGMA table_info(salvate)")}
    assert {"ultimo_controllo", "trovati", "ultimi_id", "nuovi"} <= colonne
    assert a.impostazioni() == {}
    assert a.cronologia()[0]["permalink"] == "testo=usura"
    assert a.grezzo_consultata("id1") == {"id": "id1"}
    copie = list((tmp_path / "backup").glob("iudex-*.sqlite"))
    assert len(copie) == 1
    vecchio = sqlite3.connect(copie[0])
    assert vecchio.execute("PRAGMA user_version").fetchone()[0] == 0
    assert vecchio.execute("SELECT COUNT(*) FROM ricerche").fetchone()[0] == 1
    vecchio.close()
    a.chiudi()
    # Riaperto, è già alla versione corrente: nessuna nuova copia.
    Archivio(db).chiudi()
    assert len(list((tmp_path / "backup").glob("iudex-*.sqlite"))) == 1


def test_archivio_nuovo_senza_copia(tmp_path):
    a = Archivio(tmp_path / "nuovo.sqlite")
    assert a.versione_schema == VERSIONE_SCHEMA
    assert not (tmp_path / "backup").exists()
    a.chiudi()


def test_impostazioni():
    a = Archivio(":memory:")
    a.scrivi_impostazioni({"conserva_storico": False, "impronte_personalizzate": [{"nome": "x"}]})
    assert a.impostazioni() == {
        "conserva_storico": False,
        "impronte_personalizzate": [{"nome": "x"}],
    }
    a.scrivi_impostazioni({"conserva_storico": None})
    assert a.impostazioni() == {"impronte_personalizzate": [{"nome": "x"}]}
    a.chiudi()


# --- indice locale del testo (ricerca per nominativo senza chiedere alla Corte) ----------


def _grezzo(testo: str) -> dict:
    return {"ocr": [testo], "tipoprov": "Sentenza", "numdec": "1", "anno": "2026"}


def test_indice_locale_trova_nomi_senza_accenti_e_parole_invertite():
    a = Archivio(":memory:")
    a.scrivi_consultata(
        "snpen1",
        {"numero": "1", "anno": "2026"},
        _grezzo("ricorso di Niccolò D'Angelo contro la sentenza"),
    )
    a.scrivi_consultata(
        "snpen2",
        {"numero": "2", "anno": "2026"},
        _grezzo("nei confronti di ROSSI MARIO, nato a Roma"),
    )
    a.scrivi_sentenza("snciv3", {"numero": "3"}, "la società Edil Sud s.r.l. in liquidazione")

    assert [r["id_sentenza"] for r in a.cerca_locale('"Niccolo D Angelo"')] == ["snpen1"]
    trovate = a.cerca_locale('"Mario Rossi" OR "Rossi Mario"')
    assert [r["id_sentenza"] for r in trovate] == ["snpen2"]
    assert "«ROSSI» «MARIO»" in trovate[0]["estratto"] or "«ROSSI MARIO»" in trovate[0]["estratto"]
    assert trovate[0]["estremi"]["numero"] == "2"
    assert [r["id_sentenza"] for r in a.cerca_locale("Edil Sud")] == ["snciv3"]
    assert a.cerca_locale('"Giuseppe Verdi"') == []
    # Testo che non e' una query valida: nessun errore, nessun risultato.
    assert a.cerca_locale('") OR (') == []
    a.chiudi()


def test_indice_locale_si_aggiorna_e_si_svuota_con_le_sentenze():
    a = Archivio(":memory:")
    a.scrivi_sentenza("snciv3", {}, "Alfa Beta")
    a.scrivi_sentenza("snciv3", {}, "Gamma Delta")
    assert a.cerca_locale("Alfa") == [] and len(a.cerca_locale("Gamma")) == 1
    a.svuota_sentenze()
    assert a.cerca_locale("Gamma") == []
    a.chiudi()


def test_migrazione_6_indicizza_le_sentenze_gia_salvate(tmp_path):
    percorso = tmp_path / "c.sqlite"
    a = Archivio(percorso)
    a.scrivi_consultata("snpen9", {"numero": "9"}, _grezzo("imputato Carlo Bianchi"))
    # Come un archivio della versione 5: niente indice.
    a._conn.execute("DROP TABLE testi_fts")
    a._conn.execute("PRAGMA user_version = 5")
    a._conn.commit()
    a.chiudi()
    b = Archivio(percorso)
    assert b.versione_schema == VERSIONE_SCHEMA
    assert [r["id_sentenza"] for r in b.cerca_locale('"Carlo Bianchi"')] == ["snpen9"]
    b.chiudi()


# --- cache delle norme (schema 7) ------------------------------------------------------

GIORNO = 86400
CHIAVE_ATTO = "LS|241|1990"
URN_CC = "urn:nir:stato:regio.decreto:1942-03-16;262:2"
CHIAVE_VIGENTE = f"{URN_CC}~art2043|"
CHIAVE_DATATA = f"{URN_CC}~art2043|2001-01-01"


def _atto() -> Atto:
    return Atto(
        codice_redazionale="090G0294",
        data_gu="1990-08-18",
        data_emanazione="1990-08-07",
        titolo="Nuove norme in materia di procedimento amministrativo",
        urn="urn:nir:stato:legge:1990-08-07;241",
    )


def _articolo(vigenza: str | None = None) -> Articolo:
    return Articolo(
        numero="2043",
        rubrica="Risarcimento per fatto illecito",
        testo="Qualunque fatto doloso o colposo, che cagiona ad altri un danno ingiusto…",
        note=None,
        inizio_vigenza="1942-04-21",
        fine_vigenza=None,
        vigenza_richiesta=vigenza,
        titolo_atto="Codice civile",
        url="https://www.normattiva.it/uri-res/N2Ls?" + URN_CC + "~art2043",
    )


def _invecchia(a: Archivio, chiave: str, giorni: int) -> None:
    with a._conn:
        a._conn.execute(
            "UPDATE norme SET quando = ? WHERE chiave = ?", (time.time() - giorni * GIORNO, chiave)
        )


def test_migrazione_6_a_7_con_copia_di_sicurezza_e_idempotente(tmp_path):
    db = tmp_path / "iudex.sqlite"
    a = Archivio(db)
    a.annota_ricerca(
        testo="usura",
        riferimenti=None,
        filtri={},
        ordinamento="pubblicazione",
        pagina=1,
        permalink="testo=usura",
        trovati=3,
    )
    a.scrivi_consultata("snciv1", {"numero": "1"}, _grezzo("testo della sentenza"))
    # Come un archivio della versione 6: niente tabelle delle norme.
    a._conn.execute("DROP INDEX norme_quando")
    a._conn.execute("DROP TABLE norme")
    a._conn.execute("DROP TABLE atti")
    a._conn.execute("PRAGMA user_version = 6")
    a._conn.commit()
    a.chiudi()
    assert not (tmp_path / "backup").exists()

    b = Archivio(db)
    assert b.versione_schema == VERSIONE_SCHEMA == 7
    tabelle = {
        r["name"]
        for r in b._conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'index')")
    }
    assert {"atti", "norme", "norme_quando"} <= tabelle
    assert b.conta_diario() == 1 and b.conta_consultate() == 1
    assert b.conta_norme() == 0
    copie = list((tmp_path / "backup").glob("iudex-*.sqlite"))
    assert len(copie) == 1
    vecchio = sqlite3.connect(copie[0])
    assert vecchio.execute("PRAGMA user_version").fetchone()[0] == 6
    assert vecchio.execute("SELECT COUNT(*) FROM diario").fetchone()[0] == 1
    vecchio.close()
    # La migrazione ripetuta non cambia nulla e non perde i dati già in cache.
    b.scrivi_norma(CHIAVE_VIGENTE, _articolo())
    with b._conn:
        MIGRAZIONI[7](b._conn)
    assert b.conta_norme() == 1
    b.chiudi()
    # Riaperto, è già alla versione corrente: nessuna nuova copia.
    c = Archivio(db)
    assert c.versione_schema == VERSIONE_SCHEMA and c.conta_norme() == 1
    c.chiudi()
    assert len(list((tmp_path / "backup").glob("iudex-*.sqlite"))) == 1


def test_tabelle_delle_norme_fuori_dai_dati_dell_utente():
    assert "atti" not in TABELLE_UTENTE and "norme" not in TABELLE_UTENTE


def test_atti_scritti_e_letti():
    a = Archivio(":memory:")
    assert a.leggi_atto(CHIAVE_ATTO) is None
    a.scrivi_atto(CHIAVE_ATTO, _atto())
    assert a.leggi_atto(CHIAVE_ATTO) == _atto()
    # Un codice, letto via URN: niente codice redazionale né data della Gazzetta.
    codice = Atto(None, None, "1942-03-16", "Codice civile", URN_CC)
    a.scrivi_atto("COD|262|1942", codice)
    assert a.leggi_atto("COD|262|1942") == codice
    a.chiudi()


def test_norma_vigente_scade_dopo_il_ttl():
    a = Archivio(":memory:")
    ttl = 30 * GIORNO
    assert a.leggi_norma(CHIAVE_VIGENTE, ttl) is None
    a.scrivi_norma(CHIAVE_VIGENTE, _articolo())
    assert a.leggi_norma(CHIAVE_VIGENTE, ttl) == _articolo()
    _invecchia(a, CHIAVE_VIGENTE, 29)
    assert a.leggi_norma(CHIAVE_VIGENTE, ttl) == _articolo()
    _invecchia(a, CHIAVE_VIGENTE, 31)
    assert a.leggi_norma(CHIAVE_VIGENTE, ttl) is None
    riga = a._conn.execute("SELECT vigenza, permanente FROM norme").fetchone()
    assert (riga["vigenza"], riga["permanente"]) == ("", 0)
    a.chiudi()


def test_norma_a_una_vigenza_data_e_permanente():
    a = Archivio(":memory:")
    a.scrivi_norma(CHIAVE_DATATA, _articolo("2001-01-01"), "2001-01-01")
    _invecchia(a, CHIAVE_DATATA, 3650)
    assert a.leggi_norma(CHIAVE_DATATA, 30 * GIORNO) == _articolo("2001-01-01")
    riga = a._conn.execute("SELECT vigenza, permanente, contenuto FROM norme").fetchone()
    assert (riga["vigenza"], riga["permanente"]) == ("2001-01-01", 1)
    # JSON leggibile, senza escape degli accenti.
    assert "…" in riga["contenuto"]
    # La permanenza si può anche indicare a mano.
    a.scrivi_norma("x|", _articolo(), "", permanente=True)
    _invecchia(a, "x|", 3650)
    assert a.leggi_norma("x|", 30 * GIORNO) is not None
    a.chiudi()


def test_pulizia_delle_norme_solo_con_il_ttl_e_solo_non_permanenti():
    a = Archivio(":memory:")
    a.scrivi_norma(CHIAVE_VIGENTE, _articolo())
    a.scrivi_norma(CHIAVE_DATATA, _articolo("2001-01-01"), "2001-01-01")
    a.scrivi_norma(f"{URN_CC}~art2044|", _articolo())
    a.scrivi_atto(CHIAVE_ATTO, _atto())
    _invecchia(a, CHIAVE_VIGENTE, 40)
    _invecchia(a, CHIAVE_DATATA, 40)
    assert a.conta_norme() == 3
    # Vecchia firma (due argomenti, come la usa Praeco): le norme non si toccano.
    assert a.pulisci_scadute(3600, GIORNO) == 0
    assert a.pulisci_scadute(-1, -1) == 0
    assert a.conta_norme() == 3
    # Con il TTL delle norme: via solo la vigente scaduta.
    assert a.pulisci_scadute(3600, GIORNO, 30 * GIORNO) == 1
    assert a.conta_norme() == 2
    assert a.leggi_norma(CHIAVE_VIGENTE, 10**9) is None
    assert a.leggi_norma(CHIAVE_DATATA, 0) is not None
    assert a.leggi_norma(f"{URN_CC}~art2044|", 30 * GIORNO) is not None
    # Gli atti sono permanenti: nessuna pulizia li tocca.
    assert a.pulisci_scadute(-1, -1, -1) == 1
    assert a.conta_norme() == 1 and a.leggi_atto(CHIAVE_ATTO) == _atto()
    a.chiudi()
