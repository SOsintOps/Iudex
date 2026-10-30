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
from iudex.mcp_server import BASE, finestra, leggi_riferimento, mcp  # noqa: E402

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
    assert set(strumenti) == {
        "cerca_sentenze",
        "cerca_per_norma",
        "leggi_sentenza",
        "leggi_norma",
        "verifica_citazioni",
    }
    for nome in strumenti:
        assert strumenti[nome].annotations.read_only_hint is True
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


# --- leggi_norma -------------------------------------------------------------------------------

NORMA = {
    "atto": {"titolo": "Codice civile", "codice_redazionale": "042U0262", "data_gu": "1942-04-04"},
    "articolo": {
        "numero": "2043",
        "rubrica": "Risarcimento per fatto illecito",
        "testo": "Qualunque fatto doloso o colposo, che cagiona ad altri un danno ingiusto...",
        "note": None,
    },
    "vigenza": {"inizio": "1942-04-21", "fine": None, "richiesta": None},
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262",
    "fonte": "Normattiva (IPZS), CC BY 4.0",
    "da_cache": False,
}


def test_riferimenti_normativi_letti_dal_testo():
    assert leggi_riferimento("art. 2043 c.c.") == {
        "tipo": "CC",
        "numero": "",
        "anno": "",
        "articolo": "2043",
    }
    assert leggi_riferimento("art. 13 d.lgs. 196/2003") == {
        "tipo": "DLG",
        "numero": "196",
        "anno": "2003",
        "articolo": "13",
    }
    assert leggi_riferimento("art. 2-bis l. 241/1990")["articolo"] == "2-bis"
    assert leggi_riferimento("art. 2 terdecies d.lgs. 196/2003")["articolo"] == "2-terdecies"
    assert leggi_riferimento("art. 1 d.P.R. n. 445 del 2000")["tipo"] == "DPR"
    assert leggi_riferimento("art. 3 Cost.")["tipo"] == "COST"
    assert leggi_riferimento("art. 5 regolamento UE 2016/679") is None
    assert leggi_riferimento("qualcosa") is None


@respx.mock
async def test_leggi_norma_dal_riferimento():
    rotta = respx.get(BASE + "/api/norma").mock(return_value=httpx.Response(200, json=NORMA))
    r = await _chiama("leggi_norma", {"riferimento": "art. 2043 c.c."})
    t = _testo(r)
    assert r.is_error is False
    parametri = dict(rotta.calls[0].request.url.params)
    assert parametri["tipo"] == "CC" and parametri["articolo"] == "2043"
    assert "vigenza" not in parametri
    assert "Art. 2043 - Risarcimento per fatto illecito" in t
    assert "Vigenza: dal 1942-04-21 (testo vigente)" in t
    assert "normattiva.it" in t and "Fonte: Normattiva (IPZS)" in t
    assert "Qualunque fatto doloso" in t


@respx.mock
async def test_leggi_norma_con_i_campi_e_la_vigenza():
    rotta = respx.get(BASE + "/api/norma").mock(return_value=httpx.Response(200, json=NORMA))
    await _chiama(
        "leggi_norma",
        {"tipo": "DLG", "numero": "196", "anno": "2003", "articolo": "13", "vigenza": "2015-01-01"},
    )
    parametri = dict(rotta.calls[0].request.url.params)
    assert parametri == {
        "tipo": "DLG",
        "numero": "196",
        "anno": "2003",
        "articolo": "13",
        "vigenza": "2015-01-01",
    }


@respx.mock
async def test_leggi_norma_errori():
    r = await _chiama("leggi_norma", {"riferimento": "il codice della strada"})
    assert r.is_error is True and "non interpretabile" in _testo(r)
    assert respx.calls.call_count == 0
    respx.get(BASE + "/api/norma").mock(
        return_value=httpx.Response(502, json={"errore": "Normattiva non disponibile"})
    )
    r = await _chiama("leggi_norma", {"riferimento": "art. 2043 c.c."})
    assert r.is_error is True and "Normattiva non disponibile" in _testo(r)


# --- verifica_citazioni ------------------------------------------------------------------------

SU_2008 = {
    "id": "snciv2008U26972S",
    "archivio": "Civile",
    "kind": "snciv",
    "sezione": "Unite",
    "sezione_codice": "U",
    "tipo": "Sentenza",
    "numero": "26972",
    "anno": "2008",
    "ecli": "ECLI:IT:CASS:2008:26972CIV",
}


def _ricerca(documenti: list[dict]) -> httpx.Response:
    return httpx.Response(
        200,
        json={"trovati": len(documenti), "descrizione": "x", "pagina": 1, "documenti": documenti},
    )


@respx.mock
async def test_verifica_citazione_che_esiste():
    respx.get(BASE + "/api/consultate").mock(return_value=httpx.Response(200, json=[]))
    cerca = respx.get(BASE + "/api/cerca").mock(return_value=_ricerca([SU_2008]))
    r = await _chiama(
        "verifica_citazioni", {"citazioni": ["Cass. civ., Sez. Un., 11 novembre 2008, n. 26972"]}
    )
    t = _testo(r)
    assert r.is_error is False
    assert "-> esiste (SentenzeWeb)" in t and "snciv2008U26972S" in t
    assert "ECLI:IT:CASS:2008:26972CIV" in t and "attenzione" not in t
    assert cerca.call_count == 1
    parametri = dict(cerca.calls[0].request.url.params)
    assert parametri["testo"] == "26972/2008" and parametri["anno"] == "2008"
    assert parametri["kind"] == "snciv"


@respx.mock
async def test_verifica_prima_le_sentenze_consultate():
    respx.get(BASE + "/api/consultate").mock(
        return_value=httpx.Response(
            200, json=[{"id_sentenza": SU_2008["id"], "documento": SU_2008}]
        )
    )
    cerca = respx.get(BASE + "/api/cerca").mock(return_value=_ricerca([]))
    r = await _chiama(
        "verifica_citazioni",
        {"citazioni": ["Cass. civ. sez. III n. 26972/2008", "Cass. S.U. n. 26972/2008"]},
    )
    t = _testo(r)
    assert "consultate su questo computer" in t and "0 richieste alla Corte" in t
    # La sezione citata (III) non coincide: lo si dice, senza cambiare l'esito.
    assert "attenzione: la citazione indica la sezione Terza" in t
    assert cerca.call_count == 0


@respx.mock
async def test_verifica_citazione_non_trovata():
    respx.get(BASE + "/api/consultate").mock(return_value=httpx.Response(200, json=[]))
    # Un risultato con estremi diversi non conta come conferma.
    altro = dict(SU_2008, numero="26973", id="snciv2008U26973S")
    respx.get(BASE + "/api/cerca").mock(return_value=_ricerca([altro]))
    r = await _chiama("verifica_citazioni", {"citazioni": ["Cass. civ. n. 26972/2008"]})
    t = _testo(r)
    assert "-> non trovata nell'archivio online di SentenzeWeb" in t
    assert "non prova che la sentenza non esista" in t
    assert "inesistente" not in t.lower()


@respx.mock
async def test_verifica_fonte_non_raggiungibile_502():
    respx.get(BASE + "/api/consultate").mock(return_value=httpx.Response(200, json=[]))
    cerca = respx.get(BASE + "/api/cerca").mock(
        return_value=httpx.Response(502, json={"errore": "il server della Corte non risponde"})
    )
    r = await _chiama(
        "verifica_citazioni",
        {"citazioni": ["Cass. civ. n. 26972/2008", "Cass. pen. n. 1234/2020"]},
    )
    t = _testo(r)
    assert r.is_error is False
    assert t.count("fonte non raggiungibile") >= 2 and "verifica non fatta" in t
    assert "inesistente" not in t.lower() and "non trovata nell" not in t
    # Dopo la prima risposta negativa della fonte non si insiste.
    assert cerca.call_count == 1 and "richiesta non fatta" in t


@respx.mock
async def test_verifica_anno_futuro_senza_richieste():
    r = await _chiama(
        "verifica_citazioni",
        {"citazioni": ["Cass. civ. n. 1234/2099", "Cass. pen. n. 55/1998", "una frase qualsiasi"]},
    )
    t = _testo(r)
    assert r.is_error is False
    assert "1. «Cass. civ. n. 1234/2099» -> fuori archivio: anno 2099 non plausibile" in t
    assert "2. «Cass. pen. n. 55/1998» -> fuori archivio" in t and "dal 2000" in t
    assert "3. «una frase qualsiasi» -> non interpretabile" in t
    assert respx.calls.call_count == 0


@respx.mock
async def test_verifica_citazioni_ripetute_una_richiesta():
    respx.get(BASE + "/api/consultate").mock(return_value=httpx.Response(200, json=[]))
    cerca = respx.get(BASE + "/api/cerca").mock(return_value=_ricerca([SU_2008]))
    r = await _chiama(
        "verifica_citazioni",
        {"citazioni": ["Cass. civ. n. 26972/2008", "Cass. civ., 11 novembre 2008, n. 26972"]},
    )
    assert _testo(r).count("-> esiste") == 2 and cerca.call_count == 1


@respx.mock
async def test_verifica_oltre_dieci_citazioni_rifiutate():
    r = await _chiama(
        "verifica_citazioni", {"citazioni": [f"Cass. civ. n. {n}/2020" for n in range(1, 12)]}
    )
    assert r.is_error is True and "al massimo 10 citazioni" in _testo(r)
    assert respx.calls.call_count == 0
