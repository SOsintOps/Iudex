"""Ambiente del pacchetto Linux (iudex.autonoma.ambiente)."""

from iudex.autonoma.ambiente import VARIABILI_GTK, confezione, ripristina_ambiente

PACCHETTO = "/tmp/.mount_IudexAb/usr/lib/iudex/_internal"


def _ambiente():
    amb = {nome: PACCHETTO for nome in VARIABILI_GTK}
    amb["GI_TYPELIB_PATH"] = PACCHETTO + "/gi_typelibs"
    amb["XDG_DATA_DIRS"] = f"{PACCHETTO}/share:/usr/local/share:/usr/share"
    amb["LD_LIBRARY_PATH"] = f"{PACCHETTO}:/opt/lib"
    amb["LD_LIBRARY_PATH_ORIG"] = "/opt/lib"
    return amb


def test_da_eseguibile_su_linux_toglie_le_variabili_del_pacchetto():
    amb = _ambiente()
    ripristina_ambiente(amb, eseguibile=True, piattaforma="linux", cartella_pacchetto=PACCHETTO)
    assert not any(nome in amb for nome in VARIABILI_GTK)
    assert amb["GI_TYPELIB_PATH"] == PACCHETTO + "/gi_typelibs"
    assert amb["XDG_DATA_DIRS"] == "/usr/local/share:/usr/share"
    assert amb["LD_LIBRARY_PATH"] == "/opt/lib"


def test_senza_valore_di_prima_toglie_ld_library_path_e_xdg_vuoto():
    amb = _ambiente()
    del amb["LD_LIBRARY_PATH_ORIG"]
    amb["XDG_DATA_DIRS"] = PACCHETTO + "/share"
    ripristina_ambiente(amb, eseguibile=True, piattaforma="linux", cartella_pacchetto=PACCHETTO)
    assert "LD_LIBRARY_PATH" not in amb and "XDG_DATA_DIRS" not in amb


def test_dai_sorgenti_e_su_windows_non_cambia_nulla():
    for eseguibile, piattaforma in ((False, "linux"), (True, "win32")):
        amb = _ambiente()
        ripristina_ambiente(amb, eseguibile=eseguibile, piattaforma=piattaforma)
        assert amb == _ambiente()


def test_confezione(tmp_path):
    assert confezione(tmp_path) is None
    (tmp_path / "confezione").write_text("deb\n", encoding="utf-8")
    assert confezione(tmp_path) == "deb"
    (tmp_path / "confezione").write_text("appimage", encoding="utf-8")
    assert confezione(tmp_path) == "appimage"
    (tmp_path / "confezione").write_text("altro", encoding="utf-8")
    assert confezione(tmp_path) is None
