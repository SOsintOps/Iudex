"""Il client rispetta l'intervallo minimo, ripete una volta sola e non insiste su 429."""

import time
from pathlib import Path

import httpx
import pytest
import respx

import iudex.client as modulo_client
from iudex.client import ClientSentenzeWeb, ErroreRemoto
from iudex.config import URL_SNCASS, URL_SOLR, Impostazioni

RISPOSTA = {"responseHeader": {"QTime": 1}, "response": {"numFound": 0, "docs": []}}


def impostazioni_test(tmp_path: Path, intervallo=0.3) -> Impostazioni:
    return Impostazioni(cartella_dati=tmp_path, intervallo_minimo=intervallo, timeout=5)


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
    # tre richieste (pagina + 2 query) con almeno 0,3 s fra una e la successiva
    assert durata >= 0.6
    richiesta = solr.calls[0].request
    assert richiesta.headers["X-Requested-With"] == "XMLHttpRequest"
    assert "Chrome/" in richiesta.headers["User-Agent"]
    assert richiesta.headers["Referer"] == URL_SNCASS
    assert richiesta.content == b"q=a"
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
async def test_non_insiste_su_429(tmp_path):
    respx.get(URL_SNCASS).mock(return_value=httpx.Response(200, text=""))
    rotta = respx.post(URL_SOLR + "?app.query").mock(return_value=httpx.Response(429))
    client = ClientSentenzeWeb(impostazioni_test(tmp_path, intervallo=0.0))
    with pytest.raises(ErroreRemoto) as errore:
        await client.cerca([("q", "a")])
    assert errore.value.stato == 429 and rotta.call_count == 1
    await client.chiudi()
