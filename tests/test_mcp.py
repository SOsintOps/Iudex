"""Gli strumenti MCP parlano con l'API locale e restituiscono testo leggibile da un modello.

Il server si prova in memoria con ``Client(mcp)``, come indica la guida ai test dell'SDK
MCP Python; il client si apre dentro ogni test e non in una fixture (con pytest-asyncio
setup e teardown di una fixture asincrona girano in task diversi e anyio lo rifiuta).
L'API locale di Iudex è simulata con ``respx``.
"""

import httpx
import pytest
import respx

pytest.importorskip("mcp")

from mcp import Client  # noqa: E402

from iudex import mcp_server  # noqa: E402
from iudex.mcp_server import BASE, finestra, mcp  # noqa: E402

DOC = {
    "id": "snciv2026L26495S",
    "archivio": "Civile",
    "sezione": "Lavoro",
    "tipo": "Sentenza",
    "numero": "26495",
    "anno": "2026",
    "data_decisione": "2026-09-22",
    "data_deposito": "2026-10-09",
    "ecli": "ECLI:IT:CASS:2026:26495CIV",
    "pdf": "https://example.invalid/x.pdf",
    "frammenti": ['il <em class="hit">licenziamento</em> è nullo'],
    "materia": ["LAVORO SUBORDINATO"],
    "massima": "P.Q.M. rigetta",
    "riferimenti_normativi": [{"testo": "art. 18 legge 300/1970"}],
}


def _testo(risultato) -> str:
    return "".join(c.text for c in risultato.content)


async def _chiama(nome: str, argomenti: dict):
    async with Client(mcp) as c:
        return await c.call_tool(nome, argomenti)


def test_finestra_inizio_e_fine():
    testo = "A" * 9000 + "P.Q.M. La Corte rigetta il ricorso." + "B" * 3000
    pqm = testo.find("P.Q.M.")
    corto = finestra(testo, 0, 6000, pqm)
    assert corto.startswith("A" * 4000) and "omessi" in corto
    assert "P.Q.M. La Corte rigetta" in corto and len(corto) < 6200
    # Con da_carattere si legge la parte omessa, senza tagli.
    assert finestra(testo, 4000, 1000) == testo[4000:5000]
    # Testo breve: intero.
    assert finestra("breve", 0, 12000) == "breve"
    # Senza P.Q.M. la coda è la fine del testo.
    assert finestra("x" * 20000, 0, 3000).endswith("x" * 1000)


async def test_strumenti_elencati_con_annotazioni():
    async with Client(mcp) as c:
        strumenti = {s.name: s for s in (await c.list_tools()).tools}
    assert set(strumenti) == {"cerca_sentenze", "cerca_per_norma", "leggi_sentenza"}
    assert strumenti["leggi_sentenza"].annotations.read_only_hint is True
    proprieta = strumenti["cerca_sentenze"].input_schema["properties"]
    assert proprieta["archivio"]["enum"] == ["", "snciv", "snpen"]


@respx.mock
async def test_cerca_sentenze_con_segnale():
    rotta = respx.get(BASE + "/api/cerca").mock(
        return_value=httpx.Response(
            200,
            json={
                "trovati": 1,
                "descrizione": "licenziamento",
                "pagina": 1,
                "documenti": [DOC],
                "segnali": {"contrasto": 2, "conformita": 5},
            },
        )
    )
    r = await _chiama(
        "cerca_sentenze", {"testo": "licenziamento", "archivio": "snciv", "segnale": "contrasto"}
    )
    testo = _testo(r)
    assert r.is_error is False
    assert "1 provvedimenti" in testo and "«licenziamento»" in testo
    assert "2 segnalano un contrasto" in testo
    parametri = dict(rotta.calls[0].request.url.params)
    assert parametri["kind"] == "snciv" and parametri["segnale"] == "contrasto"
    assert rotta.calls[0].request.headers["X-Iudex"] == "1"


@respx.mock
async def test_il_token_va_nelle_chiamate(monkeypatch):
    monkeypatch.setenv("IUDEX_TOKEN", "segreto-di-prova")
    rotta = respx.get(BASE + "/api/cerca").mock(
        return_value=httpx.Response(
            200, json={"trovati": 0, "descrizione": "x", "pagina": 1, "documenti": []}
        )
    )
    await _chiama("cerca_sentenze", {"testo": "x"})
    assert rotta.calls[0].request.headers["X-Iudex-Token"] == "segreto-di-prova"


@respx.mock
async def test_cerca_per_norma():
    rotta = respx.get(BASE + "/api/cerca").mock(
        return_value=httpx.Response(
            200, json={"trovati": 0, "descrizione": "rif. art. 2043 c.c.", "documenti": []}
        )
    )
    r = await _chiama("cerca_per_norma", {"riferimento": "art. 2043 c.c."})
    assert "0 provvedimenti" in _testo(r)
    assert dict(rotta.calls[0].request.url.params)["rif"] == "art. 2043 c.c."


@respx.mock
async def test_leggi_sentenza_mostra_la_fine():
    testo = "Premesse. " * 1500 + "P.Q.M. La Corte rigetta il ricorso."
    respx.get(BASE + f"/api/sentenza/{DOC['id']}").mock(
        return_value=httpx.Response(
            200, json={"documento": DOC, "testo": testo, "posizione_pqm": testo.find("P.Q.M.")}
        )
    )
    r = await _chiama("leggi_sentenza", {"id_sentenza": DOC["id"], "quanti": 3000})
    t = _testo(r)
    assert "Sentenza n. 26495/2026" in t and "art. 18 legge 300/1970" in t
    assert "omessi" in t and t.rstrip().endswith("rigetta il ricorso.")


@respx.mock
async def test_errori_come_tool_error():
    respx.get(BASE + "/api/cerca").mock(
        return_value=httpx.Response(503, json={"errore": "il server ha chiesto una pausa"})
    )
    r = await _chiama("cerca_sentenze", {"testo": "x"})
    assert r.is_error is True and "pausa" in _testo(r)

    respx.get(BASE + "/api/sentenza/zzz").mock(side_effect=httpx.ConnectError("rifiutata"))
    r = await _chiama("leggi_sentenza", {"id_sentenza": "zzz"})
    assert r.is_error is True and "va aperto Iudex" in _testo(r)
    assert mcp_server.RIGHE_MASSIME == 20
