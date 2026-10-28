"""Finestra nativa (pywebview) con icona nell'area di notifica (pystray).

Su Windows la finestra usa WebView2 (presente in Windows 11), su Linux WebKitGTK, su macOS
WebKit. L'icona offre "Apri", "Mantieni in esecuzione" ed "Esci": con "Mantieni in
esecuzione" la chiusura della finestra la nasconde soltanto e il server resta acceso (serve
a Praeco, il cui pianificatore lavora in sottofondo). Richiede l'extra ``desktop``.
"""

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger("iudex.autonoma")


def identita_windows(titolo: str) -> str:
    """L'AppUserModelID dell'app (``SOsintOps.Iudex``), dalla prima parola del titolo. È lo
    stesso dei collegamenti: così Windows raggruppa la finestra sotto il collegamento (con
    la sua icona) e non sotto ``pythonw.exe``."""
    return f"SOsintOps.{titolo.split()[0].capitalize()}"


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
        threading.Thread(target=self._crea_tray, name="tray", daemon=True).start()
        webview.start(icon=self._file_icona())
        # Tutte le finestre sono chiuse: si esce davvero.
        self._uscita = True
        if self._icona_tray is not None:
            self._icona_tray.stop()
        if self.all_uscita:
            self.all_uscita()
