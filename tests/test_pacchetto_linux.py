"""Regola delle librerie del pacchetto Linux (packaging/librerie_linux.py)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packaging"))

from librerie_linux import SISTEMA, TENUTE, dato_da_tenere, dipendenze, filtra, tieni  # noqa: E402

SYS = "/usr/lib/x86_64-linux-gnu/"
PY = "/opt/hostedtoolcache/Python/3.13.9/x64/lib/"
PIP = "/opt/hostedtoolcache/Python/3.13.9/x64/lib/python3.13/site-packages/"


@pytest.mark.parametrize(
    "destinazione, origine",
    [
        ("libglib-2.0.so.0", SYS + "libglib-2.0.so.0"),
        ("libssl.so.3", SYS + "libssl.so.3"),
        ("libsqlite3.so.0", SYS + "libsqlite3.so.0"),
        ("libz.so.1", "/lib/x86_64-linux-gnu/libz.so.1"),
        ("gio_modules/libgiognutls.so", SYS + "gio/modules/libgiognutls.so"),
        ("lib/gdk-pixbuf/loaders/libpixbufloader-png.so", SYS + "gdk-pixbuf-2.0/loaders/x.so"),
    ],
)
def test_le_librerie_di_sistema_escono(destinazione, origine):
    assert not tieni(destinazione, origine)


@pytest.mark.parametrize(
    "destinazione, origine",
    [
        ("libgirepository-1.0.so.1", SYS + "libgirepository-1.0.so.1"),
        ("libayatana-appindicator3.so.1", SYS + "libayatana-appindicator3.so.1"),
        ("gi_typelibs/Gtk-3.0.typelib", SYS + "girepository-1.0/Gtk-3.0.typelib"),
        ("gi_typelibs/WebKit2-4.1.typelib", SYS + "girepository-1.0/WebKit2-4.1.typelib"),
        ("pillow.libs/libjpeg-6dc8d115.so.62.4.0", PIP + "pillow.libs/libjpeg-6dc8d115.so.62.4.0"),
        ("libpython3.13.so.1.0", PY + "libpython3.13.so.1.0"),
        ("python3.13/lib-dynload/_ssl.cpython-313-x86_64-linux-gnu.so", PY + "x/_ssl.so"),
    ],
)
def test_restano_python_typelib_e_le_tenute(destinazione, origine):
    assert tieni(destinazione, origine)


def test_tenute_sono_sei():
    assert len(TENUTE) == 6


def test_dati_di_gtk_esclusi():
    assert not dato_da_tenere("share/icons/Adwaita/index.theme")
    assert not dato_da_tenere("etc/gtk-3.0/settings.ini")
    assert dato_da_tenere("iudex/static/app.js")
    assert not tieni("share/glib-2.0/schemas/gschemas.compiled", SYS + "x")
    assert tieni("iudex/static/app.js", "/home/runner/work/Iudex/src/iudex/static/app.js")


def test_filtra_toglie_i_collegamenti_rotti():
    voci = [
        ("libglib-2.0.so.0.7200.4", SYS + "libglib-2.0.so.0.7200.4", "BINARY"),
        ("libglib-2.0.so.0", "libglib-2.0.so.0.7200.4", "SYMLINK"),
        ("libpython3.13.so.1.0", PY + "libpython3.13.so.1.0", "BINARY"),
        ("libpython3.13.so", "libpython3.13.so.1.0", "SYMLINK"),
    ]
    assert [v[0] for v in filtra(voci)] == ["libpython3.13.so.1.0", "libpython3.13.so"]


def test_dipendenze_con_alternative_senza_doppioni():
    campo = dipendenze({"libssl.so.3", "libcrypto.so.3", "libglib-2.0.so.0", "libc.so.6"})
    voci = campo.split(", ")
    assert voci[:2] == ["libc6 (>= 2.35)", "libwebkit2gtk-4.1-0"]
    assert voci.count("libssl3t64 | libssl3") == 1
    assert voci.count("libc6 (>= 2.35)") == 1
    assert "libglib2.0-0t64 | libglib2.0-0" in voci


def test_dipendenza_sconosciuta_ferma_la_costruzione():
    with pytest.raises(KeyError, match="libsconosciuta.so.1"):
        dipendenze({"libsconosciuta.so.1"})


def test_ogni_pacchetto_ha_un_nome_valido():
    for pacchetto in SISTEMA.values():
        for alternativa in pacchetto.split(" | "):
            assert (
                alternativa.split(" ")[0]
                .replace(".", "")
                .replace("-", "")
                .replace("+", "")
                .isalnum()
            )
