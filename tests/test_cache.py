from iudex.cache import Archivio


def test_risposte_con_ttl():
    a = Archivio(":memory:")
    a.scrivi_risposta("k", {"n": 1})
    assert a.leggi_risposta("k", 60) == {"n": 1}
    assert a.leggi_risposta("k", -1) is None
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
