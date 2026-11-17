"""Diagnosi e avviso quando la finestra non può aprirsi su Linux (nessuna finestra vera)."""

import pytest

from iudex.autonoma import finestra
from iudex.autonoma.finestra import messaggio_motore, verifica_motore

SCHERMO = {"DISPLAY": ":0"}


def _carica_che_fallisce(testo):
    def carica(_nome):
        raise OSError(testo)

    return carica


def test_senza_schermo():
    assert verifica_motore(eseguibile=True, ambiente={}) == ("schermo", "")


def test_eseguibile_webkit_mancante_o_incompatibile():
    mancante = _carica_che_fallisce(
        "libwebkit2gtk-4.1.so.0: cannot open shared object file: No such file or directory"
    )
    assert verifica_motore(eseguibile=True, ambiente=SCHERMO, carica=mancante)[0] == (
        "webkit_mancante"
    )
    rotto = _carica_che_fallisce(
        "/lib/x86_64-linux-gnu/libgudev-1.0.so.0: undefined symbol: g_once_init_enter_pointer"
    )
    esito, dettaglio = verifica_motore(eseguibile=True, ambiente=SCHERMO, carica=rotto)
    assert esito == "webkit_incompatibile" and "g_once_init_enter_pointer" in dettaglio


def test_eseguibile_webkit_presente():
    assert verifica_motore(eseguibile=True, ambiente=SCHERMO, carica=lambda _n: None) is None


@pytest.mark.parametrize(
    "esito, eseguibile, atteso",
    [
        ("schermo", True, "DISPLAY"),
        ("webkit_mancante", True, "sudo apt install libwebkit2gtk-4.1-0"),
        ("webkit_mancante", False, "gir1.2-webkit2-4.1 python3-gi"),
        ("webkit_incompatibile", True, ".deb"),
        ("gi_mancante", False, "--system-site-packages"),
        ("typelib_mancante", False, "gir1.2-webkit2-4.1"),
        ("avvio", True, "non si è aperta"),
    ],
)
def test_un_messaggio_per_ogni_esito(esito, eseguibile, atteso):
    assert atteso in messaggio_motore(esito, eseguibile=eseguibile)


def test_messaggi_senza_fedora_e_con_dettaglio():
    for esito in ("webkit_mancante", "webkit_incompatibile", "typelib_mancante"):
        assert "Fedora" not in messaggio_motore(esito, eseguibile=True)
    assert messaggio_motore("avvio", "Errore: x", eseguibile=True).endswith("(Errore: x)")


def test_finestra_impossibile_registra_avvisa_ed_esce(tmp_path, monkeypatch, caplog, capsys):
    pytest.importorskip("webview")  # iudex.desktop esce con SystemExit se manca l'extra desktop
    desktop = pytest.importorskip("iudex.desktop")
    avvisi = []
    monkeypatch.setattr(finestra, "avviso", lambda titolo, testo: avvisi.append(testo) or True)
    with pytest.raises(SystemExit) as uscita:
        desktop.finestra_impossibile("webkit_mancante", "dettaglio", tmp_path)
    assert uscita.value.code == 1
    assert "WebKitGTK" in avvisi[0] and "iudex.log" in avvisi[0]
    assert "finestra non aperta (webkit_mancante)" in caplog.text
    assert "WebKitGTK" in capsys.readouterr().err


def test_errore_concatenato_di_pyinstaller():
    """Nell'eseguibile l'errore del caricatore arriva come causa di quello di PyInstaller."""

    def carica(_nome):
        try:
            raise OSError("libwebkit2gtk-4.1.so.0: cannot open shared object file")
        except OSError as base:
            raise OSError("Failed to load dynlib/dll 'libwebkit2gtk-4.1.so.0'") from base

    esito, dettaglio = verifica_motore(eseguibile=True, ambiente=SCHERMO, carica=carica)
    assert esito == "webkit_mancante" and "cannot open shared object" in dettaglio
