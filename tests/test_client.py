"""Il client rispetta l'intervallo minimo, ripete una volta sola e non insiste su 429."""

import time
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

import iudex.client as modulo_client
from iudex.client import ClientSentenzeWeb, ErroreRemoto, secondi_retry_after
from iudex.config import URL_ESTREMI, URL_SNCASS, URL_SOLR, Impostazioni
from iudex.impronte import impronta_del_giorno

RISPOSTA = {"responseHeader": {"QTime": 1}, "response": {"numFound": 0, "docs": []}}


def impostazioni_test(tmp_path: Path, intervallo=0.3, impronta="chrome") -> Impostazioni:
    return Impostazioni(
        cartella_dati=tmp_path, intervallo_minimo=intervallo, timeout=5, impronta=impronta
    )


@respx.mock
async def test_prima_la_pagina_poi_la_query_con_intervallo(tmp_path):
    pagina = respx.get(URL_SNCASS).mock(return_value=httpx.Response(200, text="<html></html>"))
    solr = respx.post(URL_SOLR + "?app.query").mock(return_value=httpx.Response(200, json=RISPOSTA))
    client = ClientSentenzeWeb(impostazioni_test(tmp_path))
    inizio = time.monotonic()
    await client.cerca([("q", "a")])
    await client.cerca([("q", "b")])
    durata = time.monotonic() - inizio
    assert pagina.call_count == 1 and solr.call_count == 2
    # tre richieste (pagina + 2 query) con almeno 0,3 s fra una e la successiva; su Windows
    # asyncio.sleep può svegliarsi qualche millisecondo prima (orologio a circa 15,6 ms)
    assert durata >= 0.6 - 0.032
    richiesta = solr.calls[0].request
    assert richiesta.headers["X-Requested-With"] == "XMLHttpRequest"
    assert "Chrome/" in richiesta.headers["User-Agent"]
    assert richiesta.headers["Referer"] == URL_SNCASS
    assert richiesta.content == b"q=a"
    await client.chiudi()


@respx.mock
async def test_cambio_di_giorno_riapre_la_sessione_con_il_browser_nuovo(tmp_path, monkeypatch):
    pagina = respx.get(URL_SNCASS).mock(return_value=httpx.Response(200, text=""))
    solr = respx.post(URL_SOLR + "?app.query").mock(return_value=httpx.Response(200, json=RISPOSTA))
    giorni = iter([date(2026, 10, 25), date(2026, 10, 25), date(2026, 10, 26)])

    class Oggi(date):
        @classmethod
        def today(cls):
            return next(giorni)

    monkeypatch.setattr(modulo_client, "date", Oggi)
    client = ClientSentenzeWeb(impostazioni_test(tmp_path, intervallo=0.0, impronta=None))
    await client.cerca([("q", "a")])
    await client.cerca([("q", "b")])
    await client.cerca([("q", "c")])
    # Stesso giorno: una sola apertura di sessione; giorno nuovo: pagina e client nuovi.
    assert pagina.call_count == 2 and solr.call_count == 3
    prima, seconda, terza = (c.request.headers for c in solr.calls)
    assert prima["User-Agent"] == seconda["User-Agent"] != terza["User-Agent"]
    attesa = impronta_del_giorno(date(2026, 10, 26))
    assert terza["User-Agent"] == attesa.user_agent
    assert pagina.calls[1].request.headers["Accept"] == attesa.accept_pagina
    # Firefox non manda i client hints; Chromium sì.
    for intestazioni in (prima, terza):
        assert ("sec-ch-ua" in intestazioni) == ("Firefox" not in intestazioni["User-Agent"])
    await client.chiudi()


@respx.mock
async def test_ripete_una_volta_su_500(tmp_path, monkeypatch):
    respx.get(URL_SNCASS).mock(return_value=httpx.Response(200, text=""))
    rotta = respx.post(URL_SOLR + "?app.query").mock(
        side_effect=[httpx.Response(500), httpx.Response(200, json=RISPOSTA)]
    )
    originale = modulo_client.asyncio.sleep

    async def dormi_poco(_):
        await originale(0)

    # L'attesa fra i tentativi è di 5 s: la accorciamo a zero per il test.
    monkeypatch.setattr(modulo_client.asyncio, "sleep", dormi_poco)
    client = ClientSentenzeWeb(impostazioni_test(tmp_path, intervallo=0.0))
    dati = await client.cerca([("q", "a")])
    assert dati["response"]["numFound"] == 0 and rotta.call_count == 2
    await client.chiudi()


@respx.mock
async def test_non_insiste_su_429_e_rispetta_retry_after(tmp_path):
    respx.get(URL_SNCASS).mock(return_value=httpx.Response(200, text=""))
    rotta = respx.post(URL_SOLR + "?app.query").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "120"})
    )
    client = ClientSentenzeWeb(impostazioni_test(tmp_path, intervallo=0.0))
    with pytest.raises(ErroreRemoto) as errore:
        await client.cerca([("q", "a")])
    assert errore.value.stato == 429 and rotta.call_count == 1
    assert "120 s" in str(errore.value) and 118 <= client.pausa_residua() <= 120
    # Durante la pausa il rifiuto è locale: nessuna richiesta parte.
    with pytest.raises(ErroreRemoto):
        await client.cerca([("q", "b")])
    assert rotta.call_count == 1
    await client.chiudi()


def test_secondi_retry_after():
    assert secondi_retry_after("30") == 30
    assert secondi_retry_after(None) is None and secondi_retry_after("domani") is None
    # Data HTTP (RFC 9110): 90 secondi dopo l'istante di riferimento.
    assert secondi_retry_after("Thu, 01 Jan 1970 00:01:30 GMT", adesso=0) == 90
    assert secondi_retry_after("Thu, 01 Jan 1970 00:00:10 GMT", adesso=100) == 0


@respx.mock
async def test_403_senza_retry_after_pausa_e_sessione_da_riaprire(tmp_path):
    pagina = respx.get(URL_SNCASS).mock(return_value=httpx.Response(200, text=""))
    respx.post(URL_SOLR + "?app.query").mock(return_value=httpx.Response(403))
    client = ClientSentenzeWeb(impostazioni_test(tmp_path, intervallo=0.0))
    with pytest.raises(ErroreRemoto):
        await client.cerca([("q", "a")])
    assert client.pausa_residua() > 55 and client._sessione_pronta is False
    assert pagina.call_count == 1
    await client.chiudi()


@respx.mock
async def test_pagina_html_al_posto_del_json_riapre_la_sessione(tmp_path):
    pagina = respx.get(URL_SNCASS).mock(return_value=httpx.Response(200, text=""))
    respx.post(URL_SOLR + "?app.query").mock(
        side_effect=[
            httpx.Response(200, text="<html>sessione scaduta</html>"),
            httpx.Response(200, json=RISPOSTA),
        ]
    )
    client = ClientSentenzeWeb(impostazioni_test(tmp_path, intervallo=0.0))
    with pytest.raises(ErroreRemoto):
        await client.cerca([("q", "a")])
    dati = await client.cerca([("q", "a")])
    assert dati["response"]["numFound"] == 0 and pagina.call_count == 2
    await client.chiudi()


@respx.mock
async def test_json_senza_documenti_e_estremi_html_sono_errori(tmp_path):
    respx.get(URL_SNCASS).mock(return_value=httpx.Response(200, text=""))
    respx.post(URL_SOLR + "?app.query").mock(return_value=httpx.Response(200, json={"x": 1}))
    respx.get(URL_ESTREMI).mock(
        return_value=httpx.Response(
            200, text="<!DOCTYPE html><html></html>", headers={"content-type": "text/html"}
        )
    )
    client = ClientSentenzeWeb(impostazioni_test(tmp_path, intervallo=0.0))
    with pytest.raises(ErroreRemoto, match="inattesa"):
        await client.cerca([("q", "a")])
    with pytest.raises(ErroreRemoto, match="pagina"):
        await client.normalizza_riferimento("art. 2043 c.c.")
    await client.chiudi()
