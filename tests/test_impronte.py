"""L'impronta del giorno è deterministica, coerente e fissabile."""

from datetime import date, timedelta

import pytest

from iudex.impronte import (
    CODICI,
    IMPRONTE,
    ImprontaNonCoerente,
    impronta_attiva,
    impronta_del_giorno,
    personalizzata,
    sec_ch_ua_chromium,
)

UA_EDGE = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0"
)
UA_FIREFOX = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0"


def test_impronta_personalizzata_coerente():
    edge = personalizzata("Edge mio", UA_EDGE, "it-IT")
    assert edge.client_hints["sec-ch-ua"] == sec_ch_ua_chromium(151, "Microsoft Edge")
    assert edge.client_hints["sec-ch-ua-platform"] == '"Windows"'
    assert edge.header_comuni()["User-Agent"] == UA_EDGE
    firefox = personalizzata("Volpe", UA_FIREFOX, "it-IT,it;q=0.8")
    assert firefox.client_hints == {} and "image/png" in firefox.accept_pagina
    for argomenti in (
        ("x", UA_EDGE, "it-IT", {"sec-ch-ua": '"Chromium";v="99"'}),  # versione diversa
        ("x", UA_FIREFOX, "it-IT", {"sec-ch-ua": '"Firefox";v="150"'}),  # Firefox non li manda
        ("x", "curl/8.0", "it-IT", {}),
        ("x", "Mozilla/5.0 (X11) Strano/1.0", "it-IT", {}),
        ("x", UA_EDGE, " ", {}),
    ):
        with pytest.raises(ImprontaNonCoerente):
            personalizzata(*argomenti)


def test_impronta_attiva_nei_quattro_modi():
    giorno = date(2026, 10, 28)
    proprie = [
        {"nome": "Edge mio", "user_agent": UA_EDGE, "accept_language": "it-IT"},
        {"nome": "Volpe", "user_agent": UA_FIREFOX, "accept_language": "it-IT"},
    ]
    assert impronta_attiva(giorno, {"impronta_modo": "giorno"}) is impronta_del_giorno(giorno)
    fissa = impronta_attiva(giorno, {"impronta_modo": "fissa", "impronta_fissa": "firefox"})
    assert fissa.codice == "firefox"
    scelte = {
        "impronta_modo": "personalizzata",
        "impronta_personalizzata": "Volpe",
        "impronte_personalizzate": proprie,
    }
    assert impronta_attiva(giorno, scelte).nome == "Volpe"
    # IUDEX_IMPRONTA vince su tutto.
    assert impronta_attiva(giorno, scelte, fissata="edge").codice == "edge"
    solo_proprie = {
        "impronta_modo": "rotazione",
        "impronte_personalizzate": proprie,
        "rotazione_include_predefinite": False,
    }
    nomi = {impronta_attiva(giorno + timedelta(d), solo_proprie).nome for d in range(4)}
    assert nomi == {"Edge mio", "Volpe"}
    con_predefinite = {**solo_proprie, "rotazione_include_predefinite": True}
    nomi = {impronta_attiva(giorno + timedelta(d), con_predefinite).nome for d in range(5)}
    assert len(nomi) == 5


def test_stesso_giorno_stessa_impronta_e_rotazione_completa():
    inizio = date(2026, 10, 25)
    assert impronta_del_giorno(inizio) is impronta_del_giorno(inizio)
    viste = {impronta_del_giorno(inizio + timedelta(days=i)).codice for i in range(len(IMPRONTE))}
    assert viste == set(CODICI)
    assert impronta_del_giorno(inizio) != impronta_del_giorno(inizio + timedelta(days=1))


def test_scelta_fissa_vince_sul_giorno():
    for codice in CODICI:
        assert impronta_del_giorno(date(2026, 10, 25), codice).codice == codice
    assert impronta_del_giorno(date(2026, 10, 25), " Firefox ").codice == "firefox"
    with pytest.raises(ValueError, match="chrome, edge, firefox"):
        impronta_del_giorno(date(2026, 10, 25), "safari")


def test_header_coerenti_per_browser():
    per_codice = {i.codice: i for i in IMPRONTE}
    chrome, edge, firefox = per_codice["chrome"], per_codice["edge"], per_codice["firefox"]
    for impronta in IMPRONTE:
        assert "Windows NT 10.0" in impronta.user_agent and "su Windows" in impronta.nome
        assert impronta.header_pagina()["Sec-Fetch-Mode"] == "navigate"
        assert impronta.header_comuni()["User-Agent"] == impronta.user_agent
    assert "Edg/" in edge.user_agent and "Edg/" not in chrome.user_agent
    assert '"Microsoft Edge"' in edge.client_hints["sec-ch-ua"]
    assert '"Google Chrome"' in chrome.client_hints["sec-ch-ua"]
    assert chrome.client_hints["sec-ch-ua-platform"] == '"Windows"'
    assert "Firefox/" in firefox.user_agent and not firefox.client_hints
    assert "sec-ch-ua" not in firefox.header_comuni()
    assert "image/svg+xml" in firefox.accept_pagina


def test_sec_ch_ua_come_chromium():
    # Valori reali: Chrome 155 dalla cattura CDP del 21 ottobre 2026, gli altri da Chrome
    # 126-131 (ordine, marchio "greased" e versione dipendono solo dalla versione maggiore).
    assert (
        sec_ch_ua_chromium(155, "Google Chrome")
        == '"Google Chrome";v="155", "Chromium";v="155", "Not(A:Brand";v="24"'
    )
    assert (
        sec_ch_ua_chromium(131, "Google Chrome")
        == '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'
    )
    assert (
        sec_ch_ua_chromium(130, "Google Chrome")
        == '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"'
    )
    assert (
        sec_ch_ua_chromium(127, "Google Chrome")
        == '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"'
    )
    assert (
        sec_ch_ua_chromium(126, "Microsoft Edge")
        == '"Not/A)Brand";v="8", "Chromium";v="126", "Microsoft Edge";v="126"'
    )
