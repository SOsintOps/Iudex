"""Quali librerie entrano nel pacchetto Linux di Iudex (PyInstaller) e quali restano del sistema.

Regola: tutto ciò che PyInstaller raccoglie dalle cartelle di sistema (``/usr/lib``, ``/lib``…)
resta del sistema. In un processo c'è una sola copia di ogni libreria, la prima caricata:
WebKitGTK del sistema è costruito con GLib, GTK, OpenSSL, SQLite… del suo sistema, e se trova
quelle della macchina di costruzione (più vecchie) non si carica. Nel pacchetto restano Python,
i moduli Python con le librerie che i pacchetti di PyPI portano con sé, i file ``typelib`` e le
poche librerie in ``TENUTE``, che il sistema può non avere e che WebKitGTK non usa.

Solo libreria standard: lo usano ``iudex.spec``, ``controlla_pacchetto.py`` e i test.
"""

from __future__ import annotations

from pathlib import PurePosixPath

# Cartelle di sistema: ciò che viene da qui non entra nel pacchetto.
CARTELLE_DI_SISTEMA = ("/usr/lib", "/lib", "/usr/lib64", "/lib64", "/usr/local/lib")

# Librerie di sistema che restano nel pacchetto: il sistema può non averle e WebKitGTK non le
# carica. Servono a PyGObject (girepository) e all'icona nell'area di notifica (Ayatana).
TENUTE = frozenset(
    {
        "libgirepository-1.0.so.1",
        "libayatana-appindicator3.so.1",
        "libayatana-ido3-0.4.so.0",
        "libayatana-indicator3.so.7",
        "libdbusmenu-glib.so.4",
        "libdbusmenu-gtk3.so.4",
    }
)

# Dati di GTK che non entrano: icone, temi, schemi, moduli GIO, lettori di immagini. Senza le
# librerie di GTK nel pacchetto vengono dal sistema.
DATI_ESCLUSI = ("share/", "etc/", "gio_modules/", "lib/gdk-pixbuf/")

# Descrizioni delle interfacce (typelib) che il pacchetto deve contenere.
TYPELIB_RICHIESTI = ("WebKit2-4.1", "JavaScriptCore-4.1", "Soup-3.0", "Gtk-3.0")

# Da libreria del sistema a pacchetto Debian/Ubuntu. Le alternative coprono i nomi «t64» di
# Ubuntu 24.04 e successivi e i nomi di prima (Ubuntu 22.04).
SISTEMA = {
    "libc.so.6": "libc6 (>= 2.35)",
    "libm.so.6": "libc6 (>= 2.35)",
    "libpthread.so.0": "libc6 (>= 2.35)",
    "libdl.so.2": "libc6 (>= 2.35)",
    "librt.so.1": "libc6 (>= 2.35)",
    "libutil.so.1": "libc6 (>= 2.35)",
    "ld-linux-x86-64.so.2": "libc6 (>= 2.35)",
    "libgcc_s.so.1": "libgcc-s1",
    "libstdc++.so.6": "libstdc++6",
    "libz.so.1": "zlib1g",
    "libbz2.so.1.0": "libbz2-1.0",
    "liblzma.so.5": "liblzma5",
    "libexpat.so.1": "libexpat1",
    "libffi.so.8": "libffi8",
    "libuuid.so.1": "libuuid1",
    "libssl.so.3": "libssl3t64 | libssl3",
    "libcrypto.so.3": "libssl3t64 | libssl3",
    "libsqlite3.so.0": "libsqlite3-0",
    "libglib-2.0.so.0": "libglib2.0-0t64 | libglib2.0-0",
    "libgobject-2.0.so.0": "libglib2.0-0t64 | libglib2.0-0",
    "libgio-2.0.so.0": "libglib2.0-0t64 | libglib2.0-0",
    "libgmodule-2.0.so.0": "libglib2.0-0t64 | libglib2.0-0",
    "libgtk-3.so.0": "libgtk-3-0t64 | libgtk-3-0",
    "libgdk-3.so.0": "libgtk-3-0t64 | libgtk-3-0",
    "libgdk_pixbuf-2.0.so.0": "libgdk-pixbuf-2.0-0 | libgdk-pixbuf2.0-0",
    "libatk-1.0.so.0": "libatk1.0-0t64 | libatk1.0-0",
    "libcairo.so.2": "libcairo2",
    "libcairo-gobject.so.2": "libcairo-gobject2",
    "libpango-1.0.so.0": "libpango-1.0-0",
    "libpangocairo-1.0.so.0": "libpangocairo-1.0-0",
    "libharfbuzz.so.0": "libharfbuzz0b",
    "libfontconfig.so.1": "libfontconfig1",
    "libfreetype.so.6": "libfreetype6",
    "libX11.so.6": "libx11-6",
    "libdbus-1.so.3": "libdbus-1-3",
    "libwebkit2gtk-4.1.so.0": "libwebkit2gtk-4.1-0",
    "libjavascriptcoregtk-4.1.so.0": "libjavascriptcoregtk-4.1-0",
    "libsoup-3.0.so.0": "libsoup-3.0-0",
}

# Sempre nel campo Depends del .deb: la finestra usa WebKitGTK, caricato tramite typelib (non
# compare fra le librerie richieste dai file del pacchetto).
SEMPRE = ("libc6 (>= 2.35)", "libwebkit2gtk-4.1-0")


def da_sistema(origine: str) -> bool:
    """Vero se il file viene da una cartella di sistema."""
    percorso = PurePosixPath(origine).as_posix()
    return any(percorso == c or percorso.startswith(c + "/") for c in CARTELLE_DI_SISTEMA)


def tieni(destinazione: str, origine: str) -> bool:
    """Vero se il file (destinazione nel pacchetto, origine sulla macchina) entra nel pacchetto."""
    destinazione = PurePosixPath(destinazione).as_posix()
    if destinazione.startswith("gi_typelibs/"):
        return True
    if not dato_da_tenere(destinazione):
        return False
    if da_sistema(origine):
        return PurePosixPath(destinazione).name in TENUTE
    return True


def dato_da_tenere(destinazione: str) -> bool:
    """Falso per i dati di GTK che restano del sistema (``DATI_ESCLUSI``)."""
    destinazione = PurePosixPath(destinazione).as_posix()
    return not any(destinazione.startswith(d) for d in DATI_ESCLUSI)


def filtra(voci: list) -> list:
    """Le voci di PyInstaller (destinazione, origine, tipo) che entrano nel pacchetto.

    I collegamenti simbolici (tipo ``SYMLINK``, origine = destinazione del collegamento) restano
    solo se resta il file a cui puntano, così nel pacchetto non ci sono collegamenti rotti.
    """
    tenute = [v for v in voci if v[2] == "SYMLINK" or tieni(v[0], v[1])]
    presenti = {PurePosixPath(v[0]).as_posix() for v in tenute if v[2] != "SYMLINK"}
    risultato = []
    for v in tenute:
        if v[2] == "SYMLINK":
            bersaglio = (PurePosixPath(v[0]).parent / v[1]).as_posix()
            if bersaglio not in presenti:
                continue
        risultato.append(v)
    return risultato


def dipendenze(nomi) -> str:
    """Il campo ``Depends`` del .deb per le librerie di sistema ``nomi``.

    Un nome che non è in ``SISTEMA`` dà ``KeyError``: la costruzione si ferma, così nessuna
    dipendenza resta senza pacchetto.
    """
    sconosciuti = sorted(n for n in nomi if n not in SISTEMA)
    if sconosciuti:
        raise KeyError("librerie senza pacchetto in SISTEMA: " + ", ".join(sconosciuti))
    voci = list(SEMPRE)
    for nome in sorted(nomi):
        if SISTEMA[nome] not in voci:
            voci.append(SISTEMA[nome])
    return ", ".join(voci)
