"""Il server locale dell'app: ``/health`` riconoscibile, scelta della porta, sorveglianza del
processo genitore, uvicorn in un thread, log su file.

``/health`` risponde ``{"app", "versione", "pid"}`` senza l'header delle API: così chi avvia
l'app distingue la propria istanza già accesa da un altro programma sulla stessa porta e,
nel primo caso, la riusa invece di avviarne una seconda (come Voicebox).
"""

from __future__ import annotations

import json
import logging
import os
import socket
import sys
import threading
import time
import urllib.request
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path

log = logging.getLogger("iudex.autonoma")


def aggiungi_health(app, nome: str, versione: str) -> None:
    """Registra ``GET /health`` sull'app FastAPI."""

    @app.get("/health", include_in_schema=False)
    async def health() -> dict:
        return {"app": nome, "versione": versione, "pid": os.getpid()}


def leggi_health(host: str, porta: int, timeout: float = 1.5) -> dict | None:
    """La risposta di ``/health`` su quella porta, o ``None`` se non c'è un'app nostra."""
    try:
        url = f"http://{host}:{porta}/health"
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 - solo locale
            dati = json.load(r)
    except (OSError, ValueError):
        return None
    return dati if isinstance(dati, dict) and "app" in dati else None


def porta_libera(host: str, porta: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, porta))
        except OSError:
            return False
    return True


def scegli_porta(host: str, porta: int, nome: str, tentativi: int = 20) -> tuple[int, bool]:
    """``(porta, già_attiva)``: la prima porta libera da ``porta`` in su, oppure quella su
    cui risponde già un'istanza di ``nome`` (da riusare)."""
    for candidata in range(porta, porta + tentativi):
        if porta_libera(host, candidata):
            return candidata, False
        h = leggi_health(host, candidata)
        if h and h.get("app") == nome:
            return candidata, True
    raise RuntimeError(f"nessuna porta libera fra {porta} e {porta + tentativi - 1}")


def processo_vivo(pid: int) -> bool:
    """Il processo ``pid`` esiste ancora. Su Windows non si usa ``os.kill(pid, 0)``, che lì
    terminerebbe il processo."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        processo = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not processo:
            return False
        codice = ctypes.c_ulong()
        try:
            if not kernel32.GetExitCodeProcess(processo, ctypes.byref(codice)):
                return False
            return codice.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(processo)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def sorveglia_genitore(
    pid: int, alla_morte: Callable[[], None], intervallo: float = 2.0
) -> threading.Thread:
    """Thread che chiama ``alla_morte`` quando il processo ``pid`` (la finestra che ha
    avviato il server) non c'è più: il server non resta orfano."""

    def ciclo() -> None:
        while processo_vivo(pid):
            time.sleep(intervallo)
        log.info("il processo %s è terminato: chiusura del server", pid)
        alla_morte()

    t = threading.Thread(target=ciclo, name="sorveglia-genitore", daemon=True)
    t.start()
    return t


def log_su_file(cartella: Path, nome: str) -> Path:
    """Aggiunge al logging un file rotante ``log/<nome>.log`` (2 MB, 5 copie)."""
    percorso = cartella / "log" / f"{nome}.log"
    percorso.parent.mkdir(parents=True, exist_ok=True)
    gestore = RotatingFileHandler(percorso, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    gestore.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(gestore)
    return percorso


def attendi(url: str, secondi: float = 20.0) -> bool:
    """Aspetta che ``url`` risponda (il server è partito)."""
    scadenza = time.monotonic() + secondi
    while time.monotonic() < scadenza:
        try:
            with urllib.request.urlopen(url, timeout=1):  # noqa: S310 - indirizzo locale
                return True
        except OSError:
            time.sleep(0.2)
    return False


class ServerInThread:
    """uvicorn in un thread, fermabile da fuori (chiusura della finestra o del genitore)."""

    def __init__(self, app, host: str, porta: int):
        import uvicorn

        self.host, self.porta = host, porta
        self.server = uvicorn.Server(uvicorn.Config(app, host=host, port=porta, log_level="info"))
        self.thread = threading.Thread(target=self.server.run, name="server", daemon=True)

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.porta}/"

    def avvia(self) -> bool:
        self.thread.start()
        return attendi(self.url + "health")

    def ferma(self, attesa: float = 10.0) -> None:
        self.server.should_exit = True
        if self.thread.is_alive() and threading.current_thread() is not self.thread:
            self.thread.join(timeout=attesa)
