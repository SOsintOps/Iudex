"""Finestra nativa (pywebview) con icona nell'area di notifica (pystray).

Su Windows la finestra usa WebView2 (presente in Windows 11), su Linux WebKitGTK, su macOS
WebKit. L'icona offre "Apri", "Mantieni in esecuzione" ed "Esci": con "Mantieni in
esecuzione" la chiusura della finestra la nasconde soltanto e il server resta acceso (serve
alle app che lavorano in sottofondo). Richiede l'extra ``desktop``.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger("iudex.autonoma")


def identita_windows(titolo: str, installata: bool | None = None) -> str:
    """L'AppUserModelID dell'app (``SOsintOps.Iudex``), dalla prima parola del titolo. È lo
    stesso dei collegamenti: così Windows raggruppa la finestra sotto il collegamento (con
    la sua icona) e non sotto ``pythonw.exe``. Dai sorgenti si aggiunge ``.Sviluppo``, così
    sulla barra la versione di sviluppo non si confonde con l'app installata."""
    from .cartelle import congelata

    nome = f"SOsintOps.{titolo.split()[0].capitalize()}"
    installata = congelata() if installata is None else installata
    return nome if installata else f"{nome}.Sviluppo"


def _dichiara_identita(titolo: str) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(identita_windows(titolo))
    except (AttributeError, OSError):
        log.warning("AppUserModelID non impostato: sulla barra resta l'icona del programma")


class Guscio:
    """La finestra e l'icona di un'app; ``avvia()`` blocca finché l'utente non esce."""

    def __init__(
        self,
        url: str,
        titolo: str,
        *,
        icona: Path | None = None,
        resta_attivo: bool = False,
        nascosto: bool = False,
        all_uscita: Callable[[], None] | None = None,
    ):
        self.url, self.titolo, self.icona = url, titolo, icona
        self.resta_attivo = resta_attivo
        # Parte solo come icona nell'area di notifica (avvio con il sistema); non su macOS,
        # dove l'icona manca e la finestra non si potrebbe riaprire.
        self.nascosto = nascosto and sys.platform != "darwin"
        self.all_uscita = all_uscita
        self.finestra = None
        self._icona_tray = None
        self._uscita = False

    # --- finestra -------------------------------------------------------------------------

    def _alla_chiusura(self) -> bool | None:
        """``False`` annulla la chiusura (pywebview): la finestra si nasconde soltanto."""
        if self.resta_attivo and not self._uscita and self._icona_tray is not None:
            self.finestra.hide()
            return False
        return None

    def _file_icona(self) -> str | None:
        """L'icona della finestra per pywebview. Senza, su Windows la finestra prende quella
        del programma che la avvia (``pythonw.exe`` dai sorgenti). Su Windows pywebview vuole
        un ``.ico`` (un PNG fa fallire l'avvio): si usa quello accanto a ``icona``, lo stesso
        dei collegamenti; altrove il PNG."""
        if self.icona is None:
            return None
        file_ = self.icona.with_suffix(".ico") if sys.platform == "win32" else self.icona
        return str(file_) if file_.exists() else None

    def mostra(self) -> None:
        if self.finestra is not None:
            self.finestra.show()
            self.finestra.restore()

    def esci(self) -> None:
        self._uscita = True
        if self._icona_tray is not None:
            self._icona_tray.stop()
        if self.finestra is not None:
            self.finestra.destroy()

    # --- icona nell'area di notifica ------------------------------------------------------

    def _crea_tray(self) -> None:
        if sys.platform == "darwin":  # pystray vuole il thread principale, che è di pywebview
            return
        try:
            import pystray
            from PIL import Image
        except ImportError:
            log.warning("pystray o Pillow mancanti: niente icona nell'area di notifica")
            return
        immagine = (
            Image.open(self.icona)
            if self.icona and self.icona.exists()
            else Image.new("RGB", (64, 64), "#0066ff")
        )

        def cambia(_icona, voce) -> None:
            self.resta_attivo = not self.resta_attivo

        menu = pystray.Menu(
            pystray.MenuItem("Apri", lambda: self.mostra(), default=True),
            pystray.MenuItem(
                "Mantieni in esecuzione", cambia, checked=lambda _voce: self.resta_attivo
            ),
            pystray.MenuItem("Esci", lambda: self.esci()),
        )
        self._icona_tray = pystray.Icon(self.titolo.split()[0].lower(), immagine, self.titolo, menu)
        self._icona_tray.run()

    # --- ciclo ----------------------------------------------------------------------------

    def avvia(self) -> None:
        import webview

        _dichiara_identita(self.titolo)
        self.finestra = webview.create_window(
            self.titolo,
            self.url,
            width=1480,
            height=940,
            min_size=(900, 600),
            text_select=True,
            hidden=self.nascosto,
        )
        self.finestra.events.closing += self._alla_chiusura
        # Righe di registro per l'assistenza e per la prova di avvio nella costruzione.
        self.finestra.events.shown += lambda: log.info("finestra aperta")
        self.finestra.events.loaded += lambda: log.info("pagina caricata")
        threading.Thread(target=self._crea_tray, name="tray", daemon=True).start()
        webview.start(icon=self._file_icona())
        # Tutte le finestre sono chiuse: si esce davvero.
        self._uscita = True
        if self._icona_tray is not None:
            self._icona_tray.stop()
        if self.all_uscita:
            self.all_uscita()


# --- diagnosi del motore della finestra su Linux ----------------------------------------------

LIBRERIA_WEBKIT = "libwebkit2gtk-4.1.so.0"


def verifica_motore(
    *,
    eseguibile: bool | None = None,
    ambiente: dict | None = None,
    carica=None,
) -> tuple[str, str] | None:
    """Su Linux, perché la finestra non può partire: ``(esito, dettaglio)``, o ``None`` se va.

    Esiti: ``schermo`` (nessuna sessione grafica), ``webkit_mancante`` (WebKitGTK non è
    installato), ``webkit_incompatibile`` (installato ma non si carica), e dai sorgenti
    ``gi_mancante`` (manca PyGObject) e ``typelib_mancante`` (manca il typelib di WebKitGTK).
    """
    from .cartelle import congelata

    ambiente = os.environ if ambiente is None else ambiente
    eseguibile = congelata() if eseguibile is None else eseguibile
    if not (ambiente.get("DISPLAY") or ambiente.get("WAYLAND_DISPLAY")):
        return "schermo", ""
    if eseguibile:
        if carica is None:
            import ctypes

            carica = ctypes.CDLL
        try:
            carica(LIBRERIA_WEBKIT)
        except OSError as exc:
            testo = str(exc)
            if "cannot open shared object" in testo or "No such file" in testo:
                return "webkit_mancante", testo
            return "webkit_incompatibile", testo
        return None
    try:
        import gi
    except ImportError as exc:
        return "gi_mancante", str(exc)
    try:
        gi.require_version("WebKit2", "4.1")
    except ValueError as exc:
        return "typelib_mancante", str(exc)
    return None


def messaggio_motore(
    esito: str, dettaglio: str = "", *, app: str = "Iudex", eseguibile: bool | None = None
) -> str:
    """Il testo per l'utente per un esito di ``verifica_motore`` (o ``avvio`` per un errore
    durante l'apertura della finestra)."""
    from .cartelle import congelata

    eseguibile = congelata() if eseguibile is None else eseguibile
    if esito == "schermo":
        testo = (
            f"{app} non trova uno schermo: le variabili DISPLAY e WAYLAND_DISPLAY sono vuote.\n"
            f"Avvia {app} dalla sessione grafica, non da una console di testo o via ssh."
        )
    elif esito == "webkit_mancante":
        comando = (
            "sudo apt install libwebkit2gtk-4.1-0"
            if eseguibile
            else "sudo apt install gir1.2-webkit2-4.1 python3-gi python3-gi-cairo"
        )
        testo = (
            f"Manca WebKitGTK, che serve alla finestra di {app}. Installalo e riapri {app}:\n"
            f"  {comando}"
        )
    elif esito == "webkit_incompatibile":
        testo = (
            f"WebKitGTK è installato ma non si carica con questo pacchetto di {app}.\n"
            f"Su Debian e Ubuntu installa il pacchetto .deb di {app}; altrimenti segnala il "
            "problema con il testo qui sotto."
        )
    elif esito == "gi_mancante":
        testo = (
            "Manca PyGObject, che serve alla finestra. Installalo e ricrea l'ambiente con i "
            "pacchetti di sistema:\n"
            "  sudo apt install python3-gi python3-gi-cairo gir1.2-webkit2-4.1\n"
            "  python3 -m venv --system-site-packages .venv"
        )
    elif esito == "typelib_mancante":
        testo = (
            f"Manca la descrizione di WebKitGTK per Python. Installala e riapri {app}:\n"
            "  sudo apt install gir1.2-webkit2-4.1"
        )
    else:
        testo = f"La finestra di {app} non si è aperta."
    return f"{testo}\n({dettaglio})" if dettaglio else testo


def avviso(titolo: str, testo: str) -> bool:
    """Mostra ``testo`` in una finestra di avviso (GTK, poi zenity, kdialog, xmessage).

    Restituisce falso se nessuna finestra ha potuto aprirsi: il testo resta sul terminale e nel
    registro, scritti da chi chiama.
    """
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        if Gtk.init_check()[0]:
            dialogo = Gtk.MessageDialog(
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE,
                text=titolo,
            )
            dialogo.format_secondary_text(testo)
            for figlio in dialogo.get_message_area().get_children():
                if isinstance(figlio, Gtk.Label):
                    figlio.set_selectable(True)
            dialogo.run()
            dialogo.destroy()
            return True
    except Exception:  # noqa: BLE001 - GTK assente o non avviabile: si prova altro
        log.debug("avviso GTK non riuscito", exc_info=True)
    for comando in (
        ["zenity", "--error", "--title", titolo, "--text", testo],
        ["kdialog", "--title", titolo, "--error", testo],
        ["xmessage", "-center", f"{titolo}\n\n{testo}"],
    ):
        if shutil.which(comando[0]):
            try:
                subprocess.run(comando, check=False, timeout=600)
                return True
            except (OSError, subprocess.SubprocessError):
                continue
    return False
