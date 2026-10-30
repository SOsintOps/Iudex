"""Client di Normattiva: risoluzione degli atti, lettura degli articoli, errori, parser HTML.

Nessuna rete: ``respx`` risponde con le risposte reali della sonda del 30/10/2026, salvate in
``tests/fixture/normattiva/`` senza le intestazioni ricevute.
"""

import json
from pathlib import Path

import httpx
import pytest
import respx

import iudex.norme as norme
from iudex.client import ErroreRemoto
from iudex.config import impostazioni
from iudex.norme import (
    FONTE,
    URL_API,
    Atto,
    ClientNormattiva,
    NormaNonTrovata,
    articolo_da_html,
    dividi_articolo,
    url_eurlex,
    url_normattiva,
)

FIXTURE = Path(__file__).parent / "fixture" / "normattiva"
RICERCA = URL_API + "/ricerca/avanzata"
DETTAGLIO = URL_API + "/atto/dettaglio-atto"
DETTAGLIO_URN = URL_API + "/atto/dettaglio-atto-urn"
DENOMINAZIONI = URL_API + "/tipologiche/denominazione-atto"


def fixture(nome: str) -> httpx.Response:
    dati = json.loads((FIXTURE / nome).read_text(encoding="utf-8"))
    return httpx.Response(dati["http"], json=dati["risposta"])


def html_di(nome: str) -> str:
    dati = json.loads((FIXTURE / nome).read_text(encoding="utf-8"))
    return dati["risposta"]["data"]["atto"]["articoloHtml"]


def corpo(rotta, indice: int = 0) -> dict:
    return json.loads(rotta.calls[indice].request.content)


@pytest.fixture
def orologio(monkeypatch):
    """Orologio finto: le attese del client avanzano il tempo e vengono annotate."""
    stato = {"adesso": 1000.0, "attese": []}

    async def dormi(secondi):
        stato["attese"].append(round(secondi, 3))
        stato["adesso"] += secondi

    monkeypatch.setattr(norme, "_orologio", lambda: stato["adesso"])
    monkeypatch.setattr(norme, "_dormi", dormi)
    return stato


@respx.mock
async def test_risolve_la_legge_e_legge_l_articolo_2_bis(orologio):
    ricerca = respx.post(RICERCA).mock(return_value=fixture("ricerca-legge-241-1990.json"))
    dettaglio = respx.post(DETTAGLIO).mock(
        return_value=fixture("dettaglio-art-2bis-l-241-1990.json")
    )
    client = ClientNormattiva()
    atto = await client.risolvi_atto("LS", "241", "1990")
    assert atto == Atto(
        codice_redazionale="090G0294",
        data_gu="1990-08-18",
        data_emanazione="1990-08-07",
        titolo="LEGGE 7 agosto 1990, n. 241",
        urn="urn:nir:stato:legge:1990-08-07;241",
    )
    richiesta = ricerca.calls[0].request
    assert richiesta.headers["Content-Type"] == "application/json"
    assert richiesta.headers["Accept"] == "application/json"
    assert richiesta.headers["User-Agent"].startswith("Iudex/")
    assert corpo(ricerca)["denominazioneAtto"] == "LEGGE"
    assert (corpo(ricerca)["numeroProvvedimento"], corpo(ricerca)["annoProvvedimento"]) == (
        "241",
        "1990",
    )

    articolo = await client.leggi_articolo(atto, "2-bis", "2026-10-30")
    inviato = corpo(dettaglio)
    assert (inviato["idArticolo"], inviato["sottoArticolo"]) == (2, 2)
    assert inviato["codiceRedazionale"] == "090G0294" and inviato["dataGU"] == "1990-08-18"
    assert inviato["dataVigenza"] == "2026-10-30"
    assert articolo.numero == "2-bis"
    assert articolo.rubrica == (
        "Conseguenze per il ritardo dell'amministrazione nella conclusione del procedimento"
    )
    assert articolo.testo.startswith("1. Le pubbliche amministrazioni")
    assert "((1-bis. Fatto salvo" in articolo.testo and "modalità" in articolo.testo
    assert "\n\n2. COMMA ABROGATO DAL D.LGS. 2 LUGLIO 2010, N. 104." in articolo.testo
    assert "AGGIORNAMENTO" not in articolo.testo
    assert articolo.note.startswith("AGGIORNAMENTO (29)")
    assert "D.L. 21 giugno 2013, n. 69" in articolo.note
    assert (articolo.inizio_vigenza, articolo.fine_vigenza) == ("2013-08-21", None)
    assert articolo.vigenza_richiesta == "2026-10-30"
    assert articolo.titolo_atto == "LEGGE 7 agosto 1990, n. 241"
    assert articolo.url == (
        "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1990-08-07;241~art2bis"
    )
    assert articolo.fonte == FONTE
    # Due richieste, la seconda dopo l'intervallo minimo.
    assert orologio["attese"] == [2.0]
    assert client.stat.chiamate == 2 and len(client.stat.registro) == 2
    await client.chiudi()


@respx.mock
async def test_risolve_il_regio_decreto_dalla_ricerca(orologio):
    respx.post(RICERCA).mock(return_value=fixture("ricerca-rd-262-1942.json"))
    client = ClientNormattiva()
    atto = await client.risolvi_atto("RD", "0262", "1942")
    assert (atto.codice_redazionale, atto.data_gu) == ("042U0262", "1942-04-04")
    assert atto.urn == "urn:nir:stato:regio.decreto:1942-03-16;262"
    await client.chiudi()


@respx.mock
async def test_codice_civile_dall_allegato_via_urn_senza_ricerca(orologio):
    ricerca = respx.post(RICERCA).mock(return_value=httpx.Response(500))
    urn = respx.post(DETTAGLIO_URN).mock(return_value=fixture("urn-art-2043-cc.json"))
    client = ClientNormattiva()
    atto = await client.risolvi_atto("cc", "", "")
    assert atto.codice_redazionale is None and ricerca.call_count == 0
    articolo = await client.leggi_articolo(atto, "2043")
    assert corpo(urn) == {"urn": "urn:nir:stato:regio.decreto:1942-03-16;262:2~art2043"}
    assert articolo.numero == "2043"
    assert articolo.rubrica == "Risarcimento per fatto illecito"
    assert articolo.testo.startswith("Qualunque fatto doloso o colposo")
    assert articolo.note is None and articolo.vigenza_richiesta is None
    assert articolo.inizio_vigenza == "1942-04-19"
    assert articolo.titolo_atto == "REGIO DECRETO 16 marzo 1942, n. 262"
    assert articolo.url.endswith("urn:nir:stato:regio.decreto:1942-03-16;262:2~art2043")
    # Con una data di vigenza e un suffisso l'URN porta "~art<n><suffisso>!vig=".
    await client.leggi_articolo(atto, "2043-bis", "2020-01-01")
    assert corpo(urn, 1)["urn"].endswith(";262:2~art2043bis!vig=2020-01-01")
    await client.chiudi()


@pytest.mark.parametrize("tipo", ["LR", "CEDU", "TUE", "TFUE", "REG", "DIR", "XYZ", ""])
async def test_tipi_che_normattiva_non_ha(tipo):
    client = ClientNormattiva()
    with pytest.raises(ValueError):
        await client.risolvi_atto(tipo, "1", "2020")
    assert client.stat.chiamate == 0


@respx.mock
async def test_404_del_dettaglio_e_norma_non_trovata(orologio):
    rotta = respx.post(DETTAGLIO).mock(return_value=fixture("dettaglio-404.json"))
    client = ClientNormattiva()
    atto = Atto("042U0262", "1942-04-04", "1942-03-16", "R.D. 262/1942", "")
    with pytest.raises(NormaNonTrovata):
        await client.leggi_articolo(atto, "2043")
    assert rotta.call_count == 1
    await client.chiudi()


@respx.mock
async def test_ricerca_vuota_e_ambigua(orologio):
    vuota = {"listaAtti": [], "numeroAttiTrovati": 0}
    dati = json.loads((FIXTURE / "ricerca-legge-241-1990.json").read_text(encoding="utf-8"))
    doppia = dati["risposta"]
    doppia["listaAtti"] = doppia["listaAtti"] * 2
    rotta = respx.post(RICERCA).mock(
        side_effect=[httpx.Response(200, json=vuota), httpx.Response(200, json=doppia)]
    )
    client = ClientNormattiva()
    with pytest.raises(NormaNonTrovata):
        await client.risolvi_atto("LS", "241", "1990")
    with pytest.raises(ErroreRemoto, match="ambiguo"):
        await client.risolvi_atto("LS", "241", "1990")
    assert rotta.call_count == 2
    await client.chiudi()


@respx.mock
async def test_decreto_ministeriale_prova_due_denominazioni(orologio):
    dati = json.loads((FIXTURE / "ricerca-legge-241-1990.json").read_text(encoding="utf-8"))
    trovato = dati["risposta"]
    rotta = respx.post(RICERCA).mock(
        side_effect=[httpx.Response(200, json={"listaAtti": []}), httpx.Response(200, json=trovato)]
    )
    client = ClientNormattiva()
    atto = await client.risolvi_atto("DM", "241", "1990")
    assert [corpo(rotta, i)["denominazioneAtto"] for i in range(2)] == [
        "DECRETO",
        "DECRETO MINISTERIALE",
    ]
    # Prefisso URN dei decreti ministeriali non noto: il link usa il codice redazionale.
    assert atto.urn == ""
    assert url_normattiva(atto, "1") == (
        "https://www.normattiva.it/atto/caricaDettaglioAtto?"
        "atto.dataPubblicazioneGazzetta=1990-08-18&atto.codiceRedazionale=090G0294"
    )
    await client.chiudi()


@respx.mock
async def test_urn_ambiguo(orologio):
    risposta = {"success": True, "data": {"atto": None, "lista": [{"urn": "a"}, {"urn": "b"}]}}
    respx.post(DETTAGLIO_URN).mock(return_value=httpx.Response(200, json=risposta))
    client = ClientNormattiva()
    with pytest.raises(ErroreRemoto, match="ambiguo"):
        await client.leggi_articolo(norme.CODICI["COST"], "3")
    await client.chiudi()


@pytest.mark.parametrize(
    ("stato", "intestazioni", "pausa"), [(429, {"Retry-After": "120"}, 120), (409, {}, 60)]
)
@respx.mock
async def test_409_e_429_mettono_in_pausa_senza_ripetere(orologio, stato, intestazioni, pausa):
    rotta = respx.post(RICERCA).mock(return_value=httpx.Response(stato, headers=intestazioni))
    client = ClientNormattiva()
    with pytest.raises(ErroreRemoto) as errore:
        await client.risolvi_atto("LS", "241", "1990")
    assert errore.value.stato == stato and rotta.call_count == 1
    assert client.pausa_residua() == pausa
    # Durante la pausa nessuna richiesta parte: rifiuto locale.
    with pytest.raises(ErroreRemoto, match="pausa"):
        await client.risolvi_atto("LS", "241", "1990")
    assert rotta.call_count == 1
    orologio["adesso"] += pausa
    assert client.pausa_residua() == 0
    await client.chiudi()


@respx.mock
async def test_500_ripete_una_volta_poi_fonte_non_disponibile(orologio):
    rotta = respx.post(DETTAGLIO_URN).mock(return_value=httpx.Response(500))
    client = ClientNormattiva()
    with pytest.raises(ErroreRemoto) as errore:
        await client.leggi_articolo(norme.CODICI["CP"], "575")
    assert "fonte temporaneamente non disponibile" in str(errore.value)
    assert not isinstance(errore.value, NormaNonTrovata)
    assert rotta.call_count == 2
    # Il nuovo tentativo parte dopo l'intervallo minimo.
    assert orologio["attese"] == [2.0]
    await client.chiudi()


@respx.mock
async def test_500_poi_risposta_buona(orologio):
    rotta = respx.post(DETTAGLIO_URN).mock(
        side_effect=[httpx.Response(500), fixture("urn-art-2043-cc.json")]
    )
    client = ClientNormattiva()
    articolo = await client.leggi_articolo(norme.CODICI["CC"], "2043")
    assert articolo.testo.startswith("Qualunque") and rotta.call_count == 2
    await client.chiudi()


@respx.mock
async def test_code_1000_e_un_guasto_non_una_norma_mancante(orologio):
    guasto = {"code": "1000", "message": "errore generico", "success": False}
    rotta = respx.post(DETTAGLIO).mock(return_value=httpx.Response(404, json=guasto))
    client = ClientNormattiva()
    atto = Atto("090G0294", "1990-08-18", "1990-08-07", "LEGGE 7 agosto 1990, n. 241", "")
    with pytest.raises(ErroreRemoto, match="fonte temporaneamente non disponibile"):
        await client.leggi_articolo(atto, "1")
    assert rotta.call_count == 2
    await client.chiudi()


@respx.mock
async def test_errore_di_rete_ripete_una_volta(orologio):
    rotta = respx.post(RICERCA).mock(side_effect=httpx.ConnectError("rete assente"))
    client = ClientNormattiva()
    with pytest.raises(ErroreRemoto, match="fonte temporaneamente non disponibile"):
        await client.risolvi_atto("LS", "241", "1990")
    assert rotta.call_count == 2 and client.stat.registro[-1].stato is None
    await client.chiudi()


@respx.mock
async def test_get_senza_content_type_e_intervallo_rispettato(orologio):
    rotta = respx.get(DENOMINAZIONI).mock(return_value=fixture("denominazioni.json"))
    client = ClientNormattiva(intervallo_minimo=3.5)
    for _ in range(3):
        denominazioni = await client.denominazioni()
    assert {"label": "PLE", "value": "LEGGE"} in denominazioni
    assert rotta.call_count == 3
    for chiamata in rotta.calls:
        assert "content-type" not in chiamata.request.headers
        assert chiamata.request.content == b""
        assert chiamata.request.headers["Accept"] == "application/json"
    assert orologio["attese"] == [3.5, 3.5]
    await client.chiudi()


def test_intervallo_predefinito_dalle_impostazioni():
    assert impostazioni.intervallo_normattiva == 2.0
    assert ClientNormattiva().intervallo_minimo == impostazioni.intervallo_normattiva


def test_dividi_articolo():
    assert dividi_articolo("2-bis") == (2, 2)
    assert dividi_articolo("2043") == (2043, 1)
    assert dividi_articolo("art. 13 ter") == (13, 3)
    assert dividi_articolo("380bis") == (380, 2)
    assert dividi_articolo("0111-decies") == (111, 10)
    for sbagliato in ("", "0", "bis", "12-foo", "12345", "1/2"):
        with pytest.raises(ValueError):
            dividi_articolo(sbagliato)


def test_url_normattiva_dei_codici():
    assert url_normattiva(norme.CODICI["COST"], "111") == (
        "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:costituzione:1947-12-27~art111"
    )
    assert url_normattiva(norme.CODICI["CPC"], "380-bis").endswith(";1443:1~art380bis")


def test_url_eurlex_regolamenti_e_direttive():
    gdpr = url_eurlex("REG", "679", "2016")
    assert gdpr == {
        "eli": "https://eur-lex.europa.eu/eli/reg/2016/679/oj/ita",
        "celex": "32016R0679",
        "url": "https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32016R0679",
    }
    direttiva = url_eurlex("DIR", "1024", "2019")
    assert direttiva["celex"] == "32019L1024"
    assert direttiva["eli"] == "https://eur-lex.europa.eu/eli/dir/2019/1024/oj/ita"
    assert direttiva["url"].endswith("?uri=CELEX:32019L1024")
    # Numero portato a quattro cifre nel CELEX, senza zeri iniziali nell'ELI.
    breve = url_eurlex("reg", "0012", "2003")
    assert breve["celex"] == "32003R0012"
    assert breve["eli"].endswith("/eli/reg/2003/12/oj/ita")


def test_url_eurlex_trattati_e_altri_tipi():
    tue = url_eurlex("TUE", "", "")
    assert tue["celex"] == "12016M/TXT" and tue["eli"] is None
    assert tue["url"] == "https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:12016M/TXT"
    assert url_eurlex("TFUE", "", "")["celex"] == "12016E/TXT"
    for tipo, numero, anno in (
        ("LS", "241", "1990"),
        ("CC", "", ""),
        ("CEDU", "", ""),
        ("", "679", "2016"),
        ("REG", "", "2016"),
        ("REG", "679", ""),
        ("REG", "679/2016", "2016"),
        ("REG", "0", "2016"),
        ("REG", "12345", "2016"),
        ("DIR", "1024", "19"),
    ):
        assert url_eurlex(tipo, numero, anno) is None, (tipo, numero, anno)


def test_articolo_da_html_sulle_fixture():
    numero, rubrica, testo, note = articolo_da_html(html_di("dettaglio-art-2bis-l-241-1990.json"))
    assert numero == "2-bis" and rubrica.endswith("conclusione del procedimento")
    assert testo.count("\n\n") == 3  # comma 1, comma 1-bis inserito, rinvio (29), comma 2
    assert "  " not in testo and "\xa0" not in testo
    assert "((29))" in testo and note.startswith("AGGIORNAMENTO (29)")
    assert "-----" not in note
    numero, rubrica, testo, note = articolo_da_html(html_di("urn-art-2043-cc.json"))
    assert (numero, rubrica, note) == ("2043", "Risarcimento per fatto illecito", None)
    assert testo == (
        "Qualunque fatto doloso o colposo, che cagiona ad altri un danno ingiusto, obbliga "
        "colui che ha commesso il fatto a risarcire il danno."
    )


def test_articolo_da_html_tollerante():
    html = (
        '<div class="bodyTesto"><h2 class="article-num-akn">Art. 3</h2>'
        '<div class="article-heading-akn">(Uguaglianza)</div>'
        '<div class="art-comma-div-akn"><span class="comma-num-akn">1. </span>'
        '<span class="art_text_in_comma">Tutti&nbsp;i cittadini <a href="x">hanno</a> pari'
        "<br>dignità: <div class='pointedList-first-akn'>a) primo;"
        "<div class='pointedList-rest-akn'>b) secondo."
        "</span></div><p>"
    )
    numero, rubrica, testo, note = articolo_da_html(html)
    assert (numero, rubrica, note) == ("3", "Uguaglianza", None)
    assert testo == "1. Tutti i cittadini hanno pari\ndignità:\na) primo;\nb) secondo."
    assert articolo_da_html("") == (None, None, "", None)
