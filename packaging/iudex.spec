# PyInstaller: Iudex come cartella unica (onedir, più rapida all'avvio di onefile).
# Windows: finestra nativa (pywebview, WebView2) senza console. Linux: server e browser
# predefinito, senza pywebview (niente GTK e WebKit nel pacchetto).
# Costruzione: python -m PyInstaller --noconfirm --distpath build/dist --workpath build/lavoro packaging/iudex.spec
import sys

from PyInstaller.utils.hooks import collect_submodules

RADICE = SPECPATH + "/.."
WINDOWS = sys.platform == "win32"

nascosti = collect_submodules("uvicorn") + ["iudex.app"]
esclusi = ["tkinter", "pytest", "ruff"]
if WINDOWS:
    nascosti += collect_submodules("pystray")
else:
    esclusi += ["webview", "pystray"]

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
