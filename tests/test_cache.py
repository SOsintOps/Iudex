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
