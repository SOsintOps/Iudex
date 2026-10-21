"""Le API rispondono solo con l'header dell'interfaccia e orchestrano client e cache."""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

import iudex.app as modulo_app
from iudex.config import URL_SNCASS, URL_SOLR, Impostazioni

H = {"X-Iudex": "1"}


def _doc(i: int, kind: str = "snciv") -> dict:
    return {
        "id": f"{kind}2026L{26000 + i}S",
        "kind": kind,
        "numdec": str(26000 + i),
        "anno": "2026",
        "szdec": "L",
        "ssz": "0",
        "tipoprov": "Sentenza",
        "datdec": "20260904",
        "datdep": ["20261014"],
        "filename": [f"./20261014/{kind}@sL0@a2026@n{26000 + i}@tS.pdf"],
        "materia": ["LAVORO SUBORDINATO"],
        "ocr": ["Testo del provvedimento. FATTI DI CAUSA 1. Primo. P.Q.M. La Corte rigetta."],
        "ocrdis": ["P.Q.M. La Corte rigetta."],
        "rnc-sp": ["LS"],
        "rnc-num": ["0300"],
        "rnc-dat": ["1970"],
        "rnc-art": ["0018 00"],
        "rnc-com": [""],
    }


def _risposta(docs: list[dict], trovati: int | None = None, highlighting=None) -> dict:
    return {
        "responseHeader": {"QTime": 3},
        "response": {"numFound": trovati if trovati is not None else len(docs), "docs": docs},
        "facet_counts": {
            "facet_fields": {
                "kind": ["snciv", 3, "snpen", 1],
                "materia": ["LAVORO SUBORDINATO", 4],
                "anno": ["2026", 4],
            }
        },
        "highlighting": highlighting or {},
    }


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Le impostazioni sono immutabili: si sostituisce l'oggetto usato dal modulo.
    monkeypatch.setattr(
        modulo_app, "impostazioni", Impostazioni(cartella_dati=tmp_path, intervallo_minimo=0.0)
    )
    with respx.mock(assert_all_called=False) as mock:
        mock.get(URL_SNCASS).mock(return_value=httpx.Response(200, text=""))
        with TestClient(modulo_app.app) as c:
            yield c, mock


def test_api_rifiuta_senza_header(client):
    c, _ = client
    assert c.get("/api/stato").status_code == 403
    assert c.get("/api/stato", headers=H).status_code == 200
    assert c.get("/").status_code == 200


def test_pagine_di_aiuto(client):
    c, _ = client
    for nome in ("guida", "faq", "versioni", "software-simili", "licenza"):
        r = c.get(f"/{nome}.html")
        assert r.status_code == 200, nome
        assert "Help" in r.text, nome
    assert c.get("/inesistente.html").status_code == 404
    assert "Guida all'utilizzo" in c.get("/guida.html").text
    assert "MIT License" in c.get("/licenza.html").text


def test_ricerca_con_facet_materia_e_cache(client):
    c, mock = client
    rotta = mock.post(URL_SOLR + "?app.query").mock(
        return_value=httpx.Response(200, json=_risposta([_doc(1), _doc(2)], trovati=2))
    )
    parametri = {"testo": "mobbing", "materia": "LAVORO SUBORDINATO"}
    r = c.get("/api/cerca", params=parametri, headers=H)
    assert r.status_code == 200
    d = r.json()
    assert d["trovati"] == 2 and d["dalla_cache"] is False
    assert d["facet"]["materia"][0]["etichetta"] == "LAVORO SUBORDINATO"
    assert 'materia:"LAVORO SUBORDINATO"' in d["query"]
    assert d["permalink"] == "testo=mobbing&materia=LAVORO+SUBORDINATO"
    corpo = rotta.calls[0].request.content.decode()
    assert "facet.field=materia" in corpo and "f.materia.facet.limit=60" in corpo
    # Seconda chiamata identica: dalla cache, nessuna richiesta in più.
    r2 = c.get("/api/cerca", params=parametri, headers=H)
    assert r2.json()["dalla_cache"] is True and rotta.call_count == 1
    cron = c.get("/api/cronologia", headers=H).json()
    assert len(cron) == 1 and cron[0]["filtri"] == {"materia": ["LAVORO SUBORDINATO"]}


def test_sentenza_paragrafi_riferimenti_ed_evidenziazione(client):
    c, mock = client
    doc = _doc(5)
    marcato = {doc["id"]: {"ocr": ['Testo <em class="hit">rigetta</em>. P.Q.M. La Corte.']}}
    rotta = mock.post(URL_SOLR).mock(
        return_value=httpx.Response(200, json=_risposta([doc], highlighting=marcato))
    )
    parametri = {"evidenzia": "nomatch AND (rigetta)"}
    r = c.get(f"/api/sentenza/{doc['id']}", params=parametri, headers=H)
    d = r.json()
    assert r.status_code == 200 and d["dalla_cache"] is False
    assert "\n\nFATTI DI CAUSA\n\n" in d["testo"] and "\n\nP.Q.M.\n\n" in d["testo"]
    assert d["posizione_pqm"] == d["testo"].find("P.Q.M.")
    assert d["testo_evidenziato"].startswith('Testo <em class="hit">rigetta</em>')
    assert d["documento"]["riferimenti_normativi"][0]["testo"] == "art. 18 legge 300/1970"
    assert d["documento"]["massima"].startswith("P.Q.M.")
    # Riapertura: dalla cache, con il testo marcato conservato, nessuna chiamata.
    r2 = c.get(f"/api/sentenza/{doc['id']}", params=parametri, headers=H)
    assert r2.json()["dalla_cache"] is True and r2.json()["testo_evidenziato"] is not None
    assert rotta.call_count == 1


def test_export_massimo_fa_due_chiamate(client):
    c, mock = client
    pagina1 = _risposta([_doc(i) for i in range(50)], trovati=70)
    pagina2 = _risposta([_doc(50 + i) for i in range(20)], trovati=70)
    rotta = mock.post(URL_SOLR + "?app.query").mock(
        side_effect=[httpx.Response(200, json=pagina1), httpx.Response(200, json=pagina2)]
    )
    parametri = {"testo": "x", "formato": "csv", "massimo": 100}
    r = c.get("/api/export", params=parametri, headers=H)
    assert r.status_code == 200 and rotta.call_count == 2
    righe = r.text.strip().splitlines()
    assert len(righe) == 71  # intestazione + 70 provvedimenti
    assert "attachment" in r.headers["content-disposition"]


def test_salvate_controllo_novita(client):
    c, mock = client
    rotta = mock.post(URL_SOLR + "?app.query").mock(
        side_effect=[
            httpx.Response(200, json=_risposta([_doc(1), _doc(2)], trovati=2)),
            httpx.Response(200, json=_risposta([_doc(3), _doc(1), _doc(2)], trovati=3)),
        ]
    )
    c.post("/api/salvate", json={"nome": "prova", "permalink": "testo=mobbing"}, headers=H)
    id_salvata = c.get("/api/salvate", headers=H).json()[0]["id"]
    primo = c.post(f"/api/salvate/{id_salvata}/controlla", headers=H).json()
    assert primo["prima_volta"] is True and primo["nuovi"] == []
    # Svuoto la cache delle ricerche per forzare la seconda chiamata.
    c.delete("/api/cache", headers=H)
    secondo = c.post(f"/api/salvate/{id_salvata}/controlla", headers=H).json()
    assert secondo["prima_volta"] is False
    assert [d["id"] for d in secondo["nuovi"]] == [_doc(3)["id"]]
    assert rotta.call_count == 2
    salvata = c.get("/api/salvate", headers=H).json()[0]
    assert salvata["nuovi"] == 1 and salvata["trovati"] == 3


def test_preferiti_con_nota_e_svuota_cache(client):
    c, _ = client
    c.post("/api/preferiti", json={"id": "abc", "estremi": {"numero": "1"}}, headers=H)
    r = c.put("/api/preferiti/abc", json={"nota": "da citare"}, headers=H)
    assert r.json()["nota"] == "da citare"
    assert c.get("/api/preferiti", headers=H).json()[0]["nota"] == "da citare"
    assert c.put("/api/preferiti/zzz", json={"nota": "x"}, headers=H).status_code == 404
    assert c.delete("/api/cache/sentenze", headers=H).json()["ok"] is True
