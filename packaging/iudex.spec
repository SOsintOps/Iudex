# PyInstaller: Iudex come cartella unica (onedir, più rapida all'avvio di onefile).
# Windows: finestra nativa (pywebview, WebView2) senza console. Linux: finestra pywebview con
# GTK (PyGObject nel pacchetto) e WebKitGTK del sistema; niente più ripiego sul browser.
# Costruzione: python -m PyInstaller --noconfirm --distpath build/dist --workpath build/lavoro packaging/iudex.spec
import sys

from PyInstaller.utils.hooks import collect_submodules

RADICE = SPECPATH + "/.."
WINDOWS = sys.platform == "win32"

nascosti = collect_submodules("uvicorn") + ["iudex.app"]
# Di pywebview solo le piattaforme utili qui (niente Android, macOS o Qt).
nascosti += collect_submodules(
    "webview",
    filter=lambda nome: not any(p in nome for p in (".android", ".cocoa", ".qt")),
)
nascosti += collect_submodules("pystray")
esclusi = ["tkinter", "pytest", "ruff"]
if not WINDOWS:
    # Backend GTK di pywebview: i moduli gi vengono dal pacchetto, le librerie WebKitGTK
    # restano quelle del sistema (se mancano, il messaggio in iudex/desktop.py).
    nascosti += ["gi", "gi.repository.Gtk", "gi.repository.WebKit2"]

a = Analysis(
    [SPECPATH + "/avvio.py"],
    pathex=[RADICE],
    datas=[
        (RADICE + "/iudex/static", "iudex/static"),
        (RADICE + "/iudex/certs", "iudex/certs"),
    ],
    hiddenimports=nascosti,
    excludes=esclusi,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Iudex" if WINDOWS else "iudex",
    console=not WINDOWS,
    icon=RADICE + "/iudex/static/favicon.ico" if WINDOWS else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Iudex")
