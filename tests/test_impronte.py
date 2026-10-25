"""L'impronta del giorno è deterministica, coerente e fissabile."""

from datetime import date, timedelta

import pytest

from iudex.impronte import CODICI, IMPRONTE, impronta_del_giorno, sec_ch_ua_chromium


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
