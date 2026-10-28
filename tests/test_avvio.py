"""L'avvio non apre una seconda istanza e spiega la porta occupata senza traccia Python."""

import iudex.__main__ as avvio


def test_porta_occupata_da_iudex_non_ne_avvia_un_altro(monkeypatch, capsys):
    monkeypatch.setattr(avvio, "_porta_occupata", lambda: True)
    monkeypatch.setattr(avvio, "_versione_in_ascolto", lambda: "0.5.0")
    monkeypatch.setattr(avvio.uvicorn, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    assert avvio.main([]) == 0
    assert "già in ascolto" in capsys.readouterr().out


def test_niente_piu_modalita_browser():
    # Iudex si usa dalla sua finestra: --apri non esiste più.
    import pytest

    with pytest.raises(SystemExit):
        avvio.main(["--apri"])


def test_porta_occupata_da_altro(monkeypatch, capsys):
    monkeypatch.setattr(avvio, "_porta_occupata", lambda: True)
    monkeypatch.setattr(avvio, "_versione_in_ascolto", lambda: None)
    assert avvio.main([]) == 1
    assert "IUDEX_PORTA" in capsys.readouterr().err


def test_porta_libera_avvia_uvicorn(monkeypatch):
    chiamate = []
    monkeypatch.setattr(avvio, "_porta_occupata", lambda: False)
    monkeypatch.setattr(avvio.uvicorn, "run", lambda *a, **k: chiamate.append(k))
    assert avvio.main([]) == 0
    assert chiamate[0]["port"] == avvio.impostazioni.porta
