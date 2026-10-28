"""Le API rispondono solo con l'header dell'interfaccia e orchestrano client e cache."""

import io
import zipfile

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

import iudex.app as modulo_app
from iudex.config import URL_PDF, URL_SNCASS, URL_SOLR, Impostazioni

H = {"X-Iudex": "1"}


class ClientIudex(TestClient):
    """Il client di prova con il token di Iudex, come la finestra (letto all'avvio dell'app)."""

    def __enter__(self):
        c = super().__enter__()
        c.headers["X-Iudex-Token"] = modulo_app.app.state.token
        return c


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
        with ClientIudex(modulo_app.app) as c:
            yield c, mock


def test_api_rifiuta_senza_header(client):
    c, _ = client
    assert c.get("/api/stato").status_code == 403
    stato = c.get("/api/stato", headers=H)
    assert stato.status_code == 200
    assert "su Windows" in stato.json()["impronta"] and stato.json()["impronta_fissa"] is False
    assert c.get("/api/stato", headers={**H, "Host": "evil.example.com:8765"}).status_code == 403
    assert c.get("/").status_code == 200


def test_accesso_solo_con_il_token(client, tmp_path):
    c, _ = client
    token = (tmp_path / "token").read_text(encoding="ascii").strip()
    assert token == modulo_app.app.state.token and len(token) >= 40
    senza = {"X-Iudex-Token": ""}
    # Un browser qualsiasi: né le pagine né le API né i PDF.
    pagina = c.get("/", headers=senza)
    assert pagina.status_code == 401 and "dalla sua finestra" in pagina.text
    assert c.get("/api/stato", headers={**H, **senza}).status_code == 401
    assert c.get("/guida.html", headers=senza).status_code == 401
    assert c.get("/pdf/snciv2026L26001S", headers=senza).status_code == 401
    assert c.get("/api/stato", headers={**H, "X-Iudex-Token": "sbagliato"}).status_code == 401
    # Liberi: /health e i file statici.
    assert c.get("/health", headers=senza).json()["app"] == "iudex"
    assert c.get("/static/app.css", headers=senza).status_code == 200
    # La finestra: /accesso con il token lascia il cookie e porta alla pagina.
    del c.headers["X-Iudex-Token"]
    assert c.get("/accesso", params={"codice": "no"}).status_code == 401
    r = c.get("/accesso", params={"codice": token}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert "httponly" in r.headers["set-cookie"].lower()
    assert "samesite=strict" in r.headers["set-cookie"].lower()
    assert c.get("/").status_code == 200 and c.get("/api/stato", headers=H).status_code == 200
    # Token rigenerato: il cookie nuovo vale, il vecchio token no.
    nuovo = c.post("/api/token/rigenera", headers=H)
    assert nuovo.status_code == 200 and c.get("/api/stato", headers=H).status_code == 200
    assert (tmp_path / "token").read_text(encoding="ascii").strip() != token
    c.cookies.clear()
    assert c.get("/api/stato", headers={**H, "X-Iudex-Token": token}).status_code == 401


def test_impostazioni(client):
    c, _ = client
    r = c.get("/api/impostazioni", headers=H).json()
    assert r["valori"]["conserva_storico"] is True and r["valori"]["impronta_modo"] == "giorno"
    assert r["bloccate"] == {} and "chrome" in r["codici_impronta"]
    impronta = {"nome": "Mio", "user_agent": UA_CHROME_150, "accept_language": "it-IT"}
    r = c.put(
        "/api/impostazioni",
        headers=H,
        json={
            "conserva_storico": False,
            "pdf_apertura": "programma",
            "impronte_personalizzate": [impronta],
            "impronta_modo": "personalizzata",
            "impronta_personalizzata": "Mio",
        },
    )
    assert r.status_code == 200
    v = r.json()["valori"]
    assert v["conserva_storico"] is False and v["pdf_apertura"] == "programma"
    assert v["impronte_personalizzate"][0]["client_hints"] == {}
    # Restano salvate; null riporta al predefinito.
    v = c.put("/api/impostazioni", headers=H, json={"pdf_apertura": None}).json()["valori"]
    assert v["pdf_apertura"] == "finestra" and v["conserva_storico"] is False
    for corpo, errore in (
        ({"pdf_apertura": "stampante"}, "pdf_apertura"),
        ({"sconosciuta": 1}, "sconosciuta"),
        ({"impronta_personalizzata": "Altra"}, "personalizzata"),
        ({"impronte_personalizzate": [{"nome": "x"}]}, "user_agent"),
    ):
        r = c.put("/api/impostazioni", headers=H, json=corpo)
        assert r.status_code == 422 and errore in r.json()["detail"]
    assert c.put("/api/impostazioni", json={}).status_code == 403


UA_CHROME_150 = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
)


def test_impronta_personalizzata_usata_dal_client(client):
    c, mock = client
    ricerca = mock.post(URL_SOLR + "?app.query").mock(
        return_value=httpx.Response(200, json=_risposta([_doc(30)], trovati=1))
    )
    mia = {"nome": "Ufficio", "user_agent": UA_CHROME_150, "accept_language": "it-IT,it;q=0.9"}
    # Un'impronta non coerente non si salva.
    r = c.put(
        "/api/impostazioni",
        headers=H,
        json={"impronte_personalizzate": [{**mia, "client_hints": {"sec-ch-ua": '"X";v="99"'}}]},
    )
    assert r.status_code == 422 and "150" in r.json()["detail"]
    c.put(
        "/api/impostazioni",
        headers=H,
        json={
            "impronte_personalizzate": [mia],
            "impronta_modo": "personalizzata",
            "impronta_personalizzata": "Ufficio",
        },
    )
    prova = c.post("/api/impronta/prova", headers=H).json()
    assert prova["nome"] == "Ufficio" and 'v="150"' in prova["header"]["sec-ch-ua"]
    assert c.get("/api/stato", headers=H).json()["impronta"] == "Ufficio"
    c.get("/api/cerca", params={"testo": "frode"}, headers=H)
    inviata = ricerca.calls[0].request.headers
    assert inviata["User-Agent"] == UA_CHROME_150 and inviata["Accept-Language"].startswith("it-IT")
    # Prova di un'impronta non salvata, e un User-Agent che non è di un browser.
    altra = c.post("/api/impronta/prova", headers=H, json={**mia, "nome": "Bozza"}).json()
    assert altra["nome"] == "Bozza"
    assert (
        c.post("/api/impronta/prova", headers=H, json={"user_agent": "curl/8"}).status_code == 422
    )
    # Il nome di questo computer.
    r = c.put("/api/impostazioni", headers=H, json={"nome_macchina": "Portatile ufficio"})
    assert r.json()["macchina"]["nome"] == "Portatile ufficio"


def test_impostazioni_bloccate_da_variabile(tmp_path, monkeypatch):
    monkeypatch.setattr(
        modulo_app,
        "impostazioni",
        Impostazioni(cartella_dati=tmp_path, intervallo_minimo=0.0, impronta="edge"),
    )
    with ClientIudex(modulo_app.app) as c:
        r = c.get("/api/impostazioni", headers=H).json()
        assert r["valori"]["impronta_modo"] == "fissa" and r["valori"]["impronta_fissa"] == "edge"
        assert "IUDEX_IMPRONTA" in r["bloccate"]["impronta_modo"]
        r = c.put("/api/impostazioni", headers=H, json={"impronta_modo": "giorno"})
        assert r.status_code == 422


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


def test_segnali_nella_ricerca_e_nel_permalink(client):
    c, mock = client
    risposta = _risposta([_doc(1)], trovati=1)
    risposta["facet_counts"]["facet_queries"] = {
        'ocr:("contrasto giurisprudenziale" OR "difforme orientamento")': 2,
        'ocr:("orientamento consolidato" OR "in senso conforme")': 7,
    }
    rotta = mock.post(URL_SOLR + "?app.query").mock(return_value=httpx.Response(200, json=risposta))
    d = c.get("/api/cerca", params={"testo": "mobbing"}, headers=H).json()
    assert d["segnali"] == {"contrasto": 2, "conformita": 7}
    corpo = rotta.calls[0].request.content.decode()
    assert corpo.count("facet.query=") == 2
    d = c.get("/api/cerca", params={"testo": "mobbing", "segnale": "contrasto"}, headers=H).json()
    assert d["permalink"] == "testo=mobbing&segnale=contrasto"
    assert d["query"].endswith('ocr:("contrasto giurisprudenziale" OR "difforme orientamento")')
    assert "segnalano un contrasto" in d["descrizione"]
    assert c.get("/api/cronologia", headers=H).json()[0]["filtri"] == {"segnale": ["contrasto"]}
    r = c.get("/api/cerca", params={"testo": "x", "segnale": "boh"}, headers=H)
    assert r.status_code == 422


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


def test_diario_registra_ricerche_e_aperture(client):
    c, mock = client
    doc = _doc(7)
    ricerca = mock.post(URL_SOLR + "?app.query").mock(
        return_value=httpx.Response(200, json=_risposta([doc], trovati=1))
    )
    dettaglio = mock.post(URL_SOLR).mock(return_value=httpx.Response(200, json=_risposta([doc])))
    # Due ricerche (la seconda dalla cache): due voci senza grezzo.
    c.get("/api/cerca", params={"testo": "mobbing"}, headers=H)
    c.get("/api/cerca", params={"testo": "mobbing"}, headers=H)
    assert ricerca.call_count == 1
    voci = c.get("/api/diario", headers=H).json()
    assert [v["tipo"] for v in voci] == ["ricerca", "ricerca"]
    assert voci[0]["permalink"] == "testo=mobbing" and voci[0]["trovati"] == 1
    assert c.get("/api/stato", headers=H).json()["sentenze_consultate"] == 0
    # Prima apertura: una chiamata di dettaglio, grezzo salvato.
    r = c.get(f"/api/sentenza/{doc['id']}", params={"da": "testo=mobbing"}, headers=H).json()
    assert r["consultazione"]["volte"] == 1 and dettaglio.call_count == 1
    assert r["consultazione"]["aperture"][0]["permalink"] == "testo=mobbing"
    grezzo = c.get(f"/api/consultate/{doc['id']}/grezzo", headers=H).json()
    assert grezzo["rnc-sp"] == ["LS"] and grezzo["ocr"] == doc["ocr"]
    # Seconda apertura da un'altra ricerca: voce nuova, nessuna chiamata.
    r2 = c.get(f"/api/sentenza/{doc['id']}", params={"da": "testo=x"}, headers=H).json()
    assert r2["consultazione"]["volte"] == 2 and dettaglio.call_count == 1
    assert [a["permalink"] for a in r2["consultazione"]["aperture"]] == ["testo=x", "testo=mobbing"]
    per_sentenza = c.get("/api/diario", params={"sentenza": doc["id"]}, headers=H).json()
    assert len(per_sentenza) == 2 and per_sentenza[0]["documento"]["numero"] == "26007"
    giorni = c.get("/api/diario/giorni", headers=H).json()
    assert giorni[0]["ricerche"] == 2 and giorni[0]["sentenze"] == 2
    assert c.get("/api/diario", params={"giorno": giorni[0]["giorno"]}, headers=H).json()
    assert c.get("/api/consultate", headers=H).json()[0]["volte"] == 2
    # Sentenza già in cache ma mai consultata: una chiamata per avere il grezzo, poi basta.
    altro = _doc(8)
    dettaglio.mock(return_value=httpx.Response(200, json=_risposta([altro])))
    c.get(f"/api/export/sentenza/{altro['id']}", headers=H)
    assert dettaglio.call_count == 2  # l'export non è una consultazione
    assert len(c.get("/api/diario", headers=H).json()) == 4
    c.get(f"/api/sentenza/{altro['id']}", headers=H)
    assert dettaglio.call_count == 3
    c.get(f"/api/sentenza/{altro['id']}", headers=H)
    assert dettaglio.call_count == 3
    assert c.get("/api/consultate/zzz/grezzo", headers=H).status_code == 404
    # Export e copia di sicurezza.
    jsonl = c.get("/api/export/diario", headers=H)
    assert jsonl.status_code == 200 and len(jsonl.text.strip().splitlines()) == 6
    csv_ = c.get("/api/export/diario", params={"formato": "csv"}, headers=H).text
    assert csv_.splitlines()[0].startswith("id;quando;giorno;tipo") and "Cass. civ." in csv_
    zip_ = c.get("/api/export/consultate", headers=H)
    assert zip_.headers["content-type"] == "application/zip" and zip_.content[:2] == b"PK"
    nomi = zipfile.ZipFile(io.BytesIO(zip_.content)).namelist()
    assert f"{doc['id']}.json" in nomi and f"{altro['id']}.txt" in nomi
    backup = c.post("/api/backup", headers=H).json()
    assert backup["ok"] and backup["percorso"].endswith(".sqlite")


def test_memoria_delle_ricerche_e_provenienza(client):
    c, mock = client
    archivio = modulo_app.app.state.archivio
    pagina1, pagina2 = [_doc(1), _doc(2)], [_doc(3)]
    ricerca = mock.post(URL_SOLR + "?app.query").mock(
        side_effect=[
            httpx.Response(200, json=_risposta(pagina1, trovati=3)),
            httpx.Response(200, json=_risposta(pagina2, trovati=3)),
        ]
    )
    parametri = {"testo": "usura", "righe": 2}
    c.get("/api/cerca", params=parametri, headers=H)
    c.get("/api/cerca", params={**parametri, "pagina": 2}, headers=H)
    c.get("/api/cerca", params=parametri, headers=H)  # dalla cache: conta lo stesso
    assert ricerca.call_count == 2 and archivio.conta_esecuzioni() == 3
    voce = c.get("/api/cronologia", headers=H).json()[0]
    assert voce["permalink"] == "testo=usura&righe=2" and voce["volte"] == 2
    righe = archivio._conn.execute(
        "SELECT e.pagina, e.dalla_cache, r.posizione, r.id_sentenza, r.estremi"
        " FROM risultati r JOIN esecuzioni e ON e.id = r.id_esecuzione ORDER BY e.id, r.posizione"
    ).fetchall()
    assert [(r["pagina"], r["posizione"]) for r in righe] == [
        (1, 1),
        (1, 2),
        (2, 3),
        (1, 1),
        (1, 2),
    ]
    assert righe[-1]["dalla_cache"] == 1 and '"numero": "26002"' in righe[1]["estremi"]
    # Da quali ricerche è uscita una sentenza.
    provenienze = archivio.provenienze([_doc(3)["id"], _doc(1)["id"], "zzz"])
    assert [p["ricerca"] for p in provenienze[_doc(3)["id"]]] == ["testo=usura&righe=2"]
    assert provenienze[_doc(1)["id"]][0]["descrizione"] == "usura" and "zzz" not in provenienze
    # Cancellare la ricerca cancella anche esecuzioni e risultati.
    c.delete(f"/api/cronologia/{voce['id']}", headers=H)
    assert archivio.conta_esecuzioni() == 0 and archivio.provenienze([_doc(1)["id"]]) == {}


def test_storico_spento_non_registra_niente(client):
    c, mock = client
    archivio = modulo_app.app.state.archivio
    doc = _doc(4)
    mock.post(URL_SOLR + "?app.query").mock(
        return_value=httpx.Response(200, json=_risposta([doc], trovati=1))
    )
    dettaglio = mock.post(URL_SOLR).mock(return_value=httpx.Response(200, json=_risposta([doc])))
    c.put("/api/impostazioni", headers=H, json={"conserva_storico": False})
    c.get("/api/cerca", params={"testo": "riciclaggio"}, headers=H)
    c.get(f"/api/sentenza/{doc['id']}", params={"da": "testo=riciclaggio"}, headers=H)
    c.get(f"/api/sentenza/{doc['id']}", headers=H)
    assert dettaglio.call_count == 2  # niente testo in cache
    assert c.get("/api/cronologia", headers=H).json() == []
    assert archivio.conta_diario() == 0 and archivio.conta_consultate() == 0
    assert archivio.conta_esecuzioni() == 0 and archivio.conta_risposte() == 0
    assert archivio.conta_sentenze() == 0
    # Riacceso, si registra di nuovo.
    c.put("/api/impostazioni", headers=H, json={"conserva_storico": True})
    c.get("/api/cerca", params={"testo": "riciclaggio"}, headers=H)
    assert archivio.conta_esecuzioni() == 1 and len(c.get("/api/cronologia", headers=H).json()) == 1


def test_badge_gia_vista_e_riapertura_dal_grezzo(client):
    c, mock = client
    archivio = modulo_app.app.state.archivio
    vista, nuova = _doc(5), _doc(6)
    mock.post(URL_SOLR + "?app.query").mock(
        return_value=httpx.Response(200, json=_risposta([vista, nuova], trovati=2))
    )
    dettaglio = mock.post(URL_SOLR).mock(return_value=httpx.Response(200, json=_risposta([vista])))
    c.get("/api/cerca", params={"testo": "estorsione"}, headers=H)
    c.get(f"/api/sentenza/{vista['id']}", params={"da": "testo=estorsione"}, headers=H)
    archivio.annota_sentenza(vista["id"], "testo=estorsione", tipo="pdf")
    # Un'altra ricerca dove esce la stessa sentenza: il badge la riconosce.
    docs = c.get("/api/cerca", params={"testo": "usura"}, headers=H).json()["documenti"]
    c_vista, c_nuova = docs[0]["consultazione"], docs[1]["consultazione"]
    assert c_nuova is None
    assert c_vista["volte"] == 2 and c_vista["pdf"] == 1 and c_vista["ultima"] >= c_vista["prima"]
    assert c_vista["aperta_da"][0]["descrizione"] == "estorsione"
    # Nel badge le ricerche precedenti: quella in corso si registra dopo la risposta.
    assert [u["descrizione"] for u in c_vista["uscita_in"]] == ["estorsione"]
    r = c.get(f"/api/sentenza/{vista['id']}", headers=H).json()
    assert len(r["consultazione"]["uscita_in"]) == 2
    # Preferiti con il badge.
    c.post("/api/preferiti", headers=H, json={"id": vista["id"], "estremi": {"numero": "1"}})
    assert c.get("/api/preferiti", headers=H).json()[0]["consultazione"]["volte"] == 3
    # Testi della cache svuotati: la sentenza consultata si riapre dal grezzo, senza richieste.
    c.delete("/api/cache/sentenze", headers=H)
    chiamate = dettaglio.call_count
    r = c.get(f"/api/sentenza/{vista['id']}", headers=H).json()
    assert dettaglio.call_count == chiamate and r["dalla_cache"] is True
    assert "Testo del provvedimento" in str(r["testo"])
    assert c.get("/api/diario/giorni", headers=H).json()[0]["pdf"] == 1


def test_apertura_fallita_non_e_una_consultazione(client):
    # Visto dal vivo il 28/10: rete caduta durante l'apertura, la sentenza risultava "già vista".
    c, mock = client
    archivio = modulo_app.app.state.archivio
    doc = _doc(40)
    dettaglio = mock.post(URL_SOLR).mock(side_effect=httpx.ConnectError("rete caduta"))
    r = c.get(f"/api/sentenza/{doc['id']}", params={"da": "testo=x"}, headers=H)
    assert r.status_code == 502 and dettaglio.call_count >= 1
    assert archivio.conta_diario() == 0 and archivio.consultazioni([doc["id"]]) == {}
    # Tornata la rete, la prima apertura riuscita è la prima consultazione.
    dettaglio.side_effect = None
    dettaglio.return_value = httpx.Response(200, json=_risposta([doc]))
    r = c.get(f"/api/sentenza/{doc['id']}", params={"da": "testo=x"}, headers=H).json()
    assert r["consultazione"]["volte"] == 1 and archivio.conta_diario() == 1


PDF_FINTO = b"%PDF-1.7\n% sentenza di prova\n%%EOF\n"


def test_pdf_salvato_una_volta_e_servito_in_locale(client, tmp_path):
    c, mock = client
    archivio = modulo_app.app.state.archivio
    doc = _doc(9)
    mock.post(URL_SOLR).mock(return_value=httpx.Response(200, json=_risposta([doc])))
    scarica = mock.get(url__startswith=URL_PDF).mock(
        return_value=httpx.Response(
            200, content=PDF_FINTO, headers={"content-type": "application/pdf"}
        )
    )
    assert c.get(f"/pdf/{doc['id']}").status_code == 404  # non ancora scaricato
    r = c.post(f"/api/pdf/{doc['id']}", headers=H, json={"da": "testo=usura"}).json()
    assert r["url"] == f"/pdf/{doc['id']}" and r["gia_locale"] is False and r["salvato"] is True
    assert scarica.call_count == 1
    file_ = tmp_path / "pdf" / f"{doc['id']}.pdf"
    assert file_.read_bytes() == PDF_FINTO
    voce = archivio.pdf(doc["id"])
    assert voce["percorso"] == f"{doc['id']}.pdf" and voce["byte"] == len(PDF_FINTO)
    # Seconda apertura: dalla copia locale, nessuna richiesta.
    r = c.post(f"/api/pdf/{doc['id']}", headers=H).json()
    assert r["gia_locale"] is True and scarica.call_count == 1
    servito = c.get(f"/pdf/{doc['id']}")
    assert servito.status_code == 200 and servito.content == PDF_FINTO
    assert servito.headers["content-type"] == "application/pdf"
    assert servito.headers["content-disposition"].startswith("inline")
    # Due consultazioni di tipo pdf nel diario, la prima con la ricerca di provenienza.
    voci = [v for v in archivio.diario(id_sentenza=doc["id"]) if v["tipo"] == "pdf"]
    assert len(voci) == 2 and voci[-1]["permalink"] == "testo=usura"
    stato = c.get("/api/stato", headers=H).json()
    assert stato["pdf_salvati"] == 1 and stato["cartella_pdf"].endswith("pdf")
    # Cambiando cartella i PDF salvati si spostano e restano raggiungibili.
    nuova = tmp_path / "altrove"
    c.put("/api/impostazioni", headers=H, json={"cartella_pdf": str(nuova)})
    assert (nuova / f"{doc['id']}.pdf").exists() and not file_.exists()
    assert c.get(f"/pdf/{doc['id']}").content == PDF_FINTO
    # Id non validi: nessun percorso fuori dalla cartella.
    assert c.get("/pdf/..%2F..%2Fsegreto").status_code == 404
    assert c.post("/api/pdf/a.b", headers=H).status_code == 404


def test_pdf_con_storico_spento_non_si_salva(client, tmp_path):
    c, mock = client
    archivio = modulo_app.app.state.archivio
    doc = _doc(10)
    mock.post(URL_SOLR).mock(return_value=httpx.Response(200, json=_risposta([doc])))
    mock.get(url__startswith=URL_PDF).mock(
        return_value=httpx.Response(
            200, content=PDF_FINTO, headers={"content-type": "application/pdf"}
        )
    )
    c.put("/api/impostazioni", headers=H, json={"conserva_storico": False})
    r = c.post(f"/api/pdf/{doc['id']}", headers=H).json()
    assert r["salvato"] is False and r["percorso"] is None
    assert c.get(f"/pdf/{doc['id']}").content == PDF_FINTO
    assert archivio.conta_pdf() == 0 and archivio.conta_diario() == 0
    assert not (tmp_path / "pdf").exists()


def test_pdf_non_disponibile_o_non_pdf(client):
    c, mock = client
    oscurata = {**_doc(11), "filename": []}
    mock.post(URL_SOLR).mock(return_value=httpx.Response(200, json=_risposta([oscurata])))
    r = c.post(f"/api/pdf/{oscurata['id']}", headers=H)
    assert r.status_code == 404 and "oscuramento" in r.json()["detail"]
    doc = _doc(12)
    mock.post(URL_SOLR).mock(return_value=httpx.Response(200, json=_risposta([doc])))
    mock.get(url__startswith=URL_PDF).mock(
        return_value=httpx.Response(
            200, text="<html>errore</html>", headers={"content-type": "text/html"}
        )
    )
    r = c.post(f"/api/pdf/{doc['id']}", headers=H)
    assert r.status_code == 502 and "non ha restituito un PDF" in r.json()["errore"]


def _storico_di_prova(c, mock):
    """Una ricerca con due sentenze, una aperta (testo e PDF salvato)."""
    aperta, vista = _doc(13), _doc(14)
    mock.post(URL_SOLR + "?app.query").mock(
        return_value=httpx.Response(200, json=_risposta([aperta, vista], trovati=2))
    )
    mock.post(URL_SOLR).mock(return_value=httpx.Response(200, json=_risposta([aperta])))
    mock.get(url__startswith=URL_PDF).mock(
        return_value=httpx.Response(
            200, content=PDF_FINTO, headers={"content-type": "application/pdf"}
        )
    )
    c.get("/api/cerca", params={"testo": "bancarotta"}, headers=H)
    c.get(f"/api/sentenza/{aperta['id']}", params={"da": "testo=bancarotta"}, headers=H)
    c.post(f"/api/pdf/{aperta['id']}", headers=H, json={"da": "testo=bancarotta"})
    return aperta, vista


def test_export_del_database_delle_ricerche(client):
    c, mock = client
    aperta, vista = _storico_di_prova(c, mock)
    macchina = modulo_app.app.state.archivio.macchina
    # CSV per Excel: BOM, punto e virgola, una riga per sentenza uscita.
    r = c.get("/api/export/ricerche", params={"formato": "csv"}, headers=H)
    assert r.headers["content-type"].startswith("text/csv")
    righe = r.content.decode("utf-8-sig").splitlines()
    assert righe[0].startswith("id_esecuzione;quando;macchina;descrizione") and len(righe) == 3
    assert "bancarotta" in righe[1] and ";sì;" in righe[1] and ";no;;no;" in righe[2]
    assert r.content.startswith(b"\xef\xbb\xbf")  # BOM UTF-8
    consultazioni = c.get(
        "/api/export/ricerche", params={"formato": "csv", "tabella": "consultazioni"}, headers=H
    ).content.decode("utf-8-sig")
    assert ";testo;" in consultazioni and ";pdf;" in consultazioni
    # JSONL: ogni record con il suo tipo, macchina e uid stabili.
    import json as _json

    record = [
        _json.loads(x)
        for x in c.get(
            "/api/export/ricerche", params={"formato": "jsonl"}, headers=H
        ).text.splitlines()
    ]
    assert record[0] == {"record": "pacchetto", "app": "iudex", "formato": 1}
    tipi = {x["record"] for x in record}
    assert {"macchina", "ricerca", "esecuzione", "risultato", "diario", "consultata", "pdf"} <= tipi
    esecuzione = next(x for x in record if x["record"] == "esecuzione")
    assert esecuzione["macchina"] == macchina and len(esecuzione["uid"]) == 32
    assert next(x for x in record if x["record"] == "macchina")["id"] == macchina
    # ZIP: CSV, JSONL, consultate, testi e PDF.
    zip_ = zipfile.ZipFile(io.BytesIO(c.get("/api/export/ricerche", headers=H).content))
    nomi = set(zip_.namelist())
    assert {"LEGGIMI.txt", "ricerche.csv", "risultati.csv", "ricerche.jsonl"} <= nomi
    assert f"pdf/{aperta['id']}.pdf" in nomi and f"consultate/{aperta['id']}.json" in nomi
    assert f"testi/{aperta['id']}.txt" in nomi and f"pdf/{vista['id']}.pdf" not in nomi
    assert zip_.read(f"pdf/{aperta['id']}.pdf") == PDF_FINTO


def _istanza(cartella, monkeypatch):
    """Un Iudex con la propria cartella dei dati (per provare l'importazione fra due)."""
    monkeypatch.setattr(
        modulo_app, "impostazioni", Impostazioni(cartella_dati=cartella, intervallo_minimo=0.0)
    )
    return ClientIudex(modulo_app.app)


def test_importazione_unisce_senza_duplicati(tmp_path, monkeypatch):
    # Computer A: una ricerca, una sentenza aperta con il PDF; export ZIP e JSONL.
    with respx.mock(assert_all_called=False) as mock, _istanza(tmp_path / "a", monkeypatch) as a:
        mock.get(URL_SNCASS).mock(return_value=httpx.Response(200, text=""))
        aperta, _ = _storico_di_prova(a, mock)
        macchina_a = modulo_app.app.state.archivio.macchina
        pacchetto = a.get("/api/export/ricerche", headers=H).content
        jsonl = a.get("/api/export/ricerche", params={"formato": "jsonl"}, headers=H).content
    # Computer B: una sua ricerca, poi l'importazione del pacchetto di A.
    with respx.mock(assert_all_called=False) as mock, _istanza(tmp_path / "b", monkeypatch) as b:
        mock.get(URL_SNCASS).mock(return_value=httpx.Response(200, text=""))
        mock.post(URL_SOLR + "?app.query").mock(
            return_value=httpx.Response(200, json=_risposta([_doc(20)], trovati=1))
        )
        b.get("/api/cerca", params={"testo": "truffa"}, headers=H)
        archivio = modulo_app.app.state.archivio
        r = b.post("/api/importa", params={"nome": "a.zip"}, headers=H, content=pacchetto)
        assert r.status_code == 200, r.text
        esito = r.json()
        assert esito["formato"] == "zip" and esito["copia_di_sicurezza"].endswith(".sqlite")
        assert esito["ricerche"] == {"aggiunte": 1, "presenti": 0}
        assert esito["esecuzioni"]["aggiunte"] == 1 and esito["risultati"]["aggiunte"] == 2
        assert esito["consultate"]["aggiunte"] == 1 and esito["pdf"]["aggiunti"] == 1
        assert (tmp_path / "b" / "pdf" / f"{aperta['id']}.pdf").read_bytes() == PDF_FINTO
        assert macchina_a in archivio.macchine() and len(archivio.macchine()) == 2
        assert len(b.get("/api/cronologia", headers=H).json()) == 2
        # La provenienza e il badge arrivano con lo storico; il testo si riapre senza rete.
        assert archivio.provenienze([aperta["id"]])[aperta["id"]][0]["descrizione"] == "bancarotta"
        assert archivio.consultazioni([aperta["id"]])[aperta["id"]]["pdf"] == 1
        testo = b.get(f"/api/sentenza/{aperta['id']}", headers=H).json()
        assert testo["dalla_cache"] is True
        # Seconda importazione dello stesso pacchetto e poi del JSONL: niente di nuovo.
        for corpo, nome in ((pacchetto, "a.zip"), (jsonl, "a.jsonl")):
            again = b.post("/api/importa", params={"nome": nome}, headers=H, content=corpo).json()
            assert again["esecuzioni"]["aggiunte"] == 0 and again["diario"]["aggiunte"] == 0
            assert again["ricerche"]["aggiunte"] == 0 and again["consultate"]["aggiunte"] == 0
        assert again["formato"] == "jsonl"
        assert archivio.conta_esecuzioni() == 2 and archivio.conta_pdf() == 1
        # Copia del database di A (anche di una versione vecchia si migra a parte).
        db_a = (tmp_path / "a" / "iudex.sqlite").read_bytes()
        da_db = b.post("/api/importa", params={"nome": "a.sqlite"}, headers=H, content=db_a)
        assert da_db.json()["formato"] == "sqlite" and da_db.json()["esecuzioni"]["aggiunte"] == 0
        # File non validi.
        for corpo in (b"", b"non sono un export", b"PK\x03\x04rotto"):
            assert b.post("/api/importa", headers=H, content=corpo).status_code == 422


def test_primo_avvio_chiede_la_cartella_dei_pdf(client):
    c, _ = client
    assert c.get("/api/impostazioni", headers=H).json()["cartella_pdf_da_scegliere"] is True
    c.put("/api/impostazioni", headers=H, json={"cartella_pdf": None, "cartella_pdf_scelta": True})
    r = c.get("/api/impostazioni", headers=H).json()
    assert r["cartella_pdf_da_scegliere"] is False and r["valori"]["cartella_pdf"] is None


def test_installazione_ini_in_codifica_di_windows(tmp_path):
    from iudex import pdf

    (tmp_path / "installazione.ini").write_bytes(
        "[pdf]\ncartella = C:\\Sentenze è qui\n".encode("cp1252")
    )
    assert pdf.da_installazione(tmp_path) == "C:\\Sentenze è qui"
    (tmp_path / "installazione.ini").write_text("non è un ini", encoding="utf-8")
    assert pdf.da_installazione(tmp_path) is None


def test_cartella_pdf_dall_installer(tmp_path, monkeypatch):
    (tmp_path / "installazione.ini").write_text(
        "[pdf]\ncartella = D:\\Sentenze\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        modulo_app, "impostazioni", Impostazioni(cartella_dati=tmp_path, intervallo_minimo=0.0)
    )
    with ClientIudex(modulo_app.app) as c:
        r = c.get("/api/impostazioni", headers=H).json()
        assert r["valori"]["cartella_pdf"] == "D:\\Sentenze"
        assert r["cartella_pdf_da_scegliere"] is False  # scelta nell'installer


def test_errori_di_validazione_e_interni_in_json(client, monkeypatch):
    c, _ = client
    json_h = {**H, "Content-Type": "application/json"}
    r = c.post("/api/salvate", content="non è json", headers=json_h)
    assert r.status_code == 422 and "dati non validi" in r.json()["errore"]
    r = c.post("/api/salvate", json={"nome": "", "permalink": "testo=a"}, headers=H)
    assert r.status_code == 422 and "nome" in r.json()["errore"]
    r = c.post("/api/preferiti", json=["lista"], headers=H)
    assert r.status_code == 422
    r = c.put("/api/preferiti/abc", json={"nota": "x" * 3000}, headers=H)
    assert r.status_code == 422

    def guasto():
        raise RuntimeError("disco pieno")

    # Starlette rilancia l'eccezione al server dopo la risposta: nel test va disattivato.
    with ClientIudex(modulo_app.app, raise_server_exceptions=False) as c2:
        c2.app.state.archivio.cronologia = guasto
        r = c2.get("/api/cronologia", headers=H)
    assert r.status_code == 500 and r.json() == {"errore": "errore interno di Iudex (RuntimeError)"}


def test_429_del_server_diventa_503_con_pausa(client):
    c, mock = client
    mock.post(URL_SOLR + "?app.query").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "30"})
    )
    r = c.get("/api/cerca", params={"testo": "x"}, headers=H)
    assert r.status_code == 503 and r.json()["stato_remoto"] == 429
    assert 28 <= c.get("/api/stato", headers=H).json()["pausa_residua_s"] <= 30


def test_preferiti_con_nota_e_svuota_cache(client):
    c, _ = client
    c.post("/api/preferiti", json={"id": "abc", "estremi": {"numero": "1"}}, headers=H)
    r = c.put("/api/preferiti/abc", json={"nota": "da citare"}, headers=H)
    assert r.json()["nota"] == "da citare"
    assert c.get("/api/preferiti", headers=H).json()[0]["nota"] == "da citare"
    assert c.put("/api/preferiti/zzz", json={"nota": "x"}, headers=H).status_code == 404
    assert c.delete("/api/cache/sentenze", headers=H).json()["ok"] is True
