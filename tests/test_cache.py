import sqlite3
import zlib

from iudex.cache import SCHEMA, VERSIONE_SCHEMA, Archivio

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
    assert b.versione_schema == VERSIONE_SCHEMA == 6
    assert [r["id_sentenza"] for r in b.cerca_locale('"Carlo Bianchi"')] == ["snpen9"]
    b.chiudi()
