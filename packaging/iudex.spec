# PyInstaller: Iudex come cartella unica (onedir, più rapida all'avvio di onefile).
# Windows: finestra nativa (pywebview, WebView2) senza console. Linux: finestra pywebview con
# PyGObject e i typelib nel pacchetto; GTK, WebKitGTK e ogni altra libreria di sistema vengono
# dal sistema (regola in packaging/librerie_linux.py, controllo in controlla_pacchetto.py).
# Costruzione: python -m PyInstaller --noconfirm --distpath build/dist --workpath build/lavoro packaging/iudex.spec
import sys

from PyInstaller.utils.hooks import collect_submodules

sys.path.insert(0, SPECPATH)

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
dati = [
    (RADICE + "/src/iudex/static", "iudex/static"),
    (RADICE + "/src/iudex/certs", "iudex/certs"),
]
config_hook = {}
if not WINDOWS:
    # Backend GTK di pywebview: i moduli gi e i typelib vengono dal pacchetto, le librerie
    # (WebKitGTK compreso) dal sistema. Se mancano, il messaggio in src/iudex/desktop.py.
    nascosti += ["gi", "gi.repository.Gtk", "gi.repository.WebKit2"]
    # readline e curses: Iudex non li usa e chiederebbero al sistema libreadline e libncursesw.
    esclusi += ["readline", "curses", "_curses", "_curses_panel"]
    # Icone, temi e traduzioni di GTK restano del sistema.
    config_hook = {"gi": {"icons": [], "themes": [], "languages": []}}
    # I typelib di WebKitGTK: letti dal girepository del pacchetto, fatti con i suoi strumenti.
    TYPELIB = "/usr/lib/x86_64-linux-gnu/girepository-1.0/"
    dati += [
        (TYPELIB + nome + ".typelib", "gi_typelibs")
        for nome in ("WebKit2-4.1", "JavaScriptCore-4.1", "Soup-3.0")
    ]

a = Analysis(
    [SPECPATH + "/avvio.py"],
    pathex=[RADICE + "/src"],
    datas=dati,
    hiddenimports=nascosti,
    excludes=esclusi,
    hooksconfig=config_hook,
)
if not WINDOWS:
    from librerie_linux import filtra

    a.binaries = filtra(a.binaries)
    a.datas = filtra(a.datas)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Iudex" if WINDOWS else "iudex",
    console=not WINDOWS,
    icon=RADICE + "/src/iudex/static/favicon.ico" if WINDOWS else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Iudex")
